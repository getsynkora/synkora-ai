import 'dart:async';

import 'package:flutter/material.dart';

import '../../../l10n/app_localizations.dart';
import '../../l10n/app_locale_controller.dart';
import '../../theme/app_theme.dart';

/// Gives screens the language controller, and a way to save the pick on the
/// signed-in account.
class AppLocaleScope extends InheritedNotifier<AppLocaleController> {
  const AppLocaleScope({
    super.key,
    required AppLocaleController controller,
    required this.saveToAccount,
    required super.child,
  }) : super(notifier: controller);

  /// Saves the language on the account. Best effort: the pick still applies on
  /// this device if it fails.
  final Future<void> Function(String languageCode) saveToAccount;

  static AppLocaleScope of(BuildContext context) {
    final scope = context.dependOnInheritedWidgetOfExactType<AppLocaleScope>();
    assert(scope != null, 'No AppLocaleScope above this widget');
    return scope!;
  }

  AppLocaleController get controller => notifier!;
}

/// Each language is shown in its own name.
String languageName(Locale locale) => switch (locale.languageCode) {
  'de' => 'Deutsch',
  'en' => 'English',
  _ => locale.languageCode,
};

/// What the Profile row shows: the pick, or "System default".
String currentLanguageLabel(BuildContext context) {
  final chosen = AppLocaleScope.of(context).controller.chosen;
  return chosen == null
      ? AppLocalizations.of(context).languageSystem
      : languageName(chosen);
}

Future<void> showLanguageSheet(BuildContext context) {
  final scope = AppLocaleScope.of(context);
  final controller = scope.controller;
  final l10n = AppLocalizations.of(context);

  Future<void> pick(BuildContext sheetContext, Locale? locale) async {
    Navigator.of(sheetContext).pop();
    await controller.choose(locale);
    if (locale != null) unawaited(scope.saveToAccount(locale.languageCode));
  }

  return showModalBottomSheet<void>(
    context: context,
    backgroundColor: SynkoraColors.panel,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
    ),
    builder: (sheetContext) {
      return SafeArea(
        child: ListView(
          shrinkWrap: true,
          padding: const EdgeInsets.all(20),
          children: [
            Text(
              l10n.language,
              style: Theme.of(sheetContext).textTheme.headlineMedium,
            ),
            const SizedBox(height: 12),
            _LanguageOption(
              label: l10n.languageSystem,
              selected: controller.chosen == null,
              onTap: () => pick(sheetContext, null),
            ),
            for (final locale in AppLocaleController.supported)
              _LanguageOption(
                label: languageName(locale),
                selected: controller.chosen == locale,
                onTap: () => pick(sheetContext, locale),
              ),
          ],
        ),
      );
    },
  );
}

class _LanguageOption extends StatelessWidget {
  const _LanguageOption({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Card(
        child: ListTile(
          title: Text(label),
          trailing: selected ? const Icon(Icons.check_circle_rounded) : null,
          onTap: onTap,
        ),
      ),
    );
  }
}
