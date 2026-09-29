import 'package:drift/drift.dart';

import '../client/models.dart';
import 'cache_database.dart';

/// Handles all SQLite read/write for chat messages.
///
/// SECURITY: every row is scoped by (widgetKey, identityKey). widgetKey alone
/// identifies the org's widget config, not the person using it -- it's the
/// same value for every rider on a given app build. identityKey must be the
/// caller's resolved user/session identity (see
/// SynkoraChatController._identityKey) so that a device previously used by
/// one identified user never surfaces that user's cached messages to the
/// next person who opens the chat. Never call these methods with a
/// widgetKey-only scope.
class LocalCache {
  final CacheDatabase _db;

  LocalCache(this._db);

  // ---------------------------------------------------------------------------
  // Load
  // ---------------------------------------------------------------------------

  Future<List<ChatMessage>> loadMessages(
    String widgetKey,
    String identityKey, {
    String? convId,
  }) async {
    final query = _db.select(_db.messages)
      ..where(
        (t) =>
            t.widgetKey.equals(widgetKey) & t.identityKey.equals(identityKey),
      )
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

  Future<void> upsertMessages(
    String widgetKey,
    String identityKey,
    List<ChatMessage> messages, {
    String? convId,
  }) async {
    await _db.batch((batch) {
      for (final msg in messages) {
        batch.insert(
          _db.messages,
          MessagesCompanion(
            id: Value(msg.id),
            widgetKey: Value(widgetKey),
            identityKey: Value(identityKey),
            convId: Value(convId),
            role: Value(_roleToString(msg.role)),
            content: Value(msg.content),
            ts: Value(msg.timestamp),
            isStreaming: Value(msg.isStreaming),
          ),
          mode: InsertMode.insertOrReplace,
        );
      }
    });
  }

  Future<void> upsertMessage(
    String widgetKey,
    String identityKey,
    ChatMessage msg, {
    String? convId,
  }) async {
    await _db.into(_db.messages).insertOnConflictUpdate(
          MessagesCompanion(
            id: Value(msg.id),
            widgetKey: Value(widgetKey),
            identityKey: Value(identityKey),
            convId: Value(convId),
            role: Value(_roleToString(msg.role)),
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
  Future<void> cleanupIncomplete(String widgetKey, String identityKey) async {
    await (_db.delete(_db.messages)
          ..where(
            (t) =>
                t.widgetKey.equals(widgetKey) &
                t.identityKey.equals(identityKey) &
                t.isStreaming.equals(true),
          ))
        .go();
  }

  Future<void> clearMessages(
    String widgetKey,
    String identityKey, {
    String? convId,
  }) async {
    final query = _db.delete(_db.messages)
      ..where(
        (t) =>
            t.widgetKey.equals(widgetKey) & t.identityKey.equals(identityKey),
      );
    if (convId != null) {
      query.where((t) => t.convId.equals(convId));
    }
    await query.go();
  }

  // ---------------------------------------------------------------------------
  // Private helpers
  // ---------------------------------------------------------------------------

  static String _roleToString(MessageRole role) => switch (role) {
        MessageRole.user => 'user',
        MessageRole.operator => 'operator',
        MessageRole.assistant => 'assistant',
      };

  static MessageRole _roleFromString(String role) => switch (role) {
        'user' => MessageRole.user,
        'operator' => MessageRole.operator,
        _ => MessageRole.assistant,
      };

  ChatMessage _rowToMessage(Message row) => ChatMessage(
        id: row.id,
        role: _roleFromString(row.role),
        content: row.content,
        timestamp: row.ts,
        isStreaming: row.isStreaming,
      );

  Future<void> close() => _db.close();
}
