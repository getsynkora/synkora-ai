import 'package:flutter/material.dart';

import '../client/models.dart';
import '../theme/chat_text_styles.dart';

class SuggestionChips extends StatelessWidget {
  final List<SuggestionPrompt> prompts;
  final Color primaryColor;
  final void Function(String prompt) onTap;

  const SuggestionChips({
    super.key,
    required this.prompts,
    required this.primaryColor,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    if (prompts.isEmpty) return const SizedBox.shrink();

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final isCompact = constraints.maxWidth < 320;
          return GridView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: isCompact ? 1 : 2,
              crossAxisSpacing: 8,
              mainAxisSpacing: 8,
              childAspectRatio: isCompact ? 2.45 : 1.18,
            ),
            itemCount: prompts.length,
            itemBuilder: (context, i) => _ChipCard(
              prompt: prompts[i],
              primaryColor: primaryColor,
              onTap: () => onTap(prompts[i].prompt),
            ),
          );
        },
      ),
    );
  }
}

class _ChipCard extends StatelessWidget {
  final SuggestionPrompt prompt;
  final Color primaryColor;
  final VoidCallback onTap;

  const _ChipCard({
    required this.prompt,
    required this.primaryColor,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(16),
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: Colors.white,
          border: Border.all(color: const Color(0x14000000)),
          boxShadow: const [
            BoxShadow(
              color: Color(0x0A000000),
              blurRadius: 8,
              offset: Offset(0, 2),
            ),
          ],
          borderRadius: BorderRadius.circular(16),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (prompt.icon.isNotEmpty)
              Container(
                width: 32,
                height: 32,
                decoration: BoxDecoration(
                  color: primaryColor.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(10),
                ),
                alignment: Alignment.center,
                child: Text(prompt.icon, style: ChatTextStyles.txtStyleRegular16),
              ),
            const SizedBox(height: 8),
            Text(
              prompt.title,
              style: ChatTextStyles.txtStyleSemiB13,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
            if (prompt.description.isNotEmpty) ...[
              const SizedBox(height: 3),
              Text(
                prompt.description,
                style: ChatTextStyles.txtStyleRegular11.copyWith(
                  color: const Color(0xFF64748B),
                  height: 1.35,
                ),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ],
        ),
      ),
    );
  }
}
