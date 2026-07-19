import 'dart:async';

import 'package:flutter/material.dart';
import 'package:lottie/lottie.dart';

import '../client/models.dart';
import '../client/synkora_client.dart';
import '../controller/synkora_chat_controller.dart';
import '../theme/chat_text_styles.dart';
import 'message_bubble.dart';
// suggestion_chips.dart intentionally kept for custom emptyStateWidget use

// Brand palette
const _kTeal = Color(0xFF10717C);
const _kBg = Color(0xFFF5F7F8);
const _kPanel = Color(0xFFFFFFFF);
const _kInk = Color(0xFF1A1A2E);
const _kMuted = Color(0xFF94A3B8);
const _kBorder = Color(0x14000000);

// Main bottom-tab indexes
const _kTabHome = 0;
const _kTabChat = 1;

// Overlay views that sit above the tab UI (no bottom nav shown)
enum _OverlayView { none, chatMessages, preChatForm }

/// Drop-in chat widget. Place anywhere in your widget tree.
///
/// ```dart
/// SynkoraChatWidget(
///   widgetKey: 'wk_xxx',
///   baseUrl: 'https://your-synkora.com',
/// )
/// ```
class SynkoraChatWidget extends StatefulWidget {
  final String widgetKey;
  final String baseUrl;
  final String? userId;
  final String? sessionId;
  final WidgetUser? user;
  final String? userHash;
  final SynkoraChatController? controller;
  final Color? primaryColor;
  final VoidCallback? onClose;
  final Widget? emptyStateWidget;
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
  int _tabIndex = _kTabHome;
  _OverlayView _overlay = _OverlayView.none;
  final _inputController = TextEditingController();
  final _scrollController = ScrollController();
  final _focusNode = FocusNode();
  StreamSubscription<String>? _messageTriggerSub;

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
    _messageTriggerSub = _controller.messageTriggerStream.listen(_sendPrompt);
  }

  void _onControllerUpdate() {
    if (!_resolvedInitialView && !_controller.isLoading) {
      _resolvedInitialView = true;
      if (_controller.hasConversationContent) {
        _tabIndex = _kTabChat;
        _overlay = _OverlayView.chatMessages;
      }
      if (mounted) setState(() {});
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
    _messageTriggerSub?.cancel();
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
    if (_controller.shouldShowPreChatForm) {
      _pendingSendText = text;
      _inputController.clear();
      setState(() => _overlay = _OverlayView.preChatForm);
      return;
    }
    setState(() {
      _tabIndex = _kTabChat;
      _overlay = _OverlayView.chatMessages;
    });
    _inputController.clear();
    _controller.send(text);
  }

  String? _pendingSendText;

  void _closeOverlay() {
    setState(() => _overlay = _OverlayView.none);
  }

  Future<void> _openSession(WidgetSession session) async {
    setState(() => _overlay = _OverlayView.chatMessages);
    await _controller.resumeSession(session.id);
  }

  Future<void> _newSession() async {
    await _controller.startNewSession();
    setState(() {
      _tabIndex = _kTabChat;
      _overlay = _OverlayView.chatMessages;
    });
  }

  Future<void> _closeSession(WidgetSession session) async {
    await _controller.closeSession(session.id);
    await _controller.loadSessions();
  }

  Future<void> _sendPrompt(String prompt) async {
    setState(() {
      _tabIndex = _kTabChat;
      _overlay = _OverlayView.chatMessages;
    });
    await _controller.send(prompt);
  }

  Future<void> _clearSession() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: _kPanel,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Text(
          'Clear current chat',
          style: ChatTextStyles.txtStyleSemiB16.copyWith(color: _kInk),
        ),
        content: Text(
          'This starts a fresh local chat. Server-side history is kept.',
          style: ChatTextStyles.txtStyleRegular14.copyWith(color: _kMuted),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: Text(
              'Cancel',
              style: ChatTextStyles.txtStyleSemiB14.copyWith(color: _kMuted),
            ),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            style: FilledButton.styleFrom(
              backgroundColor: _kTeal,
              foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(10)),
            ),
            child: Text(
              'Clear',
              style: ChatTextStyles.txtStyleSemiB14
                  .copyWith(color: Colors.white),
            ),
          ),
        ],
      ),
    );
    if (confirmed == true) {
      await _controller.clearSession();
      if (mounted) setState(() => _overlay = _OverlayView.none);
    }
  }

  Color get _primary =>
      widget.primaryColor ??
      _controller.config?.theme.primaryColor ??
      _kTeal;

  /// Returns black or white depending on the luminance of [bg].
  Color _onColor(Color bg) =>
      bg.computeLuminance() > 0.4 ? const Color(0xFF1A1A2E) : Colors.white;

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
        final hasInitError = !_controller.isLoading &&
            config == null &&
            _controller.error != null;

        final isOverlay = _overlay != _OverlayView.none;
        final inMessages = _overlay == _OverlayView.chatMessages;
        final showInputBar = inMessages &&
            !_controller.isCurrentSessionClosed &&
            !_controller.isHandoffActive &&
            _controller.pendingApproval == null;
        final showHandoff = inMessages && _controller.isHandoffActive;

        return Scaffold(
          backgroundColor: _kBg,
          appBar: _buildAppBar(config),
          bottomNavigationBar: isOverlay
              ? null
              : _BottomNav(
                  currentIndex: _tabIndex,
                  primaryColor: _primary,
                  onTap: (i) {
                    if (i == _kTabChat) _controller.loadSessions();
                    setState(() => _tabIndex = i);
                  },
                ),
          body: hasInitError
              ? _ConnectionErrorState(
                  message: _controller.error!,
                  baseUrl: widget.baseUrl,
                  onRetry: _controller.retry,
                  primaryColor: _primary,
                )
              : Column(
                  children: [
                    if (_controller.error != null && inMessages)
                      _ErrorBanner(
                        message: _controller.error!,
                        onRetry: _controller.retry,
                      ),

                    Expanded(
                      child: _controller.isLoading
                          ? _LoadingIndicator(primaryColor: _primary)
                          : _buildBody(config),
                    ),

                    if (showInputBar)
                      _InputBar(
                        controller: _inputController,
                        focusNode: _focusNode,
                        placeholder: config?.theme.placeholder ?? 'Type a message...',
                        primaryColor: _primary,
                        isStreaming: _controller.isStreaming,
                        onSend: _send,
                        agentName: _formatAgentName(config?.agentName ?? ''),
                      ),

                    if (showHandoff)
                      const _HandoffFooter(),
                  ],
                ),
        );
      },
    );
  }

  PreferredSizeWidget _buildAppBar(WidgetConfig? config) {
    final agentName = _formatAgentName(config?.agentName ?? '');
    final fg = _onColor(_primary);
    final fgSubtle = fg.withValues(alpha: 0.65);
    final isOverlay = _overlay != _OverlayView.none;

    return AppBar(
      backgroundColor: _primary,
      foregroundColor: fg,
      elevation: 0,
      toolbarHeight: 60,
      automaticallyImplyLeading: false,
      leading: isOverlay
          ? IconButton(
              icon: Icon(Icons.arrow_back, color: fg),
              onPressed: _closeOverlay,
            )
          : null,
      title: Row(
        children: [
          _AppBarAvatar(
            avatarUrl: config?.agentAvatarUrl,
            primaryColor: _primary,
            foregroundColor: fg,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(
                  agentName,
                  overflow: TextOverflow.ellipsis,
                  style: ChatTextStyles.txtStyleSemiB16.copyWith(color: fg),
                ),
                Text(
                  _appBarSubtitle,
                  style: ChatTextStyles.txtStyleRegular12.copyWith(color: fgSubtle),
                ),
              ],
            ),
          ),
        ],
      ),
      actions: [
        // New chat — only shown inside a messages view
        if (_overlay == _OverlayView.chatMessages && _controller.hasConversationContent)
          IconButton(
            icon: Icon(Icons.add_comment_outlined, color: fg),
            tooltip: 'New chat',
            onPressed: _clearSession,
          ),
        if (widget.onClose != null)
          IconButton(
            icon: Icon(Icons.close, color: fg),
            onPressed: widget.onClose,
          ),
      ],
    );
  }

  String get _appBarSubtitle {
    if (_overlay == _OverlayView.preChatForm) return 'Before we start';
    if (_overlay == _OverlayView.chatMessages) {
      if (_controller.isHandoffActive) return 'Connected to support';
      if (_controller.pendingApproval != null) return 'Waiting for approval';
      if (_controller.hasConversationContent) return 'Online';
      return 'Ready to chat';
    }
    if (_tabIndex == _kTabChat) return 'Your conversations';
    return 'Welcome';
  }

  Widget _buildBody(WidgetConfig? config) {
    // Overlay views take priority
    if (_overlay == _OverlayView.chatMessages) {
      return _buildChatView(config);
    }

    if (_overlay == _OverlayView.preChatForm) {
      return _PreChatFormScreen(
        config: _controller.config!.preChatForm,
        primaryColor: _primary,
        onSubmit: ({String? name, String? email, String? phone}) {
          _controller.submitPreChatForm(name: name, email: email, phone: phone);
          final pending = _pendingSendText;
          _pendingSendText = null;
          setState(() {
            _overlay = _OverlayView.none;
            _tabIndex = _kTabChat;
          });
          if (pending != null) _controller.send(pending);
        },
        onSkip: () {
          _controller.submitPreChatForm();
          final pending = _pendingSendText;
          _pendingSendText = null;
          setState(() {
            _overlay = _OverlayView.none;
            _tabIndex = _kTabChat;
          });
          if (pending != null) _controller.send(pending);
        },
      );
    }

    // Main tabs
    if (_tabIndex == _kTabHome) {
      // Find last ongoing (active) session for the home card
      final ongoingSession = _controller.sessions
          .where((s) => s.isActive)
          .isNotEmpty
          ? _controller.sessions.firstWhere((s) => s.isActive)
          : (_controller.sessions.isNotEmpty ? _controller.sessions.first : null);

      return _HomeScreen(
        config: config,
        primaryColor: _primary,
        hasConversationContent: _controller.hasConversationContent,
        customBody: widget.emptyStateWidget,
        recentSession: ongoingSession,
        onStartChat: _newSession,
        onResumeSession: (s) => _openSession(s),
        onSuggestion: _sendPrompt,
      );
    }

    // Chat tab → sessions list
    return _SessionsScreen(
      sessions: _controller.sessions,
      isLoading: _controller.sessionsLoading,
      primaryColor: _primary,
      agentName: _formatAgentName(config?.agentName ?? 'Assistant'),
      agentAvatarUrl: config?.agentAvatarUrl,
      onSessionTap: _openSession,
      onNewSession: _newSession,
      onSessionClose: _closeSession,
    );
  }

  Widget _buildChatView(WidgetConfig? config) {
    if (_controller.isCurrentSessionClosed) {
      return Column(
        children: [
          Expanded(child: _MessageList(
            messages: _controller.messages,
            scrollController: _scrollController,
            primaryColor: _primary,
            agentAvatarUrl: config?.agentAvatarUrl,
            agentName: _formatAgentName(config?.agentName ?? ''),
            onLinkTap: widget.onLinkTap,
          )),
          const _ChatClosedBanner(),
        ],
      );
    }

    if (_controller.messages.isEmpty) {
      return _ChatEmptyState(
        onOpenHome: () => setState(() => _tabIndex = _kTabHome),
        primaryColor: _primary,
      );
    }

    final hasPendingApproval = _controller.pendingApproval != null;
    final extraItems = hasPendingApproval ? 1 : 0;

    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.only(top: 12, bottom: 12),
      itemCount: _controller.messages.length + extraItems,
      itemBuilder: (context, i) {
        final msgs = _controller.messages;
        if (hasPendingApproval && i == msgs.length) {
          final approval = _controller.pendingApproval!;
          return _ApprovalCard(
            event: approval,
            primaryColor: _primary,
            onApprove: () =>
                _controller.respondApproval(approval.approvalId, 'approved'),
            onReject: () =>
                _controller.respondApproval(approval.approvalId, 'rejected'),
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
          primaryColor: _primary,
          agentAvatarUrl: config?.agentAvatarUrl,
          agentName: _formatAgentName(config?.agentName ?? ''),
          showAvatar: msg.role != MessageRole.user && isLastInGroup,
          onLinkTap: widget.onLinkTap,
        );
      },
    );
  }
}

// ---------------------------------------------------------------------------
// App bar avatar
// ---------------------------------------------------------------------------

class _AppBarAvatar extends StatelessWidget {
  final String? avatarUrl;
  final Color primaryColor;
  final Color foregroundColor;

  const _AppBarAvatar({
    this.avatarUrl,
    required this.primaryColor,
    required this.foregroundColor,
  });

  @override
  Widget build(BuildContext context) {
    if (avatarUrl != null && avatarUrl!.isNotEmpty) {
      return CircleAvatar(
        radius: 18,
        backgroundImage: NetworkImage(avatarUrl!),
        backgroundColor: foregroundColor.withValues(alpha: 0.15),
      );
    }
    return CircleAvatar(
      radius: 18,
      backgroundColor: foregroundColor.withValues(alpha: 0.15),
      child: Icon(Icons.auto_awesome, size: 16, color: foregroundColor),
    );
  }
}

// ---------------------------------------------------------------------------
// Home screen
// ---------------------------------------------------------------------------

class _HomeScreen extends StatelessWidget {
  final WidgetConfig? config;
  final Color primaryColor;
  final bool hasConversationContent;
  final Widget? customBody;
  final WidgetSession? recentSession;
  final VoidCallback onStartChat;
  final Future<void> Function(WidgetSession) onResumeSession;
  final void Function(String) onSuggestion;

  const _HomeScreen({
    required this.config,
    required this.primaryColor,
    required this.hasConversationContent,
    required this.customBody,
    required this.recentSession,
    required this.onStartChat,
    required this.onResumeSession,
    required this.onSuggestion,
  });

  String _greeting() {
    final raw = config?.theme.welcomeMessage ?? '';
    if (raw.isNotEmpty) return raw.split('\n').first.trim();
    return 'Hello there';
  }

  String _subGreeting() {
    final raw = config?.theme.welcomeMessage ?? '';
    final parts = raw.split('\n');
    if (parts.length > 1) return parts.skip(1).join('\n').trim();
    return 'How can we help?';
  }

  String _relativeTime(DateTime dt) {
    final diff = DateTime.now().difference(dt);
    if (diff.inMinutes < 1) return 'Now';
    if (diff.inMinutes < 60) return '${diff.inMinutes}min';
    if (diff.inHours < 24) return '${diff.inHours}hr';
    if (diff.inDays == 1) return '1d';
    return '${diff.inDays}d';
  }

  @override
  Widget build(BuildContext context) {
    final prompts = config?.suggestionPrompts ?? [];

    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Gradient hero
          Container(
            padding: const EdgeInsets.fromLTRB(24, 32, 24, 40),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [
                  primaryColor,
                  primaryColor.withValues(alpha: 0.75),
                ],
              ),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _greeting(),
                  style: ChatTextStyles.txtStyleBold34
                      .copyWith(color: Colors.white, height: 1.15),
                ),
                const SizedBox(height: 4),
                Text(
                  _subGreeting(),
                  style: ChatTextStyles.txtStyleBold34
                      .copyWith(color: Colors.white70, height: 1.15),
                ),
              ],
            ),
          ),

          // White content area
          Container(
            color: _kBg,
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
            child: Column(
              children: [
                // Pull cards up to overlap the hero slightly
                const SizedBox(height: 0),

                // Start new conversation card
                _HomeCard(
                  onTap: onStartChat,
                  child: Row(
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Start new conversation',
                              style: ChatTextStyles.txtStyleSemiB16
                                  .copyWith(color: _kInk),
                            ),
                            const SizedBox(height: 2),
                            Text(
                              'Typically reply within few moments',
                              style: ChatTextStyles.txtStyleRegular13
                                  .copyWith(color: _kMuted),
                            ),
                          ],
                        ),
                      ),
                      Icon(Icons.arrow_forward,
                          color: primaryColor, size: 20),
                    ],
                  ),
                ),

                // Recent message card
                if (recentSession != null) ...[
                  const SizedBox(height: 10),
                  _HomeCard(
                    onTap: () => onResumeSession(recentSession!),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Recent message',
                          style: ChatTextStyles.txtStyleSemiB14
                              .copyWith(color: _kInk),
                        ),
                        const SizedBox(height: 8),
                        Row(
                          children: [
                            CircleAvatar(
                              radius: 16,
                              backgroundColor:
                                  primaryColor.withValues(alpha: 0.12),
                              child: Icon(Icons.auto_awesome,
                                  size: 14, color: primaryColor),
                            ),
                            const SizedBox(width: 10),
                            Expanded(
                              child: Text(
                                recentSession!.firstMessage ?? 'Conversation',
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: ChatTextStyles.txtStyleRegular13
                                    .copyWith(color: _kMuted),
                              ),
                            ),
                            const SizedBox(width: 8),
                            Text(
                              _relativeTime(recentSession!.lastActivityAt),
                              style: ChatTextStyles.txtStyleRegular12
                                  .copyWith(color: _kMuted),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ],

                // Custom body OR FAQs / suggestions
                if (customBody != null) ...[
                  const SizedBox(height: 10),
                  customBody!,
                ] else if (prompts.isNotEmpty) ...[
                  const SizedBox(height: 10),
                  _HomeCard(
                    onTap: null,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'FAQs',
                          style: ChatTextStyles.txtStyleSemiB16
                              .copyWith(color: _kInk),
                        ),
                        const SizedBox(height: 12),
                        ...prompts.map((p) => _FaqRow(
                              prompt: p,
                              primaryColor: primaryColor,
                              onTap: () => onSuggestion(p.prompt),
                            )),
                      ],
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _HomeCard extends StatelessWidget {
  final Widget child;
  final VoidCallback? onTap;

  const _HomeCard({required this.child, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.only(top: 10),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: _kPanel,
          borderRadius: BorderRadius.circular(16),
          boxShadow: const [
            BoxShadow(
              color: Color(0x0A000000),
              blurRadius: 10,
              offset: Offset(0, 2),
            ),
          ],
        ),
        child: child,
      ),
    );
  }
}

class _FaqRow extends StatelessWidget {
  final SuggestionPrompt prompt;
  final Color primaryColor;
  final VoidCallback onTap;

  const _FaqRow({
    required this.prompt,
    required this.primaryColor,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(8),
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 12),
            child: Row(
              children: [
                if (prompt.icon.isNotEmpty) ...[
                  Text(prompt.icon,
                      style: ChatTextStyles.txtStyleRegular16),
                  const SizedBox(width: 10),
                ],
                Expanded(
                  child: Text(
                    prompt.title,
                    style: ChatTextStyles.txtStyleRegular14
                        .copyWith(color: _kInk),
                  ),
                ),
                Icon(Icons.chevron_right, color: _kMuted, size: 18),
              ],
            ),
          ),
        ),
        const Divider(height: 1, color: _kBorder),
      ],
    );
  }
}

// ---------------------------------------------------------------------------
// Sessions screen
// ---------------------------------------------------------------------------

class _SessionsScreen extends StatelessWidget {
  final List<WidgetSession> sessions;
  final bool isLoading;
  final Color primaryColor;
  final String agentName;
  final String? agentAvatarUrl;
  final Future<void> Function(WidgetSession) onSessionTap;
  final VoidCallback onNewSession;
  final Future<void> Function(WidgetSession) onSessionClose;

  const _SessionsScreen({
    required this.sessions,
    required this.isLoading,
    required this.primaryColor,
    required this.agentName,
    this.agentAvatarUrl,
    required this.onSessionTap,
    required this.onNewSession,
    required this.onSessionClose,
  });

  String _relativeTime(DateTime dt) {
    final diff = DateTime.now().difference(dt);
    if (diff.inMinutes < 1) return 'Now';
    if (diff.inMinutes < 60) return '${diff.inMinutes}min';
    if (diff.inHours < 24) return '${diff.inHours}hr';
    if (diff.inDays == 1) return '1d';
    if (diff.inDays < 7) return '${diff.inDays}d';
    final w = (diff.inDays / 7).floor();
    return '${w}w';
  }

  @override
  Widget build(BuildContext context) {
    if (isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (sessions.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.chat_bubble_outline, size: 48, color: _kMuted),
            const SizedBox(height: 16),
            Text(
              'No previous sessions',
              style:
                  ChatTextStyles.txtStyleSemiB14.copyWith(color: _kMuted),
            ),
            const SizedBox(height: 8),
            Text(
              'Start a new chat to begin',
              style:
                  ChatTextStyles.txtStyleRegular12.copyWith(color: _kMuted),
            ),
            const SizedBox(height: 24),
            FilledButton.icon(
              onPressed: onNewSession,
              style: FilledButton.styleFrom(
                backgroundColor: primaryColor,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(24)),
              ),
              icon: const Icon(Icons.add, size: 18),
              label: Text('New chat',
                  style: ChatTextStyles.txtStyleSemiB14
                      .copyWith(color: Colors.white)),
            ),
          ],
        ),
      );
    }

    return Stack(
      children: [
        ListView.builder(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 80),
          itemCount: sessions.length,
          itemBuilder: (context, i) {
            final session = sessions[i];
            return _SessionCard(
              session: session,
              primaryColor: primaryColor,
              agentName: agentName,
              agentAvatarUrl: agentAvatarUrl,
              timeLabel: _relativeTime(session.lastActivityAt),
              onTap: () => onSessionTap(session),
              onClose: session.isActive
                  ? () => onSessionClose(session)
                  : null,
            );
          },
        ),
        Positioned(
          bottom: 16,
          right: 16,
          child: FloatingActionButton.extended(
            onPressed: onNewSession,
            backgroundColor: primaryColor,
            foregroundColor: Colors.white,
            icon: const Icon(Icons.add, size: 20),
            label: Text('New chat',
                style: ChatTextStyles.txtStyleSemiB13
                    .copyWith(color: Colors.white)),
          ),
        ),
      ],
    );
  }
}

class _SessionCard extends StatelessWidget {
  final WidgetSession session;
  final Color primaryColor;
  final String agentName;
  final String? agentAvatarUrl;
  final String timeLabel;
  final VoidCallback onTap;
  final VoidCallback? onClose;

  const _SessionCard({
    required this.session,
    required this.primaryColor,
    required this.agentName,
    this.agentAvatarUrl,
    required this.timeLabel,
    required this.onTap,
    this.onClose,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: _kPanel,
          borderRadius: BorderRadius.circular(16),
          boxShadow: const [
            BoxShadow(
              color: Color(0x0A000000),
              blurRadius: 8,
              offset: Offset(0, 2),
            ),
          ],
        ),
        child: Row(
          children: [
            // Agent avatar
            agentAvatarUrl != null && agentAvatarUrl!.isNotEmpty
                ? CircleAvatar(
                    radius: 22,
                    backgroundImage: NetworkImage(agentAvatarUrl!),
                    backgroundColor: primaryColor.withValues(alpha: 0.12),
                  )
                : CircleAvatar(
                    radius: 22,
                    backgroundColor: primaryColor.withValues(alpha: 0.12),
                    child: Icon(Icons.auto_awesome, size: 18, color: primaryColor),
                  ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Agent name
                  Text(
                    agentName,
                    style: ChatTextStyles.txtStyleSemiB14.copyWith(color: _kInk),
                  ),
                  const SizedBox(height: 2),
                  // Last message preview
                  Text(
                    session.firstMessage ?? 'Conversation',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: ChatTextStyles.txtStyleRegular12.copyWith(color: _kMuted),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    session.isActive ? 'Active' : 'Closed',
                    style: ChatTextStyles.txtStyleRegular12.copyWith(
                      color: session.isActive ? const Color(0xFF22C55E) : _kMuted,
                    ),
                  ),
                ],
              ),
            ),
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(
                  timeLabel,
                  style: ChatTextStyles.txtStyleRegular12.copyWith(color: _kMuted),
                ),
                if (onClose != null) ...[
                  const SizedBox(height: 4),
                  GestureDetector(
                    onTap: onClose,
                    child: Text(
                      'End',
                      style: ChatTextStyles.txtStyleSemiB12.copyWith(
                        color: const Color(0xFFE53935),
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ],
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Pre-chat form
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
            style: ChatTextStyles.txtStyleBoldB16.copyWith(color: _kInk),
          ),
          const SizedBox(height: 6),
          Text(
            'Share a bit about yourself so we can help you better. All fields are optional.',
            style:
                ChatTextStyles.txtStyleRegular13.copyWith(color: _kMuted),
          ),
          const SizedBox(height: 24),
          if (cfg.showName) ...[
            _FormField(
                label: 'Name',
                controller: _nameCtrl,
                hint: 'Your name',
                primaryColor: widget.primaryColor),
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
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 14),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12)),
                elevation: 0,
              ),
              child: Text(
                'Start chatting',
                style: ChatTextStyles.txtStyleSemiB14
                    .copyWith(color: Colors.white),
              ),
            ),
          ),
          if (cfg.skippable) ...[
            const SizedBox(height: 10),
            Center(
              child: TextButton(
                onPressed: widget.onSkip,
                child: Text(
                  'Skip',
                  style: ChatTextStyles.txtStyleRegular13
                      .copyWith(color: _kMuted),
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
        Text(label,
            style: ChatTextStyles.txtStyleSemiB12.copyWith(color: _kInk)),
        const SizedBox(height: 6),
        TextField(
          controller: controller,
          keyboardType: keyboardType,
          style: ChatTextStyles.txtStyleRegular14.copyWith(color: _kInk),
          decoration: InputDecoration(
            hintText: hint,
            hintStyle:
                ChatTextStyles.txtStyleRegular14.copyWith(color: _kMuted),
            filled: true,
            fillColor: _kBg,
            contentPadding:
                const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(10),
              borderSide: const BorderSide(color: _kBorder),
            ),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(10),
              borderSide: const BorderSide(color: _kBorder),
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

// ---------------------------------------------------------------------------
// Chat empty state
// ---------------------------------------------------------------------------

class _ChatEmptyState extends StatelessWidget {
  final VoidCallback onOpenHome;
  final Color primaryColor;

  const _ChatEmptyState({required this.onOpenHome, required this.primaryColor});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            SizedBox(
              width: 120,
              height: 120,
              child: Lottie.asset(
                'packages/synkora_chat/lib/src/assets/animations/choose_your_colors.json',
                repeat: true,
              ),
            ),
            const SizedBox(height: 20),
            Text(
              'Ask me anything',
              style: ChatTextStyles.txtStyleBold20.copyWith(color: _kInk),
            ),
            const SizedBox(height: 8),
            Text(
              'Type a message below or go back to browse suggested prompts.',
              textAlign: TextAlign.center,
              style: ChatTextStyles.txtStyleRegular14
                  .copyWith(color: _kMuted, height: 1.5),
            ),
            const SizedBox(height: 20),
            OutlinedButton(
              onPressed: onOpenHome,
              style: OutlinedButton.styleFrom(
                foregroundColor: primaryColor,
                side: BorderSide(color: primaryColor.withValues(alpha: 0.4)),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12)),
              ),
              child: Text('Browse suggestions',
                  style: ChatTextStyles.txtStyleSemiB14),
            ),
          ],
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Chat closed banner
// ---------------------------------------------------------------------------

class _ChatClosedBanner extends StatelessWidget {
  const _ChatClosedBanner();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(vertical: 20),
      decoration: const BoxDecoration(
        color: _kPanel,
        border: Border(top: BorderSide(color: _kBorder)),
      ),
      child: Column(
        children: [
          Text(
            'Chat closed',
            style: ChatTextStyles.txtStyleSemiB16.copyWith(color: _kInk),
          ),
          const SizedBox(height: 4),
          Text(
            'The conversation is read only',
            style: ChatTextStyles.txtStyleRegular13.copyWith(color: _kMuted),
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Message list (reusable for read-only closed sessions)
// ---------------------------------------------------------------------------

class _MessageList extends StatelessWidget {
  final List<ChatMessage> messages;
  final ScrollController scrollController;
  final Color primaryColor;
  final String? agentAvatarUrl;
  final String agentName;
  final void Function(String href)? onLinkTap;

  const _MessageList({
    required this.messages,
    required this.scrollController,
    required this.primaryColor,
    required this.agentAvatarUrl,
    required this.agentName,
    this.onLinkTap,
  });

  @override
  Widget build(BuildContext context) {
    return ListView.builder(
      controller: scrollController,
      padding: const EdgeInsets.only(top: 12, bottom: 12),
      itemCount: messages.length,
      itemBuilder: (context, i) {
        final msg = messages[i];
        if (msg.content.isEmpty && !msg.isStreaming) {
          return const SizedBox.shrink();
        }
        final next = i + 1 < messages.length ? messages[i + 1] : null;
        final isLastInGroup = next == null || next.role != msg.role;
        return MessageBubble(
          message: msg,
          primaryColor: primaryColor,
          agentAvatarUrl: agentAvatarUrl,
          agentName: agentName,
          showAvatar: msg.role != MessageRole.user && isLastInGroup,
          onLinkTap: onLinkTap,
        );
      },
    );
  }
}

// ---------------------------------------------------------------------------
// Approval card
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
                const Icon(Icons.approval_outlined,
                    size: 18, color: Color(0xFFB45309)),
                const SizedBox(width: 8),
                Text(
                  'Approval required',
                  style: ChatTextStyles.txtStyleSemiB14
                      .copyWith(color: const Color(0xFF78350F)),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              event.message.isNotEmpty
                  ? event.message
                  : 'The agent wants to run "${event.toolName}" and needs your approval.',
              style: ChatTextStyles.txtStyleRegular13.copyWith(
                color: const Color(0xFF78350F),
                height: 1.4,
              ),
            ),
            if (event.toolArgs.isNotEmpty) ...[
              const SizedBox(height: 6),
              Text(
                'Tool: ${event.toolName}',
                style: ChatTextStyles.txtStyleSemiB12
                    .copyWith(color: const Color(0xFFB45309)),
              ),
            ],
            if (event.expiresAt != null) ...[
              const SizedBox(height: 4),
              Text(
                'Expires: ${event.expiresAt}',
                style: ChatTextStyles.txtStyleRegular11
                    .copyWith(color: const Color(0xFFB45309)),
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
                          borderRadius: BorderRadius.circular(10)),
                    ),
                    child: Text('Reject',
                        style: ChatTextStyles.txtStyleSemiB14.copyWith(
                            color: const Color(0xFF78350F))),
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
                          borderRadius: BorderRadius.circular(10)),
                    ),
                    child: Text('Approve',
                        style: ChatTextStyles.txtStyleSemiB14
                            .copyWith(color: Colors.white)),
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
// Handoff footer
// ---------------------------------------------------------------------------

class _HandoffFooter extends StatelessWidget {
  const _HandoffFooter();

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
          Expanded(
            child: Text(
              'Connected to support — the agent is paused',
              style: ChatTextStyles.txtStyleSemiB13
                  .copyWith(color: const Color(0xFF78350F)),
            ),
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Error banner
// ---------------------------------------------------------------------------

class _ErrorBanner extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;

  const _ErrorBanner({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Material(
      color: const Color(0xFFFFF2EC),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        child: Row(
          children: [
            const Icon(Icons.error_outline,
                color: Color(0xFFC45F34), size: 16),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                message,
                style: ChatTextStyles.txtStyleRegular13
                    .copyWith(color: const Color(0xFF8B3F1E)),
              ),
            ),
            TextButton(
              onPressed: onRetry,
              style: TextButton.styleFrom(foregroundColor: _kInk),
              child: Text('Retry',
                  style: ChatTextStyles.txtStyleSemiB13),
            ),
          ],
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
  final String agentName;

  const _InputBar({
    required this.controller,
    required this.focusNode,
    required this.placeholder,
    required this.primaryColor,
    required this.isStreaming,
    required this.onSend,
    required this.agentName,
  });

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Container(
        color: _kPanel,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Divider(height: 1, color: _kBorder),
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 10, 12, 6),
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
                      style: ChatTextStyles.txtStyleRegular15
                          .copyWith(color: _kInk),
                      decoration: InputDecoration(
                        hintText: placeholder,
                        hintStyle: ChatTextStyles.txtStyleRegular15
                            .copyWith(color: _kMuted),
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(24),
                          borderSide:
                              const BorderSide(color: _kBorder),
                        ),
                        enabledBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(24),
                          borderSide:
                              const BorderSide(color: _kBorder),
                        ),
                        focusedBorder: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(24),
                          borderSide: BorderSide(
                              color: primaryColor, width: 1.5),
                        ),
                        filled: true,
                        fillColor: _kBg,
                        contentPadding: const EdgeInsets.symmetric(
                            horizontal: 16, vertical: 11),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  SizedBox(
                    width: 44,
                    height: 44,
                    child: isStreaming
                        ? Center(
                            child: SizedBox(
                              width: 22,
                              height: 22,
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
                                size: 20,
                              ),
                            ),
                          ),
                  ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Text(
                'Powered by $agentName',
                style: ChatTextStyles.txtStyleRegular11
                    .copyWith(color: _kMuted),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Connection error
// ---------------------------------------------------------------------------

class _ConnectionErrorState extends StatelessWidget {
  final String message;
  final String baseUrl;
  final VoidCallback onRetry;
  final Color primaryColor;

  const _ConnectionErrorState({
    required this.message,
    required this.baseUrl,
    required this.onRetry,
    required this.primaryColor,
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
              color: _kPanel,
              border: Border.all(color: const Color(0x26C45F34)),
              borderRadius: BorderRadius.circular(20),
              boxShadow: const [
                BoxShadow(
                  color: Color(0x12000000),
                  blurRadius: 24,
                  offset: Offset(0, 12),
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
                  child: const Icon(Icons.wifi_off_rounded,
                      color: Color(0xFFC45F34)),
                ),
                const SizedBox(height: 16),
                Text(
                  'Connection issue',
                  style:
                      ChatTextStyles.txtStyleBoldB16.copyWith(color: _kInk),
                ),
                const SizedBox(height: 8),
                Text(
                  message,
                  style: ChatTextStyles.txtStyleRegular14
                      .copyWith(color: _kMuted, height: 1.5),
                ),
                const SizedBox(height: 16),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: _kBg,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: _kBorder),
                  ),
                  child: Text(
                    'Expected: $baseUrl',
                    style: ChatTextStyles.txtStyleSemiB13
                        .copyWith(color: _kInk),
                  ),
                ),
                const SizedBox(height: 16),
                FilledButton(
                  onPressed: onRetry,
                  style: FilledButton.styleFrom(
                    backgroundColor: primaryColor,
                    foregroundColor: Colors.white,
                    minimumSize: const Size.fromHeight(48),
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(14)),
                  ),
                  child: Text(
                    'Retry connection',
                    style: ChatTextStyles.txtStyleSemiB14
                        .copyWith(color: Colors.white),
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


// ---------------------------------------------------------------------------
// Bottom navigation bar
// ---------------------------------------------------------------------------

class _BottomNav extends StatelessWidget {
  final int currentIndex;
  final Color primaryColor;
  final void Function(int) onTap;

  const _BottomNav({
    required this.currentIndex,
    required this.primaryColor,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        color: _kPanel,
        border: Border(top: BorderSide(color: _kBorder)),
      ),
      child: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 8),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              _NavItem(
                icon: Icons.home_rounded,
                label: 'Home',
                selected: currentIndex == _kTabHome,
                primaryColor: primaryColor,
                onTap: () => onTap(_kTabHome),
              ),
              _NavItem(
                icon: Icons.chat_bubble_rounded,
                label: 'Chat',
                selected: currentIndex == _kTabChat,
                primaryColor: primaryColor,
                onTap: () => onTap(_kTabChat),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _NavItem extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool selected;
  final Color primaryColor;
  final VoidCallback onTap;

  const _NavItem({
    required this.icon,
    required this.label,
    required this.selected,
    required this.primaryColor,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final color = selected ? primaryColor : _kMuted;
    return GestureDetector(
      onTap: onTap,
      behavior: HitTestBehavior.opaque,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 4),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, color: color, size: 24),
            const SizedBox(height: 3),
            Text(
              label,
              style: ChatTextStyles.txtStyleSemiB11.copyWith(color: color),
            ),
          ],
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Loading indicator
// ---------------------------------------------------------------------------

class _LoadingIndicator extends StatefulWidget {
  final Color primaryColor;
  const _LoadingIndicator({required this.primaryColor});

  @override
  State<_LoadingIndicator> createState() => _LoadingIndicatorState();
}

class _LoadingIndicatorState extends State<_LoadingIndicator>
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
              children: [
                ...List.generate(3, (i) {
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
                            color: widget.primaryColor
                                .withValues(alpha: opacity * 0.6),
                            width: 2,
                          ),
                        ),
                      ),
                    ),
                  );
                }),
                Container(
                  width: 16,
                  height: 16,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: widget.primaryColor,
                  ),
                  child: const Icon(Icons.auto_awesome,
                      size: 10, color: Colors.white),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}
