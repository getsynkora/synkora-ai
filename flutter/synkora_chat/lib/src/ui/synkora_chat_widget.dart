import 'package:flutter/material.dart';

import '../client/models.dart';
import '../client/synkora_client.dart';
import '../controller/synkora_chat_controller.dart';
import 'message_bubble.dart';
import 'suggestion_chips.dart';

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
        client: SynkoraClient(widgetKey: widget.widgetKey, baseUrl: widget.baseUrl),
        userId: widget.userId,
        sessionId: widget.sessionId,
      );
    }
    _controller.init();
    _controller.addListener(_onControllerUpdate);
  }

  void _onControllerUpdate() {
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
    _inputController.clear();
    _controller.send(text);
  }

  Color get _primaryColor =>
      widget.primaryColor ?? _controller.config?.theme.primaryColor ?? const Color(0xFF6366F1);

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
        return Scaffold(
          appBar: AppBar(
            backgroundColor: _primaryColor,
            foregroundColor: Colors.white,
            elevation: 0,
            leading: widget.onClose != null
                ? IconButton(icon: const Icon(Icons.close), onPressed: widget.onClose)
                : null,
            automaticallyImplyLeading: false,
            title: Row(
              children: [
                if (config?.agentAvatarUrl != null && config!.agentAvatarUrl!.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: CircleAvatar(
                      radius: 16,
                      backgroundImage: NetworkImage(config.agentAvatarUrl!),
                    ),
                  ),
                Text(
                  _formatAgentName(config?.agentName ?? ''),
                  style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                ),
              ],
            ),
          ),
          body: Column(
            children: [
              // Error banner
              if (_controller.error != null)
                Material(
                  color: Colors.red.shade50,
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                    child: Row(
                      children: [
                        const Icon(Icons.error_outline, color: Colors.red, size: 16),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            _controller.error!,
                            style: const TextStyle(color: Colors.red, fontSize: 13),
                          ),
                        ),
                        TextButton(
                          onPressed: _controller.retry,
                          child: const Text('Retry'),
                        ),
                      ],
                    ),
                  ),
                ),

              // Message list or loading skeleton
              Expanded(
                child: _controller.isLoading
                    ? _LoadingSkeleton(primaryColor: _primaryColor)
                    : _controller.messages.isEmpty
                        ? SingleChildScrollView(
                            child: widget.emptyStateWidget ??
                                SuggestionChips(
                                  prompts: config?.suggestionPrompts ?? [],
                                  primaryColor: _primaryColor,
                                  onTap: _controller.send,
                                ),
                          )
                        : ListView.builder(
                            controller: _scrollController,
                            padding: const EdgeInsets.only(top: 8, bottom: 8),
                            itemCount: _controller.messages.length,
                            itemBuilder: (context, i) {
                              final msg = _controller.messages[i];
                              // Skip empty non-streaming messages (e.g. corrupted cache)
                              if (msg.content.isEmpty && !msg.isStreaming) {
                                return const SizedBox.shrink();
                              }
                              return MessageBubble(
                                message: msg,
                                primaryColor: _primaryColor,
                                agentAvatarUrl: config?.agentAvatarUrl,
                              );
                            },
                          ),
              ),

              // Input bar
              _InputBar(
                controller: _inputController,
                focusNode: _focusNode,
                placeholder: config?.theme.placeholder ?? 'Type a message...',
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
          color: Theme.of(context).colorScheme.surface,
          border: Border(top: BorderSide(color: Theme.of(context).colorScheme.outlineVariant)),
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
                  hintStyle: TextStyle(color: Theme.of(context).colorScheme.onSurface.withOpacity(0.4)),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(24),
                    borderSide: BorderSide.none,
                  ),
                  filled: true,
                  fillColor: Theme.of(context).colorScheme.surfaceContainerHighest,
                  contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
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
                        child: CircularProgressIndicator(strokeWidth: 2, color: primaryColor),
                      )
                    : Icon(Icons.send_rounded, color: primaryColor),
                style: IconButton.styleFrom(
                  backgroundColor: primaryColor.withOpacity(0.1),
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

class _LoadingSkeletonState extends State<_LoadingSkeleton> with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  late final Animation<double> _anim;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(vsync: this, duration: const Duration(milliseconds: 1200))..repeat(reverse: true);
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
        final color = Theme.of(context).colorScheme.onSurface.withOpacity(_anim.value * 0.15);
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            _SkeletonBubble(width: 200, color: color),
            const SizedBox(height: 12),
            Align(
              alignment: Alignment.centerRight,
              child: _SkeletonBubble(width: 140, color: widget.primaryColor.withOpacity(_anim.value * 0.3)),
            ),
            const SizedBox(height: 12),
            _SkeletonBubble(width: 260, color: color),
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
