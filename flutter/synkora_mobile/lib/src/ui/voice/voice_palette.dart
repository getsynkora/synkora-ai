import 'package:flutter/material.dart';

import '../../voice/voice_conversation.dart';

/// Colors that describe one conversation state.
class VoicePalette {
  const VoicePalette({
    required this.core,
    required this.mid,
    required this.edge,
    required this.accent,
    required this.glow,
  });

  /// Bright centre of the orb.
  final Color core;
  final Color mid;

  /// Deep colour at the rim.
  final Color edge;

  /// Swirl highlights drifting inside the orb.
  final Color accent;

  /// Colour of the halo and background light.
  final Color glow;

  static VoicePalette lerp(VoicePalette a, VoicePalette b, double t) =>
      VoicePalette(
        core: Color.lerp(a.core, b.core, t)!,
        mid: Color.lerp(a.mid, b.mid, t)!,
        edge: Color.lerp(a.edge, b.edge, t)!,
        accent: Color.lerp(a.accent, b.accent, t)!,
        glow: Color.lerp(a.glow, b.glow, t)!,
      );

  /// Resting, waiting for "Hey Synkora".
  static const armed = VoicePalette(
    core: Color(0xFF3FA68A),
    mid: Color(0xFF1B6B5A),
    edge: Color(0xFF0A2E28),
    accent: Color(0xFF5CC8B0),
    glow: Color(0xFF1FA383),
  );

  /// The assistant is hearing you.
  static const listening = VoicePalette(
    core: Color(0xFF8CF5D2),
    mid: Color(0xFF2FC79A),
    edge: Color(0xFF07503F),
    accent: Color(0xFF6EC8FF),
    glow: Color(0xFF3CF0B8),
  );

  /// Working on an answer.
  static const thinking = VoicePalette(
    core: Color(0xFF9DA8FF),
    mid: Color(0xFF5B68F0),
    edge: Color(0xFF1C2178),
    accent: Color(0xFFB69CFF),
    glow: Color(0xFF6C74FF),
  );

  /// The assistant is talking.
  static const speaking = VoicePalette(
    core: Color(0xFFFFC9A6),
    mid: Color(0xFFFF8A8F),
    edge: Color(0xFF9E2F58),
    accent: Color(0xFFFFD27A),
    glow: Color(0xFFFF8A9E),
  );

  static const error = VoicePalette(
    core: Color(0xFFFFA39B),
    mid: Color(0xFFF04F5B),
    edge: Color(0xFF6A1424),
    accent: Color(0xFFFF9E7A),
    glow: Color(0xFFFF4D5E),
  );

  static VoicePalette of(VoicePhase phase) => switch (phase) {
    VoicePhase.idle || VoicePhase.armed => armed,
    VoicePhase.listening => listening,
    VoicePhase.thinking => thinking,
    VoicePhase.speaking => speaking,
    VoicePhase.error => error,
  };
}
