import 'dart:math' as math;
import 'dart:typed_data';

import 'pcm.dart';

/// Frame-level speech detector based on loudness relative to an adaptive
/// noise floor.
///
/// The floor is a low percentile of the last couple of seconds of loudness,
/// so a steady hum (fan, car, air conditioning) is learned as background even
/// though it is loud, while speech bursts - which occupy only part of the
/// window - do not raise it. Learning is paused by the caller while a person
/// is mid-sentence so a long utterance cannot drag the floor up.
class EnergyVad {
  EnergyVad({
    this.marginDb = 14,
    this.minSpeechDb = -48,
    this.initialFloorDb = -62,
    this.maxFloorDb = -34,
    this.windowFrames = 100,
    this.floorPercentile = 0.15,
    this.calibrationFrames = 15,
  }) : _floorDb = initialFloorDb;

  final double marginDb;
  final double minSpeechDb;
  final double initialFloorDb;
  final double maxFloorDb;
  final int windowFrames;
  final double floorPercentile;

  /// Frames at the start used only to measure the room (never speech).
  final int calibrationFrames;

  final List<double> _window = [];
  double _floorDb;
  double _lastDb = -90;
  int _seen = 0;

  double get noiseFloorDb => _floorDb;
  double get lastDb => _lastDb;
  bool get calibrated => _seen >= calibrationFrames;
  double get thresholdDb => math.max(_floorDb + marginDb, minSpeechDb);

  /// Returns true if [frame] looks like speech. Pass `learn: false` while the
  /// user is known to be talking so the floor is not pulled up by speech.
  ///
  /// [extraThresholdDb] raises the bar for this frame only; used while the
  /// assistant is speaking so its own voice leaking into the microphone is
  /// not mistaken for the user.
  bool process(Int16List frame, {bool learn = true, double? extraThresholdDb}) {
    final db = frameDb(frame);
    _lastDb = db;
    if (!calibrated) {
      _seen++;
      _remember(db);
      return false;
    }
    final isSpeech = db > math.max(thresholdDb, extraThresholdDb ?? -200);
    if (learn) _remember(db);
    return isSpeech;
  }

  void _remember(double db) {
    _window.add(db);
    if (_window.length > windowFrames) _window.removeAt(0);
    final sorted = List<double>.of(_window)..sort();
    final index = ((sorted.length - 1) * floorPercentile).floor();
    _floorDb = sorted[index].clamp(-80.0, maxFloorDb);
  }

  void reset() {
    _window.clear();
    _floorDb = initialFloorDb;
    _lastDb = -90;
    _seen = 0;
  }
}

enum EndpointEventType {
  /// The user started talking.
  speechStart,

  /// The user stopped talking; [EndpointEvent.audio] holds the utterance.
  speechEnd,

  /// Nothing was said within the allowed waiting time.
  noSpeech,

  /// The utterance hit the maximum length and was cut off.
  maxLength,
}

class EndpointEvent {
  const EndpointEvent(this.type, {this.audio, this.speechDuration});

  final EndpointEventType type;

  /// Utterance samples including a short lead-in. Only set for
  /// [EndpointEventType.speechEnd] and [EndpointEventType.maxLength].
  final Int16List? audio;

  /// Duration of detected speech, excluding lead-in and trailing silence.
  final Duration? speechDuration;
}

class EndpointConfig {
  const EndpointConfig({
    this.frameMs = 20,
    this.onsetFrames = 4,
    this.endSilenceMs = 850,
    this.noSpeechTimeoutMs = 8000,
    this.maxUtteranceMs = 30000,
    this.prerollMs = 480,
    this.minSpeechMs = 240,
    this.marginDb = 14,
    this.minSpeechDb = -48,
  });

  /// Tuned for being spoken to.
  const EndpointConfig.turn() : this();

  /// Tuned for detecting that the user is talking over the assistant: needs
  /// longer, louder speech so playback echo and small noises do not interrupt.
  const EndpointConfig.bargeIn()
    : this(
        onsetFrames: 14,
        marginDb: 20,
        minSpeechDb: -40,
        noSpeechTimeoutMs: 0,
      );

  final int frameMs;

  /// Consecutive speech frames required to confirm the start of speech.
  final int onsetFrames;

  /// Trailing silence that ends an utterance.
  final int endSilenceMs;

  /// Give up if no speech starts within this long (0 disables).
  final int noSpeechTimeoutMs;
  final int maxUtteranceMs;

  /// Audio kept from before speech was confirmed.
  final int prerollMs;

  /// Shorter bursts of speech are discarded as clicks/coughs.
  final int minSpeechMs;
  final double marginDb;
  final double minSpeechDb;
}

/// Splits a continuous microphone stream into utterances.
///
/// Feed 20 ms frames to [feed]; it returns an [EndpointEvent] when something
/// noteworthy happened, otherwise null.
class TurnEndpointer {
  TurnEndpointer([this.config = const EndpointConfig()])
    : _vad = EnergyVad(
        marginDb: config.marginDb,
        minSpeechDb: config.minSpeechDb,
      ),
      _preroll = PcmRingBuffer(
        kVoiceSampleRate * config.prerollMs ~/ 1000 + kVoiceFrameSamples,
      );

  final EndpointConfig config;
  final EnergyVad _vad;
  final PcmRingBuffer _preroll;
  final PcmBuilder _utterance = PcmBuilder();

  bool _inSpeech = false;
  int _speechRun = 0;
  int _silenceMs = 0;
  int _speechMs = 0;
  int _elapsedMs = 0;
  int _utteranceMs = 0;

  bool get inSpeech => _inSpeech;
  double get lastDb => _vad.lastDb;
  EnergyVad get vad => _vad;

  /// [extraThresholdDb] temporarily raises the speech threshold (see
  /// [EnergyVad.process]).
  EndpointEvent? feed(Int16List frame, {double? extraThresholdDb}) {
    final isSpeech = _vad.process(
      frame,
      learn: !_inSpeech,
      extraThresholdDb: extraThresholdDb,
    );
    _elapsedMs += config.frameMs;

    if (!_inSpeech) {
      _preroll.push(frame);
      _speechRun = isSpeech ? _speechRun + 1 : 0;
      if (_speechRun >= config.onsetFrames) {
        _inSpeech = true;
        _silenceMs = 0;
        _speechMs = _speechRun * config.frameMs;
        // Include everything the detector needed time to confirm, plus lead-in.
        final lead = _preroll.tail();
        _utterance.add(lead);
        _utteranceMs = lead.length * 1000 ~/ kVoiceSampleRate;
        return const EndpointEvent(EndpointEventType.speechStart);
      }
      if (config.noSpeechTimeoutMs > 0 &&
          _elapsedMs >= config.noSpeechTimeoutMs) {
        _elapsedMs = 0;
        return const EndpointEvent(EndpointEventType.noSpeech);
      }
      return null;
    }

    _utterance.add(frame);
    _utteranceMs += config.frameMs;
    if (isSpeech) {
      _silenceMs = 0;
      _speechMs += config.frameMs;
    } else {
      _silenceMs += config.frameMs;
    }

    if (_silenceMs >= config.endSilenceMs) {
      return _finish(EndpointEventType.speechEnd);
    }
    if (_utteranceMs >= config.maxUtteranceMs) {
      return _finish(EndpointEventType.maxLength);
    }
    return null;
  }

  EndpointEvent? _finish(EndpointEventType type) {
    final speechMs = _speechMs;
    final audio = _utterance.takeSamples();
    _resetState();
    if (speechMs < config.minSpeechMs) {
      // A click or cough, not an utterance: keep listening.
      return null;
    }
    return EndpointEvent(
      type,
      audio: audio,
      speechDuration: Duration(milliseconds: speechMs),
    );
  }

  /// Removes and returns the audio of an utterance that is still in progress
  /// (lead-in plus speech so far), and resets this endpointer.
  ///
  /// Used to hand speech that began while the assistant was talking over to
  /// the turn endpointer, so the user's first words are not lost.
  ({Int16List audio, int speechMs}) takeInProgress() {
    final result = (audio: _utterance.takeSamples(), speechMs: _speechMs);
    _resetState();
    return result;
  }

  /// Continues as if an utterance had already started with [audio], which
  /// contained [speechMs] of speech. Emits no `speechStart` for it.
  void adoptInProgress(Int16List audio, {required int speechMs}) {
    _resetState();
    _utterance.takeSamples();
    _utterance.add(audio);
    _utteranceMs = audio.length * 1000 ~/ kVoiceSampleRate;
    _speechMs = speechMs;
    _inSpeech = true;
  }

  void _resetState() {
    _inSpeech = false;
    _speechRun = 0;
    _silenceMs = 0;
    _speechMs = 0;
    _utteranceMs = 0;
    _elapsedMs = 0;
    _preroll.clear();
  }

  /// Starts a fresh wait for speech (and its timeout).
  void reset({bool keepNoiseFloor = true}) {
    _utterance.takeSamples();
    _resetState();
    if (!keepNoiseFloor) _vad.reset();
  }
}
