import 'package:drift/drift.dart';

import '../client/models.dart';
import 'cache_database.dart';

/// Handles all SQLite read/write for chat messages.
class LocalCache {
  final CacheDatabase _db;

  LocalCache(this._db);

  // ---------------------------------------------------------------------------
  // Load
  // ---------------------------------------------------------------------------

  Future<List<ChatMessage>> loadMessages(String widgetKey, {String? convId}) async {
    final query = _db.select(_db.messages)
      ..where((t) => t.widgetKey.equals(widgetKey))
      ..orderBy([(t) => OrderingTerm.asc(t.ts)]);

    if (convId != null) {
      query.where((t) => t.convId.equals(convId));
    }

    final rows = await query.get();
    return rows.map(_rowToMessage).toList();
  }

  // ---------------------------------------------------------------------------
  // Save / upsert
  // ---------------------------------------------------------------------------

  Future<void> upsertMessages(String widgetKey, List<ChatMessage> messages) async {
    await _db.batch((batch) {
      for (final msg in messages) {
        batch.insert(
          _db.messages,
          MessagesCompanion(
            id: Value(msg.id),
            widgetKey: Value(widgetKey),
            convId: Value(msg.id), // convId stored separately when available
            role: Value(msg.role == MessageRole.user ? 'user' : 'assistant'),
            content: Value(msg.content),
            ts: Value(msg.timestamp),
            isStreaming: Value(msg.isStreaming),
          ),
          mode: InsertMode.insertOrReplace,
        );
      }
    });
  }

  Future<void> upsertMessage(String widgetKey, ChatMessage msg, {String? convId}) async {
    await _db.into(_db.messages).insertOnConflictUpdate(
          MessagesCompanion(
            id: Value(msg.id),
            widgetKey: Value(widgetKey),
            convId: Value(convId),
            role: Value(msg.role == MessageRole.user ? 'user' : 'assistant'),
            content: Value(msg.content),
            ts: Value(msg.timestamp),
            isStreaming: Value(msg.isStreaming),
          ),
        );
  }

  // ---------------------------------------------------------------------------
  // Cleanup
  // ---------------------------------------------------------------------------

  /// Removes messages left in streaming state (app was killed mid-stream).
  Future<void> cleanupIncomplete(String widgetKey) async {
    await (_db.delete(_db.messages)
          ..where((t) => t.widgetKey.equals(widgetKey) & t.isStreaming.equals(true)))
        .go();
  }

  // ---------------------------------------------------------------------------
  // Private helpers
  // ---------------------------------------------------------------------------

  ChatMessage _rowToMessage(Message row) => ChatMessage(
        id: row.id,
        role: row.role == 'user' ? MessageRole.user : MessageRole.assistant,
        content: row.content,
        timestamp: row.ts,
        isStreaming: row.isStreaming,
      );

  Future<void> close() => _db.close();
}
