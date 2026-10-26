import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:speech_to_text/speech_recognition_error.dart';
import 'package:speech_to_text/speech_recognition_result.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;

import '../audio/chime.dart';
import '../ports.dart';
import '../voice_profile.dart';

/// Errors that just mean nobody spoke; they are not a sign of a broken
/// recognizer.
const _silenceErrors = {'error_no_match', 'error_speech_timeout', 'error_busy'};

/// After this many attempts in a row fail for real (not silence), tell the user.
const _maxConsecutiveFailures = 3;

const _permissionMessage =
    'Speech recognition is turned off. Allow Microphone and Speech '
    'Recognition for Synkora in your phone settings to talk to this agent.';

/// Listens with the phone's own recognizer (the free `web_speech` provider).
class DeviceSpeechRecognizer implements LiveSpeechRecognizer {
  DeviceSpeechRecognizer({stt.SpeechToText? speech})
    : _speech = speech ?? stt.SpeechToText();

  final stt.SpeechToText _speech;
  final StreamController<String> _partials = StreamController.broadcast();

  bool _initialized = false;
  bool _available = false;
  String? _systemLocale;
  List<String> _locales = const [];
  Completer<String?>? _pending;
  String _last = '';
  DateTime? _blockedUntil;
  Object? _fatal;
  String? _failureCode;
  int _consecutiveFailures = 0;

  @override
  Stream<String> get partials => _partials.stream;

  Future<void> _ensureInitialized() async {
    if (_initialized) return;
    _available = await _speech.initialize(
      onStatus: _onStatus,
      onError: _onError,
      options: [
        stt.SpeechToText.androidIntentLookup,
        stt.SpeechToText.androidAlwaysUseStop,
        stt.SpeechToText.androidNoBluetooth,
      ],
    );
    _initialized = true;
    if (!_available) return;
    _systemLocale = (await _speech.systemLocale())?.localeId;
    _locales = [for (final l in await _speech.locales()) l.localeId];
  }

  /// Maps a BCP-47 tag such as `en-US` onto the engine's locale id.
  String? _localeFor(String? requested) {
    if (requested == null || requested.isEmpty) return _systemLocale;
    String norm(String s) => s.replaceAll('-', '_').toLowerCase();
    final wanted = norm(requested);
    for (final id in _locales) {
      if (norm(id) == wanted) return id;
    }
    final language = wanted.split('_').first;
    for (final id in _locales) {
      if (norm(id).startsWith('${language}_')) return id;
    }
    return _systemLocale;
  }

  @override
  Future<String?> listenOnce({
    String? locale,
    Duration listenFor = const Duration(seconds: 30),
    Duration pauseFor = const Duration(milliseconds: 1600),
  }) async {
    final blocked = _blockedUntil;
    if (blocked != null && DateTime.now().isBefore(blocked)) return null;

    await _ensureInitialized();
    if (!_available) throw const VoiceUnavailableException(_permissionMessage);

    _fatal = null;
    _failureCode = null;
    _last = '';
    final pending = _pending = Completer<String?>();
    try {
      await _speech.listen(
        onResult: _onResult,
        listenOptions: stt.SpeechListenOptions(
          partialResults: true,
          cancelOnError: true,
          listenMode: stt.ListenMode.dictation,
          listenFor: listenFor,
          pauseFor: pauseFor,
          localeId: _localeFor(locale),
        ),
      );
    } catch (e) {
      _complete(null);
      rethrow;
    }
    final text = await pending.future;
    final fatal = _fatal;
    if (fatal != null) throw fatal;

    if (text != null && text.isNotEmpty) {
      _consecutiveFailures = 0;
    } else if (_failureCode != null) {
      // The recognizer errored instead of hearing silence. A few in a row mean
      // it is not working on this device right now; say so instead of retrying
      // forever in silence.
      if (++_consecutiveFailures >= _maxConsecutiveFailures) {
        _consecutiveFailures = 0;
        throw VoiceUnavailableException(
          "Your phone's speech recognition isn't working right now "
          '(${_failureCode!}). Check Settings > Siri & Dictation, or switch '
          'this agent to a cloud voice in its Voice settings.',
        );
      }
    }
    return text;
  }

  void _onResult(SpeechRecognitionResult result) {
    _last = result.recognizedWords;
    if (!_partials.isClosed) _partials.add(_last);
    if (result.finalResult) _complete(_last);
  }

  void _onStatus(String status) {
    if (kDebugMode) debugPrint('DeviceSpeech status: $status');
    // "done" arrives after the engine stops, with or without a final result.
    if (status == 'done' || status == 'notListening') {
      _complete(_last.isEmpty ? null : _last);
    }
  }

  void _onError(SpeechRecognitionError error) {
    final code = error.errorMsg.toLowerCase().trim();
    if (kDebugMode) {
      debugPrint('DeviceSpeech error: $code permanent=${error.permanent}');
    }
    if (code == 'error_too_many_requests') {
      // Android limits how often recognition may start; back off.
      _blockedUntil = DateTime.now().add(const Duration(seconds: 15));
      _complete(null);
    } else if (code.contains('permission')) {
      _fatal = const VoiceUnavailableException(_permissionMessage);
      _complete(null);
    } else {
      if (!_silenceErrors.contains(code)) _failureCode = code;
      // Otherwise: no match / speech timeout, which just means nothing heard.
      _complete(_last.isEmpty ? null : _last);
    }
  }

  void _complete(String? text) {
    final pending = _pending;
    if (pending != null && !pending.isCompleted) pending.complete(text);
  }

  @override
  Future<void> stop() async {
    if (!_initialized || !_speech.isListening) return;
    await _speech.stop();
  }

  @override
  Future<void> cancel() async {
    _complete(null);
    if (_initialized && _speech.isListening) await _speech.cancel();
  }
}

/// Speaks with the phone's own voice (the free `web_speech` provider).
class DeviceSpeechOutput implements AudioOutput {
  DeviceSpeechOutput({FlutterTts? tts}) : _tts = tts ?? FlutterTts();

  final FlutterTts _tts;
  final StreamController<double> _level = StreamController.broadcast();
  Completer<void>? _speaking;
  Timer? _levelTimer;
  bool _configured = false;
  String? _locale;

  @override
  Stream<double> get level => _level.stream;

  Future<void> _configure() async {
    if (_configured) return;
    _configured = true;
    _tts.setCompletionHandler(_finish);
    _tts.setCancelHandler(_finish);
    _tts.setErrorHandler((_) => _finish());
    if (Platform.isIOS) {
      await _tts.setSharedInstance(true);
      // Share the echo-cancelling voice-chat session with the microphone.
      await _tts.setIosAudioCategory(
        IosTextToSpeechAudioCategory.playAndRecord,
        [
          IosTextToSpeechAudioCategoryOptions.allowBluetooth,
          IosTextToSpeechAudioCategoryOptions.allowBluetoothA2DP,
          IosTextToSpeechAudioCategoryOptions.defaultToSpeaker,
        ],
        IosTextToSpeechAudioMode.voiceChat,
      );
    }
  }

  void _finish() {
    _levelTimer?.cancel();
    _levelTimer = null;
    if (!_level.isClosed) _level.add(0);
    final speaking = _speaking;
    if (speaking != null && !speaking.isCompleted) speaking.complete();
  }

  @override
  Future<void> play(SynthesizedAudio audio) async {
    final speech = audio.deviceSpeech;
    if (speech == null) return;
    await _configure();
    final locale = speech.locale;
    if (locale != null && locale != _locale) {
      _locale = locale;
      await _tts.setLanguage(locale);
    }
    // iOS rates run 0..1 with 0.5 normal; Android is 1.0 normal.
    final base = Platform.isIOS ? 0.5 : 1.0;
    await _tts.setSpeechRate((base * speech.speed).clamp(0.1, 1.5));

    final done = _speaking = Completer<void>();
    final started = Stopwatch()..start();
    _levelTimer?.cancel();
    _levelTimer = Timer.periodic(const Duration(milliseconds: 33), (_) {
      if (!_level.isClosed) _level.add(syntheticSpeechLevel(started.elapsed));
    });
    await _tts.speak(speech.text);
    await done.future;
  }

  @override
  Future<void> stop() async {
    await _tts.stop();
    _finish();
  }

  @override
  Future<void> dispose() async {
    _levelTimer?.cancel();
    await _tts.stop();
    await _level.close();
  }
}

/// Sends each clip to the right player: the phone's voice for text clips, the
/// audio player for synthesized audio.
class RoutingAudioOutput implements AudioOutput {
  RoutingAudioOutput({required this.audio, required this.device}) {
    _subs = [audio.level.listen(_level.add), device.level.listen(_level.add)];
  }

  final AudioOutput audio;
  final AudioOutput device;
  final StreamController<double> _level = StreamController.broadcast();
  late final List<StreamSubscription<double>> _subs;

  @override
  Stream<double> get level => _level.stream;

  @override
  Future<void> play(SynthesizedAudio clip) =>
      clip.deviceSpeech != null ? device.play(clip) : audio.play(clip);

  @override
  Future<void> stop() async {
    await Future.wait([audio.stop(), device.stop()]);
  }

  @override
  Future<void> dispose() async {
    for (final s in _subs) {
      await s.cancel();
    }
    await audio.dispose();
    await device.dispose();
    await _level.close();
  }
}

/// Chooses between the workspace's cloud voice and the phone's own voice
/// according to the active agent's [VoiceProfile].
class RoutingSpeechSynthesizer implements SpeechSynthesizer {
  RoutingSpeechSynthesizer(this.cloud);

  final SpeechSynthesizer cloud;

  /// Updated whenever the active agent changes.
  VoiceProfile profile = VoiceProfile.empty;

  @override
  Future<SynthesizedAudio> synthesize(String text, {String? language}) async {
    final p = profile;
    if (p.speak == SpeechSource.cloud) {
      return cloud.synthesize(text, language: language);
    }
    return SynthesizedAudio.device(
      DeviceSpeech(text: text, locale: p.locale, speed: p.speed),
    );
  }
}
