import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';

import '../client/models.dart';

class MessageBubble extends StatelessWidget {
  final ChatMessage message;
  final Color primaryColor;
  final String? agentAvatarUrl;
  /// Show avatar on this bubble (false = last-in-group collapsed).
  final bool showAvatar;
  /// Called when the user taps a link inside the agent's message.
  final void Function(String href)? onLinkTap;

  const MessageBubble({
    super.key,
    required this.message,
    required this.primaryColor,
    this.agentAvatarUrl,
    this.showAvatar = true,
    this.onLinkTap,
  });

  bool get _isUser => message.role == MessageRole.user;
  bool get _isOperator => message.role == MessageRole.operator;

  // Agent bubble — cool slate, clearly distinct from any primaryColor
  static const _agentSurface = Color(0xFFF1F5F9);
  // Operator bubble — warm amber tint to stand out from agent messages
  static const _operatorSurface = Color(0xFFFFF8E1);

  @override
  Widget build(BuildContext context) {
    // User text: white on dark primaryColor, near-black on light primaryColor
    final userFg =
        ThemeData.estimateBrightnessForColor(primaryColor) == Brightness.dark
        ? Colors.white
        : const Color(0xFF0F172A);

    // Tighter gap within a group, looser gap between groups
    final verticalPad = showAvatar || _isUser ? 6.0 : 2.0;

    // Operator messages render as a full-width banner-style row
    if (_isOperator) {
      return Padding(
        padding: EdgeInsets.fromLTRB(16, 2, 16, verticalPad),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          mainAxisAlignment: MainAxisAlignment.start,
          children: [
            if (showAvatar)
              const _OperatorAvatar()
            else
              const SizedBox(width: 32),
            const SizedBox(width: 8),
            Flexible(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Padding(
                    padding: EdgeInsets.only(left: 2, bottom: 3),
                    child: Text(
                      'Support',
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                        color: Color(0xFFB45309),
                        letterSpacing: 0.3,
                      ),
                    ),
                  ),
                  Container(
                    constraints: BoxConstraints(
                      maxWidth: MediaQuery.of(context).size.width * 0.75,
                    ),
                    padding: const EdgeInsets.symmetric(
                        horizontal: 14, vertical: 11),
                    decoration: const BoxDecoration(
                      color: _operatorSurface,
                      borderRadius: BorderRadius.only(
                        topLeft: Radius.circular(20),
                        topRight: Radius.circular(20),
                        bottomLeft: Radius.circular(5),
                        bottomRight: Radius.circular(20),
                      ),
                    ),
                    child: Text(
                      message.content,
                      style: const TextStyle(
                        color: Color(0xFF78350F),
                        fontSize: 15,
                        height: 1.45,
                        letterSpacing: 0.1,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      );
    }

    return Padding(
      padding: EdgeInsets.fromLTRB(16, 2, 16, verticalPad),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        mainAxisAlignment: _isUser
            ? MainAxisAlignment.end
            : MainAxisAlignment.start,
        children: [
          if (!_isUser) ...[
            if (showAvatar)
              _AgentAvatar(avatarUrl: agentAvatarUrl, primaryColor: primaryColor)
            else
              const SizedBox(width: 32), // same width as avatar diameter
            const SizedBox(width: 8),
          ],
          Flexible(
            child: Container(
              constraints: BoxConstraints(
                maxWidth: MediaQuery.of(context).size.width * 0.75,
              ),
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 11),
              decoration: BoxDecoration(
                color: _isUser ? primaryColor : _agentSurface,
                borderRadius: BorderRadius.only(
                  topLeft: const Radius.circular(20),
                  topRight: const Radius.circular(20),
                  bottomLeft: _isUser
                      ? const Radius.circular(20)
                      : const Radius.circular(5),
                  bottomRight: _isUser
                      ? const Radius.circular(5)
                      : const Radius.circular(20),
                ),
              ),
              child: message.isStreaming && message.content.isEmpty
                  ? _TypingDots(color: primaryColor)
                  : _isUser
                  ? Text(
                      message.content,
                      style: TextStyle(
                        color: userFg,
                        fontSize: 15,
                        height: 1.45,
                        letterSpacing: 0.1,
                      ),
                    )
                  : _MarkdownContent(
                      content: message.content,
                      primaryColor: primaryColor,
                      onLinkTap: onLinkTap,
                    ),
            ),
          ),
          if (_isUser) ...[
            const SizedBox(width: 8),
            const _UserAvatar(),
          ],
        ],
      ),
    );
  }
}

/// Renders markdown with horizontally scrollable tables and link tap support.
class _MarkdownContent extends StatelessWidget {
  final String content;
  final Color primaryColor;
  final void Function(String href)? onLinkTap;

  static const _ink = Color(0xFF0F172A);
  static const _tableBorder = Color(0x1E0F172A);
  static const _tableRow = Color(0x080F172A);

  const _MarkdownContent({
    required this.content,
    required this.primaryColor,
    this.onLinkTap,
  });

  bool get _hasTable => content.contains('|');

  @override
  Widget build(BuildContext context) {
    final styleSheet = MarkdownStyleSheet.fromTheme(Theme.of(context)).copyWith(
      p: const TextStyle(color: _ink, fontSize: 15, height: 1.4),
      strong: const TextStyle(color: _ink, fontSize: 15, fontWeight: FontWeight.w600),
      em: const TextStyle(color: _ink, fontSize: 15, fontStyle: FontStyle.italic),
      code: TextStyle(
        backgroundColor: const Color(0xFFE2E8F0),
        fontSize: 13,
        color: primaryColor,
        fontFamily: 'monospace',
      ),
      codeblockDecoration: BoxDecoration(
        color: const Color(0xFFF3F4F6),
        borderRadius: BorderRadius.circular(8),
      ),
      // Table styles
      tableBorder: TableBorder.all(color: _tableBorder, width: 1),
      tableHead: const TextStyle(
        fontSize: 13,
        fontWeight: FontWeight.w600,
        color: _ink,
      ),
      tableBody: const TextStyle(fontSize: 13, color: _ink, height: 1.3),
      tableHeadAlign: TextAlign.left,
      tableCellsPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      tableColumnWidth: const FlexColumnWidth(),
      tableCellsDecoration: const BoxDecoration(color: _tableRow),
      a: TextStyle(
        color: primaryColor,
        decoration: TextDecoration.underline,
        decorationColor: primaryColor,
      ),
    );

    final body = MarkdownBody(
      data: content,
      styleSheet: styleSheet,
      shrinkWrap: true,
      onTapLink: (text, href, title) {
        if (href != null && onLinkTap != null) {
          onLinkTap!(href);
        }
      },
    );

    // Wrap in horizontal scroll only when a table is present so normal
    // messages stay at natural width without unnecessary scroll physics.
    if (_hasTable) {
      return SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: ConstrainedBox(
          // Minimum width = bubble width; expands as wide as needed for table
          constraints: BoxConstraints(
            minWidth: 0,
            maxWidth: MediaQuery.of(context).size.width * 1.5,
          ),
          child: body,
        ),
      );
    }

    return body;
  }
}

class _UserAvatar extends StatelessWidget {
  const _UserAvatar();

  @override
  Widget build(BuildContext context) {
    return CircleAvatar(
      radius: 16,
      backgroundColor: const Color(0xFFE2E8F0),
      child: const Icon(
        Icons.person,
        size: 17,
        color: Color(0xFF64748B),
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
        radius: 16,
        backgroundImage: NetworkImage(avatarUrl!),
        backgroundColor: primaryColor.withValues(alpha: 0.12),
      );
    }
    return CircleAvatar(
      radius: 16,
      backgroundColor: primaryColor,
      child: const Icon(
        Icons.auto_awesome,
        size: 15,
        color: Colors.white,
      ),
    );
  }
}

class _OperatorAvatar extends StatelessWidget {
  const _OperatorAvatar();

  @override
  Widget build(BuildContext context) {
    return CircleAvatar(
      radius: 16,
      backgroundColor: const Color(0xFFFEF3C7),
      child: const Icon(
        Icons.support_agent,
        size: 17,
        color: Color(0xFFB45309),
      ),
    );
  }
}

class _TypingDots extends StatefulWidget {
  final Color color;
  const _TypingDots({required this.color});

  @override
  State<_TypingDots> createState() => _TypingDotsState();
}

class _TypingDotsState extends State<_TypingDots>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    )..repeat();
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
                    color: widget.color.withValues(alpha: 0.6),
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
