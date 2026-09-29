import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:synkora_chat/src/cache/cache_database.dart';
import 'package:synkora_chat/src/cache/local_cache.dart';
import 'package:synkora_chat/src/client/models.dart';

/// Regression test for the cross-user chat history leak: a device previously
/// used by rider A must never surface A's cached messages to rider B, even
/// though both share the same widgetKey (it's the org's widget config, not a
/// per-person value).
void main() {
  late LocalCache cache;

  setUp(() {
    cache = LocalCache(CacheDatabase(NativeDatabase.memory()));
  });

  tearDown(() => cache.close());

  ChatMessage msg(String id, String content) => ChatMessage(
        id: id,
        role: MessageRole.user,
        content: content,
        timestamp: DateTime(2026, 9, 27, 11, 59),
      );

  test(
    'messages cached under one identity are invisible to a different identity on the same widgetKey',
    () async {
      const widgetKey = 'wk_shared_device';

      // Rider A (+8809810) discusses a refund for trip #E09221.
      await cache.upsertMessages(
        widgetKey,
        'rider_+8809810',
        [
          msg('m1',
              'refund for trip #E09221, GPS: Borhan Uddin Chowdhury Rd -> Banshbaria')
        ],
        convId: 'conv_a',
      );

      // Rider B (+8809813) opens chat on the same physical device.
      final riderBView = await cache.loadMessages(widgetKey, 'rider_+8809813');

      expect(riderBView, isEmpty);

      // Rider A's own reload still sees their own history.
      final riderAView = await cache.loadMessages(widgetKey, 'rider_+8809810');
      expect(riderAView, hasLength(1));
      expect(riderAView.single.content, contains('E09221'));
    },
  );

  test('clearMessages only clears the calling identity\'s rows', () async {
    const widgetKey = 'wk_shared_device';
    await cache.upsertMessages(widgetKey, 'rider_a', [msg('m1', 'a says hi')]);
    await cache.upsertMessages(widgetKey, 'rider_b', [msg('m2', 'b says hi')]);

    await cache.clearMessages(widgetKey, 'rider_a');

    expect(await cache.loadMessages(widgetKey, 'rider_a'), isEmpty);
    expect(await cache.loadMessages(widgetKey, 'rider_b'), hasLength(1));
  });
}
