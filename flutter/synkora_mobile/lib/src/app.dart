import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';

import 'config/app_environment.dart';
import 'services/agent_service.dart';
import 'services/api_client.dart';
import 'services/auth_service.dart';
import 'services/secure_token_store.dart';
import 'state/session_controller.dart';
import 'theme/app_theme.dart';
import 'ui/screens/home_screen.dart';
import 'ui/screens/sign_in_screen.dart';
import 'ui/screens/tenant_selection_screen.dart';
import 'ui/widgets/mesh_background.dart';

class SynkoraMobileApp extends StatefulWidget {
  const SynkoraMobileApp({super.key});

  @override
  State<SynkoraMobileApp> createState() => _SynkoraMobileAppState();
}

class _SynkoraMobileAppState extends State<SynkoraMobileApp> {
  late final SessionController _sessionController;
  late final SynkoraAgentService _agentService;

  @override
  void initState() {
    super.initState();
    final authService = SynkoraAuthService(baseUrl: AppEnvironment.apiBaseUrl);
    _sessionController = SessionController(
      authService: authService,
      tokenStore: const SecureTokenStore(),
    );
    final apiClient = SynkoraApiClient(
      baseUrl: AppEnvironment.apiBaseUrl,
      accessTokenProvider: () => _sessionController.accessToken,
    );
    _agentService = SynkoraAgentService(apiClient);
    _sessionController.bootstrap();
  }

  @override
  void dispose() {
    _sessionController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _sessionController,
      builder: (context, _) {
        return MaterialApp(
          debugShowCheckedModeBanner: false,
          title: 'Synkora AI',
          theme: buildSynkoraTheme(),
          home: switch (_sessionController.stage) {
            SessionStage.booting => const _BootScreen(),
            SessionStage.signedOut => SignInScreen(
              controller: _sessionController,
            ),
            SessionStage.selectingTenant => TenantSelectionScreen(
              controller: _sessionController,
            ),
            SessionStage.ready => HomeScreen(
              key: ValueKey(_sessionController.activeTenant?.tenantId),
              sessionController: _sessionController,
              agentService: _agentService,
            ),
          },
        );
      },
    );
  }
}

class _BootScreen extends StatefulWidget {
  const _BootScreen();

  @override
  State<_BootScreen> createState() => _BootScreenState();
}

class _BootScreenState extends State<_BootScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(seconds: 4),
  )..repeat();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      body: Stack(
        children: [
          const Positioned.fill(child: MeshBackground()),
          Positioned.fill(
            child: DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [
                    SynkoraColors.ink.withValues(alpha: 0.78),
                    const Color(0xFF12382E).withValues(alpha: 0.42),
                    const Color(0xFF1A2332).withValues(alpha: 0.78),
                  ],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
              ),
            ),
          ),
          SafeArea(
            child: Center(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 28),
                child: AnimatedBuilder(
                  animation: _controller,
                  builder: (context, _) {
                    final pulse = 0.96 + ((1 + math.sin(_controller.value * math.pi * 2)) * 0.03);
                    final orbitRotation = _controller.value * math.pi * 2;
                    final drift = math.sin(_controller.value * math.pi * 2) * 10;

                    return Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        SizedBox(
                          width: 220,
                          height: 220,
                          child: Stack(
                            alignment: Alignment.center,
                            children: [
                              Transform.rotate(
                                angle: orbitRotation * 0.55,
                                child: Opacity(
                                  opacity: 0.82,
                                  child: SvgPicture.asset(
                                    'assets/art/synkora_ai_orbit.svg',
                                    width: 220,
                                    height: 220,
                                  ),
                                ),
                              ),
                              Transform.translate(
                                offset: Offset(0, drift),
                                child: Transform.scale(
                                  scale: pulse,
                                  child: Container(
                                    width: 124,
                                    height: 124,
                                    padding: const EdgeInsets.all(18),
                                    decoration: BoxDecoration(
                                      color: Colors.white.withValues(alpha: 0.12),
                                      borderRadius: BorderRadius.circular(36),
                                      border: Border.all(
                                        color: Colors.white.withValues(alpha: 0.24),
                                      ),
                                      boxShadow: [
                                        BoxShadow(
                                          color: SynkoraColors.primary.withValues(alpha: 0.18),
                                          blurRadius: 32,
                                          offset: const Offset(0, 18),
                                        ),
                                      ],
                                    ),
                                    child: SvgPicture.asset(
                                      'assets/art/synkora_brand_mark.svg',
                                    ),
                                  ),
                                ),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 28),
                        Text(
                          'Synkora AI',
                          textAlign: TextAlign.center,
                          style: theme.textTheme.displayMedium?.copyWith(
                            color: Colors.white,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        const SizedBox(height: 10),
                        Text(
                          'Branded by Synkora',
                          textAlign: TextAlign.center,
                          style: theme.textTheme.bodyLarge?.copyWith(
                            color: Colors.white.withValues(alpha: 0.72),
                            letterSpacing: 0.6,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        const SizedBox(height: 12),
                        Text(
                          'Loading your workspace, agents, and premium actions.',
                          textAlign: TextAlign.center,
                          style: theme.textTheme.bodyMedium?.copyWith(
                            color: Colors.white.withValues(alpha: 0.54),
                          ),
                        ),
                        const SizedBox(height: 24),
                        _SplashLoader(progress: _controller.value),
                      ],
                    );
                  },
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _SplashLoader extends StatelessWidget {
  const _SplashLoader({required this.progress});

  final double progress;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 176,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: List.generate(4, (index) {
          final offset = (progress * 4 - index).abs();
          final intensity = (1 - offset.clamp(0, 1)).toDouble();
          final height = 8 + (intensity * 16);

          return Padding(
            padding: const EdgeInsets.symmetric(horizontal: 5),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 120),
              width: 18,
              height: height,
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [
                    Color.lerp(
                      Colors.white.withValues(alpha: 0.42),
                      SynkoraColors.primary,
                      intensity,
                    )!,
                    Color.lerp(
                      Colors.white.withValues(alpha: 0.18),
                      SynkoraColors.accentWarm,
                      intensity,
                    )!,
                  ],
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                ),
                borderRadius: BorderRadius.circular(999),
                boxShadow: [
                  BoxShadow(
                    color: SynkoraColors.primary.withValues(alpha: 0.18 * intensity),
                    blurRadius: 12,
                    offset: const Offset(0, 6),
                  ),
                ],
              ),
            ),
          );
        }),
      ),
    );
  }
}
