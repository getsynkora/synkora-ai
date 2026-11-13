import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';

import '../../voice/voice_conversation.dart';
import 'voice_palette.dart';

/// Deep night-sky background with slow aurora light tinted by the current
/// conversation state.
class VoiceBackdrop extends StatefulWidget {
  const VoiceBackdrop({super.key, required this.phase});

  final VoicePhase phase;

  @override
  State<VoiceBackdrop> createState() => _VoiceBackdropState();
}

class _VoiceBackdropState extends State<VoiceBackdrop>
    with SingleTickerProviderStateMixin {
  late final Ticker _ticker;
  final ValueNotifier<int> _frame = ValueNotifier(0);
  Duration _last = Duration.zero;
  double _time = 0;
  late Color _glow = VoicePalette.of(widget.phase).glow;
  late Color _accent = VoicePalette.of(widget.phase).accent;

  @override
  void initState() {
    super.initState();
    _ticker = createTicker((elapsed) {
      final dt = ((elapsed - _last).inMicroseconds / 1e6).clamp(0.0, 0.05);
      _last = elapsed;
      _time += dt;
      final target = VoicePalette.of(widget.phase);
      final k = 1 - math.exp(-2.5 * dt);
      _glow = Color.lerp(_glow, target.glow, k)!;
      _accent = Color.lerp(_accent, target.accent, k)!;
      _frame.value++;
    })..start();
  }

  @override
  void dispose() {
    _ticker.dispose();
    _frame.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return RepaintBoundary(
      child: CustomPaint(
        size: Size.infinite,
        painter: _BackdropPainter(
          repaint: _frame,
          read: () => (_time, _glow, _accent),
        ),
      ),
    );
  }
}

class _BackdropPainter extends CustomPainter {
  _BackdropPainter({required Listenable repaint, required this.read})
    : super(repaint: repaint);

  final (double, Color, Color) Function() read;

  @override
  void paint(Canvas canvas, Size size) {
    final (time, glow, accent) = read();
    final rect = Offset.zero & size;
    canvas.drawRect(
      rect,
      Paint()
        ..shader = const LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [Color(0xFF05080F), Color(0xFF0A1020), Color(0xFF060912)],
          stops: [0, 0.55, 1],
        ).createShader(rect),
    );

    void light(Offset anchor, double radius, Color color, double alpha) {
      canvas.drawCircle(
        anchor,
        radius,
        Paint()
          ..shader = RadialGradient(
            colors: [
              color.withValues(alpha: alpha),
              color.withValues(alpha: 0),
            ],
          ).createShader(Rect.fromCircle(center: anchor, radius: radius)),
      );
    }

    final w = size.width;
    final h = size.height;
    light(
      Offset(w * (0.5 + 0.18 * math.sin(time * 0.21)), h * 0.40),
      w * 0.95,
      glow,
      0.20,
    );
    light(
      Offset(w * (0.12 + 0.10 * math.sin(time * 0.17 + 1)), h * 0.12),
      w * 0.70,
      accent,
      0.10,
    );
    light(
      Offset(w * (0.92 + 0.08 * math.cos(time * 0.19)), h * 0.78),
      w * 0.75,
      accent,
      0.09,
    );
  }

  @override
  bool shouldRepaint(covariant _BackdropPainter oldDelegate) => false;
}
