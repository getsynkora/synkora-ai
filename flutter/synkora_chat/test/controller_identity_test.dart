import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:synkora_chat/src/cache/cache_database.dart';
import 'package:synkora_chat/synkora_chat.dart';

/// Regression test for the bug where a rebuilt SynkoraChatWidget with a
/// freshly-fetched userHash/identityToken silently kept using whatever
/// values were passed in at the widget's very first build, because
/// SynkoraChatController had no way to update its identity after
/// construction and SynkoraChatWidget never called one.
void main() {
  group('SynkoraChatController.updateIdentity', () {
    test('replaces userHash, user, and userId with the new values', () async {
      final controller = SynkoraChatController(
        client: SynkoraClient(
            widgetKey: 'wk_test', baseUrl: 'https://example.test'),
        userId: 'old-user',
        userHash: 'old-hash',
        // In-memory cache: avoids path_provider (no platform channel in a
        // plain `test()`) and isolates each test from the on-disk cache file.
        cacheDatabase: CacheDatabase(NativeDatabase.memory()),
      );

      expect(controller.userId, 'old-user');
      expect(controller.userHash, 'old-hash');
      expect(controller.user, isNull);

      controller.updateIdentity(
        user: const WidgetUser(id: 'new-user'),
        userId: 'new-user',
        userHash: 'new-hash',
        identityToken: 'new-token',
      );

      expect(controller.userId, 'new-user');
      expect(controller.userHash, 'new-hash');
      expect(controller.user?.id, 'new-user');

      // SECURITY: a changed identity must trigger a reload (see
      // SynkoraChatController.updateIdentity) so a previous identity's
      // already-loaded messages never linger in memory under the new one.
      // Let that unawaited reload settle (it'll fail closed against the fake
      // host -- irrelevant here) before disposing.
      await pumpEventQueue();
      controller.dispose();
    });

    test(
        'starting with no identity, then identifying a user via updateIdentity, sticks',
        () async {
      final controller = SynkoraChatController(
        client: SynkoraClient(
            widgetKey: 'wk_test', baseUrl: 'https://example.test'),
        cacheDatabase: CacheDatabase(NativeDatabase.memory()),
      );

      expect(controller.userId, isNull);
      expect(controller.userHash, isNull);

      controller.updateIdentity(
        userId: 'late-user',
        userHash: 'late-hash',
      );

      expect(controller.userId, 'late-user');
      expect(controller.userHash, 'late-hash');

      await pumpEventQueue();
      controller.dispose();
    });
  });
}
