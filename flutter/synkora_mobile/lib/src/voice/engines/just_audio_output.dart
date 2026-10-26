import 'dart:async';
import 'dart:io';

import 'package:just_audio/just_audio.dart';
import 'package:path_provider/path_provider.dart';

import '../audio/chime.dart';
import '../ports.dart';

/// Plays synthesized speech with `just_audio` and reports a live loudness
/// level that follows the audio, for the on-screen visualiser.
class JustAudioOutput implements AudioOutput {
  JustAudioOutput({AudioPlayer? player})
    : _player =
          player ??
          AudioPlayer(
            // The conversation manages interruptions and the session itself.
            handleInterruptions: false,
          );

  final AudioPlayer _player;
  final StreamController<double> _level = StreamController.broadcast();
  Timer? _levelTimer;
  int _clipCounter = 0;
  Directory? _directory;

  @override
  Stream<double> get level => _level.stream;

  @override
  Future<void> play(SynthesizedAudio audio) async {
    final file = await _writeClip(audio);
    try {
      await _player.setFilePath(file.path);
      _startLevelTimer(audio);
      // Completes when playback reaches the end or stop() is called.
      await _player.play();
    } finally {
      _levelTimer?.cancel();
      _levelTimer = null;
      if (!_level.isClosed) _level.add(0);
      unawaited(_deleteQuietly(file));
    }
  }

  @override
  Future<void> stop() async {
    _levelTimer?.cancel();
    _levelTimer = null;
    await _player.stop();
    if (!_level.isClosed) _level.add(0);
  }

  @override
  Future<void> dispose() async {
    _levelTimer?.cancel();
    await _player.dispose();
    await _level.close();
  }

  void _startLevelTimer(SynthesizedAudio audio) {
    _levelTimer?.cancel();
    _levelTimer = Timer.periodic(const Duration(milliseconds: 33), (_) {
      if (_level.isClosed) return;
      final position = _player.position;
      _level.add(
        audio.envelope.isEmpty
            ? syntheticSpeechLevel(position)
            : levelAt(audio.envelope, audio.envelopeStep, position),
      );
    });
  }

  Future<File> _writeClip(SynthesizedAudio audio) async {
    _directory ??= await getTemporaryDirectory();
    final extension = switch (audio.mimeType) {
      'audio/wav' => 'wav',
      'audio/mpeg' => 'mp3',
      _ => 'm4a',
    };
    final file = File(
      '${_directory!.path}/synkora_voice_${_clipCounter++ % 6}.$extension',
    );
    await file.writeAsBytes(audio.bytes, flush: true);
    return file;
  }

  Future<void> _deleteQuietly(File file) async {
    try {
      if (await file.exists()) await file.delete();
    } catch (_) {
      // Temp files are cleaned up by the OS eventually.
    }
  }
}
