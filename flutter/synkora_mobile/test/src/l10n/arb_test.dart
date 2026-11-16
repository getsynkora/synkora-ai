import 'dart:convert';
import 'dart:io';

import 'package:flutter/widgets.dart' show Locale;
import 'package:flutter_test/flutter_test.dart';
import 'package:synkora_mobile/l10n/app_localizations.dart';

Map<String, dynamic> load(String code) =>
    jsonDecode(File('lib/l10n/app_$code.arb').readAsStringSync())
        as Map<String, dynamic>;

Map<String, String> messages(Map<String, dynamic> arb) => {
  for (final e in arb.entries)
    if (!e.key.startsWith('@') && e.value is String) e.key: e.value as String,
};

/// {name}, {count, plural, ...} -> the argument names a message uses.
Set<String> arguments(String text) => {
  for (final m in RegExp(r'\{(\w+)').allMatches(text)) m.group(1)!,
};

void main() {
  final english = messages(load('en'));
  final german = messages(load('de'));

  test('German has exactly the messages English has', () {
    expect(german.keys.toSet().difference(english.keys.toSet()), isEmpty);
    expect(english.keys.toSet().difference(german.keys.toSet()), isEmpty);
  });

  test('German keeps every argument English uses', () {
    for (final key in english.keys) {
      expect(
        arguments(german[key]!),
        arguments(english[key]!),
        reason: 'arguments of $key',
      );
    }
  });

  test('no message is empty', () {
    for (final entry in german.entries) {
      expect(entry.value.trim(), isNotEmpty, reason: entry.key);
    }
  });

  test('every language the app lists has a file and the other way round', () {
    final files = Directory('lib/l10n')
        .listSync()
        .map((f) => f.path.split('/').last)
        .where((n) => n.endsWith('.arb'))
        .map((n) => n.replaceAll('app_', '').replaceAll('.arb', ''))
        .toSet();
    final supported = AppLocalizations.supportedLocales
        .map((l) => l.languageCode)
        .toSet();

    expect(files, supported);
  });

  test('plurals and arguments are filled in', () {
    final en = lookupAppLocalizations(const Locale('en'));
    final de = lookupAppLocalizations(const Locale('de'));

    expect(en.runsCount(1), '1 run');
    expect(en.runsCount(3), '3 runs');
    expect(de.runsCount(1), '1 Ausführung');
    expect(de.runsCount(3), '3 Ausführungen');
    expect(de.welcomeBack('Anna'), 'Willkommen zurück, Anna');
    expect(de.successPercent(80), '80% erfolgreich');
    expect(de.timeMinutesAgo(5), 'vor 5 Min.');
    expect(en.timeMinutesAgo(5), '5m ago');
  });
}
