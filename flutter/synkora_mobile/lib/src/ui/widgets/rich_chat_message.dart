import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../models/synkora_models.dart';
import '../../theme/app_theme.dart';

class RichChatMessage extends StatelessWidget {
  const RichChatMessage({
    super.key,
    required this.message,
    this.agentAvatarUrl,
  });

  final ChatMessage message;
  final String? agentAvatarUrl;

  bool get _isUser => message.role == 'user';

  @override
  Widget build(BuildContext context) {
    final bubbleColor = _isUser
        ? SynkoraColors.ink
        : (message.isError ? const Color(0xFFFFF1F2) : Colors.white);
    final textColor = _isUser
        ? Colors.white
        : (message.isError ? SynkoraColors.danger : SynkoraColors.ink);

    return Padding(
      padding: const EdgeInsets.only(bottom: 18),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        mainAxisAlignment: _isUser
            ? MainAxisAlignment.end
            : MainAxisAlignment.start,
        children: [
          if (!_isUser) ...[
            _AgentAvatar(avatarUrl: agentAvatarUrl),
            const SizedBox(width: 10),
          ],
          Flexible(
            child: Container(
              constraints: BoxConstraints(
                maxWidth: MediaQuery.of(context).size.width * 0.78,
              ),
              padding: const EdgeInsets.fromLTRB(16, 14, 16, 12),
              decoration: BoxDecoration(
                color: bubbleColor,
                borderRadius: BorderRadius.only(
                  topLeft: const Radius.circular(26),
                  topRight: const Radius.circular(26),
                  bottomLeft: Radius.circular(_isUser ? 26 : 10),
                  bottomRight: Radius.circular(_isUser ? 10 : 26),
                ),
                border: _isUser
                    ? null
                    : Border.all(
                        color: message.isError
                            ? SynkoraColors.danger.withValues(alpha: 0.15)
                            : SynkoraColors.border,
                      ),
                boxShadow: [
                  BoxShadow(
                    color: const Color(0xFF0F172A).withValues(alpha: 0.04),
                    blurRadius: 24,
                    offset: const Offset(0, 12),
                  ),
                ],
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (message.attachments.isNotEmpty) ...[
                    _AttachmentGrid(
                      attachments: message.attachments,
                      isUser: _isUser,
                    ),
                    if (message.content.trim().isNotEmpty)
                      const SizedBox(height: 12),
                  ],
                  if (message.content.trim().isEmpty && message.isStreaming)
                    const _TypingIndicator()
                  else if (message.content.trim().isNotEmpty)
                    _isUser
                        ? Text(
                            message.content,
                            style: Theme.of(context).textTheme.bodyLarge
                                ?.copyWith(color: textColor, height: 1.45),
                          )
                        : _MarkdownMessage(
                            content: message.content,
                            textColor: textColor,
                          ),
                  const SizedBox(height: 10),
                  Text(
                    [
                      formatRelativeTimestamp(message.createdAt),
                      if (message.isStreaming) 'Streaming',
                    ].join(' • '),
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: _isUser
                          ? Colors.white.withValues(alpha: 0.72)
                          : SynkoraColors.muted,
                      letterSpacing: 0.2,
                    ),
                  ),
                ],
              ),
            ),
          ),
          if (_isUser) ...[
            const SizedBox(width: 10),
            const _UserAvatar(),
          ],
        ],
      ),
    );
  }
}

class _MarkdownMessage extends StatelessWidget {
  const _MarkdownMessage({required this.content, required this.textColor});

  final String content;
  final Color textColor;

  bool get _containsTable =>
      RegExp(r'^\|.+\|$', multiLine: true).hasMatch(content);

  @override
  Widget build(BuildContext context) {
    final styleSheet = MarkdownStyleSheet.fromTheme(Theme.of(context)).copyWith(
      p: Theme.of(context).textTheme.bodyLarge?.copyWith(
        color: textColor,
        height: 1.55,
      ),
      h1: Theme.of(context).textTheme.headlineMedium?.copyWith(
        color: textColor,
      ),
      h2: Theme.of(context).textTheme.titleLarge?.copyWith(color: textColor),
      h3: Theme.of(context).textTheme.titleMedium?.copyWith(
        color: textColor,
        fontWeight: FontWeight.w700,
      ),
      blockquote: Theme.of(context).textTheme.bodyLarge?.copyWith(
        color: SynkoraColors.primaryDeep,
        height: 1.5,
      ),
      strong: Theme.of(context).textTheme.bodyLarge?.copyWith(
        color: textColor,
        fontWeight: FontWeight.w700,
      ),
      em: Theme.of(context).textTheme.bodyLarge?.copyWith(
        color: textColor,
        fontStyle: FontStyle.italic,
      ),
      code: const TextStyle(
        color: SynkoraColors.primaryDeep,
        fontFamily: 'monospace',
        fontSize: 13,
      ),
      codeblockDecoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: const Color(0x140F172A)),
      ),
      codeblockPadding: const EdgeInsets.all(14),
      listBullet: Theme.of(context).textTheme.bodyLarge?.copyWith(
        color: SynkoraColors.primaryDeep,
        fontWeight: FontWeight.w700,
      ),
      tableBorder: TableBorder.all(color: const Color(0x140F172A)),
      tableHead: Theme.of(context).textTheme.bodyMedium?.copyWith(
        color: SynkoraColors.ink,
        fontWeight: FontWeight.w700,
      ),
      tableBody: Theme.of(context).textTheme.bodyMedium?.copyWith(
        color: SynkoraColors.ink,
        height: 1.4,
      ),
      tableCellsPadding: const EdgeInsets.symmetric(
        horizontal: 12,
        vertical: 10,
      ),
      tableHeadAlign: TextAlign.left,
      a: const TextStyle(
        color: SynkoraColors.primaryDeep,
        decoration: TextDecoration.underline,
      ),
    );

    final markdown = MarkdownBody(
      data: content,
      shrinkWrap: true,
      selectable: true,
      styleSheet: styleSheet,
      sizedImageBuilder: (config) => _MarkdownImage(
        uri: config.uri,
        title: config.title,
        alt: config.alt,
        width: config.width,
        height: config.height,
      ),
      onTapLink: (text, href, title) {
        if (href == null || href.isEmpty) return;
        unawaited(_launchExternal(href));
      },
    );

    if (_containsTable) {
      return SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: ConstrainedBox(
          constraints: BoxConstraints(
            minWidth: MediaQuery.of(context).size.width * 0.56,
          ),
          child: markdown,
        ),
      );
    }

    return markdown;
  }
}

class _AttachmentGrid extends StatelessWidget {
  const _AttachmentGrid({required this.attachments, required this.isUser});

  final List<ChatAttachment> attachments;
  final bool isUser;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: attachments
          .map(
            (attachment) => Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: _AttachmentCard(
                attachment: attachment,
                isUser: isUser,
              ),
            ),
          )
          .toList(),
    );
  }
}

class _AttachmentCard extends StatelessWidget {
  const _AttachmentCard({required this.attachment, required this.isUser});

  final ChatAttachment attachment;
  final bool isUser;

  @override
  Widget build(BuildContext context) {
    final surface = isUser
        ? Colors.white.withValues(alpha: 0.08)
        : const Color(0xFFF8FAFC);
    final borderColor = isUser
        ? Colors.white.withValues(alpha: 0.12)
        : const Color(0x160F172A);
    final textColor = isUser ? Colors.white : SynkoraColors.ink;

    return Material(
      color: Colors.transparent,
      child: InkWell(
        borderRadius: BorderRadius.circular(20),
        onTap: attachment.openUrl == null
            ? null
            : () => unawaited(_launchExternal(attachment.openUrl!)),
        child: Ink(
          decoration: BoxDecoration(
            color: surface,
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: borderColor),
          ),
          child: attachment.isImage && attachment.previewUrl != null
              ? Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    ClipRRect(
                      borderRadius: const BorderRadius.vertical(
                        top: Radius.circular(19),
                      ),
                      child: AspectRatio(
                        aspectRatio: 1.35,
                        child: Image.network(
                          attachment.previewUrl!,
                          fit: BoxFit.cover,
                          errorBuilder: (_, _, _) => Container(
                            color: surface,
                            alignment: Alignment.center,
                            child: Icon(
                              Icons.broken_image_outlined,
                              color: textColor.withValues(alpha: 0.65),
                            ),
                          ),
                        ),
                      ),
                    ),
                    Padding(
                      padding: const EdgeInsets.fromLTRB(14, 12, 14, 14),
                      child: _AttachmentMeta(
                        attachment: attachment,
                        textColor: textColor,
                        mutedColor: isUser
                            ? Colors.white.withValues(alpha: 0.72)
                            : SynkoraColors.muted,
                      ),
                    ),
                  ],
                )
              : Padding(
                  padding: const EdgeInsets.all(14),
                  child: Row(
                    children: [
                      Container(
                        width: 44,
                        height: 44,
                        decoration: BoxDecoration(
                          color: isUser
                              ? Colors.white.withValues(alpha: 0.1)
                              : SynkoraColors.panel,
                          borderRadius: BorderRadius.circular(14),
                        ),
                        child: Icon(
                          _attachmentIcon(attachment),
                          color: textColor,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: _AttachmentMeta(
                          attachment: attachment,
                          textColor: textColor,
                          mutedColor: isUser
                              ? Colors.white.withValues(alpha: 0.72)
                              : SynkoraColors.muted,
                        ),
                      ),
                      Icon(
                        Icons.open_in_new_rounded,
                        size: 18,
                        color: textColor.withValues(alpha: 0.78),
                      ),
                    ],
                  ),
                ),
        ),
      ),
    );
  }

  IconData _attachmentIcon(ChatAttachment attachment) {
    if (attachment.isPdf) return Icons.picture_as_pdf_outlined;
    if (attachment.fileType.contains('sheet') ||
        attachment.fileType.contains('csv')) {
      return Icons.table_chart_outlined;
    }
    if (attachment.fileType.contains('word') ||
        attachment.fileType.contains('document')) {
      return Icons.description_outlined;
    }
    return Icons.attach_file_rounded;
  }
}

class _AttachmentMeta extends StatelessWidget {
  const _AttachmentMeta({
    required this.attachment,
    required this.textColor,
    required this.mutedColor,
  });

  final ChatAttachment attachment;
  final Color textColor;
  final Color mutedColor;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          attachment.fileName,
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
          style: Theme.of(context).textTheme.bodyLarge?.copyWith(
            color: textColor,
            fontWeight: FontWeight.w700,
            height: 1.3,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          '${attachment.fileType.split('/').last.toUpperCase()} • ${formatByteSize(attachment.fileSize)}',
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
            color: mutedColor,
            letterSpacing: 0.2,
          ),
        ),
      ],
    );
  }
}

class _MarkdownImage extends StatelessWidget {
  const _MarkdownImage({
    required this.uri,
    required this.title,
    required this.alt,
    this.width,
    this.height,
  });

  final Uri uri;
  final String? title;
  final String? alt;
  final double? width;
  final double? height;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: GestureDetector(
        onTap: () => unawaited(_launchExternal(uri.toString())),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(20),
          child: Container(
            decoration: BoxDecoration(
              border: Border.all(color: const Color(0x120F172A)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                ConstrainedBox(
                  constraints: BoxConstraints(
                    maxHeight: height ?? 240,
                    maxWidth: width ?? double.infinity,
                  ),
                  child: Image.network(
                    uri.toString(),
                    fit: BoxFit.cover,
                    errorBuilder: (_, _, _) => Container(
                      height: 96,
                      color: const Color(0xFFF8FAFC),
                      alignment: Alignment.center,
                      child: const Icon(Icons.broken_image_outlined),
                    ),
                  ),
                ),
                if ((title?.isNotEmpty ?? false) || (alt?.isNotEmpty ?? false))
                  Padding(
                    padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
                    child: Text(
                      title?.trim().isNotEmpty == true ? title!.trim() : alt!,
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: SynkoraColors.muted,
                      ),
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

class _UserAvatar extends StatelessWidget {
  const _UserAvatar();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 36,
      height: 36,
      decoration: BoxDecoration(
        color: SynkoraColors.primary.withValues(alpha: 0.18),
        borderRadius: BorderRadius.circular(14),
      ),
      child: const Icon(Icons.north_east_rounded, color: SynkoraColors.ink),
    );
  }
}

class _AgentAvatar extends StatelessWidget {
  const _AgentAvatar({this.avatarUrl});

  final String? avatarUrl;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 36,
      height: 36,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(14),
        gradient: const LinearGradient(
          colors: [Color(0xFF79DFBC), Color(0xFFB7F0DD)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
      ),
      clipBehavior: Clip.antiAlias,
      child: avatarUrl != null && avatarUrl!.isNotEmpty
          ? Image.network(
              avatarUrl!,
              fit: BoxFit.cover,
              errorBuilder: (_, _, _) => const _AgentAvatarFallback(),
            )
          : const _AgentAvatarFallback(),
    );
  }
}

class _AgentAvatarFallback extends StatelessWidget {
  const _AgentAvatarFallback();

  @override
  Widget build(BuildContext context) {
    return const Icon(
      Icons.auto_awesome_rounded,
      size: 18,
      color: SynkoraColors.ink,
    );
  }
}

class _TypingIndicator extends StatefulWidget {
  const _TypingIndicator();

  @override
  State<_TypingIndicator> createState() => _TypingIndicatorState();
}

class _TypingIndicatorState extends State<_TypingIndicator>
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
    return SizedBox(
      width: 48,
      child: AnimatedBuilder(
        animation: _controller,
        builder: (context, _) {
          return Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: List.generate(3, (index) {
              final animationOffset = (_controller.value - (index * 0.18))
                  .clamp(0.0, 1.0)
                  .toDouble();
              final opacity =
                  (0.28 + ((1 - (animationOffset - 0.5).abs() * 2) * 0.72))
                      .toDouble();
              return Container(
                width: 8,
                height: 8,
                decoration: BoxDecoration(
                  color: SynkoraColors.primaryDeep.withValues(alpha: opacity),
                  borderRadius: BorderRadius.circular(999),
                ),
              );
            }),
          );
        },
      ),
    );
  }
}

Future<void> _launchExternal(String rawUrl) async {
  final uri = Uri.tryParse(rawUrl);
  if (uri == null) return;
  await launchUrl(uri, mode: LaunchMode.externalApplication);
}
