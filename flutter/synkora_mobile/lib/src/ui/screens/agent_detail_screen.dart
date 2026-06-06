import 'package:flutter/material.dart';

import '../../models/synkora_models.dart';
import '../../services/agent_service.dart';
import '../../theme/app_theme.dart';
import 'agent_chat_screen.dart';

class AgentDetailScreen extends StatefulWidget {
  const AgentDetailScreen({
    super.key,
    required this.agent,
    required this.agentService,
  });

  final AgentSummary agent;
  final SynkoraAgentService agentService;

  @override
  State<AgentDetailScreen> createState() => _AgentDetailScreenState();
}

class _AgentDetailScreenState extends State<AgentDetailScreen> {
  late Future<_AgentDetailState> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<_AgentDetailState> _load() async {
    final detail = await widget.agentService.getAgent(widget.agent.slug);
    final conversations = await widget.agentService.loadConversations(
      widget.agent.id,
      source: 'flutter',
    );
    return _AgentDetailState(agent: detail, conversations: conversations);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Agent')),
      body: FutureBuilder<_AgentDetailState>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Text(snapshot.error.toString()),
              ),
            );
          }
          final state = snapshot.data!;
          final agent = state.agent;
          return ListView(
            padding: const EdgeInsets.all(20),
            children: [
              Card(
                color: SynkoraColors.ink,
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Container(
                            width: 72,
                            height: 72,
                            decoration: BoxDecoration(
                              color: SynkoraColors.primary,
                              borderRadius: BorderRadius.circular(24),
                            ),
                            clipBehavior: Clip.antiAlias,
                            child: agent.avatarUrl != null &&
                                    agent.avatarUrl!.isNotEmpty
                                ? Image.network(
                                    agent.avatarUrl!,
                                    fit: BoxFit.cover,
                                    errorBuilder: (_, _, _) => const Icon(
                                      Icons.smart_toy_outlined,
                                      color: SynkoraColors.ink,
                                    ),
                                  )
                                : const Icon(
                                    Icons.smart_toy_outlined,
                                    color: SynkoraColors.ink,
                                  ),
                          ),
                          const SizedBox(width: 16),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  agent.name,
                                  style: theme.textTheme.displayMedium
                                      ?.copyWith(color: Colors.white),
                                ),
                                const SizedBox(height: 8),
                                Text(
                                  agent.description,
                                  style: theme.textTheme.bodyLarge?.copyWith(
                                    color: Colors.white70,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 20),
                      Wrap(
                        spacing: 10,
                        runSpacing: 10,
                        children: [
                          _ActionButton(
                            icon: Icons.chat_bubble_outline_rounded,
                            label: 'Message',
                            onTap: () => _openChat(context, agent),
                          ),
                          _ActionButton(
                            icon: Icons.mic_none_rounded,
                            label: 'Talk',
                            onTap: () => _openChat(
                              context,
                              agent,
                              initialIntent: AgentChatLaunchIntent.talk,
                            ),
                          ),
                          _ActionButton(
                            icon: Icons.document_scanner_outlined,
                            label: 'Scan',
                            onTap: () => _openChat(
                              context,
                              agent,
                              initialIntent: AgentChatLaunchIntent.scan,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 18),
              Text('Capabilities', style: theme.textTheme.headlineMedium),
              const SizedBox(height: 12),
              Wrap(
                spacing: 10,
                runSpacing: 10,
                children: [
                  _CapabilityChip(label: agent.agentType),
                  if (agent.category != null)
                    _CapabilityChip(label: agent.category!),
                  _CapabilityChip(label: '${agent.executionCount} runs'),
                  if (agent.successRate != null)
                    _CapabilityChip(
                      label: '${(agent.successRate! * 100).round()}% success',
                    ),
                  for (final tag in agent.tags.take(4))
                    _CapabilityChip(label: tag),
                ],
              ),
              const SizedBox(height: 22),
              Text(
                'Recent mobile sessions',
                style: theme.textTheme.headlineMedium,
              ),
              const SizedBox(height: 12),
              if (state.conversations.isEmpty)
                Card(
                  child: ListTile(
                    title: const Text('No mobile sessions yet'),
                    subtitle: const Text(
                      'Start a fresh conversation from this agent.',
                    ),
                    trailing: const Icon(Icons.arrow_forward_rounded),
                    onTap: () => _openChat(context, agent),
                  ),
                )
              else
                for (final conversation in state.conversations.take(5))
                  Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: Card(
                      child: ListTile(
                        title: Text(conversation.name),
                        subtitle: Text(
                          formatRelativeTimestamp(conversation.updatedAt),
                        ),
                        trailing: const Icon(Icons.arrow_forward_rounded),
                        onTap: () => _openChat(
                          context,
                          agent,
                          initialConversation: conversation,
                        ),
                      ),
                    ),
                  ),
            ],
          );
        },
      ),
    );
  }

  void _openChat(
    BuildContext context,
    AgentSummary agent, {
    ConversationSummary? initialConversation,
    AgentChatLaunchIntent initialIntent = AgentChatLaunchIntent.none,
  }) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => AgentChatScreen(
          agent: agent,
          agentService: widget.agentService,
          initialConversation: initialConversation,
          initialIntent: initialIntent,
        ),
      ),
    );
  }
}

class _AgentDetailState {
  const _AgentDetailState({required this.agent, required this.conversations});

  final AgentSummary agent;
  final List<ConversationSummary> conversations;
}

class _ActionButton extends StatelessWidget {
  const _ActionButton({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final scheme = switch (label) {
      'Talk' => (
          background: [const Color(0xFFEFFCF6), SynkoraColors.primary],
          foreground: SynkoraColors.primaryDeep,
        ),
      'Scan' => (
          background: [const Color(0xFFFFF4E7), SynkoraColors.accentWarm],
          foreground: const Color(0xFF8A4A12),
        ),
      _ => (
          background: [Colors.white, const Color(0xFFF4FBF8)],
          foreground: SynkoraColors.ink,
        ),
    };

    return TweenAnimationBuilder<double>(
      duration: const Duration(milliseconds: 520),
      tween: Tween(begin: 0.96, end: 1),
      curve: Curves.easeOutCubic,
      builder: (context, value, child) {
        return Transform.scale(scale: value, child: child);
      },
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(22),
          child: Ink(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: scheme.background,
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.circular(22),
              border: Border.all(
                color: scheme.foreground.withValues(alpha: 0.16),
              ),
              boxShadow: [
                BoxShadow(
                  color: const Color(0xFF0F172A).withValues(alpha: 0.06),
                  blurRadius: 18,
                  offset: const Offset(0, 12),
                ),
              ],
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 30,
                  height: 30,
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.56),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Icon(icon, size: 18, color: scheme.foreground),
                ),
                const SizedBox(width: 10),
                Text(
                  label,
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: scheme.foreground,
                    fontWeight: FontWeight.w800,
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

class _CapabilityChip extends StatelessWidget {
  const _CapabilityChip({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: SynkoraColors.surface,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(label),
    );
  }
}
