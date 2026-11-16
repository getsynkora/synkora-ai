import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:synkora_mobile/l10n/app_localizations.dart';
import 'package:synkora_mobile/src/l10n/app_locale_controller.dart';
import 'package:synkora_mobile/src/ui/l10n/language_picker.dart';

Widget app(AppLocaleController controller, List<String> saved) {
  return AnimatedBuilder(
    animation: controller,
    builder: (context, _) => MaterialApp(
      locale: controller.appLocale,
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      builder: (context, child) => AppLocaleScope(
        controller: controller,
        saveToAccount: (code) async => saved.add(code),
        child: child!,
      ),
      home: Builder(
        builder: (context) => Scaffold(
          body: Column(
            children: [
              Text(AppLocalizations.of(context).signIn),
              Text(currentLanguageLabel(context), key: const Key('current')),
              TextButton(
                onPressed: () => showLanguageSheet(context),
                child: const Text('open'),
              ),
            ],
          ),
        ),
      ),
    ),
  );
}

void main() {
  late AppLocaleController controller;
  late List<String> saved;

  setUp(() {
    controller = AppLocaleController(deviceLocale: () => const Locale('en'));
    saved = [];
  });

  Future<void> openSheet(WidgetTester tester) async {
    await tester.pumpWidget(app(controller, saved));
    await tester.tap(find.text('open'));
    await tester.pumpAndSettle();
  }

  testWidgets('offers the system default and each language by its own name', (
    tester,
  ) async {
    await openSheet(tester);

    // Once on the page behind the sheet (the current language), once in the sheet.
    expect(find.text('System default'), findsNWidgets(2));
    expect(find.text('English'), findsOneWidget);
    expect(find.text('Deutsch'), findsOneWidget);
  });

  testWidgets(
    'picking German switches the screen, is remembered and saved on the account',
    (tester) async {
      await openSheet(tester);

      await tester.tap(find.text('Deutsch'));
      await tester.pumpAndSettle();

      expect(controller.chosen, const Locale('de'));
      expect(find.text('Anmelden'), findsOneWidget);
      expect(
        tester.widget<Text>(find.byKey(const Key('current'))).data,
        'Deutsch',
      );
      expect(saved, ['de']);
    },
  );

  testWidgets('system default clears the pick and does not touch the account', (
    tester,
  ) async {
    await controller.choose(const Locale('de'));
    await openSheet(tester);

    await tester.tap(find.text('Systemstandard'));
    await tester.pumpAndSettle();

    expect(controller.chosen, isNull);
    expect(find.text('Sign in'), findsOneWidget);
    expect(saved, isEmpty);
  });

  testWidgets('shows which language is selected', (tester) async {
    await controller.choose(const Locale('en'));
    await openSheet(tester);

    expect(find.byIcon(Icons.check_circle_rounded), findsOneWidget);
    final selected = find.ancestor(
      of: find.byIcon(Icons.check_circle_rounded),
      matching: find.byType(ListTile),
    );
    expect(
      find.descendant(of: selected, matching: find.text('English')),
      findsOneWidget,
    );
  });
}
