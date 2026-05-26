// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'cache_database.dart';

// ignore_for_file: type=lint
class $MessagesTable extends Messages with TableInfo<$MessagesTable, Message> {
  @override
  final GeneratedDatabase attachedDatabase;
  final String? _alias;
  $MessagesTable(this.attachedDatabase, [this._alias]);
  static const VerificationMeta _idMeta = const VerificationMeta('id');
  @override
  late final GeneratedColumn<String> id = GeneratedColumn<String>(
    'id',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _widgetKeyMeta = const VerificationMeta(
    'widgetKey',
  );
  @override
  late final GeneratedColumn<String> widgetKey = GeneratedColumn<String>(
    'widget_key',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _convIdMeta = const VerificationMeta('convId');
  @override
  late final GeneratedColumn<String> convId = GeneratedColumn<String>(
    'conv_id',
    aliasedName,
    true,
    type: DriftSqlType.string,
    requiredDuringInsert: false,
  );
  static const VerificationMeta _roleMeta = const VerificationMeta('role');
  @override
  late final GeneratedColumn<String> role = GeneratedColumn<String>(
    'role',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _contentMeta = const VerificationMeta(
    'content',
  );
  @override
  late final GeneratedColumn<String> content = GeneratedColumn<String>(
    'content',
    aliasedName,
    false,
    type: DriftSqlType.string,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _tsMeta = const VerificationMeta('ts');
  @override
  late final GeneratedColumn<DateTime> ts = GeneratedColumn<DateTime>(
    'ts',
    aliasedName,
    false,
    type: DriftSqlType.dateTime,
    requiredDuringInsert: true,
  );
  static const VerificationMeta _isStreamingMeta = const VerificationMeta(
    'isStreaming',
  );
  @override
  late final GeneratedColumn<bool> isStreaming = GeneratedColumn<bool>(
    'is_streaming',
    aliasedName,
    false,
    type: DriftSqlType.bool,
    requiredDuringInsert: false,
    defaultConstraints: GeneratedColumn.constraintIsAlways(
      'CHECK ("is_streaming" IN (0, 1))',
    ),
    defaultValue: const Constant(false),
  );
  @override
  List<GeneratedColumn> get $columns => [
    id,
    widgetKey,
    convId,
    role,
    content,
    ts,
    isStreaming,
  ];
  @override
  String get aliasedName => _alias ?? actualTableName;
  @override
  String get actualTableName => $name;
  static const String $name = 'messages';
  @override
  VerificationContext validateIntegrity(
    Insertable<Message> instance, {
    bool isInserting = false,
  }) {
    final context = VerificationContext();
    final data = instance.toColumns(true);
    if (data.containsKey('id')) {
      context.handle(_idMeta, id.isAcceptableOrUnknown(data['id']!, _idMeta));
    } else if (isInserting) {
      context.missing(_idMeta);
    }
    if (data.containsKey('widget_key')) {
      context.handle(
        _widgetKeyMeta,
        widgetKey.isAcceptableOrUnknown(data['widget_key']!, _widgetKeyMeta),
      );
    } else if (isInserting) {
      context.missing(_widgetKeyMeta);
    }
    if (data.containsKey('conv_id')) {
      context.handle(
        _convIdMeta,
        convId.isAcceptableOrUnknown(data['conv_id']!, _convIdMeta),
      );
    }
    if (data.containsKey('role')) {
      context.handle(
        _roleMeta,
        role.isAcceptableOrUnknown(data['role']!, _roleMeta),
      );
    } else if (isInserting) {
      context.missing(_roleMeta);
    }
    if (data.containsKey('content')) {
      context.handle(
        _contentMeta,
        content.isAcceptableOrUnknown(data['content']!, _contentMeta),
      );
    } else if (isInserting) {
      context.missing(_contentMeta);
    }
    if (data.containsKey('ts')) {
      context.handle(_tsMeta, ts.isAcceptableOrUnknown(data['ts']!, _tsMeta));
    } else if (isInserting) {
      context.missing(_tsMeta);
    }
    if (data.containsKey('is_streaming')) {
      context.handle(
        _isStreamingMeta,
        isStreaming.isAcceptableOrUnknown(
          data['is_streaming']!,
          _isStreamingMeta,
        ),
      );
    }
    return context;
  }

  @override
  Set<GeneratedColumn> get $primaryKey => {id, widgetKey};
  @override
  Message map(Map<String, dynamic> data, {String? tablePrefix}) {
    final effectivePrefix = tablePrefix != null ? '$tablePrefix.' : '';
    return Message(
      id: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}id'],
      )!,
      widgetKey: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}widget_key'],
      )!,
      convId: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}conv_id'],
      ),
      role: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}role'],
      )!,
      content: attachedDatabase.typeMapping.read(
        DriftSqlType.string,
        data['${effectivePrefix}content'],
      )!,
      ts: attachedDatabase.typeMapping.read(
        DriftSqlType.dateTime,
        data['${effectivePrefix}ts'],
      )!,
      isStreaming: attachedDatabase.typeMapping.read(
        DriftSqlType.bool,
        data['${effectivePrefix}is_streaming'],
      )!,
    );
  }

  @override
  $MessagesTable createAlias(String alias) {
    return $MessagesTable(attachedDatabase, alias);
  }
}

class Message extends DataClass implements Insertable<Message> {
  final String id;
  final String widgetKey;
  final String? convId;
  final String role;
  final String content;
  final DateTime ts;
  final bool isStreaming;
  const Message({
    required this.id,
    required this.widgetKey,
    this.convId,
    required this.role,
    required this.content,
    required this.ts,
    required this.isStreaming,
  });
  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    map['id'] = Variable<String>(id);
    map['widget_key'] = Variable<String>(widgetKey);
    if (!nullToAbsent || convId != null) {
      map['conv_id'] = Variable<String>(convId);
    }
    map['role'] = Variable<String>(role);
    map['content'] = Variable<String>(content);
    map['ts'] = Variable<DateTime>(ts);
    map['is_streaming'] = Variable<bool>(isStreaming);
    return map;
  }

  MessagesCompanion toCompanion(bool nullToAbsent) {
    return MessagesCompanion(
      id: Value(id),
      widgetKey: Value(widgetKey),
      convId: convId == null && nullToAbsent
          ? const Value.absent()
          : Value(convId),
      role: Value(role),
      content: Value(content),
      ts: Value(ts),
      isStreaming: Value(isStreaming),
    );
  }

  factory Message.fromJson(
    Map<String, dynamic> json, {
    ValueSerializer? serializer,
  }) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return Message(
      id: serializer.fromJson<String>(json['id']),
      widgetKey: serializer.fromJson<String>(json['widgetKey']),
      convId: serializer.fromJson<String?>(json['convId']),
      role: serializer.fromJson<String>(json['role']),
      content: serializer.fromJson<String>(json['content']),
      ts: serializer.fromJson<DateTime>(json['ts']),
      isStreaming: serializer.fromJson<bool>(json['isStreaming']),
    );
  }
  @override
  Map<String, dynamic> toJson({ValueSerializer? serializer}) {
    serializer ??= driftRuntimeOptions.defaultSerializer;
    return <String, dynamic>{
      'id': serializer.toJson<String>(id),
      'widgetKey': serializer.toJson<String>(widgetKey),
      'convId': serializer.toJson<String?>(convId),
      'role': serializer.toJson<String>(role),
      'content': serializer.toJson<String>(content),
      'ts': serializer.toJson<DateTime>(ts),
      'isStreaming': serializer.toJson<bool>(isStreaming),
    };
  }

  Message copyWith({
    String? id,
    String? widgetKey,
    Value<String?> convId = const Value.absent(),
    String? role,
    String? content,
    DateTime? ts,
    bool? isStreaming,
  }) => Message(
    id: id ?? this.id,
    widgetKey: widgetKey ?? this.widgetKey,
    convId: convId.present ? convId.value : this.convId,
    role: role ?? this.role,
    content: content ?? this.content,
    ts: ts ?? this.ts,
    isStreaming: isStreaming ?? this.isStreaming,
  );
  Message copyWithCompanion(MessagesCompanion data) {
    return Message(
      id: data.id.present ? data.id.value : this.id,
      widgetKey: data.widgetKey.present ? data.widgetKey.value : this.widgetKey,
      convId: data.convId.present ? data.convId.value : this.convId,
      role: data.role.present ? data.role.value : this.role,
      content: data.content.present ? data.content.value : this.content,
      ts: data.ts.present ? data.ts.value : this.ts,
      isStreaming: data.isStreaming.present
          ? data.isStreaming.value
          : this.isStreaming,
    );
  }

  @override
  String toString() {
    return (StringBuffer('Message(')
          ..write('id: $id, ')
          ..write('widgetKey: $widgetKey, ')
          ..write('convId: $convId, ')
          ..write('role: $role, ')
          ..write('content: $content, ')
          ..write('ts: $ts, ')
          ..write('isStreaming: $isStreaming')
          ..write(')'))
        .toString();
  }

  @override
  int get hashCode =>
      Object.hash(id, widgetKey, convId, role, content, ts, isStreaming);
  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      (other is Message &&
          other.id == this.id &&
          other.widgetKey == this.widgetKey &&
          other.convId == this.convId &&
          other.role == this.role &&
          other.content == this.content &&
          other.ts == this.ts &&
          other.isStreaming == this.isStreaming);
}

class MessagesCompanion extends UpdateCompanion<Message> {
  final Value<String> id;
  final Value<String> widgetKey;
  final Value<String?> convId;
  final Value<String> role;
  final Value<String> content;
  final Value<DateTime> ts;
  final Value<bool> isStreaming;
  final Value<int> rowid;
  const MessagesCompanion({
    this.id = const Value.absent(),
    this.widgetKey = const Value.absent(),
    this.convId = const Value.absent(),
    this.role = const Value.absent(),
    this.content = const Value.absent(),
    this.ts = const Value.absent(),
    this.isStreaming = const Value.absent(),
    this.rowid = const Value.absent(),
  });
  MessagesCompanion.insert({
    required String id,
    required String widgetKey,
    this.convId = const Value.absent(),
    required String role,
    required String content,
    required DateTime ts,
    this.isStreaming = const Value.absent(),
    this.rowid = const Value.absent(),
  }) : id = Value(id),
       widgetKey = Value(widgetKey),
       role = Value(role),
       content = Value(content),
       ts = Value(ts);
  static Insertable<Message> custom({
    Expression<String>? id,
    Expression<String>? widgetKey,
    Expression<String>? convId,
    Expression<String>? role,
    Expression<String>? content,
    Expression<DateTime>? ts,
    Expression<bool>? isStreaming,
    Expression<int>? rowid,
  }) {
    return RawValuesInsertable({
      if (id != null) 'id': id,
      if (widgetKey != null) 'widget_key': widgetKey,
      if (convId != null) 'conv_id': convId,
      if (role != null) 'role': role,
      if (content != null) 'content': content,
      if (ts != null) 'ts': ts,
      if (isStreaming != null) 'is_streaming': isStreaming,
      if (rowid != null) 'rowid': rowid,
    });
  }

  MessagesCompanion copyWith({
    Value<String>? id,
    Value<String>? widgetKey,
    Value<String?>? convId,
    Value<String>? role,
    Value<String>? content,
    Value<DateTime>? ts,
    Value<bool>? isStreaming,
    Value<int>? rowid,
  }) {
    return MessagesCompanion(
      id: id ?? this.id,
      widgetKey: widgetKey ?? this.widgetKey,
      convId: convId ?? this.convId,
      role: role ?? this.role,
      content: content ?? this.content,
      ts: ts ?? this.ts,
      isStreaming: isStreaming ?? this.isStreaming,
      rowid: rowid ?? this.rowid,
    );
  }

  @override
  Map<String, Expression> toColumns(bool nullToAbsent) {
    final map = <String, Expression>{};
    if (id.present) {
      map['id'] = Variable<String>(id.value);
    }
    if (widgetKey.present) {
      map['widget_key'] = Variable<String>(widgetKey.value);
    }
    if (convId.present) {
      map['conv_id'] = Variable<String>(convId.value);
    }
    if (role.present) {
      map['role'] = Variable<String>(role.value);
    }
    if (content.present) {
      map['content'] = Variable<String>(content.value);
    }
    if (ts.present) {
      map['ts'] = Variable<DateTime>(ts.value);
    }
    if (isStreaming.present) {
      map['is_streaming'] = Variable<bool>(isStreaming.value);
    }
    if (rowid.present) {
      map['rowid'] = Variable<int>(rowid.value);
    }
    return map;
  }

  @override
  String toString() {
    return (StringBuffer('MessagesCompanion(')
          ..write('id: $id, ')
          ..write('widgetKey: $widgetKey, ')
          ..write('convId: $convId, ')
          ..write('role: $role, ')
          ..write('content: $content, ')
          ..write('ts: $ts, ')
          ..write('isStreaming: $isStreaming, ')
          ..write('rowid: $rowid')
          ..write(')'))
        .toString();
  }
}

abstract class _$CacheDatabase extends GeneratedDatabase {
  _$CacheDatabase(QueryExecutor e) : super(e);
  $CacheDatabaseManager get managers => $CacheDatabaseManager(this);
  late final $MessagesTable messages = $MessagesTable(this);
  @override
  Iterable<TableInfo<Table, Object?>> get allTables =>
      allSchemaEntities.whereType<TableInfo<Table, Object?>>();
  @override
  List<DatabaseSchemaEntity> get allSchemaEntities => [messages];
}

typedef $$MessagesTableCreateCompanionBuilder =
    MessagesCompanion Function({
      required String id,
      required String widgetKey,
      Value<String?> convId,
      required String role,
      required String content,
      required DateTime ts,
      Value<bool> isStreaming,
      Value<int> rowid,
    });
typedef $$MessagesTableUpdateCompanionBuilder =
    MessagesCompanion Function({
      Value<String> id,
      Value<String> widgetKey,
      Value<String?> convId,
      Value<String> role,
      Value<String> content,
      Value<DateTime> ts,
      Value<bool> isStreaming,
      Value<int> rowid,
    });

class $$MessagesTableFilterComposer
    extends Composer<_$CacheDatabase, $MessagesTable> {
  $$MessagesTableFilterComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnFilters<String> get id => $composableBuilder(
    column: $table.id,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get widgetKey => $composableBuilder(
    column: $table.widgetKey,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get convId => $composableBuilder(
    column: $table.convId,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get role => $composableBuilder(
    column: $table.role,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<String> get content => $composableBuilder(
    column: $table.content,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<DateTime> get ts => $composableBuilder(
    column: $table.ts,
    builder: (column) => ColumnFilters(column),
  );

  ColumnFilters<bool> get isStreaming => $composableBuilder(
    column: $table.isStreaming,
    builder: (column) => ColumnFilters(column),
  );
}

class $$MessagesTableOrderingComposer
    extends Composer<_$CacheDatabase, $MessagesTable> {
  $$MessagesTableOrderingComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  ColumnOrderings<String> get id => $composableBuilder(
    column: $table.id,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get widgetKey => $composableBuilder(
    column: $table.widgetKey,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get convId => $composableBuilder(
    column: $table.convId,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get role => $composableBuilder(
    column: $table.role,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<String> get content => $composableBuilder(
    column: $table.content,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<DateTime> get ts => $composableBuilder(
    column: $table.ts,
    builder: (column) => ColumnOrderings(column),
  );

  ColumnOrderings<bool> get isStreaming => $composableBuilder(
    column: $table.isStreaming,
    builder: (column) => ColumnOrderings(column),
  );
}

class $$MessagesTableAnnotationComposer
    extends Composer<_$CacheDatabase, $MessagesTable> {
  $$MessagesTableAnnotationComposer({
    required super.$db,
    required super.$table,
    super.joinBuilder,
    super.$addJoinBuilderToRootComposer,
    super.$removeJoinBuilderFromRootComposer,
  });
  GeneratedColumn<String> get id =>
      $composableBuilder(column: $table.id, builder: (column) => column);

  GeneratedColumn<String> get widgetKey =>
      $composableBuilder(column: $table.widgetKey, builder: (column) => column);

  GeneratedColumn<String> get convId =>
      $composableBuilder(column: $table.convId, builder: (column) => column);

  GeneratedColumn<String> get role =>
      $composableBuilder(column: $table.role, builder: (column) => column);

  GeneratedColumn<String> get content =>
      $composableBuilder(column: $table.content, builder: (column) => column);

  GeneratedColumn<DateTime> get ts =>
      $composableBuilder(column: $table.ts, builder: (column) => column);

  GeneratedColumn<bool> get isStreaming => $composableBuilder(
    column: $table.isStreaming,
    builder: (column) => column,
  );
}

class $$MessagesTableTableManager
    extends
        RootTableManager<
          _$CacheDatabase,
          $MessagesTable,
          Message,
          $$MessagesTableFilterComposer,
          $$MessagesTableOrderingComposer,
          $$MessagesTableAnnotationComposer,
          $$MessagesTableCreateCompanionBuilder,
          $$MessagesTableUpdateCompanionBuilder,
          (Message, BaseReferences<_$CacheDatabase, $MessagesTable, Message>),
          Message,
          PrefetchHooks Function()
        > {
  $$MessagesTableTableManager(_$CacheDatabase db, $MessagesTable table)
    : super(
        TableManagerState(
          db: db,
          table: table,
          createFilteringComposer: () =>
              $$MessagesTableFilterComposer($db: db, $table: table),
          createOrderingComposer: () =>
              $$MessagesTableOrderingComposer($db: db, $table: table),
          createComputedFieldComposer: () =>
              $$MessagesTableAnnotationComposer($db: db, $table: table),
          updateCompanionCallback:
              ({
                Value<String> id = const Value.absent(),
                Value<String> widgetKey = const Value.absent(),
                Value<String?> convId = const Value.absent(),
                Value<String> role = const Value.absent(),
                Value<String> content = const Value.absent(),
                Value<DateTime> ts = const Value.absent(),
                Value<bool> isStreaming = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => MessagesCompanion(
                id: id,
                widgetKey: widgetKey,
                convId: convId,
                role: role,
                content: content,
                ts: ts,
                isStreaming: isStreaming,
                rowid: rowid,
              ),
          createCompanionCallback:
              ({
                required String id,
                required String widgetKey,
                Value<String?> convId = const Value.absent(),
                required String role,
                required String content,
                required DateTime ts,
                Value<bool> isStreaming = const Value.absent(),
                Value<int> rowid = const Value.absent(),
              }) => MessagesCompanion.insert(
                id: id,
                widgetKey: widgetKey,
                convId: convId,
                role: role,
                content: content,
                ts: ts,
                isStreaming: isStreaming,
                rowid: rowid,
              ),
          withReferenceMapper: (p0) => p0
              .map((e) => (e.readTable(table), BaseReferences(db, table, e)))
              .toList(),
          prefetchHooksCallback: null,
        ),
      );
}

typedef $$MessagesTableProcessedTableManager =
    ProcessedTableManager<
      _$CacheDatabase,
      $MessagesTable,
      Message,
      $$MessagesTableFilterComposer,
      $$MessagesTableOrderingComposer,
      $$MessagesTableAnnotationComposer,
      $$MessagesTableCreateCompanionBuilder,
      $$MessagesTableUpdateCompanionBuilder,
      (Message, BaseReferences<_$CacheDatabase, $MessagesTable, Message>),
      Message,
      PrefetchHooks Function()
    >;

class $CacheDatabaseManager {
  final _$CacheDatabase _db;
  $CacheDatabaseManager(this._db);
  $$MessagesTableTableManager get messages =>
      $$MessagesTableTableManager(_db, _db.messages);
}
