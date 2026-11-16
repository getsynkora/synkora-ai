import 'dart:ui';

import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:synkora_mobile/src/l10n/app_locale_controller.dart';

AppLocaleController controller({Locale device = const Locale('en', 'US')}) =>
    AppLocaleController(deviceLocale: () => device);

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('follows the phone, with English for anything not translated', () {
    expect(
      controller(device: const Locale('de', 'AT')).locale,
      const Locale('de'),
    );
    expect(
      controller(device: const Locale('en', 'GB')).locale,
      const Locale('en'),
    );
    expect(controller(device: const Locale('fr')).locale, const Locale('en'));
    expect(controller().appLocale, isNull);
  });

  test("uses the account's language over the phone's", () {
    final c = controller()..useAccountLanguage('de');

    expect(c.locale, const Locale('de'));
    expect(c.appLocale, const Locale('de'));
  });

  test('ignores an account language the app does not have', () {
    final c = controller(device: const Locale('de'))..useAccountLanguage('fr');

    expect(c.locale, const Locale('de'));
  });

  test("the person's own pick beats the account and is remembered", () async {
    final preferences = await SharedPreferences.getInstance();
    final c = AppLocaleController(
      deviceLocale: () => const Locale('en'),
      preferences: preferences,
    )..useAccountLanguage('de');

    await c.choose(const Locale('en'));

    expect(c.locale, const Locale('en'));
    expect(preferences.getString('app_language'), 'en');
  });

  test('going back to "system default" forgets the pick', () async {
    final preferences = await SharedPreferences.getInstance();
    final c = AppLocaleController(
      deviceLocale: () => const Locale('de'),
      preferences: preferences,
    );
    await c.choose(const Locale('en'));

    await c.choose(null);

    expect(c.chosen, isNull);
    expect(c.locale, const Locale('de'));
    expect(preferences.containsKey('app_language'), isFalse);
  });

  test('restores the saved pick at start-up', () async {
    SharedPreferences.setMockInitialValues({'app_language': 'de'});
    final c = controller();

    await c.restore();

    expect(c.chosen, const Locale('de'));
    expect(c.locale, const Locale('de'));
  });

  test(
    'tells listeners when the language changes, not when it stays',
    () async {
      final c = controller();
      var calls = 0;
      c.addListener(() => calls++);

      c.useAccountLanguage('de');
      c.useAccountLanguage('de');
      await c.choose(const Locale('en'));

      expect(calls, 2);
    },
  );

  test('gives texts for code without a BuildContext', () {
    expect(controller(device: const Locale('de')).strings.signIn, 'Anmelden');
    expect(controller().strings.signIn, 'Sign in');
  });
}
