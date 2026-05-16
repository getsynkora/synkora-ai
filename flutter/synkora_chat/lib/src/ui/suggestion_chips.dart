import 'package:flutter/material.dart';

import '../client/models.dart';

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
      child: GridView.builder(
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
          crossAxisCount: 2,
          crossAxisSpacing: 8,
          mainAxisSpacing: 8,
          childAspectRatio: 1.5,
        ),
        itemCount: prompts.length,
        itemBuilder: (context, i) => _ChipCard(
          prompt: prompts[i],
          primaryColor: primaryColor,
          onTap: () => onTap(prompts[i].prompt),
        ),
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
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surface,
          border: Border.all(color: Theme.of(context).colorScheme.outlineVariant),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (prompt.icon.isNotEmpty)
              Container(
                width: 30,
                height: 30,
                decoration: BoxDecoration(
                  color: primaryColor.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(8),
                ),
                alignment: Alignment.center,
                child: Text(prompt.icon, style: const TextStyle(fontSize: 16)),
              ),
            const SizedBox(height: 6),
            Text(
              prompt.title,
              style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            if (prompt.description.isNotEmpty)
              Text(
                prompt.description,
                style: TextStyle(
                  fontSize: 11,
                  color: Theme.of(context).colorScheme.onSurface.withOpacity(0.55),
                ),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
          ],
        ),
      ),
    );
  }
}
