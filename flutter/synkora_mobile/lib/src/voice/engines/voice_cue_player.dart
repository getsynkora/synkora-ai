import 'dart:async';
import 'dart:io';

import 'package:flutter/services.dart';
import 'package:just_audio/just_audio.dart';
import 'package:path_provider/path_provider.dart';

import '../audio/chime.dart';
import '../voice_conversation.dart';

/// Short, quiet audio and haptic feedback for voice moments: the wake chime,
/// the end-of-session tone and errors.
class VoiceCuePlayer {
  VoiceCuePlayer({this.sounds = true, this.haptics = true});

  bool sounds;
  bool haptics;
  AudioPlayer? _player;

  static final _wake = buildChime(const [Tone(660, 90), Tone(990, 170)]);
  static final _ended = buildChime(const [Tone(740, 90), Tone(494, 190)]);
  static final _error = buildChime(const [Tone(247, 220)], volume: 0.18);
  static final _listening = buildChime(const [Tone(880, 70)], volume: 0.12);

  void cue(VoiceCue cue) {
    if (haptics) {
      switch (cue) {
        case VoiceCue.wake:
          unawaited(HapticFeedback.mediumImpact());
        case VoiceCue.sent:
          unawaited(HapticFeedback.selectionClick());
        case VoiceCue.error:
          unawaited(HapticFeedback.heavyImpact());
        case VoiceCue.ended:
          unawaited(HapticFeedback.lightImpact());
        case VoiceCue.listening:
          break;
      }
    }
    if (!sounds) return;
    final wav = switch (cue) {
      VoiceCue.wake => _wake,
      VoiceCue.ended => _ended,
      VoiceCue.error => _error,
      VoiceCue.listening => _listening,
      VoiceCue.sent => null,
    };
    if (wav != null) unawaited(_play(wav));
  }

  Future<void> _play(List<int> wav) async {
    try {
      final dir = await getTemporaryDirectory();
      final file = File('${dir.path}/synkora_cue_${wav.length}.wav');
      if (!await file.exists()) await file.writeAsBytes(wav, flush: true);
      final player = _player ??= AudioPlayer(handleInterruptions: false);
      await player.setFilePath(file.path);
      await player.play();
    } catch (_) {
      // A missing chime must never break the conversation.
    }
  }

  Future<void> dispose() async {
    await _player?.dispose();
    _player = null;
  }
}
