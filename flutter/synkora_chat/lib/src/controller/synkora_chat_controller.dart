import 'dart:async';

import 'package:flutter/foundation.dart';

import '../cache/cache_database.dart';
import '../cache/local_cache.dart';
import '../client/models.dart';
import '../client/synkora_client.dart';

/// How long before an inactive session is automatically closed.
const _kInactivityDuration = Duration(hours: 1);

/// Public state API for the chat. Extend ChangeNotifier so any Flutter
/// widget can listen with ListenableBuilder or AnimatedBuilder.
class SynkoraChatController extends ChangeNotifier {
  final SynkoraClient _client;
  late final LocalCache _cache;

  String? userId;
  final String? sessionId;
  WidgetUser? user;
  String? userHash;

  SynkoraChatController({
    required SynkoraClient client,
    this.userId,
    this.sessionId,
    this.user,
    this.userHash,
    String? identityToken,
    CacheDatabase? cacheDatabase,
  }) : _client = client {
    _cache = LocalCache(cacheDatabase ?? CacheDatabase());
    _client.setIdentity(
        userId: user?.id ?? userId, userHash: userHash, token: identityToken);
  }

  /// Refresh the identified user / identity proof after construction — e.g. when
  /// your app fetches a fresh userHash or identityToken asynchronously, after the
  /// controller (and [SynkoraChatWidget]) were already built once.
  ///
  /// Without calling this, a rebuilt [SynkoraChatWidget] with new userHash/
  /// identityToken/user/userId props is NOT picked up: the controller — and the
  /// underlying [SynkoraClient]'s stored identity headers — otherwise keep
  /// whatever was passed in at the very first build, indefinitely, since
  /// [userHash] and identityToken are otherwise only ever set once in the
  /// constructor. [SynkoraChatWidget] calls this automatically via
  /// didUpdateWidget when it owns the controller; call it yourself if you
  /// construct and own a [SynkoraChatController] directly.
  void updateIdentity({
    WidgetUser? user,
    String? userId,
    String? userHash,
    String? identityToken,
  }) {
    this.user = user;
    this.userId = userId;
    this.userHash = userHash;
    _client.setIdentity(
        userId: user?.id ?? userId, userHash: userHash, token: identityToken);
  }

  // ---------------------------------------------------------------------------
  // Programmatic message trigger (for external button-driven sends)
  // ---------------------------------------------------------------------------

  final _messageTriggerController = StreamController<String>.broadcast();

  /// Stream the widget listens to for externally-triggered messages.
  Stream<String> get messageTriggerStream => _messageTriggerController.stream;

  /// Send a message programmatically — e.g. from a button outside the widget.
  /// When [SynkoraChatWidget] is used, it also switches the view to the chat screen.
  /// No-ops if [text] is blank or if already streaming.
  void triggerMessage(String text) {
    if (text.trim().isEmpty || _isStreaming) return;
    _messageTriggerController.add(text);
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

  // Sessions list
  List<WidgetSession> _sessions = [];
  bool _sessionsLoading = false;

  // When true, the next send() creates a new session instead of resuming
  bool _forceNewOnNextSend = false;

  // Handoff / approval state
  bool _isHandoffActive = false;
  ApprovalRequiredEvent? _pendingApproval;
  Timer? _handoffPollTimer;
  final Set<String> _seenOperatorMsgIds = {};

  // Throttle streaming renders to ~20fps so MarkdownBody doesn't re-parse
  // the growing content on every chunk (which is O(n²) over a full response).
  // Chunks still accumulate in the StringBuffer every call; only notifyListeners
  // is gated. Flushed immediately on DoneEvent/ErrorEvent so final state is instant.
  Timer? _renderFlushTimer;

  // Pre-chat form collected values (name, email, phone)
  String? _preChatName;
  String? _preChatEmail;
  String? _preChatPhone;
  bool _preChatSubmitted = false;

  // Inactivity timer
  Timer? _inactivityTimer;

  List<ChatMessage> get messages => List.unmodifiable(_messages);
  bool get isStreaming => _isStreaming;
  bool get isLoading => _isLoading;
  String? get conversationId => _conversationId;
  WidgetConfig? get config => _config;
  String? get error => _error;
  bool get isHandoffActive => _isHandoffActive;
  ApprovalRequiredEvent? get pendingApproval => _pendingApproval;
  bool get hasConversationContent =>
      _messages.any((m) => m.content.trim().isNotEmpty);

  /// Whether the pre-chat form should be shown.
  /// True when: form is enabled in config, user is not already identified,
  /// and the form hasn't been submitted/skipped yet in this session.
  bool get shouldShowPreChatForm {
    if (_preChatSubmitted) return false;
    final formConfig = _config?.preChatForm;
    if (formConfig == null || !formConfig.enabled) return false;
    // If user is already identified via userId/user, skip the form
    if (userId != null || user != null) return false;
    return true;
  }

  bool get preChatSubmitted => _preChatSubmitted;

  List<WidgetSession> get sessions => List.unmodifiable(_sessions);
  bool get sessionsLoading => _sessionsLoading;

  /// True when the current conversation is closed (read-only).
  bool get isCurrentSessionClosed {
    if (_conversationId == null) return false;
    try {
      final session = _sessions.firstWhere((s) => s.id == _conversationId);
      return !session.isActive;
    } catch (_) {
      return false;
    }
  }

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

      // Fetch config + session list + server history in parallel
      final historyUserId = user?.id ?? userId;
      final futures = <Future>[
        _client.loadConfig(),
        _client.loadHistoryBundle(userId: historyUserId, sessionId: sessionId),
        if (historyUserId != null) _client.listSessions(userId: historyUserId),
      ];
      final results = await Future.wait(futures);

      _config = results[0] as WidgetConfig;

      // Merge server history: server wins by id
      final history = results[1] as WidgetChatHistory;
      _conversationId = history.conversationId ?? _conversationId;
      final serverMessages = history.messages;
      if (serverMessages.isNotEmpty) {
        final byId = <String, ChatMessage>{};
        for (final m in _messages) {
          byId[m.id] = m;
        }
        for (final m in serverMessages) {
          byId[m.id] = m;
        }
        _messages = byId.values.toList()
          ..sort((a, b) => a.timestamp.compareTo(b.timestamp));
        await _cache.upsertMessages(
          _client.widgetKey,
          _messages,
          convId: _conversationId,
        );
      }

      // Populate sessions list
      if (historyUserId != null && results.length > 2) {
        _sessions = results[2] as List<WidgetSession>;
        // Auto-open the most recent active session if we don't have a conversation yet
        if (_conversationId == null && _sessions.isNotEmpty) {
          final mostRecent = _sessions.first;
          if (mostRecent.isActive) {
            _conversationId = mostRecent.id;
            _resetInactivityTimer();
          }
        }
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
    _resetInactivityTimer();

    // Optimistic: render user message + streaming placeholder in one frame before
    // any async work so the UI responds instantly on tap.
    final userMsg = ChatMessage(
      id: 'local_${DateTime.now().millisecondsSinceEpoch}',
      role: MessageRole.user,
      content: text,
      timestamp: DateTime.now(),
    );
    final streamingId = 'streaming_${DateTime.now().millisecondsSinceEpoch}';
    final streamingMsg = ChatMessage(
      id: streamingId,
      role: MessageRole.assistant,
      content: '',
      timestamp: DateTime.now(),
      isStreaming: true,
    );
    _messages = [..._messages, userMsg, streamingMsg];
    _isStreaming = true;
    notifyListeners(); // immediate — user sees their message + dots in the same frame

    // Persist user message to local cache async — non-blocking, cache is not
    // the source of truth (server history is fetched on reload).
    unawaited(
      _cache.upsertMessage(_client.widgetKey, userMsg, convId: _conversationId),
    );

    final buffer = StringBuffer();

    try {
      // If only userId is provided (no WidgetUser), synthesise a minimal user
      // context so the API stamps external_user_id + source on the conversation.
      // If pre-chat form was filled, include name from form.
      final effectiveUser = user ??
          (userId != null ? WidgetUser(id: userId!, name: _preChatName) : null);

      final shouldForceNew = _forceNewOnNextSend;
      _forceNewOnNextSend = false;

      final stream = _client.sendMessage(
        text,
        conversationId: _conversationId,
        sessionId: sessionId,
        user: effectiveUser,
        userHash: userHash,
        forceNew: shouldForceNew,
        userEmail: _preChatEmail,
        userPhone: _preChatPhone,
      );

      await for (final event in stream) {
        if (event is TextChunkEvent) {
          buffer.write(event.content);
          // Throttle renders to ~20fps: schedule one UI update per 50ms window.
          // Chunks still accumulate in the buffer on every call — only the
          // notifyListeners/rebuild is gated so MarkdownBody re-parses at most
          // 20 times/sec instead of once per chunk (O(n) vs O(n²) total work).
          _renderFlushTimer ??= Timer(const Duration(milliseconds: 50), () {
            _renderFlushTimer = null;
            _updateStreamingMessage(streamingId, buffer.toString());
          });
        } else if (event is DoneEvent) {
          // Cancel any pending throttled render — finalizeStreamingMessage
          // will render the complete content immediately below.
          _renderFlushTimer?.cancel();
          _renderFlushTimer = null;
          final isNewConversation = event.conversationId != null &&
              event.conversationId != _conversationId;
          _conversationId = event.conversationId ?? _conversationId;
          _resetInactivityTimer();
          _finalizeStreamingMessage(streamingId, buffer.toString());
          if (isNewConversation) {
            // Refresh session list so the new session appears immediately
            unawaited(loadSessions());
          }
          await _cache.upsertMessage(
            _client.widgetKey,
            _messages.firstWhere((m) => m.id == streamingId),
            convId: _conversationId,
          );
        } else if (event is ErrorEvent) {
          _renderFlushTimer?.cancel();
          _renderFlushTimer = null;
          _removeMessage(streamingId);
          _error = event.message;
          _appendAssistantErrorMessage(event.message);
          _isStreaming = false;
          notifyListeners();
          return;
        } else if (event is ApprovalRequiredEvent) {
          _renderFlushTimer?.cancel();
          _renderFlushTimer = null;
          _removeMessage(streamingId);
          _pendingApproval = event;
          _isStreaming = false;
          notifyListeners();
          return;
        } else if (event is HandoffInitiatedEvent) {
          _renderFlushTimer?.cancel();
          _renderFlushTimer = null;
          _isHandoffActive = true;
          // Finalize any partial streaming content before handoff message
          if (buffer.isNotEmpty) {
            _finalizeStreamingMessage(streamingId, buffer.toString());
          } else {
            _removeMessage(streamingId);
          }
          _appendSystemMessage(
            'handoff_${DateTime.now().millisecondsSinceEpoch}',
            event.summary.isNotEmpty ? event.summary : 'Connected to support',
            MessageRole.operator,
          );
          _isStreaming = false;
          notifyListeners();
          _startHandoffPolling();
          return;
        } else if (event is StatusEvent) {
          // Status events are rare (one per tool/RAG call) — render immediately,
          // not subject to the chunk throttle.
          if (event.content.isNotEmpty) {
            _updateStreamingMessage(streamingId, event.content);
          }
        } else if (event is OperatorMessageEvent) {
          // Operator messages pushed via SSE during handoff (deduped by message_id).
          if (event.messageId.isNotEmpty &&
              !_seenOperatorMsgIds.contains(event.messageId)) {
            _seenOperatorMsgIds.add(event.messageId);
            _appendSystemMessage(
              event.messageId,
              event.content,
              MessageRole.operator,
            );
            notifyListeners();
          }
        } else if (event is HandoffResolvedEvent) {
          _isHandoffActive = false;
          _stopHandoffPolling();
          _appendSystemMessage(
            'handoff_resolved_${DateTime.now().millisecondsSinceEpoch}',
            'Support session ended',
            MessageRole.operator,
          );
          notifyListeners();
        }
      }
    } catch (e) {
      _renderFlushTimer?.cancel();
      _renderFlushTimer = null;
      _removeMessage(streamingId);
      _error = e.toString();
      _appendAssistantErrorMessage(_error!);
    } finally {
      _isStreaming = false;
      notifyListeners();
    }
  }

  /// Called when the user submits or skips the pre-chat form.
  void submitPreChatForm({String? name, String? email, String? phone}) {
    _preChatName = name?.trim().isEmpty == true ? null : name?.trim();
    _preChatEmail = email?.trim().isEmpty == true ? null : email?.trim();
    _preChatPhone = phone?.trim().isEmpty == true ? null : phone?.trim();
    _preChatSubmitted = true;
    notifyListeners();
  }

  void retry() {
    if (_config == null) {
      init();
      return;
    }
    if (_lastMessage != null && !_isStreaming) {
      send(_lastMessage!);
    }
  }

  Future<void> clearSession() async {
    if (_isStreaming) return;
    _messages = [];
    _conversationId = null;
    _error = null;
    _lastMessage = null;
    await _cache.clearMessages(_client.widgetKey);
    notifyListeners();
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

  void _appendSystemMessage(String id, String content, MessageRole role) {
    _messages = [
      ..._messages,
      ChatMessage(
        id: id,
        role: role,
        content: content,
        timestamp: DateTime.now(),
      ),
    ];
  }

  /// Dismiss the pending approval (e.g. after user approves/rejects via a
  /// different channel, or the approval times out).
  void dismissApproval() {
    _pendingApproval = null;
    notifyListeners();
  }

  /// Respond to a pending approval request. [decision] is 'approved' or 'rejected'.
  /// Calls the widget API endpoint, then clears the pending approval locally.
  Future<void> respondApproval(String approvalId, String decision) async {
    try {
      await _client.respondApproval(approvalId: approvalId, decision: decision);
    } catch (_) {
      // Non-fatal — still clear local state so the UI doesn't get stuck
    } finally {
      _pendingApproval = null;
      notifyListeners();
    }
  }

  void _appendAssistantErrorMessage(String message) {
    final clean = message.replaceFirst('Exception: ', '').trim();
    if (clean.isEmpty) return;

    final last = _messages.isNotEmpty ? _messages.last : null;
    if (last != null &&
        last.role == MessageRole.assistant &&
        last.content == clean) {
      return;
    }

    _messages = [
      ..._messages,
      ChatMessage(
        id: 'error_${DateTime.now().millisecondsSinceEpoch}',
        role: MessageRole.assistant,
        content: clean,
        timestamp: DateTime.now(),
      ),
    ];
  }

  // ---------------------------------------------------------------------------
  // Sessions
  // ---------------------------------------------------------------------------

  /// Load sessions list from the server. Requires userId / user to be set.
  Future<void> loadSessions() async {
    final uid = user?.id ?? userId;
    if (uid == null) return;

    _sessionsLoading = true;
    notifyListeners();

    try {
      final fetched = await _client.listSessions(userId: uid);
      _sessions = fetched;
    } catch (_) {
      // Non-fatal — leave existing list intact
    } finally {
      _sessionsLoading = false;
      notifyListeners();
    }
  }

  /// Close the current session (or a specific session by ID).
  Future<void> closeSession([String? sessionId]) async {
    final uid = user?.id ?? userId;
    if (uid == null) return;

    final target = sessionId ?? _conversationId;
    if (target == null) return;

    _inactivityTimer?.cancel();
    _inactivityTimer = null;

    await _client.closeSession(sessionId: target, userId: uid);

    // Update local sessions list
    _sessions = _sessions.map((s) {
      if (s.id == target) {
        return WidgetSession(
          id: s.id,
          firstMessage: s.firstMessage,
          lastActivityAt: s.lastActivityAt,
          status: 'closed',
          createdAt: s.createdAt,
        );
      }
      return s;
    }).toList();
    notifyListeners();
  }

  /// Resume an existing session: sets conversation ID and loads its messages.
  Future<void> resumeSession(String conversationId) async {
    _conversationId = conversationId;
    _messages = [];
    _error = null;
    _isLoading = true;
    notifyListeners();

    try {
      final bundle = await _client.loadHistoryBundle(
        conversationId: conversationId,
      );
      // Prefer the bundle's conversation_id, but fall back to what we set
      if (bundle.conversationId != null) {
        _conversationId = bundle.conversationId;
      }
      _messages = bundle.messages;
      await _cache.upsertMessages(
        _client.widgetKey,
        _messages,
        convId: _conversationId,
      );
    } catch (_) {
      // Non-fatal — show empty chat, user can still send messages
    } finally {
      _isLoading = false;
      notifyListeners();
    }
    _resetInactivityTimer();
  }

  /// Start a fresh session (clears current messages and conversation ID).
  Future<void> startNewSession() async {
    if (_isStreaming) return;
    _inactivityTimer?.cancel();
    _inactivityTimer = null;
    _messages = [];
    _conversationId = null;
    _error = null;
    _lastMessage = null;
    _forceNewOnNextSend = true;
    await _cache.clearMessages(_client.widgetKey);
    notifyListeners();
  }

  void _resetInactivityTimer() {
    _inactivityTimer?.cancel();
    _inactivityTimer = Timer(_kInactivityDuration, () async {
      if (_conversationId != null) {
        await closeSession(_conversationId);
      }
    });
  }

  // ---------------------------------------------------------------------------
  // Handoff polling — fetches new operator messages every 4 seconds
  // ---------------------------------------------------------------------------

  void _startHandoffPolling() {
    _handoffPollTimer?.cancel();
    _handoffPollTimer = Timer.periodic(const Duration(seconds: 4), (_) {
      _pollForOperatorMessages();
    });
  }

  void _stopHandoffPolling() {
    _handoffPollTimer?.cancel();
    _handoffPollTimer = null;
    _seenOperatorMsgIds.clear();
  }

  Future<void> _pollForOperatorMessages() async {
    final convId = _conversationId;
    if (convId == null) return;
    try {
      final bundle = await _client.loadHistoryBundle(conversationId: convId);
      for (final msg in bundle.messages) {
        if (msg.role != MessageRole.operator) continue;
        if (_seenOperatorMsgIds.contains(msg.id)) continue;
        _seenOperatorMsgIds.add(msg.id);
        // Only append if not already in _messages
        if (!_messages.any((m) => m.id == msg.id)) {
          _messages = [..._messages, msg];
          notifyListeners();
        }
      }
    } catch (_) {
      // Non-fatal — polling will retry on next tick
    }
  }

  // ---------------------------------------------------------------------------
  // Dispose
  // ---------------------------------------------------------------------------

  @override
  void dispose() {
    _inactivityTimer?.cancel();
    _handoffPollTimer?.cancel();
    _renderFlushTimer?.cancel();
    _messageTriggerController.close();
    _client.dispose();
    _cache.close();
    super.dispose();
  }
}
