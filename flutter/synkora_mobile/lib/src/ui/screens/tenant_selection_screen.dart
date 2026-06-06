import 'package:flutter/material.dart';

import '../../state/session_controller.dart';
import '../../theme/app_theme.dart';
import '../widgets/mesh_background.dart';

class TenantSelectionScreen extends StatelessWidget {
  const TenantSelectionScreen({super.key, required this.controller});

  final SessionController controller;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      body: Stack(
        children: [
          const Positioned.fill(child: MeshBackground()),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Choose workspace',
                    style: theme.textTheme.displayMedium,
                  ),
                  const SizedBox(height: 12),
                  Text(
                    'Your account has access to multiple Synkora tenants. Pick the workspace you want to use on mobile.',
                    style: theme.textTheme.bodyLarge,
                  ),
                  const SizedBox(height: 24),
                  Expanded(
                    child: ListView.separated(
                      itemCount: controller.tenants.length,
                      separatorBuilder: (_, _) => const SizedBox(height: 14),
                      itemBuilder: (context, index) {
                        final tenant = controller.tenants[index];
                        final tenantName = tenant.tenantName.trim();
                        final tenantInitial = tenantName.isEmpty
                            ? 'W'
                            : tenantName.substring(0, 1).toUpperCase();
                        return Card(
                          child: InkWell(
                            borderRadius: BorderRadius.circular(28),
                            onTap: controller.isBusy
                                ? null
                                : () =>
                                      controller.selectTenant(tenant.tenantId),
                            child: Padding(
                              padding: const EdgeInsets.all(22),
                              child: Row(
                                children: [
                                  Container(
                                    width: 52,
                                    height: 52,
                                    decoration: BoxDecoration(
                                      color: SynkoraColors.ink,
                                      borderRadius: BorderRadius.circular(18),
                                    ),
                                    child: Center(
                                      child: Text(
                                        tenantInitial,
                                        style: theme.textTheme.titleLarge
                                            ?.copyWith(
                                              color: SynkoraColors.primary,
                                            ),
                                      ),
                                    ),
                                  ),
                                  const SizedBox(width: 16),
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: [
                                        Text(
                                          tenant.tenantName,
                                          style: theme.textTheme.titleLarge,
                                        ),
                                        const SizedBox(height: 6),
                                        Text(
                                          tenant.role.toUpperCase(),
                                          style: theme.textTheme.bodyMedium
                                              ?.copyWith(letterSpacing: 0.6),
                                        ),
                                      ],
                                    ),
                                  ),
                                  if (controller.isBusy &&
                                      controller.activeTenant?.tenantId ==
                                          tenant.tenantId)
                                    const SizedBox(
                                      width: 20,
                                      height: 20,
                                      child: CircularProgressIndicator(
                                        strokeWidth: 2,
                                      ),
                                    )
                                  else
                                    const Icon(Icons.arrow_forward_rounded),
                                ],
                              ),
                            ),
                          ),
                        );
                      },
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
