import 'package:flutter/material.dart';

import '../../models/synkora_models.dart';
import '../../voice/voice_conversation.dart';
import '../../voice/voice_hub.dart';
import 'voice_hub_scope.dart';
import 'voice_mode_screen.dart';
import 'voice_orb.dart';
import 'voice_palette.dart';

/// Home-screen call to action: start (or wake) a spoken conversation.
class VoiceEntryCard extends StatelessWidget {
  const VoiceEntryCard({super.key, this.agent});

  /// The agent to talk to; defaults to the last one used.
  final AgentSummary? agent;

  @override
  Widget build(BuildContext context) {
    final hub = VoiceHubScope.maybeOf(context);
    if (hub == null) return const SizedBox.shrink();
    return ListenableBuilder(
      listenable: Listenable.merge([hub, hub.settings]),
      builder: (context, _) {
        final target = agent ?? hub.defaultAgent;
        final handsFree = hub.settings.wakeEnabled && hub.wakeSupported;
        return Padding(
          padding: const EdgeInsets.only(bottom: 14),
          child: _Card(
            hub: hub,
            title: target == null
                ? 'Talk to your agents'
                : 'Talk to ${target.name}',
            subtitle: handsFree
                ? 'Hands-free is on. Just say “Hey Synkora”.'
                : 'Have a real voice conversation. Tap to start.',
            handsFree: handsFree,
            onTap: target == null ? null : () => openVoice(context, target),
          ),
        );
      },
    );
  }
}

/// Opens the full-screen voice conversation for [agent].
Future<void> openVoice(
  BuildContext context,
  AgentSummary agent, {
  String? conversationId,
}) {
  final hub = VoiceHubScope.maybeOf(context);
  if (hub == null) return Future.value();
  return Navigator.of(context).push(
    VoiceModeScreen.route(
      hub: hub,
      agent: agent,
      conversationId: conversationId,
    ),
  );
}

class _Card extends StatelessWidget {
  const _Card({
    required this.hub,
    required this.title,
    required this.subtitle,
    required this.handsFree,
    required this.onTap,
  });

  final VoiceHub hub;
  final String title;
  final String subtitle;
  final bool handsFree;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context).textTheme;
    final quiet = ValueNotifier<double>(0);
    return Semantics(
      button: true,
      label: '$title. $subtitle',
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(28),
          onTap: onTap,
          child: Ink(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(28),
              gradient: const LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [Color(0xFF0B1220), Color(0xFF10263A)],
              ),
              boxShadow: [
                BoxShadow(
                  color: VoicePalette.listening.glow.withValues(alpha: 0.22),
                  blurRadius: 30,
                  offset: const Offset(0, 14),
                ),
              ],
            ),
            padding: const EdgeInsets.fromLTRB(8, 10, 20, 10),
            child: Row(
              children: [
                SizedBox(
                  width: 96,
                  height: 96,
                  child: OverflowBox(
                    maxWidth: 150,
                    maxHeight: 150,
                    child: VoiceOrb(
                      phase: handsFree
                          ? VoicePhase.armed
                          : VoicePhase.listening,
                      inputLevel: quiet,
                      outputLevel: quiet,
                      size: 150,
                    ),
                  ),
                ),
                const SizedBox(width: 6),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        title,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: theme.titleLarge?.copyWith(
                          color: Colors.white,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        subtitle,
                        style: theme.bodyMedium?.copyWith(
                          color: Colors.white.withValues(alpha: 0.66),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                Container(
                  width: 44,
                  height: 44,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: VoicePalette.listening.mid,
                  ),
                  child: const Icon(
                    Icons.graphic_eq_rounded,
                    color: Color(0xFF05241C),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
