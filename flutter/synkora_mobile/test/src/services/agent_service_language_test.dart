import 'package:flutter/widgets.dart' show Locale;
import 'package:flutter_test/flutter_test.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:synkora_mobile/l10n/app_localizations.dart';
import 'package:synkora_mobile/src/models/synkora_models.dart';
import 'package:synkora_mobile/src/services/agent_service.dart';
import 'package:synkora_mobile/src/services/api_client.dart';

import '../voice/support/fake_api.dart';

class LanguageApi extends RecordingApi {
  LanguageApi(this._language) : super();

  final String? _language;

  @override
  String? get language => _language;
}

void main() {
  group('chat requests carry the language', () {
    test("the app's language by default", () {
      final api = LanguageApi('de');

      SynkoraAgentService(api).streamChat(agentSlug: 'muse', message: 'Hallo');

      expect(api.lastStreamPath, '/api/v1/agents/chat/stream');
      expect(api.lastStreamBody?['language'], 'de');
    });

    test('an explicit language wins (a voice conversation in French)', () {
      final api = LanguageApi('de');

      SynkoraAgentService(api).streamChat(
        agentSlug: 'muse',
        message: 'Bonjour',
        language: 'fr',
        voiceMode: true,
      );

      expect(api.lastStreamBody?['language'], 'fr');
      expect(api.lastStreamBody?['voice_mode'], isTrue);
    });

    test('nothing is sent when no language is known', () {
      final api = LanguageApi(null);

      SynkoraAgentService(api).streamChat(agentSlug: 'muse', message: 'hi');

      expect(api.lastStreamBody?.containsKey('language'), isFalse);
    });
  });

  group('the api client', () {
    test('reports the language the app asks for', () {
      final api = SynkoraApiClient(
        baseUrl: 'http://test',
        language: () => 'de',
      );

      expect(api.language, 'de');
      expect(SynkoraApiClient(baseUrl: 'http://test').language, isNull);
    });

    test('words its own errors in the app language', () async {
      final api = SynkoraApiClient(
        baseUrl: 'http://test',
        strings: () => lookupAppLocalizations(const Locale('de')),
      );

      await expectLater(
        api.getJson('/x'),
        throwsA(
          isA<SynkoraApiException>().having(
            (e) => e.message,
            'message',
            'Anmeldung erforderlich.',
          ),
        ),
      );
    });
  });

  group('relative times', () {
    setUpAll(() async {
      await initializeDateFormatting('de');
      await initializeDateFormatting('en');
    });

    final en = lookupAppLocalizations(const Locale('en'));
    final de = lookupAppLocalizations(const Locale('de'));
    DateTime ago(Duration d) => DateTime.now().subtract(d);

    test('in English', () {
      expect(formatRelativeTimestamp(null, en), 'Unknown');
      expect(
        formatRelativeTimestamp(ago(const Duration(seconds: 5)), en),
        'Just now',
      );
      expect(
        formatRelativeTimestamp(ago(const Duration(minutes: 5)), en),
        '5m ago',
      );
      expect(
        formatRelativeTimestamp(ago(const Duration(hours: 3)), en),
        '3h ago',
      );
      expect(
        formatRelativeTimestamp(ago(const Duration(days: 2)), en),
        '2d ago',
      );
    });

    test('in German', () {
      expect(formatRelativeTimestamp(null, de), 'Unbekannt');
      expect(
        formatRelativeTimestamp(ago(const Duration(seconds: 5)), de),
        'Gerade eben',
      );
      expect(
        formatRelativeTimestamp(ago(const Duration(minutes: 5)), de),
        'vor 5 Min.',
      );
      expect(
        formatRelativeTimestamp(ago(const Duration(hours: 3)), de),
        'vor 3 Std.',
      );
      expect(
        formatRelativeTimestamp(ago(const Duration(days: 2)), de),
        'vor 2 T.',
      );
    });

    test('older dates use the language\'s month names', () {
      final date = DateTime(2024, 3, 5);

      expect(formatRelativeTimestamp(date, en), 'Mar 5');
      expect(formatRelativeTimestamp(date, de), '5. März');
    });
  });
}
