import 'package:flutter/material.dart';

import '../client/models.dart';
import '../client/synkora_client.dart';
import '../controller/synkora_chat_controller.dart';
import 'message_bubble.dart';
import 'suggestion_chips.dart';

const _brandBg = Color(0xFFF7F2E7);
const _brandPanel = Color(0xFFFFFAF1);
const _brandSurface = Color(0xFFF2EBDE);
const _brandBorder = Color(0x1A171717);
const _brandInk = Color(0xFF171717);
const _brandMuted = Color(0xFF6D675F);

enum _ChatSurfaceView { home, chat }

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
      _activeView = _controller.hasConversationContent
          ? _ChatSurfaceView.chat
          : _ChatSurfaceView.home;
      if (mounted) {
        setState(() {});
      }
    }

    if (_controller.messages.isNotEmpty) {
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
    if (_activeView != _ChatSurfaceView.chat) {
      setState(() => _activeView = _ChatSurfaceView.chat);
    }
    _inputController.clear();
    _controller.send(text);
  }

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

  Future<void> _showHistorySheet() async {
    if (_controller.messages.isEmpty) return;

    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => FractionallySizedBox(
        heightFactor: 0.84,
        child: _HistorySheet(
          messages: _controller.messages,
          primaryColor: _primaryColor,
          onOpenChat: () {
            Navigator.of(context).pop();
            _openChat();
          },
          onOpenHome: () {
            Navigator.of(context).pop();
            _openHome();
          },
          onNewChat: _controller.hasConversationContent
              ? () async {
                  Navigator.of(context).pop();
                  await _clearSession();
                }
              : null,
        ),
      ),
    );
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
            leading: widget.onClose != null
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
                    if (hasConversationContent)
                      Padding(
                        padding: const EdgeInsets.only(right: 4),
                        child: IconButton(
                          tooltip: 'History',
                          onPressed: _showHistorySheet,
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
          body: hasInitError
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

                    // Input bar
                    if (_activeView == _ChatSurfaceView.chat)
                      _InputBar(
                        controller: _inputController,
                        focusNode: _focusNode,
                        placeholder:
                            config?.theme.placeholder ?? 'Type a message...',
                        primaryColor: _primaryColor,
                        isStreaming: _controller.isStreaming,
                        onSend: _send,
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
      return _LoadingSkeleton(primaryColor: _primaryColor);
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
      case _ChatSurfaceView.chat:
        if (_controller.messages.isEmpty) {
          return _ChatEmptyState(onOpenHome: _openHome);
        }

        return ListView.builder(
          controller: _scrollController,
          padding: const EdgeInsets.only(top: 8, bottom: 8),
          itemCount: _controller.messages.length,
          itemBuilder: (context, i) {
            final msg = _controller.messages[i];
            if (msg.content.isEmpty && !msg.isStreaming) {
              return const SizedBox.shrink();
            }
            return MessageBubble(
              message: msg,
              primaryColor: _primaryColor,
              agentAvatarUrl: config?.agentAvatarUrl,
            );
          },
        );
    }
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
                Container(
                  width: 64,
                  height: 64,
                  decoration: BoxDecoration(
                    color: primaryColor.withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(22),
                  ),
                  clipBehavior: Clip.antiAlias,
                  child: (config?.agentAvatarUrl?.isNotEmpty ?? false)
                      ? Image.network(
                          config!.agentAvatarUrl!,
                          fit: BoxFit.cover,
                        )
                      : Center(
                          child: Text(
                            (config?.agentName.isNotEmpty ?? false)
                                ? config!.agentName[0].toUpperCase()
                                : 'A',
                            style: const TextStyle(
                              color: _brandInk,
                              fontSize: 28,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
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
                      foregroundColor: _brandInk,
                      minimumSize: const Size.fromHeight(48),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(18),
                      ),
                    ),
                    icon: const Icon(Icons.chat_bubble_outline_rounded),
                    label: const Text('Continue conversation'),
                  ),
                  if (onClear != null) ...[
                    const SizedBox(height: 10),
                    OutlinedButton.icon(
                      onPressed: onClear,
                      style: OutlinedButton.styleFrom(
                        foregroundColor: _brandInk,
                        side: const BorderSide(color: _brandBorder),
                        minimumSize: const Size.fromHeight(44),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(18),
                        ),
                      ),
                      icon: const Icon(Icons.delete_outline_rounded),
                      label: const Text('Start fresh local chat'),
                    ),
                  ],
                ] else
                  FilledButton.icon(
                    onPressed: onContinue,
                    style: FilledButton.styleFrom(
                      backgroundColor: primaryColor,
                      foregroundColor: _brandInk,
                      minimumSize: const Size.fromHeight(48),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(18),
                      ),
                    ),
                    icon: const Icon(Icons.arrow_forward_rounded),
                    label: const Text('Open chat'),
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

  const _ChatEmptyState({required this.onOpenHome});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text(
              'No messages yet',
              style: TextStyle(
                color: _brandInk,
                fontSize: 18,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              'Open the home screen to start with a suggested prompt or begin a fresh conversation.',
              textAlign: TextAlign.center,
              style: TextStyle(color: _brandMuted, fontSize: 14, height: 1.5),
            ),
            const SizedBox(height: 16),
            FilledButton(
              onPressed: onOpenHome,
              style: FilledButton.styleFrom(
                backgroundColor: const Color(0xFF79DFBC),
                foregroundColor: _brandInk,
              ),
              child: const Text('Open home'),
            ),
          ],
        ),
      ),
    );
  }
}

class _HistorySheet extends StatelessWidget {
  final List<ChatMessage> messages;
  final Color primaryColor;
  final VoidCallback onOpenChat;
  final VoidCallback onOpenHome;
  final VoidCallback? onNewChat;

  const _HistorySheet({
    required this.messages,
    required this.primaryColor,
    required this.onOpenChat,
    required this.onOpenHome,
    required this.onNewChat,
  });

  String _formatTime(DateTime timestamp) {
    final hour = timestamp.hour % 12 == 0 ? 12 : timestamp.hour % 12;
    final minute = timestamp.minute.toString().padLeft(2, '0');
    final meridiem = timestamp.hour >= 12 ? 'PM' : 'AM';
    return '$hour:$minute $meridiem';
  }

  @override
  Widget build(BuildContext context) {
    if (messages.isEmpty) {
      return const SizedBox.shrink();
    }

    return Container(
      decoration: const BoxDecoration(
        color: _brandPanel,
        borderRadius: BorderRadius.vertical(top: Radius.circular(32)),
      ),
      child: Column(
        children: [
          const SizedBox(height: 10),
          Container(
            width: 42,
            height: 5,
            decoration: BoxDecoration(
              color: const Color(0x22171717),
              borderRadius: BorderRadius.circular(999),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(18, 18, 18, 14),
            child: Row(
              children: [
                Container(
                  width: 44,
                  height: 44,
                  decoration: BoxDecoration(
                    color: primaryColor.withValues(alpha: 0.16),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: const Icon(Icons.history_rounded, color: _brandInk),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Conversation history',
                        style: TextStyle(
                          color: _brandInk,
                          fontSize: 18,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        '${messages.length} messages in the current session',
                        style: const TextStyle(
                          color: _brandMuted,
                          fontSize: 13,
                          height: 1.4,
                        ),
                      ),
                    ],
                  ),
                ),
                IconButton(
                  onPressed: () => Navigator.of(context).pop(),
                  icon: const Icon(Icons.close_rounded, color: _brandInk),
                ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(18, 0, 18, 14),
            child: Row(
              children: [
                Expanded(
                  child: FilledButton.icon(
                    onPressed: onOpenChat,
                    style: FilledButton.styleFrom(
                      backgroundColor: primaryColor,
                      foregroundColor: _brandInk,
                      minimumSize: const Size.fromHeight(46),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(18),
                      ),
                    ),
                    icon: const Icon(Icons.chat_bubble_outline_rounded),
                    label: const Text('Back to chat'),
                  ),
                ),
                const SizedBox(width: 10),
                OutlinedButton(
                  onPressed: onOpenHome,
                  style: OutlinedButton.styleFrom(
                    foregroundColor: _brandInk,
                    side: const BorderSide(color: _brandBorder),
                    minimumSize: const Size(0, 46),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(18),
                    ),
                  ),
                  child: const Text('Home'),
                ),
              ],
            ),
          ),
          Expanded(
            child: ListView(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 20),
              children: [
                ...messages
                    .where((message) => message.content.trim().isNotEmpty)
                    .map(
                      (message) => Padding(
                        padding: const EdgeInsets.only(bottom: 10),
                        child: Container(
                          padding: const EdgeInsets.all(16),
                          decoration: BoxDecoration(
                            color: message.role == MessageRole.user
                                ? _brandSurface
                                : Colors.white,
                            borderRadius: BorderRadius.circular(20),
                            border: Border.all(color: _brandBorder),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  Container(
                                    padding: const EdgeInsets.symmetric(
                                      horizontal: 10,
                                      vertical: 6,
                                    ),
                                    decoration: BoxDecoration(
                                      color: message.role == MessageRole.user
                                          ? primaryColor.withValues(alpha: 0.24)
                                          : const Color(0x17171717),
                                      borderRadius: BorderRadius.circular(999),
                                    ),
                                    child: Text(
                                      message.role == MessageRole.user
                                          ? 'You'
                                          : 'Assistant',
                                      style: const TextStyle(
                                        color: _brandInk,
                                        fontSize: 12,
                                        fontWeight: FontWeight.w700,
                                      ),
                                    ),
                                  ),
                                  const Spacer(),
                                  Text(
                                    _formatTime(message.timestamp.toLocal()),
                                    style: const TextStyle(
                                      color: _brandMuted,
                                      fontSize: 12,
                                      fontWeight: FontWeight.w500,
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 12),
                              Text(
                                message.content,
                                style: const TextStyle(
                                  color: _brandInk,
                                  fontSize: 14,
                                  height: 1.5,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                if (onNewChat != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 6),
                    child: OutlinedButton.icon(
                      onPressed: onNewChat,
                      style: OutlinedButton.styleFrom(
                        foregroundColor: _brandInk,
                        side: const BorderSide(color: _brandBorder),
                        minimumSize: const Size.fromHeight(48),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(18),
                        ),
                      ),
                      icon: const Icon(Icons.delete_outline_rounded),
                      label: const Text('Clear current conversation'),
                    ),
                  ),
              ],
            ),
          ),
        ],
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
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: _brandPanel,
          border: const Border(top: BorderSide(color: _brandBorder)),
        ),
        child: Row(
          children: [
            Expanded(
              child: TextField(
                controller: controller,
                focusNode: focusNode,
                minLines: 1,
                maxLines: 4,
                textInputAction: TextInputAction.send,
                onSubmitted: (_) => onSend(),
                decoration: InputDecoration(
                  hintText: placeholder,
                  hintStyle: const TextStyle(color: _brandMuted),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(24),
                    borderSide: BorderSide.none,
                  ),
                  enabledBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(24),
                    borderSide: const BorderSide(color: _brandBorder),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(24),
                    borderSide: BorderSide(
                      color: primaryColor.withValues(alpha: 0.55),
                      width: 1.2,
                    ),
                  ),
                  filled: true,
                  fillColor: _brandPanel,
                  contentPadding: const EdgeInsets.symmetric(
                    horizontal: 16,
                    vertical: 10,
                  ),
                ),
              ),
            ),
            const SizedBox(width: 8),
            AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              child: IconButton(
                onPressed: isStreaming ? null : onSend,
                icon: isStreaming
                    ? SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: primaryColor,
                        ),
                      )
                    : const Icon(Icons.send_rounded, color: Color(0xFF171717)),
                style: IconButton.styleFrom(
                  backgroundColor: isStreaming
                      ? Colors.transparent
                      : primaryColor,
                  shape: const CircleBorder(),
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
