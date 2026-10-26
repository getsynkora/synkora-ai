import 'dart:async';
import 'dart:typed_data';

import 'package:record/record.dart';

import '../audio/pcm.dart';
import '../ports.dart';
import 'voice_audio_session.dart';

/// Microphone capture using the `record` plugin: 16 kHz mono PCM16, re-chunked
/// into 20 ms frames, with echo cancellation and noise suppression requested.
class RecordMic implements VoiceMic {
  RecordMic({AudioRecorder? recorder})
    : _recorder = recorder ?? AudioRecorder();

  final AudioRecorder _recorder;
  final StreamController<Int16List> _frames = StreamController.broadcast();
  final PcmFramer _framer = PcmFramer();
  StreamSubscription<Uint8List>? _subscription;
  bool _running = false;
  Future<void>? _starting;

  @override
  Stream<Int16List> get frames => _frames.stream;

  @override
  bool get isRunning => _running;

  @override
  Future<void> start() => _starting ??= _start().whenComplete(() {
    _starting = null;
  });

  Future<void> _start() async {
    if (_running) return;
    final allowed = await _recorder.hasPermission();
    if (!allowed) {
      throw const VoiceUnavailableException(
        'Microphone access is turned off. Enable it for Synkora in your '
        'phone settings to talk to your agents.',
      );
    }
    await configureVoiceAudioSession();
    // Our session (voice-chat mode) must not be reset by the recorder.
    await _recorder.ios?.manageAudioSession(false);

    final stream = await _recorder.startStream(
      const RecordConfig(
        encoder: AudioEncoder.pcm16bits,
        sampleRate: kVoiceSampleRate,
        numChannels: 1,
        echoCancel: true,
        noiseSuppress: true,
        autoGain: false,
        androidConfig: AndroidRecordConfig(
          audioSource: AndroidAudioSource.voiceCommunication,
          speakerphone: true,
        ),
      ),
    );
    _framer.reset();
    _subscription = stream.listen(
      (bytes) {
        for (final frame in _framer.add(bytes)) {
          if (!_frames.isClosed) _frames.add(frame);
        }
      },
      onError: (Object error) {
        if (!_frames.isClosed) _frames.addError(error);
      },
    );
    _running = true;
  }

  @override
  Future<void> stop() async {
    if (!_running) return;
    _running = false;
    await _subscription?.cancel();
    _subscription = null;
    await _recorder.stop();
    _framer.reset();
    await releaseVoiceAudioSession();
  }

  Future<void> dispose() async {
    await stop();
    await _frames.close();
    await _recorder.dispose();
  }
}
