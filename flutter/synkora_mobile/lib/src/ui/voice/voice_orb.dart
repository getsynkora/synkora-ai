import 'dart:math' as math;

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';

import '../../voice/voice_conversation.dart';
import 'voice_palette.dart';

/// The assistant's presence: a luminous orb that breathes while waiting,
/// ripples to your voice while listening, orbits while thinking and pulses with
/// the actual loudness of its own speech while talking.
class VoiceOrb extends StatefulWidget {
  const VoiceOrb({
    super.key,
    required this.phase,
    required this.inputLevel,
    required this.outputLevel,
    this.size = 300,
    this.userSpeaking = false,
  });

  final VoicePhase phase;
  final ValueListenable<double> inputLevel;
  final ValueListenable<double> outputLevel;
  final double size;

  /// True once the user has actually started a sentence (not just room noise).
  final bool userSpeaking;

  @override
  State<VoiceOrb> createState() => _VoiceOrbState();
}

class _VoiceOrbState extends State<VoiceOrb>
    with SingleTickerProviderStateMixin {
  late final Ticker _ticker;
  final ValueNotifier<int> _frame = ValueNotifier(0);
  Duration _last = Duration.zero;

  double _time = 0;
  double _level = 0;
  double _ring = 0;
  double _think = 0;
  double _breath = 0;
  late VoicePalette _palette = VoicePalette.of(widget.phase);

  @override
  void initState() {
    super.initState();
    _ticker = createTicker(_tick)..start();
  }

  @override
  void dispose() {
    _ticker.dispose();
    _frame.dispose();
    super.dispose();
  }

  void _tick(Duration elapsed) {
    final dt = ((elapsed - _last).inMicroseconds / 1e6).clamp(0.0, 0.05);
    _last = elapsed;
    _time += dt;

    final phase = widget.phase;
    final target = switch (phase) {
      VoicePhase.listening =>
        widget.userSpeaking
            ? math.max(0.12, widget.inputLevel.value)
            : widget.inputLevel.value * 0.35,
      VoicePhase.speaking => widget.outputLevel.value,
      VoicePhase.thinking => 0.22 + 0.08 * math.sin(_time * 3),
      VoicePhase.armed || VoicePhase.idle => 0.04,
      VoicePhase.error => 0.15,
    };
    // Rise quickly, fall slowly: reads as a voice rather than a flickering bar.
    final rate = target > _level ? 16.0 : 5.5;
    _level += (target - _level) * (1 - math.exp(-rate * dt));

    _palette = VoicePalette.lerp(
      _palette,
      VoicePalette.of(phase),
      1 - math.exp(-5.0 * dt),
    );
    final wantRing =
        (phase == VoicePhase.listening && widget.userSpeaking) ||
            phase == VoicePhase.speaking
        ? 1.0
        : 0.0;
    _ring += (wantRing - _ring) * (1 - math.exp(-6.0 * dt));
    final wantThink = phase == VoicePhase.thinking ? 1.0 : 0.0;
    _think += (wantThink - _think) * (1 - math.exp(-5.0 * dt));
    final wantBreath = (phase == VoicePhase.armed || phase == VoicePhase.idle)
        ? 1.0
        : 0.0;
    _breath += (wantBreath - _breath) * (1 - math.exp(-4.0 * dt));

    _frame.value++;
  }

  @override
  Widget build(BuildContext context) {
    return RepaintBoundary(
      child: SizedBox.square(
        dimension: widget.size,
        child: CustomPaint(
          painter: OrbPainter(
            repaint: _frame,
            read: () => OrbFrame(
              time: _time,
              level: _level,
              ring: _ring,
              think: _think,
              breath: _breath,
              palette: _palette,
            ),
          ),
        ),
      ),
    );
  }
}

/// Everything the painter needs for one frame.
class OrbFrame {
  const OrbFrame({
    required this.time,
    required this.level,
    required this.ring,
    required this.think,
    required this.breath,
    required this.palette,
  });

  final double time;

  /// 0..1 current loudness driving the shape.
  final double level;

  /// 0..1 how visible the expanding rings are.
  final double ring;

  /// 0..1 how visible the orbiting "thinking" arc is.
  final double think;

  /// 0..1 how much the slow idle breathing applies.
  final double breath;
  final VoicePalette palette;
}

class OrbPainter extends CustomPainter {
  OrbPainter({required Listenable repaint, required this.read})
    : super(repaint: repaint);

  final OrbFrame Function() read;

  @override
  void paint(Canvas canvas, Size size) {
    final f = read();
    final center = size.center(Offset.zero);
    final base = size.shortestSide * 0.5 * 0.56;
    final breathe = 1 + f.breath * 0.035 * math.sin(f.time * 1.6);
    final radius = base * breathe * (1 + 0.075 * f.level);
    final p = f.palette;

    // Halo.
    final haloRadius = radius * (1.9 + 0.5 * f.level);
    canvas.drawCircle(
      center,
      haloRadius,
      Paint()
        ..shader = RadialGradient(
          colors: [
            p.glow.withValues(alpha: 0.30 + 0.30 * f.level),
            p.glow.withValues(alpha: 0.08),
            p.glow.withValues(alpha: 0),
          ],
          stops: const [0, 0.5, 1],
        ).createShader(Rect.fromCircle(center: center, radius: haloRadius)),
    );

    // Expanding rings.
    if (f.ring > 0.01) {
      for (var i = 0; i < 3; i++) {
        final t = (f.time * 0.55 + i / 3) % 1.0;
        final ringRadius = radius * (1.06 + t * (0.55 + 0.5 * f.level));
        final alpha = (1 - t) * (0.10 + 0.34 * f.level) * f.ring;
        canvas.drawCircle(
          center,
          ringRadius,
          Paint()
            ..style = PaintingStyle.stroke
            ..strokeWidth = 1.6
            ..color = p.core.withValues(alpha: alpha),
        );
      }
    }

    // Body.
    final body = _blob(center, radius, f);
    canvas.drawShadow(
      body,
      p.glow.withValues(alpha: 0.6),
      28 + 22 * f.level,
      true,
    );
    canvas.drawPath(
      body,
      Paint()
        ..shader = RadialGradient(
          center: const Alignment(-0.3, -0.38),
          radius: 1.12,
          colors: [p.core, p.mid, p.edge],
          stops: const [0, 0.46, 1],
        ).createShader(Rect.fromCircle(center: center, radius: radius * 1.1)),
    );

    // Inner swirls, kept inside the body and added as light.
    canvas.save();
    canvas.clipPath(body);
    for (var k = 0; k < 3; k++) {
      final angle = f.time * (0.45 + 0.23 * k) + k * 2.2;
      final drift = radius * (0.34 + 0.12 * math.sin(f.time * 0.7 + k));
      final swirlCenter =
          center + Offset(math.cos(angle), math.sin(angle)) * drift;
      final swirlRadius = radius * (0.62 + 0.18 * f.level);
      canvas.drawCircle(
        swirlCenter,
        swirlRadius,
        Paint()
          ..blendMode = BlendMode.screen
          ..shader =
              RadialGradient(
                colors: [
                  (k.isEven ? p.accent : p.mid).withValues(
                    alpha: 0.26 + 0.16 * f.level,
                  ),
                  (k.isEven ? p.accent : p.mid).withValues(alpha: 0),
                ],
              ).createShader(
                Rect.fromCircle(center: swirlCenter, radius: swirlRadius),
              ),
      );
    }
    // Volume: darken toward the lower right, away from the light.
    canvas.drawCircle(
      center,
      radius * 1.05,
      Paint()
        ..shader = RadialGradient(
          center: const Alignment(-0.32, -0.4),
          radius: 1.05,
          colors: [
            Colors.black.withValues(alpha: 0),
            Colors.black.withValues(alpha: 0),
            Colors.black.withValues(alpha: 0.38),
          ],
          stops: const [0, 0.55, 1],
        ).createShader(Rect.fromCircle(center: center, radius: radius * 1.05)),
    );
    canvas.restore();

    // Rim light.
    canvas.drawPath(
      body,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.6
        ..shader = SweepGradient(
          transform: GradientRotation(f.time * 0.6),
          colors: [
            Colors.white.withValues(alpha: 0),
            Colors.white.withValues(alpha: 0.55),
            Colors.white.withValues(alpha: 0),
            Colors.white.withValues(alpha: 0.18),
            Colors.white.withValues(alpha: 0),
          ],
        ).createShader(Rect.fromCircle(center: center, radius: radius)),
    );

    // Specular highlight.
    canvas.save();
    canvas.translate(center.dx - radius * 0.34, center.dy - radius * 0.46);
    canvas.rotate(-0.5);
    canvas.drawOval(
      Rect.fromCenter(
        center: Offset.zero,
        width: radius * 0.62,
        height: radius * 0.30,
      ),
      Paint()
        ..color = Colors.white.withValues(alpha: 0.17)
        ..maskFilter = MaskFilter.blur(BlurStyle.normal, radius * 0.09),
    );
    canvas.restore();

    // Thinking arc orbiting the orb.
    if (f.think > 0.01) {
      final arcRect = Rect.fromCircle(center: center, radius: radius * 1.2);
      final start = f.time * 2.6;
      canvas.drawArc(
        arcRect,
        start,
        1.9,
        false,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 3.2
          ..strokeCap = StrokeCap.round
          ..shader = SweepGradient(
            startAngle: 0,
            endAngle: 1.9,
            colors: [
              p.accent.withValues(alpha: 0),
              p.accent.withValues(alpha: 0.95 * f.think),
            ],
            transform: GradientRotation(start),
          ).createShader(arcRect),
      );
      final tip =
          center +
          Offset(math.cos(start + 1.9), math.sin(start + 1.9)) * (radius * 1.2);
      canvas.drawCircle(
        tip,
        4.2,
        Paint()..color = Colors.white.withValues(alpha: 0.9 * f.think),
      );
    }
  }

  Path _blob(Offset center, double radius, OrbFrame f) {
    const points = 120;
    final amplitude = 0.014 + 0.065 * f.level;
    final path = Path();
    for (var i = 0; i <= points; i++) {
      final a = i / points * 2 * math.pi;
      final n =
          0.5 * math.sin(3 * a + f.time * 1.9) +
          0.3 * math.sin(5 * a - f.time * 2.4 + 1) +
          0.2 * math.sin(2 * a + f.time * 1.1 + 2);
      final r = radius * (1 + amplitude * n);
      final x = center.dx + r * math.cos(a);
      final y = center.dy + r * math.sin(a);
      if (i == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }
    return path..close();
  }

  @override
  bool shouldRepaint(covariant OrbPainter oldDelegate) => false;
}
