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
  TextColumn get convId => text().nullable()();
  TextColumn get role => text()(); // 'user' | 'assistant'
  TextColumn get content => text()();
  DateTimeColumn get ts => dateTime()();
  BoolColumn get isStreaming => boolean().withDefault(const Constant(false))();

  @override
  Set<Column> get primaryKey => {id, widgetKey};
}

// ---------------------------------------------------------------------------
// Database
// ---------------------------------------------------------------------------

@DriftDatabase(tables: [Messages])
class CacheDatabase extends _$CacheDatabase {
  CacheDatabase([QueryExecutor? executor]) : super(executor ?? _openConnection());

  @override
  int get schemaVersion => 1;

  static LazyDatabase _openConnection() {
    return LazyDatabase(() async {
      final dbFolder = await getApplicationDocumentsDirectory();
      final file = File(p.join(dbFolder.path, 'synkora_cache.db'));
      return NativeDatabase(file);
    });
  }
}
