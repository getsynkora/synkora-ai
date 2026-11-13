import 'dart:typed_data';

import '../models/synkora_models.dart';
import 'wake/wake_keywords.dart';

/// Thrown when voice cannot work at all as configured (for example the
/// workspace has no speech provider key), as opposed to a transient failure.
class VoiceUnavailableException implements Exception {
  const VoiceUnavailableException(this.message);

  final String message;

  @override
  String toString() => message;
}

/// Continuous microphone capture, delivered as 20 ms PCM16 frames at 16 kHz.
abstract class VoiceMic {
  /// Frames arrive here while the microphone is open.
  Stream<Int16List> get frames;

  bool get isRunning;

  Future<void> start();

  Future<void> stop();
}

/// Turns a recorded utterance into text.
abstract class SpeechRecognizer {
  /// [wav] is a complete 16 kHz mono WAV file.
  Future<String> transcribe(Uint8List wav, {String? language});
}

/// Text to be spoken by the phone's built-in voice instead of played back as
/// audio (the agent uses the free `web_speech` provider).
class DeviceSpeech {
  const DeviceSpeech({required this.text, this.locale, this.speed = 1.0});

  final String text;

  /// BCP-47 locale such as `en-US`; null for the device default.
  final String? locale;

  /// 1.0 is normal speed.
  final double speed;
}

/// A synthesized piece of speech.
class SynthesizedAudio {
  const SynthesizedAudio({
    required this.bytes,
    required this.mimeType,
    this.duration,
    this.envelope = const [],
    this.envelopeStep = const Duration(milliseconds: 50),
    this.deviceSpeech,
  });

  /// A clip the built-in voice will speak; there is no audio data to play.
  SynthesizedAudio.device(DeviceSpeech speech)
    : bytes = Uint8List(0),
      mimeType = 'application/x-device-speech',
      duration = null,
      envelope = const [],
      envelopeStep = const Duration(milliseconds: 50),
      deviceSpeech = speech;

  final Uint8List bytes;
  final String mimeType;

  /// Set when the phone's own voice should speak this clip.
  final DeviceSpeech? deviceSpeech;

  /// Known playback length, when it can be computed up front.
  final Duration? duration;

  /// Loudness (0..1) every [envelopeStep] of the audio, used to animate the
  /// UI in time with what is being said. Empty when unknown.
  final List<double> envelope;
  final Duration envelopeStep;
}

abstract class SpeechSynthesizer {
  Future<SynthesizedAudio> synthesize(String text, {String? language});
}

/// Listens through the phone's built-in recognizer.
///
/// Unlike [SpeechRecognizer] this owns the microphone and decides when the
/// user has finished, so the shared capture stream must be closed first.
abstract class LiveSpeechRecognizer {
  /// Words recognized so far in the current turn (for live captions).
  Stream<String> get partials;

  /// Listens for one utterance and returns what was said, or null if nothing
  /// was heard. Throws [VoiceUnavailableException] if speech recognition is
  /// not allowed or not available on this device.
  Future<String?> listenOnce({
    String? locale,
    Duration listenFor = const Duration(seconds: 30),
    Duration pauseFor = const Duration(milliseconds: 1600),
  });

  /// Stops listening and delivers what was heard so far as the result.
  Future<void> stop();

  /// Stops listening now, discarding anything not yet final.
  Future<void> cancel();
}

/// Plays synthesized speech through the speaker.
abstract class AudioOutput {
  /// Plays [audio] and completes when it has finished or [stop] was called.
  Future<void> play(SynthesizedAudio audio);

  /// Stops the current clip immediately.
  Future<void> stop();

  /// Loudness (0..1) of what is currently audible; 0 when idle.
  Stream<double> get level;

  Future<void> dispose();
}

/// Listens to microphone frames for the wake phrase.
abstract class WakeWordDetector {
  /// Returns true when the wake phrase was just heard in [frame]'s stream.
  bool process(Int16List frame);

  /// Forgets any partially matched audio.
  void reset();

  Future<void> dispose();
}

/// Optional: a detector that can report whether it is working.
abstract interface class WakeWordStatus {
  /// True once the model is loaded and listening.
  bool get isReady;

  /// Why the detector could not start, if it could not.
  String? get failure;

  /// Loads the model now (otherwise it loads on the first audio frame).
  Future<void> start();
}

/// Optional: a detector whose eagerness can be changed while running.
abstract interface class WakeSensitivityControl {
  WakeSensitivity get sensitivity;
  set sensitivity(WakeSensitivity value);
}

/// What the voice layer needs from the Synkora chat backend.
abstract class VoiceAgentGateway {
  /// Returns the id of a conversation to continue, creating one if needed.
  Future<String> createConversation(AgentSummary agent, {required String name});

  /// Streams the agent's reply to [message]. The request is flagged as a
  /// spoken conversation so replies come back short and markdown-free.
  Stream<ChatEvent> stream({
    required AgentSummary agent,
    required String message,
    required String conversationId,
  });
}
