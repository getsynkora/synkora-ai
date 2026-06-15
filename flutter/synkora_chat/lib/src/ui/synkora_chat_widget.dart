import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:lottie/lottie.dart';

import '../assets/illustrations/robot_chat.dart';
import '../assets/illustrations/robot_wave.dart';
import '../client/models.dart';
import '../client/synkora_client.dart';
import '../controller/synkora_chat_controller.dart';
import 'message_bubble.dart';
import 'suggestion_chips.dart';

const _brandBg = Color(0xFFF8FAFC);
const _brandPanel = Color(0xFFFFFFFF);
const _brandSurface = Color(0xFFF1F5F9);
const _brandBorder = Color(0x14000000);
const _brandInk = Color(0xFF0F172A);
const _brandMuted = Color(0xFF64748B);

enum _ChatSurfaceView { home, chat, sessions, preChatForm }

enum _HeaderMenuAction { home, newChat }

/// Drop-in chat widget. Place anywhere in your widget tree.
///
/// ```dart
/// SynkoraChatWidget(
///   widgetKey: 'wk_xxx',
///   baseUrl: 'https://your-synkora.com',
/// )
/// ```
class SynkoraChatWidget extends StatefulWidget {
  /// Widget API key (from the Synkora dashboard).
  final String widgetKey;

  /// Base URL of your Synkora instance. No trailing slash.
  final String baseUrl;

  /// Optional user ID for conversation continuity across sessions.
  final String? userId;

  /// Optional session ID (alternative to userId for anonymous tracking).
  final String? sessionId;

  /// Optional user context for identity-verified widgets.
  final WidgetUser? user;

  /// HMAC-SHA256(identity_secret, user.id) for identity verification.
  final String? userHash;

  /// Provide your own controller (advanced use — BYO controller for headless usage).
  final SynkoraChatController? controller;

  /// Override the primary color from server theme_config.
  final Color? primaryColor;

  /// Show a close/back button in the AppBar and call this when tapped.
  final VoidCallback? onClose;

  /// Replace the suggestion chips with a custom empty state widget.
  final Widget? emptyStateWidget;

  /// Called when the user taps a link inside an agent message.
  /// [href] is the raw URL or deep-link string from the markdown.
  /// Use this to handle in-app navigation, open a browser, etc.
  final void Function(String href)? onLinkTap;

  const SynkoraChatWidget({
    super.key,
    required this.widgetKey,
    required this.baseUrl,
    this.userId,
    this.sessionId,
    this.user,
    this.userHash,
    this.controller,
    this.primaryColor,
    this.onClose,
    this.emptyStateWidget,
    this.onLinkTap,
  });

  @override
  State<SynkoraChatWidget> createState() => _SynkoraChatWidgetState();
}

class _SynkoraChatWidgetState extends State<SynkoraChatWidget> {
  late SynkoraChatController _controller;
  bool _ownsController = false;
  bool _resolvedInitialView = false;
  _ChatSurfaceView _activeView = _ChatSurfaceView.home;
  final _inputController = TextEditingController();
  final _scrollController = ScrollController();
  final _focusNode = FocusNode();

  // Tracks the last-seen handoff/approval state so we can scroll when they arrive
  bool _lastHandoffActive = false;
  bool _lastHadPendingApproval = false;

  @override
  void initState() {
    super.initState();
    if (widget.controller != null) {
      _controller = widget.controller!;
    } else {
      _ownsController = true;
      _controller = SynkoraChatController(
        client: SynkoraClient(
          widgetKey: widget.widgetKey,
          baseUrl: widget.baseUrl,
        ),
        userId: widget.user?.id ?? widget.userId,
        sessionId: widget.sessionId,
        user: widget.user,
        userHash: widget.userHash,
      );
    }
    _controller.init();
    _controller.addListener(_onControllerUpdate);
  }

  void _onControllerUpdate() {
    if (!_resolvedInitialView && !_controller.isLoading) {
      _resolvedInitialView = true;
      final uid = widget.user?.id ?? widget.userId;
      if (uid != null) {
        // Identified user: always show sessions list first so the user can
        // pick a session or start a new one. Do NOT skip to chat even if
        // cached messages exist — the user wants to choose deliberately.
        _activeView = _ChatSurfaceView.sessions;
      } else {
        _activeView = _controller.hasConversationContent
            ? _ChatSurfaceView.chat
            : _ChatSurfaceView.home;
      }
      if (mounted) {
        setState(() {});
      }
    }

    final handoffChanged = _controller.isHandoffActive != _lastHandoffActive;
    final approvalChanged =
        (_controller.pendingApproval != null) != _lastHadPendingApproval;
    _lastHandoffActive = _controller.isHandoffActive;
    _lastHadPendingApproval = _controller.pendingApproval != null;

    if (_controller.messages.isNotEmpty || handoffChanged || approvalChanged) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (_scrollController.hasClients) {
          _scrollController.animateTo(
            _scrollController.position.maxScrollExtent,
            duration: const Duration(milliseconds: 200),
            curve: Curves.easeOut,
          );
        }
      });
    }
  }

  @override
  void dispose() {
    _controller.removeListener(_onControllerUpdate);
    if (_ownsController) _controller.dispose();
    _inputController.dispose();
    _scrollController.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  void _send() {
    final text = _inputController.text.trim();
    if (text.isEmpty || _controller.isStreaming) return;
    // Show pre-chat form before the first message if required
    if (_controller.shouldShowPreChatForm) {
      _pendingSendText = text;
      _inputController.clear();
      setState(() => _activeView = _ChatSurfaceView.preChatForm);
      return;
    }
    if (_activeView != _ChatSurfaceView.chat) {
      setState(() => _activeView = _ChatSurfaceView.chat);
    }
    _inputController.clear();
    _controller.send(text);
  }

  // Pending text held while the pre-chat form is shown
  String? _pendingSendText;

  void _openChat() {
    if (_activeView != _ChatSurfaceView.chat) {
      setState(() => _activeView = _ChatSurfaceView.chat);
    }
  }

  void _openHome() {
    if (_activeView != _ChatSurfaceView.home) {
      setState(() => _activeView = _ChatSurfaceView.home);
    }
  }

  void _openSessions() {
    _controller.loadSessions();
    setState(() => _activeView = _ChatSurfaceView.sessions);
  }

  Future<void> _openSession(WidgetSession session) async {
    setState(() => _activeView = _ChatSurfaceView.chat);
    await _controller.resumeSession(session.id);
  }

  Future<void> _newSession() async {
    await _controller.startNewSession();
    setState(() => _activeView = _ChatSurfaceView.chat);
  }

  Future<void> _closeSession(WidgetSession session) async {
    await _controller.closeSession(session.id);
    // Refresh list after close
    await _controller.loadSessions();
  }

  Future<void> _sendPrompt(String prompt) async {
    if (_activeView != _ChatSurfaceView.chat) {
      setState(() => _activeView = _ChatSurfaceView.chat);
    }
    await _controller.send(prompt);
  }

  Future<void> _clearSession() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: _brandPanel,
        title: const Text('Clear current chat'),
        content: const Text(
          'This starts a fresh local chat in the app. It does not delete server-side history unless your backend exposes that separately.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            style: FilledButton.styleFrom(
              backgroundColor: const Color(0xFF79DFBC),
              foregroundColor: _brandInk,
            ),
            child: const Text('Clear'),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      await _controller.clearSession();
      if (mounted) {
        setState(() => _activeView = _ChatSurfaceView.home);
      }
    }
  }

  Color get _primaryColor =>
      widget.primaryColor ??
      _controller.config?.theme.primaryColor ??
      const Color(0xFF79DFBC);

  /// Converts `newsletter_gatherer_agent` → `Newsletter Gatherer Agent`
  String _formatAgentName(String raw) {
    return raw
        .replaceAll('_', ' ')
        .split(' ')
        .map((w) => w.isEmpty ? w : '${w[0].toUpperCase()}${w.substring(1)}')
        .join(' ');
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: _controller,
      builder: (context, _) {
        final config = _controller.config;
        final hasInitError =
            !_controller.isLoading &&
            config == null &&
            _controller.error != null;
        final hasConversationContent = _controller.hasConversationContent;

        return Scaffold(
          backgroundColor: _brandBg,
          appBar: AppBar(
            backgroundColor: _brandInk,
            foregroundColor: const Color(0xFFF7F2E7),
            elevation: 0,
            toolbarHeight: 72,
            leading: _activeView == _ChatSurfaceView.chat &&
                    _controller.sessions.isNotEmpty
                ? IconButton(
                    icon: const Icon(Icons.arrow_back),
                    onPressed: _openSessions,
                  )
                : widget.onClose != null
                ? IconButton(
                    icon: const Icon(Icons.close),
                    onPressed: widget.onClose,
                  )
                : null,
            automaticallyImplyLeading: false,
            title: Row(
              children: [
                if (config?.agentAvatarUrl != null &&
                    config!.agentAvatarUrl!.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: CircleAvatar(
                      radius: 16,
                      backgroundImage: NetworkImage(config.agentAvatarUrl!),
                    ),
                  ),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(
                        _formatAgentName(config?.agentName ?? ''),
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                          color: Color(0xFFF7F2E7),
                        ),
                      ),
                      Text(
                        _activeView == _ChatSurfaceView.home
                            ? 'Welcome'
                            : _activeView == _ChatSurfaceView.sessions
                            ? 'Your conversations'
                            : _activeView == _ChatSurfaceView.preChatForm
                            ? 'Before we start'
                            : _controller.isHandoffActive
                            ? 'Connected to support'
                            : _controller.pendingApproval != null
                            ? 'Waiting for approval'
                            : hasConversationContent
                            ? 'Conversation in progress'
                            : 'Ready to chat',
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          fontSize: 12,
                          color: Color(0xCCF7F2E7),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            actions: hasInitError || _controller.isLoading
                ? null
                : [
                    if (widget.user?.id != null || widget.userId != null)
                      Padding(
                        padding: const EdgeInsets.only(right: 4),
                        child: IconButton(
                          tooltip: 'Sessions',
                          onPressed: _openSessions,
                          icon: Container(
                            width: 36,
                            height: 36,
                            decoration: BoxDecoration(
                              color: const Color(0x17FFFFFF),
                              borderRadius: BorderRadius.circular(14),
                              border: Border.all(
                                color: const Color(0x26FFFFFF),
                              ),
                            ),
                            child: const Icon(
                              Icons.history_rounded,
                              size: 18,
                              color: Color(0xFFF7F2E7),
                            ),
                          ),
                        ),
                      ),
                    Padding(
                      padding: const EdgeInsets.only(right: 12),
                      child: PopupMenuButton<_HeaderMenuAction>(
                        tooltip: 'More',
                        color: _brandPanel,
                        surfaceTintColor: Colors.transparent,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(18),
                          side: const BorderSide(color: _brandBorder),
                        ),
                        onSelected: (action) {
                          switch (action) {
                            case _HeaderMenuAction.home:
                              _openHome();
                            case _HeaderMenuAction.newChat:
                              _clearSession();
                          }
                        },
                        itemBuilder: (context) => [
                          if (hasConversationContent)
                            const PopupMenuItem<_HeaderMenuAction>(
                              value: _HeaderMenuAction.home,
                              child: _MenuRow(
                                icon: Icons.home_rounded,
                                label: 'Home',
                              ),
                            ),
                          if (hasConversationContent)
                            const PopupMenuItem<_HeaderMenuAction>(
                              value: _HeaderMenuAction.newChat,
                              child: _MenuRow(
                                icon: Icons.add_comment_outlined,
                                label: 'New chat',
                              ),
                            ),
                        ],
                        child: Container(
                          width: 38,
                          height: 38,
                          decoration: BoxDecoration(
                            color: const Color(0x17FFFFFF),
                            borderRadius: BorderRadius.circular(14),
                            border: Border.all(color: const Color(0x26FFFFFF)),
                          ),
                          child: const Icon(
                            Icons.more_horiz_rounded,
                            color: Color(0xFFF7F2E7),
                          ),
                        ),
                      ),
                    ),
                  ],
          ),
          body: Stack(
            children: [
              // Artistic mesh gradient background
              Positioned.fill(
                child: _MeshGradientBackground(primaryColor: _primaryColor),
              ),
              hasInitError
                  ? _ConnectionErrorState(
                      message: _controller.error!,
                      baseUrl: widget.baseUrl,
                      onRetry: _controller.retry,
                    )
                  : Column(
                      children: [
                        // Error banner
                        if (_controller.error != null)
                          Material(
                            color: const Color(0xFFFFF2EC),
                            child: Padding(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 16,
                                vertical: 8,
                              ),
                              child: Row(
                                children: [
                                  const Icon(
                                    Icons.error_outline,
                                    color: Color(0xFFC45F34),
                                    size: 16,
                                  ),
                                  const SizedBox(width: 8),
                                  Expanded(
                                    child: Text(
                                      _controller.error!,
                                      style: const TextStyle(
                                        color: Color(0xFF8B3F1E),
                                        fontSize: 13,
                                      ),
                                    ),
                                  ),
                                  TextButton(
                                    onPressed: _controller.retry,
                                    style: TextButton.styleFrom(
                                      foregroundColor: _brandInk,
                                      textStyle: const TextStyle(
                                        fontWeight: FontWeight.w600,
                                      ),
                                    ),
                                    child: const Text('Retry'),
                                  ),
                                ],
                              ),
                            ),
                          ),

                        // Message list or loading skeleton
                        Expanded(
                          child: _buildContentView(
                            config: config,
                            hasConversationContent: hasConversationContent,
                          ),
                        ),

                        // Input bar — hidden for sessions view, closed sessions,
                        // active handoffs, and pending approvals
                        if (_activeView == _ChatSurfaceView.chat &&
                            !_controller.isCurrentSessionClosed &&
                            !_controller.isHandoffActive &&
                            _controller.pendingApproval == null)
                          _InputBar(
                            controller: _inputController,
                            focusNode: _focusNode,
                            placeholder:
                                config?.theme.placeholder ?? 'Type a message...',
                            primaryColor: _primaryColor,
                            isStreaming: _controller.isStreaming,
                            onSend: _send,
                          ),
                        // Handoff active footer
                        if (_activeView == _ChatSurfaceView.chat &&
                            _controller.isHandoffActive)
                          _HandoffActiveFooter(primaryColor: _primaryColor),
                      ],
                    ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildContentView({
    required WidgetConfig? config,
    required bool hasConversationContent,
  }) {
    if (_controller.isLoading) {
      return _AiLoadingIndicator(primaryColor: _primaryColor);
    }

    switch (_activeView) {
      case _ChatSurfaceView.home:
        return _HomeScreen(
          config: config,
          primaryColor: _primaryColor,
          hasConversationContent: hasConversationContent,
          customBody: widget.emptyStateWidget,
          onContinue: _openChat,
          onClear: hasConversationContent ? _clearSession : null,
          onSuggestion: (prompt) {
            _sendPrompt(prompt);
          },
        );

      case _ChatSurfaceView.sessions:
        return _SessionsScreen(
          sessions: _controller.sessions,
          isLoading: _controller.sessionsLoading,
          primaryColor: _primaryColor,
          onSessionTap: _openSession,
          onNewSession: _newSession,
          onSessionClose: _closeSession,
        );

      case _ChatSurfaceView.preChatForm:
        return _PreChatFormScreen(
          config: _controller.config!.preChatForm,
          primaryColor: _primaryColor,
          onSubmit: ({String? name, String? email, String? phone}) {
            _controller.submitPreChatForm(name: name, email: email, phone: phone);
            final pending = _pendingSendText;
            _pendingSendText = null;
            setState(() => _activeView = _ChatSurfaceView.chat);
            if (pending != null) _controller.send(pending);
          },
          onSkip: () {
            _controller.submitPreChatForm();
            final pending = _pendingSendText;
            _pendingSendText = null;
            setState(() => _activeView = _ChatSurfaceView.chat);
            if (pending != null) _controller.send(pending);
          },
        );

      case _ChatSurfaceView.chat:
        if (_controller.isCurrentSessionClosed) {
          // Read-only banner + messages
          return Column(
            children: [
              _SessionEndedBanner(primaryColor: _primaryColor),
              Expanded(
                child: ListView.builder(
                  controller: _scrollController,
                  padding: const EdgeInsets.only(top: 8, bottom: 8),
                  itemCount: _controller.messages.length,
                  itemBuilder: (context, i) {
                    final msgs = _controller.messages;
                    final msg = msgs[i];
                    if (msg.content.isEmpty && !msg.isStreaming) {
                      return const SizedBox.shrink();
                    }
                    final next = i + 1 < msgs.length ? msgs[i + 1] : null;
                    final isLastInGroup = next == null || next.role != msg.role;
                    return MessageBubble(
                      message: msg,
                      primaryColor: _primaryColor,
                      agentAvatarUrl: config?.agentAvatarUrl,
                      showAvatar: msg.role == MessageRole.assistant && isLastInGroup,
                      onLinkTap: widget.onLinkTap,
                    );
                  },
                ),
              ),
            ],
          );
        }

        if (_controller.messages.isEmpty) {
          return _ChatEmptyState(onOpenHome: _openHome, primaryColor: _primaryColor);
        }

        final hasPendingApproval = _controller.pendingApproval != null;
        final extraItems = hasPendingApproval ? 1 : 0;

        return ListView.builder(
          controller: _scrollController,
          padding: const EdgeInsets.only(top: 8, bottom: 8),
          itemCount: _controller.messages.length + extraItems,
          itemBuilder: (context, i) {
            final msgs = _controller.messages;
            // Render the approval card as the last item
            if (hasPendingApproval && i == msgs.length) {
              final approval = _controller.pendingApproval!;
              return _ApprovalCard(
                event: approval,
                primaryColor: _primaryColor,
                onApprove: () => _controller.respondApproval(approval.approvalId, 'approved'),
                onReject: () => _controller.respondApproval(approval.approvalId, 'rejected'),
              );
            }
            final msg = msgs[i];
            if (msg.content.isEmpty && !msg.isStreaming) {
              return const SizedBox.shrink();
            }
            final next = i + 1 < msgs.length ? msgs[i + 1] : null;
            final isLastInGroup = next == null || next.role != msg.role;
            return MessageBubble(
              message: msg,
              primaryColor: _primaryColor,
              agentAvatarUrl: config?.agentAvatarUrl,
              showAvatar: msg.role == MessageRole.assistant && isLastInGroup,
              onLinkTap: widget.onLinkTap,
            );
          },
        );
    }
  }
}

// ---------------------------------------------------------------------------
// Approval card (inline in chat when approval_required SSE event arrives)
// ---------------------------------------------------------------------------

class _ApprovalCard extends StatelessWidget {
  final ApprovalRequiredEvent event;
  final Color primaryColor;
  final VoidCallback onApprove;
  final VoidCallback onReject;

  const _ApprovalCard({
    required this.event,
    required this.primaryColor,
    required this.onApprove,
    required this.onReject,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Container(
        decoration: BoxDecoration(
          color: const Color(0xFFFFFBEB),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: const Color(0xFFFDE68A)),
        ),
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(
                  Icons.approval_outlined,
                  size: 18,
                  color: Color(0xFFB45309),
                ),
                const SizedBox(width: 8),
                const Text(
                  'Approval required',
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w700,
                    color: Color(0xFF78350F),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              event.message.isNotEmpty
                  ? event.message
                  : 'The agent wants to run "${event.toolName}" and needs your approval.',
              style: const TextStyle(
                fontSize: 13,
                color: Color(0xFF78350F),
                height: 1.4,
              ),
            ),
            if (event.toolArgs.isNotEmpty) ...[
              const SizedBox(height: 6),
              Text(
                'Tool: ${event.toolName}',
                style: const TextStyle(
                  fontSize: 12,
                  color: Color(0xFFB45309),
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
            if (event.expiresAt != null) ...[
              const SizedBox(height: 4),
              Text(
                'Expires: ${event.expiresAt}',
                style: const TextStyle(
                  fontSize: 11,
                  color: Color(0xFFB45309),
                ),
              ),
            ],
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: onReject,
                    style: OutlinedButton.styleFrom(
                      foregroundColor: const Color(0xFF78350F),
                      side: const BorderSide(color: Color(0xFFFDE68A)),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(10),
                      ),
                    ),
                    child: const Text('Reject'),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: FilledButton(
                    onPressed: onApprove,
                    style: FilledButton.styleFrom(
                      backgroundColor: const Color(0xFFB45309),
                      foregroundColor: Colors.white,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(10),
                      ),
                    ),
                    child: const Text('Approve'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Handoff active footer (replaces input bar during a live handoff)
// ---------------------------------------------------------------------------

class _HandoffActiveFooter extends StatelessWidget {
  final Color primaryColor;

  const _HandoffActiveFooter({required this.primaryColor});

  @override
  Widget build(BuildContext context) {
    return Container(
      color: const Color(0xFFFFFBEB),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Row(
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: const BoxDecoration(
              color: Color(0xFF22C55E),
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 10),
          const Expanded(
            child: Text(
              'Connected to support — the agent is paused',
              style: TextStyle(
                fontSize: 13,
                color: Color(0xFF78350F),
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _MenuRow extends StatelessWidget {
  final IconData icon;
  final String label;

  const _MenuRow({required this.icon, required this.label});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, size: 18, color: _brandInk),
        const SizedBox(width: 10),
        Text(
          label,
          style: const TextStyle(
            color: _brandInk,
            fontSize: 14,
            fontWeight: FontWeight.w600,
          ),
        ),
      ],
    );
  }
}

// ---------------------------------------------------------------------------
// Sessions list screen
// ---------------------------------------------------------------------------

class _SessionsScreen extends StatelessWidget {
  final List<WidgetSession> sessions;
  final bool isLoading;
  final Color primaryColor;
  final Future<void> Function(WidgetSession) onSessionTap;
  final VoidCallback onNewSession;
  final Future<void> Function(WidgetSession) onSessionClose;

  const _SessionsScreen({
    required this.sessions,
    required this.isLoading,
    required this.primaryColor,
    required this.onSessionTap,
    required this.onNewSession,
    required this.onSessionClose,
  });

  String _relativeTime(DateTime dt) {
    final diff = DateTime.now().difference(dt);
    if (diff.inMinutes < 1) return 'Just now';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    if (diff.inDays == 1) return 'Yesterday';
    if (diff.inDays < 7) return '${diff.inDays}d ago';
    return '${dt.day}/${dt.month}/${dt.year}';
  }

  /// Returns the bucket label for a given date.
  String _bucket(DateTime dt) {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final d = DateTime(dt.year, dt.month, dt.day);
    final diff = today.difference(d).inDays;
    if (diff == 0) return 'Today';
    if (diff == 1) return 'Yesterday';
    if (diff < 7) return 'This week';
    if (diff < 30) return 'This month';
    return 'Older';
  }

  /// Build the flat list of items: header strings and WidgetSession objects interleaved.
  List<Object> _buildItems() {
    final items = <Object>[];
    String? lastBucket;
    for (final s in sessions) {
      final b = _bucket(s.lastActivityAt);
      if (b != lastBucket) {
        items.add(b); // header
        lastBucket = b;
      }
      items.add(s);
    }
    return items;
  }

  @override
  Widget build(BuildContext context) {
    final items = _buildItems();
    return Stack(
      children: [
        if (isLoading)
          const Center(child: CircularProgressIndicator())
        else if (sessions.isEmpty)
          Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(Icons.chat_bubble_outline, size: 48, color: _brandMuted),
                const SizedBox(height: 16),
                const Text(
                  'No previous sessions',
                  style: TextStyle(
                    color: _brandMuted,
                    fontSize: 14,
                    fontWeight: FontWeight.w500,
                  ),
                ),
                const SizedBox(height: 8),
                const Text(
                  'Start a new chat to begin',
                  style: TextStyle(color: _brandMuted, fontSize: 12),
                ),
              ],
            ),
          )
        else
          ListView.builder(
            padding: const EdgeInsets.only(top: 4, bottom: 80),
            itemCount: items.length,
            itemBuilder: (context, i) {
              final item = items[i];

              // Section header
              if (item is String) {
                return Padding(
                  padding: const EdgeInsets.fromLTRB(16, 16, 16, 6),
                  child: Text(
                    item,
                    style: TextStyle(
                      color: primaryColor,
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 0.6,
                    ),
                  ),
                );
              }

              // Session row
              final session = item as WidgetSession;
              final isActive = session.isActive;
              final isLast = i == items.length - 1 || items[i + 1] is String;
              return Column(
                children: [
                  ListTile(
                    onTap: () => onSessionTap(session),
                    contentPadding:
                        const EdgeInsets.symmetric(horizontal: 16, vertical: 2),
                    leading: Container(
                      width: 9,
                      height: 9,
                      margin: const EdgeInsets.only(top: 4),
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: isActive
                            ? const Color(0xFF4CAF50)
                            : const Color(0xFFBDBDBD),
                      ),
                    ),
                    title: Text(
                      session.firstMessage ?? 'Session',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: _brandInk,
                        fontSize: 13,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                    subtitle: Text(
                      _relativeTime(session.lastActivityAt),
                      style: const TextStyle(color: _brandMuted, fontSize: 11),
                    ),
                    trailing: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        PopupMenuButton<String>(
                          icon: const Icon(Icons.more_horiz, color: _brandMuted, size: 18),
                          splashRadius: 18,
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                          color: _brandPanel,
                          itemBuilder: (_) => [
                            if (isActive)
                              const PopupMenuItem(
                                value: 'close',
                                child: Row(
                                  children: [
                                    Icon(Icons.stop_circle_outlined, size: 16, color: Color(0xFFE53935)),
                                    SizedBox(width: 8),
                                    Text('End session', style: TextStyle(fontSize: 13, color: Color(0xFFE53935))),
                                  ],
                                ),
                              ),
                          ],
                          onSelected: (value) {
                            if (value == 'close') onSessionClose(session);
                          },
                        ),
                        const Icon(Icons.chevron_right, color: _brandMuted, size: 18),
                      ],
                    ),
                  ),
                  if (!isLast)
                    const Divider(height: 1, indent: 16, endIndent: 16),
                ],
              );
            },
          ),

        // New session FAB
        Positioned(
          bottom: 16,
          right: 16,
          child: FloatingActionButton.extended(
            onPressed: onNewSession,
            backgroundColor: primaryColor,
            foregroundColor: _brandInk,
            icon: const Icon(Icons.add, size: 20),
            label: const Text(
              'New chat',
              style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
            ),
          ),
        ),
      ],
    );
  }
}

// ---------------------------------------------------------------------------
// Pre-chat form screen
// ---------------------------------------------------------------------------

class _PreChatFormScreen extends StatefulWidget {
  final PreChatFormConfig config;
  final Color primaryColor;
  final void Function({String? name, String? email, String? phone}) onSubmit;
  final VoidCallback onSkip;

  const _PreChatFormScreen({
    required this.config,
    required this.primaryColor,
    required this.onSubmit,
    required this.onSkip,
  });

  @override
  State<_PreChatFormScreen> createState() => _PreChatFormScreenState();
}

class _PreChatFormScreenState extends State<_PreChatFormScreen> {
  final _nameCtrl = TextEditingController();
  final _emailCtrl = TextEditingController();
  final _phoneCtrl = TextEditingController();

  @override
  void dispose() {
    _nameCtrl.dispose();
    _emailCtrl.dispose();
    _phoneCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final cfg = widget.config;
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(20, 24, 20, 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Before we start',
            style: TextStyle(
              fontSize: 17,
              fontWeight: FontWeight.w700,
              color: _brandInk,
            ),
          ),
          const SizedBox(height: 6),
          const Text(
            'Share a bit about yourself so we can help you better. All fields are optional.',
            style: TextStyle(fontSize: 13, color: _brandMuted),
          ),
          const SizedBox(height: 24),
          if (cfg.showName) ...[
            _FormField(label: 'Name', controller: _nameCtrl, hint: 'Your name', primaryColor: widget.primaryColor),
            const SizedBox(height: 14),
          ],
          if (cfg.showEmail) ...[
            _FormField(
              label: 'Email',
              controller: _emailCtrl,
              hint: 'you@example.com',
              keyboardType: TextInputType.emailAddress,
              primaryColor: widget.primaryColor,
            ),
            const SizedBox(height: 14),
          ],
          if (cfg.showPhone) ...[
            _FormField(
              label: 'Phone',
              controller: _phoneCtrl,
              hint: '+1 555 000 0000',
              keyboardType: TextInputType.phone,
              primaryColor: widget.primaryColor,
            ),
            const SizedBox(height: 14),
          ],
          const SizedBox(height: 8),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: () => widget.onSubmit(
                name: _nameCtrl.text,
                email: _emailCtrl.text,
                phone: _phoneCtrl.text,
              ),
              style: ElevatedButton.styleFrom(
                backgroundColor: widget.primaryColor,
                foregroundColor: _brandInk,
                padding: const EdgeInsets.symmetric(vertical: 14),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                elevation: 0,
              ),
              child: const Text('Start chatting', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
            ),
          ),
          if (cfg.skippable) ...[
            const SizedBox(height: 10),
            Center(
              child: TextButton(
                onPressed: widget.onSkip,
                child: Text(
                  'Skip',
                  style: TextStyle(color: _brandMuted, fontSize: 13),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _FormField extends StatelessWidget {
  final String label;
  final TextEditingController controller;
  final String hint;
  final TextInputType? keyboardType;
  final Color primaryColor;

  const _FormField({
    required this.label,
    required this.controller,
    required this.hint,
    this.keyboardType,
    required this.primaryColor,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: _brandInk)),
        const SizedBox(height: 6),
        TextField(
          controller: controller,
          keyboardType: keyboardType,
          style: const TextStyle(fontSize: 14, color: _brandInk),
          decoration: InputDecoration(
            hintText: hint,
            hintStyle: TextStyle(color: _brandMuted, fontSize: 14),
            filled: true,
            fillColor: _brandSurface,
            contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(10),
              borderSide: const BorderSide(color: _brandBorder),
            ),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(10),
              borderSide: const BorderSide(color: _brandBorder),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(10),
              borderSide: BorderSide(color: primaryColor, width: 1.5),
            ),
          ),
        ),
      ],
    );
  }
}

class _HomeScreen extends StatelessWidget {
  final WidgetConfig? config;
  final Color primaryColor;
  final bool hasConversationContent;
  final Widget? customBody;
  final VoidCallback onContinue;
  final VoidCallback? onClear;
  final void Function(String prompt) onSuggestion;

  const _HomeScreen({
    required this.config,
    required this.primaryColor,
    required this.hasConversationContent,
    required this.customBody,
    required this.onContinue,
    required this.onClear,
    required this.onSuggestion,
  });

  @override
  Widget build(BuildContext context) {
    final btnFg = ThemeData.estimateBrightnessForColor(primaryColor) == Brightness.dark
        ? Colors.white
        : _brandInk;

    final greeting = (config?.theme.welcomeMessage.isNotEmpty ?? false)
        ? config!.theme.welcomeMessage
        : 'Hi there\nHow can we help?';
    final parts = greeting.split('\n');
    final title = parts.first.trim().isEmpty ? 'Hi there' : parts.first.trim();
    final subtitle = parts.length > 1
        ? parts.skip(1).join('\n').trim()
        : (config?.agentDescription.isNotEmpty ?? false)
        ? config!.agentDescription
        : 'Start with a suggestion or open the chat to continue the conversation.';

    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(16, 18, 16, 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: _brandPanel,
              borderRadius: BorderRadius.circular(28),
              boxShadow: const [
                BoxShadow(
                  color: Color(0x12000000),
                  blurRadius: 24,
                  offset: Offset(0, 12),
                ),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (config?.agentAvatarUrl?.isNotEmpty ?? false)
                  CircleAvatar(
                    radius: 36,
                    backgroundImage: NetworkImage(config!.agentAvatarUrl!),
                  )
                else
                  SizedBox(
                    width: 120,
                    height: 120,
                    child: Lottie.asset(
                      'packages/synkora_chat/lib/src/assets/animations/choose_your_colors.json',
                      repeat: true,
                      animate: true,
                    ),
                  ),
                const SizedBox(height: 16),
                Text(
                  title,
                  style: const TextStyle(
                    color: _brandInk,
                    fontSize: 24,
                    fontWeight: FontWeight.w700,
                    height: 1.2,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  subtitle,
                  style: const TextStyle(
                    color: _brandMuted,
                    fontSize: 14,
                    height: 1.5,
                  ),
                ),
                const SizedBox(height: 18),
                if (hasConversationContent) ...[
                  FilledButton.icon(
                    onPressed: onContinue,
                    style: FilledButton.styleFrom(
                      backgroundColor: primaryColor,
                      foregroundColor: btnFg,
                      minimumSize: const Size.fromHeight(48),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(14),
                      ),
                    ),
                    icon: const Icon(Icons.chat_bubble_outline_rounded),
                    label: const Text(
                      'Continue conversation',
                      style: TextStyle(fontWeight: FontWeight.w600),
                    ),
                  ),
                  if (onClear != null) ...[
                    const SizedBox(height: 8),
                    OutlinedButton.icon(
                      onPressed: onClear,
                      style: OutlinedButton.styleFrom(
                        foregroundColor: _brandMuted,
                        side: const BorderSide(color: _brandBorder),
                        minimumSize: const Size.fromHeight(42),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(14),
                        ),
                      ),
                      icon: const Icon(Icons.add_comment_outlined, size: 18),
                      label: const Text('Start new chat'),
                    ),
                  ],
                ] else
                  FilledButton.icon(
                    onPressed: onContinue,
                    style: FilledButton.styleFrom(
                      backgroundColor: primaryColor,
                      foregroundColor: btnFg,
                      minimumSize: const Size.fromHeight(48),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(14),
                      ),
                    ),
                    icon: const Icon(Icons.arrow_forward_rounded),
                    label: const Text(
                      'Start chatting',
                      style: TextStyle(fontWeight: FontWeight.w600),
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          if (customBody != null)
            customBody!
          else if ((config?.suggestionPrompts.isNotEmpty ?? false))
            SuggestionChips(
              prompts: config!.suggestionPrompts,
              primaryColor: primaryColor,
              onTap: onSuggestion,
            ),
        ],
      ),
    );
  }
}

class _ChatEmptyState extends StatelessWidget {
  final VoidCallback onOpenHome;
  final Color primaryColor;

  const _ChatEmptyState({
    required this.onOpenHome,
    required this.primaryColor,
  });

  @override
  Widget build(BuildContext context) {
    final hex = '#${primaryColor.toARGB32().toRadixString(16).substring(2)}';
    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            SvgPicture.string(
              robotChatSvg(hex),
              width: 180,
            ),
            const SizedBox(height: 20),
            const Text(
              'Ask me anything',
              style: TextStyle(
                color: _brandInk,
                fontSize: 20,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              'Type a message below or go back to browse suggested prompts.',
              textAlign: TextAlign.center,
              style: TextStyle(color: _brandMuted, fontSize: 14, height: 1.5),
            ),
            const SizedBox(height: 20),
            OutlinedButton(
              onPressed: onOpenHome,
              style: OutlinedButton.styleFrom(
                foregroundColor: primaryColor,
                side: BorderSide(color: primaryColor.withValues(alpha: 0.4)),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
              child: const Text('Browse suggestions'),
            ),
          ],
        ),
      ),
    );
  }
}

class _ConnectionErrorState extends StatelessWidget {
  final String message;
  final String baseUrl;
  final VoidCallback onRetry;

  const _ConnectionErrorState({
    required this.message,
    required this.baseUrl,
    required this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 420),
          child: Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: _brandPanel,
              border: Border.all(color: const Color(0x26C45F34)),
              borderRadius: BorderRadius.circular(24),
              boxShadow: const [
                BoxShadow(
                  color: Color(0x12000000),
                  blurRadius: 28,
                  offset: Offset(0, 16),
                ),
              ],
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  width: 44,
                  height: 44,
                  decoration: BoxDecoration(
                    color: const Color(0xFFFFF2EC),
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: const Icon(
                    Icons.wifi_off_rounded,
                    color: Color(0xFFC45F34),
                  ),
                ),
                const SizedBox(height: 16),
                const Text(
                  'Connection issue',
                  style: TextStyle(
                    color: _brandInk,
                    fontSize: 18,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  message,
                  style: const TextStyle(
                    color: _brandMuted,
                    fontSize: 14,
                    height: 1.5,
                  ),
                ),
                const SizedBox(height: 16),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: _brandSurface,
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: _brandBorder),
                  ),
                  child: Text(
                    'Expected API base URL: $baseUrl',
                    style: const TextStyle(
                      color: _brandInk,
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                FilledButton(
                  onPressed: onRetry,
                  style: FilledButton.styleFrom(
                    backgroundColor: const Color(0xFF79DFBC),
                    foregroundColor: _brandInk,
                    minimumSize: const Size.fromHeight(48),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(18),
                    ),
                  ),
                  child: const Text('Retry connection'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Input bar
// ---------------------------------------------------------------------------

class _InputBar extends StatelessWidget {
  final TextEditingController controller;
  final FocusNode focusNode;
  final String placeholder;
  final Color primaryColor;
  final bool isStreaming;
  final VoidCallback onSend;

  const _InputBar({
    required this.controller,
    required this.focusNode,
    required this.placeholder,
    required this.primaryColor,
    required this.isStreaming,
    required this.onSend,
  });

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Container(
        padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
        decoration: const BoxDecoration(
          color: _brandPanel,
          border: Border(top: BorderSide(color: _brandBorder)),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Expanded(
              child: TextField(
                controller: controller,
                focusNode: focusNode,
                minLines: 1,
                maxLines: 5,
                textInputAction: TextInputAction.send,
                onSubmitted: (_) => onSend(),
                style: const TextStyle(fontSize: 15, color: _brandInk),
                decoration: InputDecoration(
                  hintText: placeholder,
                  hintStyle: const TextStyle(
                    color: _brandMuted,
                    fontSize: 15,
                  ),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(22),
                    borderSide: const BorderSide(color: _brandBorder),
                  ),
                  enabledBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(22),
                    borderSide: const BorderSide(color: _brandBorder),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(22),
                    borderSide: BorderSide(
                      color: primaryColor.withValues(alpha: 0.5),
                      width: 1.5,
                    ),
                  ),
                  filled: true,
                  fillColor: _brandSurface,
                  contentPadding: const EdgeInsets.symmetric(
                    horizontal: 16,
                    vertical: 11,
                  ),
                ),
              ),
            ),
            const SizedBox(width: 8),
            SizedBox(
              width: 40,
              height: 40,
              child: isStreaming
                  ? Center(
                      child: SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: primaryColor,
                        ),
                      ),
                    )
                  : Material(
                      color: primaryColor,
                      shape: const CircleBorder(),
                      child: InkWell(
                        customBorder: const CircleBorder(),
                        onTap: onSend,
                        child: const Icon(
                          Icons.arrow_upward_rounded,
                          color: Colors.white,
                          size: 18,
                        ),
                      ),
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Loading skeleton
// ---------------------------------------------------------------------------

class _LoadingSkeleton extends StatefulWidget {
  final Color primaryColor;
  const _LoadingSkeleton({required this.primaryColor});

  @override
  State<_LoadingSkeleton> createState() => _LoadingSkeletonState();
}

class _LoadingSkeletonState extends State<_LoadingSkeleton>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  late final Animation<double> _anim;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat(reverse: true);
    _anim = Tween<double>(begin: 0.3, end: 0.7).animate(_ctrl);
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _anim,
      builder: (context, _) {
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            _SkeletonBubble(
              width: 200,
              color: _brandSurface.withValues(alpha: _anim.value),
            ),
            const SizedBox(height: 12),
            Align(
              alignment: Alignment.centerRight,
              child: _SkeletonBubble(
                width: 140,
                color: widget.primaryColor.withValues(alpha: _anim.value * 0.3),
              ),
            ),
            const SizedBox(height: 12),
            _SkeletonBubble(
              width: 260,
              color: _brandSurface.withValues(alpha: _anim.value),
            ),
          ],
        );
      },
    );
  }
}

class _SkeletonBubble extends StatelessWidget {
  final double width;
  final Color color;
  const _SkeletonBubble({required this.width, required this.color});

  @override
  Widget build(BuildContext context) => Container(
    width: width,
    height: 40,
    decoration: BoxDecoration(
      color: color,
      borderRadius: BorderRadius.circular(18),
    ),
  );
}

// ---------------------------------------------------------------------------
// Mesh gradient background
// ---------------------------------------------------------------------------

class _MeshGradientBackground extends StatelessWidget {
  final Color primaryColor;
  const _MeshGradientBackground({required this.primaryColor});

  @override
  Widget build(BuildContext context) {
    return CustomPaint(
      painter: _MeshPainter(primaryColor: primaryColor),
      child: const SizedBox.expand(),
    );
  }
}

class _MeshPainter extends CustomPainter {
  final Color primaryColor;
  const _MeshPainter({required this.primaryColor});

  @override
  void paint(Canvas canvas, Size size) {
    // Base fill
    canvas.drawRect(
      Offset.zero & size,
      Paint()..color = const Color(0xFFF8FAFC),
    );

    // Blob 1 — top-left, primaryColor tinted
    _drawBlob(
      canvas,
      center: Offset(size.width * 0.1, size.height * 0.08),
      radius: size.width * 0.55,
      color: primaryColor.withValues(alpha: 0.07),
    );

    // Blob 2 — top-right
    _drawBlob(
      canvas,
      center: Offset(size.width * 0.92, size.height * 0.05),
      radius: size.width * 0.4,
      color: primaryColor.withValues(alpha: 0.05),
    );

    // Blob 3 — bottom-left, cool blue accent
    _drawBlob(
      canvas,
      center: Offset(size.width * 0.05, size.height * 0.85),
      radius: size.width * 0.45,
      color: const Color(0xFF6366F1).withValues(alpha: 0.04),
    );

    // Blob 4 — bottom-right
    _drawBlob(
      canvas,
      center: Offset(size.width * 0.95, size.height * 0.9),
      radius: size.width * 0.5,
      color: primaryColor.withValues(alpha: 0.06),
    );
  }

  void _drawBlob(Canvas canvas, {
    required Offset center,
    required double radius,
    required Color color,
  }) {
    final paint = Paint()
      ..shader = RadialGradient(
        colors: [color, color.withValues(alpha: 0)],
      ).createShader(Rect.fromCircle(center: center, radius: radius));
    canvas.drawCircle(center, radius, paint);
  }

  @override
  bool shouldRepaint(_MeshPainter old) => old.primaryColor != primaryColor;
}

// ---------------------------------------------------------------------------
// AI loading indicator
// ---------------------------------------------------------------------------

class _AiLoadingIndicator extends StatefulWidget {
  final Color primaryColor;
  const _AiLoadingIndicator({required this.primaryColor});

  @override
  State<_AiLoadingIndicator> createState() => _AiLoadingIndicatorState();
}

class _AiLoadingIndicatorState extends State<_AiLoadingIndicator>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1800),
    )..repeat();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Center(
      child: AnimatedBuilder(
        animation: _ctrl,
        builder: (context, _) {
          return SizedBox(
            width: 80,
            height: 80,
            child: Stack(
              alignment: Alignment.center,
              children: List.generate(3, (i) {
                final delay = i * 0.33;
                final t = (_ctrl.value - delay).clamp(0.0, 1.0);
                final scale = 0.3 + 0.7 * t;
                final opacity = (1.0 - t).clamp(0.0, 1.0);
                return Opacity(
                  opacity: opacity,
                  child: Transform.scale(
                    scale: scale,
                    child: Container(
                      width: 80,
                      height: 80,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        border: Border.all(
                          color: widget.primaryColor.withValues(
                            alpha: opacity * 0.6,
                          ),
                          width: 2,
                        ),
                      ),
                    ),
                  ),
                );
              })
                ..add(
                  Container(
                    width: 16,
                    height: 16,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: widget.primaryColor,
                    ),
                    child: const Icon(
                      Icons.auto_awesome,
                      size: 10,
                      color: Colors.white,
                    ),
                  ),
                ),
            ),
          );
        },
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Session ended banner with robot wave illustration
// ---------------------------------------------------------------------------

class _SessionEndedBanner extends StatelessWidget {
  final Color primaryColor;
  const _SessionEndedBanner({required this.primaryColor});

  @override
  Widget build(BuildContext context) {
    final hex = '#${primaryColor.toARGB32().toRadixString(16).substring(2)}';
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: const BoxDecoration(
        color: Color(0xFFF0FDF4),
        border: Border(
          bottom: BorderSide(color: Color(0xFFBBF7D0)),
        ),
      ),
      child: Row(
        children: [
          SvgPicture.string(
            robotWaveSvg(hex),
            width: 48,
            height: 48,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Session ended',
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: Color(0xFF15803D),
                  ),
                ),
                const Text(
                  'This conversation is read-only.',
                  style: TextStyle(fontSize: 12, color: Color(0xFF166534)),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
