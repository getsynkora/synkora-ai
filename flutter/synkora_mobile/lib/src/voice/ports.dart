import 'dart:typed_data';

import '../models/synkora_models.dart';

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

/// A synthesized piece of speech.
class SynthesizedAudio {
  const SynthesizedAudio({
    required this.bytes,
    required this.mimeType,
    this.duration,
    this.envelope = const [],
    this.envelopeStep = const Duration(milliseconds: 50),
  });

  final Uint8List bytes;
  final String mimeType;

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
