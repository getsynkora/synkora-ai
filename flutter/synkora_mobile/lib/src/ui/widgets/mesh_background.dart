import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';

import '../../theme/app_theme.dart';

class MeshBackground extends StatefulWidget {
  const MeshBackground({super.key});

  @override
  State<MeshBackground> createState() => _MeshBackgroundState();
}

class _MeshBackgroundState extends State<MeshBackground>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(seconds: 24),
  )..repeat();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final width = constraints.maxWidth;
        final height = constraints.maxHeight;

        return AnimatedBuilder(
          animation: _controller,
          builder: (context, _) {
            final t = _controller.value * math.pi * 2;
            final driftX = math.sin(t * 0.65) * width * 0.018;
            final driftY = math.cos(t * 0.48) * height * 0.012;
            final orbitLift = math.sin(t) * 14;
            final orbitLiftReverse = math.cos(t * 0.82) * 12;
            final orbitScale = 0.96 + ((math.sin(t * 1.2) + 1) * 0.03);

            return DecoratedBox(
              decoration: const BoxDecoration(
                gradient: LinearGradient(
                  colors: [
                    Color(0xFFF9FBFB),
                    Color(0xFFF3F8F6),
                    Color(0xFFFFFAF5),
                  ],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
              ),
              child: Stack(
                fit: StackFit.expand,
                children: [
                  Positioned.fill(
                    child: IgnorePointer(
                      child: Transform.translate(
                        offset: Offset(driftX, driftY),
                        child: Opacity(
                          opacity: 0.92,
                          child: SvgPicture.asset(
                            'assets/art/synkora_ai_scene.svg',
                            fit: BoxFit.cover,
                            alignment: Alignment.center,
                          ),
                        ),
                      ),
                    ),
                  ),
                  Positioned(
                    top: height * 0.06 + orbitLift,
                    right: -width * 0.02,
                    child: IgnorePointer(
                      child: Transform.rotate(
                        angle: t * 0.38,
                        child: Transform.scale(
                          scale: orbitScale,
                          child: Opacity(
                            opacity: 0.66,
                            child: SvgPicture.asset(
                              'assets/art/synkora_ai_orbit.svg',
                              width: width * 0.34,
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                  Positioned(
                    bottom: height * 0.09 + orbitLiftReverse,
                    left: -width * 0.04,
                    child: IgnorePointer(
                      child: Transform.rotate(
                        angle: -t * 0.28,
                        child: Opacity(
                          opacity: 0.54,
                          child: SvgPicture.asset(
                            'assets/art/synkora_ai_orbit.svg',
                            width: width * 0.28,
                          ),
                        ),
                      ),
                    ),
                  ),
                  Positioned(
                    left: width * 0.12 + math.cos(t * 0.72) * 10,
                    top: height * 0.2 + math.sin(t * 0.58) * 12,
                    child: IgnorePointer(
                      child: Transform.rotate(
                        angle: -0.18 + math.sin(t * 0.5) * 0.08,
                        child: Opacity(
                          opacity: 0.2,
                          child: SvgPicture.asset(
                            'assets/art/synkora_ai_orbit.svg',
                            width: width * 0.14,
                            colorFilter: const ColorFilter.mode(
                              SynkoraColors.primaryDeep,
                              BlendMode.srcIn,
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                  Positioned(
                    right: width * 0.18 + math.sin(t * 0.54) * 12,
                    bottom: height * 0.24 + math.cos(t * 0.62) * 10,
                    child: IgnorePointer(
                      child: Transform.rotate(
                        angle: 0.22 + math.cos(t * 0.44) * 0.09,
                        child: Opacity(
                          opacity: 0.16,
                          child: SvgPicture.asset(
                            'assets/art/synkora_ai_orbit.svg',
                            width: width * 0.1,
                            colorFilter: const ColorFilter.mode(
                              SynkoraColors.accentWarm,
                              BlendMode.srcIn,
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            );
          },
        );
      },
    );
  }
}
