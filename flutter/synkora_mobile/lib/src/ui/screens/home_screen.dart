import 'package:flutter/material.dart';

import '../../models/synkora_models.dart';
import '../../services/agent_service.dart';
import '../../state/session_controller.dart';
import '../../theme/app_theme.dart';
import '../widgets/mesh_background.dart';
import 'agent_detail_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({
    super.key,
    required this.sessionController,
    required this.agentService,
  });

  final SessionController sessionController;
  final SynkoraAgentService agentService;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  var _selectedIndex = 0;

  @override
  Widget build(BuildContext context) {
    final tenantKey = ValueKey(widget.sessionController.activeTenant?.tenantId);
    final pages = <Widget>[
      AgentsHomeTab(
        key: tenantKey,
        sessionController: widget.sessionController,
        agentService: widget.agentService,
      ),
      const _PlaceholderTab(
        title: 'Inbox',
        subtitle: 'Push replies, approvals, and completions will land here.',
        icon: Icons.notifications_active_outlined,
      ),
      const _PlaceholderTab(
        title: 'Activity',
        subtitle: 'Operational activity and agent work logs will appear here.',
        icon: Icons.bolt_outlined,
      ),
      ProfileTab(sessionController: widget.sessionController),
    ];

    return Scaffold(
      body: AnimatedSwitcher(
        duration: const Duration(milliseconds: 250),
        child: pages[_selectedIndex],
      ),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _selectedIndex,
        onTap: (index) => setState(() => _selectedIndex = index),
        items: const [
          BottomNavigationBarItem(
            icon: Icon(Icons.grid_view_rounded),
            label: 'Agents',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.notifications_outlined),
            label: 'Inbox',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.auto_graph_rounded),
            label: 'Activity',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.person_outline_rounded),
            label: 'Profile',
          ),
        ],
      ),
    );
  }
}

class AgentsHomeTab extends StatefulWidget {
  const AgentsHomeTab({
    super.key,
    required this.sessionController,
    required this.agentService,
  });

  final SessionController sessionController;
  final SynkoraAgentService agentService;

  @override
  State<AgentsHomeTab> createState() => _AgentsHomeTabState();
}

class _AgentsHomeTabState extends State<AgentsHomeTab> {
  final _searchController = TextEditingController();

  List<AgentSummary> _agents = const [];
  bool _isLoading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadAgents();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _loadAgents({String? search}) async {
    setState(() {
      _isLoading = true;
      _error = null;
    });
    try {
      final agents = await widget.agentService.loadAgents(search: search);
      setState(() => _agents = agents);
    } catch (error) {
      setState(() {
        _error = error.toString();
      });
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final recommended = [..._agents]
      ..sort((left, right) {
        final successCompare = (right.successRate ?? 0).compareTo(
          left.successRate ?? 0,
        );
        if (successCompare != 0) return successCompare;
        return right.executionCount.compareTo(left.executionCount);
      });
    final spotlight = recommended.take(3).toList();

    return CustomScrollView(
      slivers: [
        SliverToBoxAdapter(
          child: Stack(
            children: [
              const SizedBox(height: 250, child: MeshBackground()),
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 72, 20, 0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Welcome back, ${widget.sessionController.account?.name.split(' ').first ?? 'there'}',
                      style: theme.textTheme.displayMedium,
                    ),
                    const SizedBox(height: 10),
                    Text(
                      'Workspace: ${widget.sessionController.activeTenant?.tenantName ?? 'Unknown'}',
                      style: theme.textTheme.bodyLarge,
                    ),
                    const SizedBox(height: 20),
                    TextField(
                      controller: _searchController,
                      onSubmitted: (value) => _loadAgents(search: value.trim()),
                      decoration: InputDecoration(
                        hintText: 'Search your agents',
                        prefixIcon: const Icon(Icons.search_rounded),
                        suffixIcon: IconButton(
                          icon: const Icon(Icons.tune_rounded),
                          onPressed: () {
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(
                                content: Text(
                                  'Filters land in the next mobile slice.',
                                ),
                              ),
                            );
                          },
                        ),
                      ),
                    ),
                    const SizedBox(height: 24),
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(20),
                        child: Row(
                          children: [
                            Container(
                              width: 54,
                              height: 54,
                              decoration: BoxDecoration(
                                color: SynkoraColors.ink,
                                borderRadius: BorderRadius.circular(18),
                              ),
                              child: const Icon(
                                Icons.rocket_launch_rounded,
                                color: SynkoraColors.primary,
                              ),
                            ),
                            const SizedBox(width: 14),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    'All tenant agents, one app',
                                    style: theme.textTheme.titleLarge,
                                  ),
                                  const SizedBox(height: 6),
                                  Text(
                                    'Jump into any agent with full account auth and Flutter-native performance.',
                                    style: theme.textTheme.bodyMedium,
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
        if (_isLoading)
          const SliverFillRemaining(
            hasScrollBody: false,
            child: Center(child: CircularProgressIndicator()),
          )
        else if (_error != null)
          SliverFillRemaining(
            hasScrollBody: false,
            child: Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(_error!, textAlign: TextAlign.center),
                    const SizedBox(height: 12),
                    FilledButton(
                      onPressed: _loadAgents,
                      child: const Text('Retry'),
                    ),
                  ],
                ),
              ),
            ),
          )
        else ...[
          if (spotlight.isNotEmpty)
            SliverToBoxAdapter(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(20, 24, 20, 0),
                child: Text('Spotlight', style: theme.textTheme.headlineMedium),
              ),
            ),
          if (spotlight.isNotEmpty)
            SliverToBoxAdapter(
              child: SizedBox(
                height: 220,
                child: ListView.separated(
                  padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
                  scrollDirection: Axis.horizontal,
                  itemCount: spotlight.length,
                  separatorBuilder: (_, _) => const SizedBox(width: 12),
                  itemBuilder: (context, index) => _SpotlightCard(
                    agent: spotlight[index],
                    onTap: () => Navigator.of(context).push(
                      MaterialPageRoute<void>(
                        builder: (_) => AgentDetailScreen(
                          agent: spotlight[index],
                          agentService: widget.agentService,
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            ),
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(20, 28, 20, 12),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      'All agents',
                      style: theme.textTheme.headlineMedium,
                    ),
                  ),
                  Text('${_agents.length}', style: theme.textTheme.titleLarge),
                ],
              ),
            ),
          ),
          SliverList.builder(
            itemCount: _agents.length,
            itemBuilder: (context, index) {
              final agent = _agents[index];
              return Padding(
                padding: const EdgeInsets.fromLTRB(20, 0, 20, 14),
                child: Card(
                  child: InkWell(
                    borderRadius: BorderRadius.circular(28),
                    onTap: () => Navigator.of(context).push(
                      MaterialPageRoute<void>(
                        builder: (_) => AgentDetailScreen(
                          agent: agent,
                          agentService: widget.agentService,
                        ),
                      ),
                    ),
                    child: Padding(
                      padding: const EdgeInsets.all(20),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          _AgentAvatar(agent: agent),
                          const SizedBox(width: 16),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  agent.name,
                                  style: theme.textTheme.titleLarge,
                                ),
                                const SizedBox(height: 6),
                                Text(
                                  agent.description,
                                  maxLines: 2,
                                  overflow: TextOverflow.ellipsis,
                                  style: theme.textTheme.bodyMedium,
                                ),
                                const SizedBox(height: 12),
                                Wrap(
                                  spacing: 8,
                                  runSpacing: 8,
                                  children: [
                                    _TagChip(label: agent.agentType),
                                    if (agent.category != null)
                                      _TagChip(label: agent.category!),
                                    _TagChip(
                                      label: '${agent.executionCount} runs',
                                    ),
                                    if (agent.successRate != null)
                                      _TagChip(
                                        label:
                                            '${(agent.successRate! * 100).round()}% success',
                                      ),
                                  ],
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(width: 12),
                          const Icon(Icons.arrow_forward_rounded),
                        ],
                      ),
                    ),
                  ),
                ),
              );
            },
          ),
          const SliverToBoxAdapter(child: SizedBox(height: 24)),
        ],
      ],
    );
  }
}

class ProfileTab extends StatelessWidget {
  const ProfileTab({super.key, required this.sessionController});

  final SessionController sessionController;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Stack(
      children: [
        const Positioned.fill(child: MeshBackground()),
        SafeArea(
          child: ListView(
            padding: const EdgeInsets.all(20),
            children: [
              Text('Profile', style: theme.textTheme.displayMedium),
              const SizedBox(height: 22),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        sessionController.account?.name ?? 'Synkora User',
                        style: theme.textTheme.headlineMedium,
                      ),
                      const SizedBox(height: 6),
                      Text(
                        sessionController.account?.email ?? '',
                        style: theme.textTheme.bodyLarge,
                      ),
                      const SizedBox(height: 18),
                      _ProfileRow(
                        label: 'Workspace',
                        value:
                            sessionController.activeTenant?.tenantName ??
                            'Unknown',
                      ),
                      _ProfileRow(
                        label: 'Role',
                        value:
                            sessionController.activeTenant?.role
                                .toUpperCase() ??
                            'UNKNOWN',
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),
              Card(
                child: Column(
                  children: [
                    ListTile(
                      leading: const Icon(Icons.swap_horiz_rounded),
                      title: const Text('Switch workspace'),
                      subtitle: const Text(
                        'Use a different tenant on this device',
                      ),
                      onTap: sessionController.tenants.length <= 1
                          ? null
                          : () => _showTenantSwitcher(context),
                    ),
                    const Divider(height: 1),
                    ListTile(
                      leading: const Icon(Icons.logout_rounded),
                      title: const Text('Sign out'),
                      subtitle: const Text(
                        'Clear the device session and return to login',
                      ),
                      onTap: () => sessionController.signOut(),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Future<void> _showTenantSwitcher(BuildContext context) async {
    await showModalBottomSheet<void>(
      context: context,
      backgroundColor: SynkoraColors.panel,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
      ),
      builder: (context) {
        return SafeArea(
          child: ListView(
            padding: const EdgeInsets.all(20),
            children: [
              Text(
                'Switch workspace',
                style: Theme.of(context).textTheme.headlineMedium,
              ),
              const SizedBox(height: 12),
              for (final tenant in sessionController.tenants)
                Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Card(
                    child: ListTile(
                      title: Text(tenant.tenantName),
                      subtitle: Text(tenant.role.toUpperCase()),
                      trailing:
                          sessionController.activeTenant?.tenantId ==
                              tenant.tenantId
                          ? const Icon(Icons.check_circle_rounded)
                          : const Icon(Icons.arrow_forward_rounded),
                      onTap: () async {
                        await sessionController.selectTenant(tenant.tenantId);
                        if (context.mounted) {
                          Navigator.of(context).pop();
                        }
                      },
                    ),
                  ),
                ),
            ],
          ),
        );
      },
    );
  }
}

class _PlaceholderTab extends StatelessWidget {
  const _PlaceholderTab({
    required this.title,
    required this.subtitle,
    required this.icon,
  });

  final String title;
  final String subtitle;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Stack(
      children: [
        const Positioned.fill(child: MeshBackground()),
        SafeArea(
          child: Center(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 520),
                child: Card(
                  child: Padding(
                    padding: const EdgeInsets.all(28),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(icon, size: 42, color: SynkoraColors.primaryDeep),
                        const SizedBox(height: 18),
                        Text(title, style: theme.textTheme.headlineMedium),
                        const SizedBox(height: 10),
                        Text(
                          subtitle,
                          textAlign: TextAlign.center,
                          style: theme.textTheme.bodyLarge,
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
    );
  }
}

class _ProfileRow extends StatelessWidget {
  const _ProfileRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        children: [
          Expanded(child: Text(label)),
          Text(value),
        ],
      ),
    );
  }
}

class _SpotlightCard extends StatelessWidget {
  const _SpotlightCard({required this.agent, required this.onTap});

  final AgentSummary agent;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return SizedBox(
      width: 280,
      child: Card(
        color: SynkoraColors.ink,
        child: InkWell(
          borderRadius: BorderRadius.circular(28),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.all(22),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _AgentAvatar(agent: agent, dark: true),
                const Spacer(),
                Text(
                  agent.name,
                  style: theme.textTheme.titleLarge?.copyWith(
                    color: Colors.white,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  agent.description,
                  maxLines: 3,
                  overflow: TextOverflow.ellipsis,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: Colors.white70,
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

class _AgentAvatar extends StatelessWidget {
  const _AgentAvatar({required this.agent, this.dark = false});

  final AgentSummary agent;
  final bool dark;

  @override
  Widget build(BuildContext context) {
    final background = dark ? SynkoraColors.primary : SynkoraColors.ink;
    final foreground = dark ? SynkoraColors.ink : SynkoraColors.primary;
    final avatarUrl = agent.avatarUrl;

    return Container(
      width: 56,
      height: 56,
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(18),
      ),
      clipBehavior: Clip.antiAlias,
      child: avatarUrl != null && avatarUrl.isNotEmpty
          ? Image.network(
              avatarUrl,
              fit: BoxFit.cover,
              errorBuilder: (_, _, _) =>
                  Icon(Icons.smart_toy_outlined, color: foreground),
            )
          : Icon(Icons.smart_toy_outlined, color: foreground),
    );
  }
}

class _TagChip extends StatelessWidget {
  const _TagChip({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: SynkoraColors.surface,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        label,
        style: Theme.of(context).textTheme.bodySmall?.copyWith(
          color: SynkoraColors.primaryDeep,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}
