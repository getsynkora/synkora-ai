import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:synkora_mobile/src/models/synkora_models.dart';
import 'package:synkora_mobile/src/voice/audio/pcm.dart';
import 'package:synkora_mobile/src/voice/ports.dart';
import 'package:synkora_mobile/src/voice/wake/wake_keywords.dart';

AgentSummary fakeAgent(
  String name, {
  String? id,
  Map<String, dynamic> voice = const {},
}) => AgentSummary(
  id: id ?? name.toLowerCase(),
  name: name,
  slug: name.toLowerCase().replaceAll(' ', '-'),
  description: '',
  agentType: 'assistant',
  avatarUrl: null,
  status: 'ACTIVE',
  category: null,
  tags: const [],
  isPublic: false,
  isSubAgent: false,
  subAgentsCount: 0,
  executionCount: 0,
  successRate: null,
  createdAt: null,
  voiceConfig: voice,
);

AgentSummary fakeAgentWithVoice(Map<String, dynamic> voice) =>
    fakeAgent('Muse', voice: voice);

class FakeMic implements VoiceMic {
  final _controller = StreamController<Int16List>.broadcast(sync: true);
  bool running = false;
  int starts = 0;
  int stops = 0;

  @override
  Stream<Int16List> get frames => _controller.stream;

  @override
  bool get isRunning => running;

  @override
  Future<void> start() async {
    running = true;
    starts++;
  }

  @override
  Future<void> stop() async {
    running = false;
    stops++;
  }

  /// Pushes [signal] through as 20 ms frames, synchronously.
  void feed(Int16List signal) {
    for (
      var o = 0;
      o + kVoiceFrameSamples <= signal.length;
      o += kVoiceFrameSamples
    ) {
      _controller.add(Int16List.sublistView(signal, o, o + kVoiceFrameSamples));
    }
  }
}

class FakeRecognizer implements SpeechRecognizer {
  final List<Object> results = [];
  final List<int> receivedBytes = [];
  Duration delay = Duration.zero;

  @override
  Future<String> transcribe(Uint8List wav, {String? language}) async {
    receivedBytes.add(wav.length);
    if (delay > Duration.zero) await Future<void>.delayed(delay);
    final next = results.isEmpty ? '' : results.removeAt(0);
    if (next is Exception) throw next;
    return next as String;
  }
}

class FakeSynth implements SpeechSynthesizer {
  final List<String> requested = [];
  final Set<String> failing = {};
  Duration delay = Duration.zero;
  Object? failAllWith;

  @override
  Future<SynthesizedAudio> synthesize(String text, {String? language}) async {
    requested.add(text);
    if (delay > Duration.zero) await Future<void>.delayed(delay);
    final failure = failAllWith;
    if (failure != null) throw failure;
    if (failing.contains(text)) throw Exception('synthesis failed');
    return SynthesizedAudio(
      bytes: Uint8List.fromList(utf8.encode(text)),
      mimeType: 'audio/wav',
    );
  }
}

/// Plays clips for [playTime] of fake time, or until stopped.
class FakeOutput implements AudioOutput {
  final List<String> played = [];
  final List<String> stoppedDuring = [];
  final _level = StreamController<double>.broadcast(sync: true);
  Duration playTime = const Duration(milliseconds: 500);
  Completer<void>? _current;
  Timer? _timer;
  String? _currentText;
  int stopCount = 0;

  @override
  Stream<double> get level => _level.stream;

  void emitLevel(double value) => _level.add(value);

  /// Text spoken by the phone's own voice (clips with no audio data).
  final List<String> playedDevice = [];

  @override
  Future<void> play(SynthesizedAudio audio) {
    final device = audio.deviceSpeech;
    final text = device?.text ?? utf8.decode(audio.bytes);
    if (device != null) {
      playedDevice.add(text);
    } else {
      played.add(text);
    }
    _currentText = text;
    final completer = Completer<void>();
    _current = completer;
    _timer = Timer(playTime, () {
      if (!completer.isCompleted) completer.complete();
    });
    return completer.future;
  }

  @override
  Future<void> stop() async {
    stopCount++;
    _timer?.cancel();
    final c = _current;
    if (c != null && !c.isCompleted) {
      if (_currentText != null) stoppedDuring.add(_currentText!);
      c.complete();
    }
  }

  @override
  Future<void> dispose() async {
    await _level.close();
  }
}

class FakeGateway implements VoiceAgentGateway {
  final List<({String agent, String message, String conversationId})> requests =
      [];
  final List<String> created = [];
  StreamController<ChatEvent>? current;
  bool cancelled = false;
  Object? createFailure;

  @override
  Future<String> createConversation(
    AgentSummary agent, {
    required String name,
  }) async {
    if (createFailure != null) throw createFailure!;
    created.add(agent.name);
    return 'conv-${created.length}';
  }

  @override
  Stream<ChatEvent> stream({
    required AgentSummary agent,
    required String message,
    required String conversationId,
  }) {
    requests.add((
      agent: agent.name,
      message: message,
      conversationId: conversationId,
    ));
    final controller = StreamController<ChatEvent>(
      onCancel: () => cancelled = true,
    );
    current = controller;
    return controller.stream;
  }

  void chunk(String text) =>
      current!.add(ChatEvent(type: 'chunk', content: text));
  void tool(String name, String status) => current!.add(
    ChatEvent(type: 'tool_status', toolName: name, status: status),
  );
  void done() {
    current!.add(const ChatEvent(type: 'done'));
    current!.close();
  }

  void error(String message) =>
      current!.add(ChatEvent(type: 'error', error: message));
}

class FakeWake
    implements WakeWordDetector, WakeWordStatus, WakeSensitivityControl {
  bool triggerOnNextFrame = false;
  @override
  WakeSensitivity sensitivity = WakeSensitivity.balanced;
  @override
  String? failure;
  bool ready = false;
  int startCalls = 0;

  @override
  bool get isReady => ready;

  @override
  Future<void> start() async {
    startCalls++;
    ready = failure == null;
  }

  int resets = 0;
  int processed = 0;

  @override
  bool process(Int16List frame) {
    processed++;
    if (triggerOnNextFrame) {
      triggerOnNextFrame = false;
      return true;
    }
    return false;
  }

  @override
  void reset() => resets++;

  @override
  Future<void> dispose() async {}
}

/// The phone's built-in recognizer: finals are queued by the test, or the
/// call waits until [finish] is called.
class FakeLive implements LiveSpeechRecognizer {
  final _partials = StreamController<String>.broadcast(sync: true);
  final List<Object?> queued = [];
  Completer<String?>? _pending;
  int listenCalls = 0;
  int stopCalls = 0;
  int cancelCalls = 0;
  String? lastLocale;
  String _last = '';

  @override
  Stream<String> get partials => _partials.stream;

  @override
  Future<String?> listenOnce({
    String? locale,
    Duration listenFor = const Duration(seconds: 30),
    Duration pauseFor = const Duration(milliseconds: 1600),
  }) {
    listenCalls++;
    lastLocale = locale;
    _last = '';
    if (queued.isNotEmpty) {
      final next = queued.removeAt(0);
      if (next is Exception) return Future.error(next);
      return Future.value(next as String?);
    }
    return (_pending = Completer<String?>()).future;
  }

  /// Streams words as the user speaks.
  void partial(String words) {
    _last = words;
    _partials.add(words);
  }

  /// Ends the current listen with [text] (null = nothing heard).
  void finish(String? text) {
    final p = _pending;
    if (p != null && !p.isCompleted) p.complete(text);
  }

  @override
  Future<void> stop() async {
    stopCalls++;
    finish(_last.isEmpty ? null : _last);
  }

  @override
  Future<void> cancel() async {
    cancelCalls++;
    finish(null);
  }
}
