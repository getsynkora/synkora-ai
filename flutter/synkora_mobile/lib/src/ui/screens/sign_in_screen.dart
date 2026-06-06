import 'package:flutter/material.dart';
import 'package:lottie/lottie.dart';

import '../../state/session_controller.dart';
import '../../theme/app_theme.dart';
import '../widgets/mesh_background.dart';

class SignInScreen extends StatefulWidget {
  const SignInScreen({super.key, required this.controller});

  final SessionController controller;

  @override
  State<SignInScreen> createState() => _SignInScreenState();
}

class _SignInScreenState extends State<SignInScreen> {
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      body: Stack(
        children: [
          const Positioned.fill(child: MeshBackground()),
          SafeArea(
            child: Center(
              child: SingleChildScrollView(
                padding: const EdgeInsets.all(24),
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 520),
                  child: Card(
                    child: Padding(
                      padding: const EdgeInsets.all(28),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Container(
                            width: 64,
                            height: 64,
                            decoration: BoxDecoration(
                              color: SynkoraColors.ink,
                              borderRadius: BorderRadius.circular(20),
                            ),
                            child: const Icon(
                              Icons.auto_awesome_rounded,
                              color: SynkoraColors.primary,
                            ),
                          ),
                          const SizedBox(height: 18),
                          Text(
                            'Synkora AI',
                            style: theme.textTheme.displayMedium,
                          ),
                          const SizedBox(height: 12),
                          Text(
                            'Use every agent in your workspace from a dedicated native app.',
                            style: theme.textTheme.bodyLarge?.copyWith(
                              color: SynkoraColors.muted,
                            ),
                          ),
                          const SizedBox(height: 28),
                          Container(
                            height: 180,
                            decoration: BoxDecoration(
                              color: SynkoraColors.surface,
                              borderRadius: BorderRadius.circular(24),
                            ),
                            child: Lottie.asset(
                              'packages/synkora_chat/lib/src/assets/animations/choose_your_colors.json',
                              repeat: true,
                            ),
                          ),
                          const SizedBox(height: 28),
                          TextField(
                            controller: _emailController,
                            keyboardType: TextInputType.emailAddress,
                            decoration: const InputDecoration(
                              labelText: 'Email',
                              prefixIcon: Icon(Icons.mail_outline_rounded),
                            ),
                          ),
                          const SizedBox(height: 16),
                          TextField(
                            controller: _passwordController,
                            obscureText: true,
                            decoration: const InputDecoration(
                              labelText: 'Password',
                              prefixIcon: Icon(Icons.lock_outline_rounded),
                            ),
                          ),
                          if (widget.controller.error != null) ...[
                            const SizedBox(height: 16),
                            Container(
                              width: double.infinity,
                              padding: const EdgeInsets.all(14),
                              decoration: BoxDecoration(
                                color: const Color(0xFFFFF1F2),
                                borderRadius: BorderRadius.circular(18),
                                border: Border.all(
                                  color: const Color(0xFFFECACA),
                                ),
                              ),
                              child: Text(
                                widget.controller.error!,
                                style: theme.textTheme.bodyMedium?.copyWith(
                                  color: SynkoraColors.danger,
                                ),
                              ),
                            ),
                          ],
                          const SizedBox(height: 20),
                          SizedBox(
                            width: double.infinity,
                            child: FilledButton.icon(
                              onPressed: widget.controller.isBusy
                                  ? null
                                  : () async {
                                      widget.controller.clearError();
                                      await widget.controller.signIn(
                                        email: _emailController.text.trim(),
                                        password: _passwordController.text,
                                      );
                                    },
                              icon: widget.controller.isBusy
                                  ? const SizedBox(
                                      width: 18,
                                      height: 18,
                                      child: CircularProgressIndicator(
                                        strokeWidth: 2,
                                      ),
                                    )
                                  : const Icon(Icons.arrow_forward_rounded),
                              label: const Text('Sign in'),
                              style: FilledButton.styleFrom(
                                backgroundColor: SynkoraColors.ink,
                                foregroundColor: SynkoraColors.primary,
                                padding: const EdgeInsets.symmetric(
                                  vertical: 18,
                                ),
                                shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(22),
                                ),
                              ),
                            ),
                          ),
                          const SizedBox(height: 16),
                          Text(
                            'This app uses the same Synkora account and tenant access model as the web app.',
                            style: theme.textTheme.bodySmall?.copyWith(
                              color: SynkoraColors.muted,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
