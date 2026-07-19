import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';

import '../client/models.dart';
import '../theme/chat_text_styles.dart';

const _kInk = Color(0xFF1A1A2E);
const _kMuted = Color(0xFF94A3B8);
const _kTableBorder = Color(0x1E0F172A);
const _kTableRow = Color(0x080F172A);

class MessageBubble extends StatelessWidget {
  final ChatMessage message;
  final Color primaryColor;
  final String? agentAvatarUrl;
  final String? agentName;
  final bool showAvatar;
  final void Function(String href)? onLinkTap;

  const MessageBubble({
    super.key,
    required this.message,
    required this.primaryColor,
    this.agentAvatarUrl,
    this.agentName,
    this.showAvatar = true,
    this.onLinkTap,
  });

  bool get _isUser => message.role == MessageRole.user;
  bool get _isOperator => message.role == MessageRole.operator;

  String _formatTime(DateTime dt) {
    final diff = DateTime.now().difference(dt);
    if (diff.inMinutes < 1) return 'Now';
    if (diff.inMinutes < 60) return '${diff.inMinutes} min';
    if (diff.inHours < 24) return '${diff.inHours}hr';
    return '${diff.inDays}d';
  }

  @override
  Widget build(BuildContext context) {
    if (_isOperator) return _OperatorBubble(message: message, showAvatar: showAvatar);

    if (_isUser) {
      return _UserBubble(
        message: message,
        primaryColor: primaryColor,
        timeLabel: _formatTime(message.timestamp),
      );
    }

    return _AgentBubble(
      message: message,
      primaryColor: primaryColor,
      agentAvatarUrl: agentAvatarUrl,
      agentName: agentName ?? 'Assistant',
      showAvatar: showAvatar,
      timeLabel: _formatTime(message.timestamp),
      onLinkTap: onLinkTap,
    );
  }
}

// ---------------------------------------------------------------------------
// Agent bubble — white card, teal avatar left, "Name · time" below
// ---------------------------------------------------------------------------

class _AgentBubble extends StatelessWidget {
  final ChatMessage message;
  final Color primaryColor;
  final String? agentAvatarUrl;
  final String agentName;
  final bool showAvatar;
  final String timeLabel;
  final void Function(String href)? onLinkTap;

  const _AgentBubble({
    required this.message,
    required this.primaryColor,
    required this.agentAvatarUrl,
    required this.agentName,
    required this.showAvatar,
    required this.timeLabel,
    this.onLinkTap,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 4, 48, 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Avatar column — always reserve space for alignment
          SizedBox(
            width: 36,
            child: showAvatar
                ? _AgentAvatar(
                    avatarUrl: agentAvatarUrl,
                    primaryColor: primaryColor,
                  )
                : null,
          ),
          const SizedBox(width: 8),
          Flexible(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // White card bubble
                Container(
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: const BorderRadius.only(
                      topLeft: Radius.circular(4),
                      topRight: Radius.circular(16),
                      bottomLeft: Radius.circular(16),
                      bottomRight: Radius.circular(16),
                    ),
                    boxShadow: const [
                      BoxShadow(
                        color: Color(0x12000000),
                        blurRadius: 8,
                        offset: Offset(0, 2),
                      ),
                    ],
                  ),
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                  child: message.isStreaming && message.content.isEmpty
                      ? _TypingDots(color: primaryColor)
                      : _MarkdownContent(
                          content: message.content,
                          primaryColor: primaryColor,
                          onLinkTap: onLinkTap,
                        ),
                ),
                if (showAvatar) ...[
                  const SizedBox(height: 4),
                  Text(
                    '$agentName · $timeLabel',
                    style: ChatTextStyles.txtStyleRegular11.copyWith(
                      color: _kMuted,
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

// ---------------------------------------------------------------------------
// User bubble — teal pill right, "You · time" below
// ---------------------------------------------------------------------------

class _UserBubble extends StatelessWidget {
  final ChatMessage message;
  final Color primaryColor;
  final String timeLabel;

  const _UserBubble({
    required this.message,
    required this.primaryColor,
    required this.timeLabel,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(48, 4, 12, 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.end,
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Flexible(
                child: Container(
                  decoration: BoxDecoration(
                    color: primaryColor,
                    borderRadius: const BorderRadius.only(
                      topLeft: Radius.circular(16),
                      topRight: Radius.circular(4),
                      bottomLeft: Radius.circular(16),
                      bottomRight: Radius.circular(16),
                    ),
                  ),
                  padding: const EdgeInsets.symmetric(
                      horizontal: 14, vertical: 12),
                  child: Text(
                    message.content,
                    style: ChatTextStyles.txtStyleRegular15.copyWith(
                      color: primaryColor.computeLuminance() > 0.4
                          ? const Color(0xFF1A1A2E)
                          : Colors.white,
                      height: 1.4,
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              const _UserAvatar(),
            ],
          ),
          const SizedBox(height: 4),
          Padding(
            padding: const EdgeInsets.only(right: 44),
            child: Text(
              'You · $timeLabel',
              style: ChatTextStyles.txtStyleRegular11.copyWith(color: _kMuted),
            ),
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Operator bubble — amber tinted, "Support · time" below
// ---------------------------------------------------------------------------

class _OperatorBubble extends StatelessWidget {
  final ChatMessage message;
  final bool showAvatar;

  const _OperatorBubble({required this.message, required this.showAvatar});

  String _formatTime(DateTime dt) {
    final diff = DateTime.now().difference(dt);
    if (diff.inMinutes < 1) return 'Now';
    if (diff.inMinutes < 60) return '${diff.inMinutes} min';
    if (diff.inHours < 24) return '${diff.inHours}hr';
    return '${diff.inDays}d';
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 4, 48, 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 36,
            child: showAvatar
                ? CircleAvatar(
                    radius: 18,
                    backgroundColor: const Color(0xFFFEF3C7),
                    child: const Icon(
                      Icons.support_agent,
                      size: 17,
                      color: Color(0xFFB45309),
                    ),
                  )
                : null,
          ),
          const SizedBox(width: 8),
          Flexible(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  decoration: BoxDecoration(
                    color: const Color(0xFFFFFBEB),
                    borderRadius: const BorderRadius.only(
                      topLeft: Radius.circular(4),
                      topRight: Radius.circular(16),
                      bottomLeft: Radius.circular(16),
                      bottomRight: Radius.circular(16),
                    ),
                    border: Border.all(color: const Color(0xFFFDE68A)),
                    boxShadow: const [
                      BoxShadow(
                        color: Color(0x08000000),
                        blurRadius: 6,
                        offset: Offset(0, 2),
                      ),
                    ],
                  ),
                  padding: const EdgeInsets.symmetric(
                      horizontal: 14, vertical: 12),
                  child: Text(
                    message.content,
                    style: ChatTextStyles.txtStyleRegular15.copyWith(
                      color: const Color(0xFF78350F),
                      height: 1.4,
                    ),
                  ),
                ),
                if (showAvatar) ...[
                  const SizedBox(height: 4),
                  Text(
                    'Support · ${_formatTime(message.timestamp)}',
                    style: ChatTextStyles.txtStyleRegular11
                        .copyWith(color: _kMuted),
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

// ---------------------------------------------------------------------------
// Avatars
// ---------------------------------------------------------------------------

class _AgentAvatar extends StatelessWidget {
  final String? avatarUrl;
  final Color primaryColor;

  const _AgentAvatar({this.avatarUrl, required this.primaryColor});

  @override
  Widget build(BuildContext context) {
    if (avatarUrl != null && avatarUrl!.isNotEmpty) {
      return CircleAvatar(
        radius: 18,
        backgroundImage: NetworkImage(avatarUrl!),
        backgroundColor: primaryColor.withValues(alpha: 0.15),
      );
    }
    return CircleAvatar(
      radius: 18,
      backgroundColor: primaryColor,
      child: const Icon(Icons.auto_awesome, size: 14, color: Colors.white),
    );
  }
}

class _UserAvatar extends StatelessWidget {
  const _UserAvatar();

  @override
  Widget build(BuildContext context) {
    return CircleAvatar(
      radius: 16,
      backgroundColor: const Color(0xFFE2E8F0),
      child: const Icon(Icons.person, size: 17, color: Color(0xFF64748B)),
    );
  }
}

// ---------------------------------------------------------------------------
// Markdown content
// ---------------------------------------------------------------------------

class _MarkdownContent extends StatelessWidget {
  final String content;
  final Color primaryColor;
  final void Function(String href)? onLinkTap;

  const _MarkdownContent({
    required this.content,
    required this.primaryColor,
    this.onLinkTap,
  });

  bool get _hasTable => content.contains('|');

  @override
  Widget build(BuildContext context) {
    final styleSheet =
        MarkdownStyleSheet.fromTheme(Theme.of(context)).copyWith(
      p: ChatTextStyles.txtStyleRegular15.copyWith(color: _kInk, height: 1.4),
      strong: ChatTextStyles.txtStyleSemiB15.copyWith(color: _kInk),
      em: ChatTextStyles.txtStyleRegular15
          .copyWith(color: _kInk, fontStyle: FontStyle.italic),
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
      tableBorder: TableBorder.all(color: _kTableBorder, width: 1),
      tableHead: ChatTextStyles.txtStyleSemiB13.copyWith(color: _kInk),
      tableBody:
          ChatTextStyles.txtStyleRegular13.copyWith(color: _kInk, height: 1.3),
      tableHeadAlign: TextAlign.left,
      tableCellsPadding:
          const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      tableColumnWidth: const FlexColumnWidth(),
      tableCellsDecoration: const BoxDecoration(color: _kTableRow),
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
        if (href != null && onLinkTap != null) onLinkTap!(href);
      },
    );

    if (_hasTable) {
      return SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: ConstrainedBox(
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

// ---------------------------------------------------------------------------
// Typing dots
// ---------------------------------------------------------------------------

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
                    color: widget.color.withValues(alpha: 0.7),
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
