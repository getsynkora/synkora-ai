import 'dart:convert';
import 'dart:io';

import 'package:drift/native.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:synkora_chat/src/cache/cache_database.dart';
import 'package:synkora_chat/synkora_chat.dart';

/// A local stand-in for the Synkora API that records what the app asked for
/// and answers the way the real server does for German and English.
class _FakeWidgetServer {
  _FakeWidgetServer._(this._server) {
    _server.listen(_handle);
  }

  final HttpServer _server;
  bool preChatEnabled = false;
  final List<Uri> configRequests = [];
  final List<Map<String, dynamic>> chatBodies = [];

  static Future<_FakeWidgetServer> start() async =>
      _FakeWidgetServer._(await HttpServer.bind('127.0.0.1', 0));

  String get baseUrl => 'http://127.0.0.1:${_server.port}';

  Future<void> close() => _server.close(force: true);

  Future<void> _handle(HttpRequest request) async {
    final path = request.uri.path;
    if (request.method == 'GET' && path == '/api/v1/widgets/config') {
      configRequests.add(request.uri);
      final german =
          request.uri.queryParameters['lang']?.startsWith('de') ?? false;
      _json(request, {
        'widget_id': 'w1',
        'agent_name': 'Muse',
        'agent_description': german ? 'Dein Assistent' : 'Your assistant',
        'theme': {
          'primary_color': '#10717C',
          'welcome_message': german
              ? 'Hallo!\nWomit können wir helfen?'
              : 'Hi!\nHow can we help?',
          'placeholder': '',
          'title': german ? 'Hilfe' : 'Help',
        },
        'suggestion_prompts': [
          {
            'title': german ? 'Preise' : 'Pricing',
            'description': '',
            'icon': '',
            'prompt': 'p',
          },
        ],
        'pre_chat_form': {'enabled': preChatEnabled, 'show_phone': true},
      });
    } else if (request.method == 'POST' && path == '/api/v1/widgets/chat') {
      chatBodies.add(
        jsonDecode(await utf8.decoder.bind(request).join())
            as Map<String, dynamic>,
      );
      request.response.headers.contentType =
          ContentType('text', 'event-stream');
      request.response.write('data: {"type":"chunk","content":"ok"}\n\n');
      request.response.write('data: {"type":"done"}\n\n');
      await request.response.close();
    } else {
      _json(request, {'messages': []});
    }
  }

  void _json(HttpRequest request, Object body) {
    request.response.headers.contentType = ContentType.json;
    request.response.write(jsonEncode(body));
    request.response.close();
  }
}

SynkoraChatController _controller(String baseUrl) => SynkoraChatController(
      client: SynkoraClient(widgetKey: 'wk_test', baseUrl: baseUrl),
      cacheDatabase: CacheDatabase(NativeDatabase.memory()),
    );

void main() {
  // flutter_test blocks real HTTP (answers 400); these tests talk to a local server.
  setUpAll(() => HttpOverrides.global = null);

  group('SynkoraChatStrings', () {
    test('German has exactly the keys English has', () {
      final english = SynkoraChatStrings.en.keys.toSet();
      final german = SynkoraChatStrings.de.keys.toSet();

      expect(german.difference(english), isEmpty,
          reason: 'German keys missing in English');
      expect(english.difference(german), isEmpty,
          reason: 'English keys missing in German');
    });

    test('German keeps every placeholder English has', () {
      final placeholder = RegExp(r'\{(\w+)\}');
      for (final key in SynkoraChatStrings.en.keys) {
        final en = SynkoraChatStrings.en.template(key)!;
        final de = SynkoraChatStrings.de.template(key)!;
        expect(
          placeholder.allMatches(de).map((m) => m.group(1)).toSet(),
          placeholder.allMatches(en).map((m) => m.group(1)).toSet(),
          reason: 'placeholders differ for "$key"',
        );
        expect(de.trim(), isNotEmpty, reason: '"$key" is empty in German');
      }
    });

    test('picks the built-in table for a locale, else English', () {
      expect(
          SynkoraChatStrings.forLocale(const Locale('de')).cancel, 'Abbrechen');
      expect(SynkoraChatStrings.forLocale(const Locale('de', 'AT')).cancel,
          'Abbrechen');
      expect(SynkoraChatStrings.forLocale(const Locale('en')).cancel, 'Cancel');
      expect(SynkoraChatStrings.forLocale(const Locale('fr')).cancel, 'Cancel');
    });

    test('fills in values', () {
      final de = SynkoraChatStrings.de;

      expect(de.approvalBody('send_email'),
          'Der Agent möchte „send_email“ ausführen und benötigt Ihre Freigabe.');
      expect(de.minutesAgo(5), '5 Min.');
      expect(SynkoraChatStrings.en.minutesAgo(5), '5 min');
      expect(SynkoraChatStrings.en.poweredBy('Muse'), 'Powered by Muse');
    });

    test('a custom table overrides some keys and falls back to English', () {
      final fr = SynkoraChatStrings.custom('fr', {'cancel': 'Annuler'});

      expect(fr.languageCode, 'fr');
      expect(fr.cancel, 'Annuler');
      expect(fr.clear, 'Clear');
    });
  });

  group('client and controller', () {
    late _FakeWidgetServer server;

    setUp(() async => server = await _FakeWidgetServer.start());
    tearDown(() => server.close());

    test('config is requested without a language until one is set', () async {
      final client =
          SynkoraClient(widgetKey: 'wk_test', baseUrl: server.baseUrl);

      await client.loadConfig();

      expect(server.configRequests.single.queryParameters, isEmpty);
    });

    test('config and chat both carry the language', () async {
      final client =
          SynkoraClient(widgetKey: 'wk_test', baseUrl: server.baseUrl)
            ..language = 'de';

      final config = await client.loadConfig();
      await client.sendMessage('hallo').toList();

      expect(server.configRequests.single.queryParameters['lang'], 'de');
      expect(config.theme.title, 'Hilfe');
      expect(server.chatBodies.single['language'], 'de');
    });

    test('chat sends no language when none is set', () async {
      final client =
          SynkoraClient(widgetKey: 'wk_test', baseUrl: server.baseUrl);

      await client.sendMessage('hi').toList();

      expect(server.chatBodies.single.containsKey('language'), isFalse);
    });

    test('setLocale before init loads the config in that language', () async {
      final controller = _controller(server.baseUrl)
        ..setLocale(const Locale('de'));

      await controller.init();

      expect(server.configRequests.single.queryParameters['lang'], 'de');
      expect(controller.config?.theme.title, 'Hilfe');
      expect(controller.strings.cancel, 'Abbrechen');
      controller.dispose();
    });

    test('changing language after init reloads the config', () async {
      final controller = _controller(server.baseUrl);
      await controller.init();
      expect(controller.config?.theme.title, 'Help');

      controller.setLocale(const Locale('de'));
      await pumpEventQueue();

      expect(controller.config?.theme.title, 'Hilfe');
      expect(controller.language, 'de');
      controller.dispose();
    });

    test('setting the same language again does not reload', () async {
      final controller = _controller(server.baseUrl)
        ..setLocale(const Locale('de'));
      await controller.init();

      controller.setLocale(const Locale('de'));
      await pumpEventQueue();

      expect(server.configRequests, hasLength(1));
      controller.dispose();
    });

    test('an own strings table wins over the built-in one', () {
      final controller = _controller(server.baseUrl);
      final custom = SynkoraChatStrings.custom('de', {'cancel': 'Zurück'});

      controller.setLocale(const Locale('de'), strings: custom);

      expect(controller.strings.cancel, 'Zurück');
      controller.dispose();
    });

    test('messages are sent with the controller language', () async {
      final controller = _controller(server.baseUrl)
        ..setLocale(const Locale('de'));
      await controller.init();

      await controller.send('Hallo');
      await pumpEventQueue();

      expect(server.chatBodies.single['language'], 'de');
      controller.dispose();
    });
  });

  group('SynkoraChatWidget', () {
    late _FakeWidgetServer server;

    setUp(() async => server = await _FakeWidgetServer.start());
    tearDown(() => server.close());

    /// Lets the controller's real HTTP calls finish. Its timers run in the test's
    /// fake clock, so alternate between real waiting and advancing that clock.
    Future<void> settle(WidgetTester tester) async {
      for (var i = 0; i < 15; i++) {
        await tester.runAsync(
          () => Future<void>.delayed(const Duration(milliseconds: 40)),
        );
        await tester.pump(const Duration(milliseconds: 100));
      }
    }

    /// Removes the chat and runs out the HTTP keep-alive timers, which would
    /// otherwise be reported as pending when the test ends.
    Future<void> finish(WidgetTester tester) async {
      await tester.pumpWidget(const SizedBox());
      await tester.pump(const Duration(seconds: 5));
    }

    Future<void> pumpChat(
      WidgetTester tester, {
      Locale? locale,
      Locale? hostLocale,
    }) async {
      final controller = _controller(server.baseUrl);
      addTearDown(controller.dispose);
      await tester.pumpWidget(
        MaterialApp(
          locale: hostLocale,
          localizationsDelegates: GlobalMaterialLocalizations.delegates,
          supportedLocales: const [Locale('en'), Locale('de')],
          home: SynkoraChatWidget(
            widgetKey: 'wk_test',
            baseUrl: server.baseUrl,
            controller: controller,
            locale: locale,
          ),
        ),
      );
      await settle(tester);
    }

    testWidgets('shows English by default', (tester) async {
      await pumpChat(tester, locale: const Locale('en'));

      expect(find.text('Home'), findsOneWidget);
      expect(find.text('Hi!'), findsOneWidget);
      expect(find.text('Start new conversation'), findsOneWidget);
      await finish(tester);
    });

    testWidgets('shows German text and server-translated config',
        (tester) async {
      await pumpChat(tester, locale: const Locale('de'));

      expect(find.text('Start'), findsOneWidget); // bottom nav "Home"
      expect(find.text('Neue Unterhaltung starten'), findsOneWidget);
      expect(find.text('Hallo!'), findsOneWidget); // welcome from the server
      expect(find.text('Home'), findsNothing);
      expect(server.configRequests.single.queryParameters['lang'], 'de');
      await finish(tester);
    });

    testWidgets('follows the host app language when no locale is given',
        (tester) async {
      await pumpChat(tester, hostLocale: const Locale('de'));

      expect(find.text('Neue Unterhaltung starten'), findsOneWidget);
      await finish(tester);
    });

    testWidgets('German text fits a small phone on every screen',
        (tester) async {
      tester.view.physicalSize = const Size(320 * 2, 640 * 2);
      tester.view.devicePixelRatio = 2;
      addTearDown(tester.view.reset);
      server.preChatEnabled = true;

      await pumpChat(tester, locale: const Locale('de'));
      expect(tester.takeException(), isNull, reason: 'home screen');

      await tester.tap(find.text('Chat').last); // sessions tab
      await settle(tester);
      expect(tester.takeException(), isNull, reason: 'sessions screen');
      await tester.tap(find.text('Start'));
      await settle(tester);

      await tester.tap(find.text('Neue Unterhaltung starten'));
      await settle(tester);
      expect(find.text('Fragen Sie mich alles'), findsOneWidget);
      expect(tester.takeException(), isNull, reason: 'empty chat');

      // Sending the first message opens the pre-chat form.
      await tester.enterText(find.byType(TextField), 'Hallo');
      await tester.testTextInput.receiveAction(TextInputAction.send);
      await settle(tester);
      expect(find.text('Bevor wir starten'), findsWidgets);
      expect(find.text('Telefon'), findsOneWidget);
      expect(tester.takeException(), isNull, reason: 'pre-chat form');
      await finish(tester);
    });

    testWidgets('keeps a language the host set on its own controller',
        (tester) async {
      final controller = _controller(server.baseUrl)
        ..setLocale(const Locale('en'));
      addTearDown(controller.dispose);
      await tester.pumpWidget(
        MaterialApp(
          locale: const Locale('de'),
          localizationsDelegates: GlobalMaterialLocalizations.delegates,
          supportedLocales: const [Locale('en'), Locale('de')],
          home: SynkoraChatWidget(
            widgetKey: 'wk_test',
            baseUrl: server.baseUrl,
            controller: controller,
          ),
        ),
      );
      await settle(tester);

      expect(find.text('Start new conversation'), findsOneWidget);
      expect(find.text('Neue Unterhaltung starten'), findsNothing);
      await finish(tester);
    });

    testWidgets('switches language when the locale changes', (tester) async {
      final controller = _controller(server.baseUrl);
      addTearDown(controller.dispose);
      Widget app(Locale locale) => MaterialApp(
            home: SynkoraChatWidget(
              widgetKey: 'wk_test',
              baseUrl: server.baseUrl,
              controller: controller,
              locale: locale,
            ),
          );

      await tester.pumpWidget(app(const Locale('en')));
      await settle(tester);
      expect(find.text('Start new conversation'), findsOneWidget);

      await tester.pumpWidget(app(const Locale('de')));
      await settle(tester);

      expect(find.text('Neue Unterhaltung starten'), findsOneWidget);
      expect(find.text('Hallo!'), findsOneWidget);
      await finish(tester);
    });
  });
}
