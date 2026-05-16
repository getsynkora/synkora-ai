import 'dart:async';

import 'package:flutter/foundation.dart';

import '../cache/cache_database.dart';
import '../cache/local_cache.dart';
import '../client/models.dart';
import '../client/synkora_client.dart';

/// Public state API for the chat. Extend ChangeNotifier so any Flutter
/// widget can listen with ListenableBuilder or AnimatedBuilder.
class SynkoraChatController extends ChangeNotifier {
  final SynkoraClient _client;
  late final LocalCache _cache;

  final String? userId;
  final String? sessionId;

  SynkoraChatController({
    required SynkoraClient client,
    this.userId,
    this.sessionId,
    CacheDatabase? cacheDatabase,
  }) : _client = client {
    _cache = LocalCache(cacheDatabase ?? CacheDatabase());
  }

  // ---------------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------------

  List<ChatMessage> _messages = [];
  bool _isStreaming = false;
  bool _isLoading = false;
  String? _conversationId;
  WidgetConfig? _config;
  String? _error;
  String? _lastMessage; // for retry

  List<ChatMessage> get messages => List.unmodifiable(_messages);
  bool get isStreaming => _isStreaming;
  bool get isLoading => _isLoading;
  String? get conversationId => _conversationId;
  WidgetConfig? get config => _config;
  String? get error => _error;

  // ---------------------------------------------------------------------------
  // Init: load config + local cache + server history in parallel
  // ---------------------------------------------------------------------------

  Future<void> init() async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      // Clean up messages stuck mid-stream from a previous session
      await _cache.cleanupIncomplete(_client.widgetKey);

      // Load local cache immediately — gives instant display
      final cached = await _cache.loadMessages(_client.widgetKey);
      _messages = List.from(cached);
      notifyListeners();

      // Fetch config + server history in parallel
      final results = await Future.wait([
        _client.loadConfig(),
        _client.loadHistory(userId: userId, sessionId: sessionId),
      ]);

      _config = results[0] as WidgetConfig;

      // Merge server history: server wins by id
      final serverMessages = results[1] as List<ChatMessage>;
      if (serverMessages.isNotEmpty) {
        final byId = <String, ChatMessage>{};
        for (final m in _messages) {
          byId[m.id] = m;
        }
        for (final m in serverMessages) {
          byId[m.id] = m;
        }
        _messages = byId.values.toList()..sort((a, b) => a.timestamp.compareTo(b.timestamp));
        await _cache.upsertMessages(_client.widgetKey, _messages);
      }

      // Prepend welcome message as a virtual message (not stored in DB)
      final welcome = _config!.theme.welcomeMessage;
      if (welcome.isNotEmpty && _messages.isEmpty) {
        _messages = [
          ChatMessage(
            id: 'welcome',
            role: MessageRole.assistant,
            content: welcome,
            timestamp: DateTime.fromMillisecondsSinceEpoch(0),
          ),
        ];
      }
    } catch (e) {
      _error = e.toString();
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  // ---------------------------------------------------------------------------
  // Send
  // ---------------------------------------------------------------------------

  Future<void> send(String text) async {
    if (_isStreaming || text.trim().isEmpty) return;
    _lastMessage = text;
    _error = null;

    // Optimistic: add user message immediately
    final userMsg = ChatMessage(
      id: 'local_${DateTime.now().millisecondsSinceEpoch}',
      role: MessageRole.user,
      content: text,
      timestamp: DateTime.now(),
    );
    _messages = [..._messages, userMsg];
    await _cache.upsertMessage(_client.widgetKey, userMsg, convId: _conversationId);

    // Add streaming placeholder for assistant
    final streamingId = 'streaming_${DateTime.now().millisecondsSinceEpoch}';
    final streamingMsg = ChatMessage(
      id: streamingId,
      role: MessageRole.assistant,
      content: '',
      timestamp: DateTime.now(),
      isStreaming: true,
    );
    _messages = [..._messages, streamingMsg];
    _isStreaming = true;
    notifyListeners();

    final buffer = StringBuffer();

    try {
      final stream = _client.sendMessage(
        text,
        conversationId: _conversationId,
        sessionId: sessionId,
      );

      await for (final event in stream) {
        if (event is TextChunkEvent) {
          buffer.write(event.content);
          _updateStreamingMessage(streamingId, buffer.toString());
        } else if (event is DoneEvent) {
          _conversationId = event.conversationId ?? _conversationId;
          _finalizeStreamingMessage(streamingId, buffer.toString());
          await _cache.upsertMessage(
            _client.widgetKey,
            _messages.firstWhere((m) => m.id == streamingId),
            convId: _conversationId,
          );
        } else if (event is ErrorEvent) {
          _removeMessage(streamingId);
          _error = event.message;
          _isStreaming = false;
          notifyListeners();
          return;
        }
      }
    } catch (e) {
      _removeMessage(streamingId);
      _error = e.toString();
    } finally {
      _isStreaming = false;
      notifyListeners();
    }
  }

  void retry() {
    if (_lastMessage != null && !_isStreaming) {
      send(_lastMessage!);
    }
  }

  // ---------------------------------------------------------------------------
  // Private helpers
  // ---------------------------------------------------------------------------

  void _updateStreamingMessage(String id, String content) {
    _messages = _messages.map((m) {
      if (m.id == id) return m.copyWith(content: content);
      return m;
    }).toList();
    notifyListeners();
  }

  void _finalizeStreamingMessage(String id, String content) {
    _messages = _messages.map((m) {
      if (m.id == id) return m.copyWith(content: content, isStreaming: false);
      return m;
    }).toList();
    notifyListeners();
  }

  void _removeMessage(String id) {
    _messages = _messages.where((m) => m.id != id).toList();
  }

  // ---------------------------------------------------------------------------
  // Dispose
  // ---------------------------------------------------------------------------

  @override
  void dispose() {
    _client.dispose();
    _cache.close();
    super.dispose();
  }
}
