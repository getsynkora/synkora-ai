import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';

import '../client/models.dart';

class MessageBubble extends StatelessWidget {
  final ChatMessage message;
  final Color primaryColor;
  final String? agentAvatarUrl;

  const MessageBubble({
    super.key,
    required this.message,
    required this.primaryColor,
    this.agentAvatarUrl,
  });

  bool get _isUser => message.role == MessageRole.user;
  static const _warmSurface = Color(0xFFF2EBDE);
  static const _warmPanel = Color(0xFFFFFAF1);
  static const _ink = Color(0xFF171717);

  @override
  Widget build(BuildContext context) {
    final userFg = ThemeData.estimateBrightnessForColor(primaryColor) == Brightness.dark
        ? Colors.white
        : const Color(0xFF11231D);

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        mainAxisAlignment: _isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        children: [
          if (!_isUser) ...[
            _AgentAvatar(avatarUrl: agentAvatarUrl, primaryColor: primaryColor),
            const SizedBox(width: 8),
          ],
          Flexible(
            child: Container(
              constraints: BoxConstraints(
                maxWidth: MediaQuery.of(context).size.width * 0.72,
              ),
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              decoration: BoxDecoration(
                color: _isUser ? primaryColor : _warmSurface,
                border: _isUser ? null : Border.all(color: const Color(0x1A171717)),
                borderRadius: BorderRadius.only(
                  topLeft: const Radius.circular(18),
                  topRight: const Radius.circular(18),
                  bottomLeft: _isUser ? const Radius.circular(18) : const Radius.circular(4),
                  bottomRight: _isUser ? const Radius.circular(4) : const Radius.circular(18),
                ),
              ),
              child: message.isStreaming && message.content.isEmpty
                  ? const _TypingDots()
                  : _isUser
                      ? Text(
                          message.content,
                          style: TextStyle(
                            color: userFg,
                            fontSize: 15,
                            height: 1.4,
                          ),
                        )
                      : MarkdownBody(
                          data: message.content,
                          styleSheet: MarkdownStyleSheet.fromTheme(Theme.of(context)).copyWith(
                            p: const TextStyle(
                              color: _ink,
                              fontSize: 15,
                              height: 1.4,
                            ),
                            strong: const TextStyle(
                              color: _ink,
                              fontSize: 15,
                              fontWeight: FontWeight.w600,
                            ),
                            code: const TextStyle(
                              backgroundColor: _warmPanel,
                              fontSize: 13,
                            ),
                          ),
                          shrinkWrap: true,
                        ),
            ),
          ),
          if (_isUser) const SizedBox(width: 4),
        ],
      ),
    );
  }
}

class _AgentAvatar extends StatelessWidget {
  final String? avatarUrl;
  final Color primaryColor;

  const _AgentAvatar({this.avatarUrl, required this.primaryColor});

  @override
  Widget build(BuildContext context) {
    if (avatarUrl != null && avatarUrl!.isNotEmpty) {
      return CircleAvatar(
        radius: 14,
        backgroundImage: NetworkImage(avatarUrl!),
        backgroundColor: primaryColor.withValues(alpha: 0.12),
      );
    }
    return CircleAvatar(
      radius: 14,
      backgroundColor: primaryColor.withValues(alpha: 0.15),
      child: Icon(Icons.smart_toy_outlined, size: 16, color: const Color(0xFF171717)),
    );
  }
}

class _TypingDots extends StatefulWidget {
  const _TypingDots();

  @override
  State<_TypingDots> createState() => _TypingDotsState();
}

class _TypingDotsState extends State<_TypingDots> with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(vsync: this, duration: const Duration(milliseconds: 900))
      ..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) {
        return Row(
          mainAxisSize: MainAxisSize.min,
          children: List.generate(3, (i) {
            final t = (_controller.value - i * 0.15).clamp(0.0, 1.0);
            final scale = 0.6 + 0.4 * (t < 0.5 ? t * 2 : (1 - t) * 2);
            return Padding(
              padding: const EdgeInsets.symmetric(horizontal: 2),
              child: Transform.scale(
                scale: scale,
                child: Container(
                  width: 7,
                  height: 7,
                  decoration: BoxDecoration(
                    color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.5),
                    shape: BoxShape.circle,
                  ),
                ),
              ),
            );
          }),
        );
      },
    );
  }
}
