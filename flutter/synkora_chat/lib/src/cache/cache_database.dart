import 'dart:io';

import 'package:drift/drift.dart';
import 'package:drift/native.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

part 'cache_database.g.dart';

// ---------------------------------------------------------------------------
// Table definition
// ---------------------------------------------------------------------------

class Messages extends Table {
  TextColumn get id => text()();
  TextColumn get widgetKey => text()();
  // Scopes cached rows to the identity (userId, or sessionId when
  // unidentified) that loaded them. widgetKey alone is shared by every rider
  // on a given org's build, so without this a device that's been used by
  // more than one identified user would surface one user's whole chat
  // history to the next person who opens the widget. See SECURITY note on
  // LocalCache.
  TextColumn get identityKey => text()();
  TextColumn get convId => text().nullable()();
  TextColumn get role => text()(); // 'user' | 'assistant' | 'operator'
  TextColumn get content => text()();
  DateTimeColumn get ts => dateTime()();
  BoolColumn get isStreaming => boolean().withDefault(const Constant(false))();

  @override
  Set<Column> get primaryKey => {id, widgetKey, identityKey};
}

// ---------------------------------------------------------------------------
// Database
// ---------------------------------------------------------------------------

@DriftDatabase(tables: [Messages])
class CacheDatabase extends _$CacheDatabase {
  CacheDatabase([QueryExecutor? executor])
      : super(executor ?? _openConnection());

  @override
  int get schemaVersion => 2;

  @override
  MigrationStrategy get migration => MigrationStrategy(
        onCreate: (m) => m.createAll(),
        onUpgrade: (m, from, to) async {
          if (from < 2) {
            // SECURITY (v1 -> v2): v1 rows were keyed only by widgetKey, which is
            // shared by every identity on a device -- that's precisely the
            // cross-user leak this migration exists to close. Never carry that
            // unscoped data forward; this is a pure cache the server always
            // re-syncs, so dropping it is safe.
            await m.deleteTable(messages.actualTableName);
            await m.createTable(messages);
          }
        },
      );

  static LazyDatabase _openConnection() {
    return LazyDatabase(() async {
      final dbFolder = await getApplicationDocumentsDirectory();
      final file = File(p.join(dbFolder.path, 'synkora_cache.db'));
      return NativeDatabase(file);
    });
  }
}
