import 'dart:ui' show Locale, PlatformDispatcher;

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../l10n/app_localizations.dart';

/// Which language the app shows.
///
/// The person's own pick (Profile → Language) always wins and is remembered on
/// the device. Otherwise the language saved on their Synkora account is used, and
/// otherwise the phone's language. Anything the app has no translation for falls
/// back to English.
class AppLocaleController extends ChangeNotifier {
  AppLocaleController({
    Locale? chosen,
    Locale Function()? deviceLocale,
    SharedPreferences? preferences,
  }) : _chosen = chosen,
       _deviceLocale =
           deviceLocale ?? (() => PlatformDispatcher.instance.locale),
       _preferences = preferences;

  static const _prefsKey = 'app_language';

  /// Languages the app is translated into.
  static const supported = [Locale('en'), Locale('de')];

  final Locale Function() _deviceLocale;
  SharedPreferences? _preferences;

  Locale? _chosen;
  Locale? _fromAccount;

  /// Reads the language picked earlier in this app (call once at start-up).
  Future<void> restore() async {
    final preferences = await SharedPreferences.getInstance();
    _preferences = preferences;
    final saved = _supportedOrNull(preferences.getString(_prefsKey));
    if (saved != _chosen) {
      _chosen = saved;
      notifyListeners();
    }
  }

  /// The language the person picked in this app, or null to follow account/phone.
  Locale? get chosen => _chosen;

  /// What to give `MaterialApp.locale`: the pick or the account's language, and
  /// null to let the phone's language decide.
  Locale? get appLocale => _chosen ?? _fromAccount;

  /// The language in use.
  Locale get locale =>
      _chosen ??
      _fromAccount ??
      _supportedOrNull(_deviceLocale().languageCode) ??
      const Locale('en');

  /// Texts for [locale], for code that has no BuildContext.
  AppLocalizations get strings => lookupAppLocalizations(locale);

  /// Picks a language, or null to follow the account/phone again.
  Future<void> choose(Locale? value) async {
    _chosen = _supportedOrNull(value?.languageCode);
    final preferences = _preferences;
    if (preferences != null) {
      if (_chosen == null) {
        await preferences.remove(_prefsKey);
      } else {
        await preferences.setString(_prefsKey, _chosen!.languageCode);
      }
    }
    notifyListeners();
  }

  /// Applies the language saved on the signed-in account (null when signed out).
  void useAccountLanguage(String? code) {
    final next = _supportedOrNull(code);
    if (next == _fromAccount) return;
    _fromAccount = next;
    notifyListeners();
  }

  static Locale? _supportedOrNull(String? code) {
    if (code == null) return null;
    final language = code.toLowerCase().split(RegExp('[-_]')).first;
    for (final locale in supported) {
      if (locale.languageCode == language) return locale;
    }
    return null;
  }
}
