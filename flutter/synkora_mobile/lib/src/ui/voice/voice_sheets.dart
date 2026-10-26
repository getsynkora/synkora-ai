import 'package:flutter/material.dart';

import '../../models/synkora_models.dart';
import '../../voice/voice_conversation.dart';
import '../../voice/voice_hub.dart';

const _sheetColor = Color(0xFF0E1526);

/// Round agent picture, or a tinted initial when there is none.
class AgentAvatar extends StatelessWidget {
  const AgentAvatar({
    super.key,
    required this.agent,
    this.size = 40,
    this.glow = const Color(0xFF3CF0B8),
  });

  final AgentSummary agent;
  final double size;
  final Color glow;

  @override
  Widget build(BuildContext context) {
    final initial = agent.name.trim().isEmpty
        ? '?'
        : agent.name.trim().characters.first.toUpperCase();
    final fallback = Container(
      width: size,
      height: size,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [glow, glow.withValues(alpha: 0.45)],
        ),
      ),
      child: Text(
        initial,
        style: TextStyle(
          color: const Color(0xFF06121A),
          fontWeight: FontWeight.w800,
          fontSize: size * 0.46,
        ),
      ),
    );
    final url = agent.avatarUrl;
    if (url == null || url.isEmpty) return fallback;
    return ClipOval(
      child: Image.network(
        url,
        width: size,
        height: size,
        fit: BoxFit.cover,
        errorBuilder: (_, _, _) => fallback,
        loadingBuilder: (_, child, progress) =>
            progress == null ? child : fallback,
      ),
    );
  }
}

Future<void> _showSheet(BuildContext context, WidgetBuilder builder) {
  return showModalBottomSheet<void>(
    context: context,
    backgroundColor: _sheetColor,
    isScrollControlled: true,
    showDragHandle: true,
    barrierColor: Colors.black.withValues(alpha: 0.55),
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
    ),
    builder: builder,
  );
}

/// Lets the user pick which agent they are talking to.
Future<void> showAgentPicker(
  BuildContext context, {
  required VoiceHub hub,
  required AgentSummary current,
}) {
  return _showSheet(context, (sheetContext) {
    final agents = hub.agents.where((a) => !a.isSubAgent).toList();
    final theme = Theme.of(sheetContext).textTheme;
    return SafeArea(
      child: ConstrainedBox(
        constraints: BoxConstraints(
          maxHeight: MediaQuery.sizeOf(sheetContext).height * 0.7,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(24, 0, 24, 4),
              child: Text(
                'Talk to',
                style: theme.titleLarge?.copyWith(
                  color: Colors.white,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(24, 0, 24, 12),
              child: Text(
                'You can also say “switch to” followed by a name.',
                style: theme.bodySmall?.copyWith(
                  color: Colors.white.withValues(alpha: 0.55),
                ),
              ),
            ),
            Flexible(
              child: agents.isEmpty
                  ? Padding(
                      padding: const EdgeInsets.all(24),
                      child: Text(
                        'No other agents yet.',
                        style: TextStyle(
                          color: Colors.white.withValues(alpha: 0.6),
                        ),
                      ),
                    )
                  : ListView.builder(
                      shrinkWrap: true,
                      padding: const EdgeInsets.fromLTRB(12, 0, 12, 16),
                      itemCount: agents.length,
                      itemBuilder: (_, index) {
                        final agent = agents[index];
                        final selected = agent.id == current.id;
                        return ListTile(
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(18),
                          ),
                          tileColor: selected
                              ? Colors.white.withValues(alpha: 0.08)
                              : null,
                          leading: AgentAvatar(agent: agent, size: 42),
                          title: Text(
                            agent.name,
                            style: const TextStyle(
                              color: Colors.white,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                          subtitle: Text(
                            agent.description,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                              color: Colors.white.withValues(alpha: 0.5),
                            ),
                          ),
                          trailing: selected
                              ? const Icon(
                                  Icons.check_circle_rounded,
                                  color: Color(0xFF3CF0B8),
                                )
                              : null,
                          onTap: () {
                            Navigator.of(sheetContext).pop();
                            if (!selected) hub.switchAgent(agent);
                          },
                        );
                      },
                    ),
            ),
          ],
        ),
      ),
    );
  });
}

/// Shows what was said in this conversation so far.
Future<void> showTranscript(BuildContext context, VoiceConversation c) {
  return _showSheet(context, (sheetContext) {
    return SafeArea(
      child: ConstrainedBox(
        constraints: BoxConstraints(
          maxHeight: MediaQuery.sizeOf(sheetContext).height * 0.75,
        ),
        child: ListenableBuilder(
          listenable: c,
          builder: (context, _) {
            final turns = c.turns;
            final theme = Theme.of(context).textTheme;
            return Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(24, 0, 24, 12),
                  child: Text(
                    'Transcript',
                    style: theme.titleLarge?.copyWith(
                      color: Colors.white,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
                Flexible(
                  child: turns.isEmpty
                      ? Padding(
                          padding: const EdgeInsets.fromLTRB(24, 8, 24, 32),
                          child: Text(
                            'Nothing yet. Start talking and your conversation will appear here.',
                            style: TextStyle(
                              color: Colors.white.withValues(alpha: 0.55),
                            ),
                          ),
                        )
                      : ListView.separated(
                          shrinkWrap: true,
                          reverse: false,
                          padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
                          itemCount: turns.length,
                          separatorBuilder: (_, _) =>
                              const SizedBox(height: 10),
                          itemBuilder: (_, i) => _TurnBubble(turn: turns[i]),
                        ),
                ),
              ],
            );
          },
        ),
      ),
    );
  });
}

class _TurnBubble extends StatelessWidget {
  const _TurnBubble({required this.turn});

  final VoiceTurn turn;

  @override
  Widget build(BuildContext context) {
    final user = turn.isUser;
    return Align(
      alignment: user ? Alignment.centerRight : Alignment.centerLeft,
      child: ConstrainedBox(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.sizeOf(context).width * 0.8,
        ),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          decoration: BoxDecoration(
            color: user
                ? const Color(0xFF3CF0B8).withValues(alpha: 0.18)
                : Colors.white.withValues(alpha: 0.08),
            borderRadius: BorderRadius.only(
              topLeft: const Radius.circular(18),
              topRight: const Radius.circular(18),
              bottomLeft: Radius.circular(user ? 18 : 4),
              bottomRight: Radius.circular(user ? 4 : 18),
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                turn.text,
                style: const TextStyle(color: Colors.white, height: 1.35),
              ),
              if (turn.interrupted)
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text(
                    'Interrupted',
                    style: TextStyle(
                      color: Colors.white.withValues(alpha: 0.45),
                      fontSize: 11,
                      fontStyle: FontStyle.italic,
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Wake word, speed, interruption and feedback preferences.
Future<void> showVoiceSettings(BuildContext context, VoiceHub hub) {
  return _showSheet(context, (sheetContext) {
    final settings = hub.settings;
    final theme = Theme.of(sheetContext).textTheme;
    return SafeArea(
      child: ListenableBuilder(
        listenable: settings,
        builder: (context, _) => SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(24, 0, 24, 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Voice settings',
                style: theme.titleLarge?.copyWith(
                  color: Colors.white,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 8),
              if (hub.wakeSupported)
                _SwitchRow(
                  title: 'Wake with “Hey Synkora”',
                  subtitle:
                      'Listens for the phrase while Synkora is open, so you can '
                      'talk hands-free. Audio is checked on your phone and is '
                      'only sent once you start speaking.',
                  value: settings.wakeEnabled,
                  onChanged: settings.setWakeEnabled,
                ),
              _SwitchRow(
                title: 'Interrupt by speaking',
                subtitle: 'Talk over the assistant to cut it off.',
                value: settings.bargeIn,
                onChanged: settings.setBargeIn,
              ),
              _SwitchRow(
                title: 'Sounds',
                subtitle: 'A soft chime when it wakes or finishes.',
                value: settings.cueSounds,
                onChanged: settings.setCueSounds,
              ),
              _SwitchRow(
                title: 'Haptics',
                subtitle: 'Gentle taps at key moments.',
                value: settings.cueHaptics,
                onChanged: settings.setCueHaptics,
              ),
              const SizedBox(height: 10),
              Text(
                'Speaking speed  ·  ${settings.speed.toStringAsFixed(2)}×',
                style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.w600,
                ),
              ),
              SliderTheme(
                data: SliderTheme.of(context).copyWith(
                  activeTrackColor: const Color(0xFF3CF0B8),
                  inactiveTrackColor: Colors.white.withValues(alpha: 0.14),
                  thumbColor: Colors.white,
                  overlayColor: const Color(0xFF3CF0B8).withValues(alpha: 0.2),
                ),
                child: Slider(
                  min: 0.8,
                  max: 1.4,
                  divisions: 12,
                  value: settings.speed,
                  onChanged: settings.setSpeed,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  });
}

class _SwitchRow extends StatelessWidget {
  const _SwitchRow({
    required this.title,
    required this.subtitle,
    required this.value,
    required this.onChanged,
  });

  final String title;
  final String subtitle;
  final bool value;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    return SwitchListTile.adaptive(
      contentPadding: EdgeInsets.zero,
      value: value,
      onChanged: onChanged,
      activeThumbColor: const Color(0xFF06121A),
      activeTrackColor: const Color(0xFF3CF0B8),
      title: Text(
        title,
        style: const TextStyle(
          color: Colors.white,
          fontWeight: FontWeight.w600,
        ),
      ),
      subtitle: Padding(
        padding: const EdgeInsets.only(top: 2),
        child: Text(
          subtitle,
          style: TextStyle(
            color: Colors.white.withValues(alpha: 0.55),
            height: 1.3,
          ),
        ),
      ),
    );
  }
}
