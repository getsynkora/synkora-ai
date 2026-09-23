import 'dart:async';
import 'dart:convert';

import 'package:dio/dio.dart';

import 'models.dart';

/// Low-level API client. No Flutter dependency — pure Dart.
/// Handles config fetch, SSE streaming, and history loading.
class SynkoraClient {
  final String widgetKey;
  final String baseUrl;

  late final Dio _dio;
  String? identityToken;
  String? sessionToken;
  final void Function(String token)? onSessionToken;

  /// Restore a capability saved by the host app, alongside its conversation ID.
  void restoreAnonymousSession(String token) {
    sessionToken = token;
    _dio.options.headers['X-Widget-Session-Token'] = token;
  }

  /// Call when your backend refreshes the short-lived identity assertion.
  void setIdentity({String? userId, String? userHash, String? token}) {
    identityToken = token;
    _dio.options.headers.remove('X-Widget-User-Id');
    _dio.options.headers.remove('X-Widget-User-Hash');
    _dio.options.headers.remove('X-Widget-Identity-Token');
    if (userId != null) _dio.options.headers['X-Widget-User-Id'] = userId;
    if (userHash != null) _dio.options.headers['X-Widget-User-Hash'] = userHash;
    if (token != null) _dio.options.headers['X-Widget-Identity-Token'] = token;
  }

  SynkoraClient(
      {required this.widgetKey, required String baseUrl, this.onSessionToken})
      : baseUrl = baseUrl.endsWith('/')
            ? baseUrl.substring(0, baseUrl.length - 1)
            : baseUrl {
    _dio = Dio(
      BaseOptions(
        baseUrl: this.baseUrl,
        connectTimeout: const Duration(seconds: 10),
        receiveTimeout: const Duration(seconds: 60),
        headers: {'X-Widget-API-Key': widgetKey, 'Accept': 'application/json'},
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Config
  // ---------------------------------------------------------------------------

  Future<WidgetConfig> loadConfig() async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/widgets/config',
      );
      return WidgetConfig.fromJson(response.data!);
    } on DioException catch (e) {
      throw Exception(await _describeDioError(e));
    }
  }

  // ---------------------------------------------------------------------------
  // Chat (SSE stream)
  // ---------------------------------------------------------------------------

  Stream<SseEvent> sendMessage(
    String message, {
    String? conversationId,
    String? sessionId,
    WidgetUser? user,
    String? userHash,
    bool forceNew = false,
    String? userEmail,
    String? userPhone,
  }) {
    final controller = StreamController<SseEvent>();

    _streamChat(
      message: message,
      conversationId: conversationId,
      sessionId: sessionId,
      user: user,
      userHash: userHash,
      forceNew: forceNew,
      userEmail: userEmail,
      userPhone: userPhone,
      controller: controller,
    );

    return controller.stream;
  }

  Future<void> _streamChat({
    required String message,
    required StreamController<SseEvent> controller,
    String? conversationId,
    String? sessionId,
    WidgetUser? user,
    String? userHash,
    bool forceNew = false,
    String? userEmail,
    String? userPhone,
  }) async {
    final cancelToken = CancelToken();

    // Cancel token is stored so dispose() can cancel in-flight requests
    _activeCancelTokens.add(cancelToken);

    try {
      final body = <String, dynamic>{
        'message': message,
        'source': 'flutter',
        if (conversationId != null) 'conversation_id': conversationId,
        if (sessionId != null) 'session_id': sessionId,
        if (user != null) 'user': user.toJson(),
        if (userHash != null) 'user_hash': userHash,
        if (identityToken != null) 'identity_token': identityToken,
        if (sessionToken != null) 'session_token': sessionToken,
        if (forceNew) 'force_new': true,
        if (userEmail != null) 'user_email': userEmail,
        if (userPhone != null) 'user_phone': userPhone,
      };

      final response = await _dio.post<ResponseBody>(
        '/api/v1/widgets/chat',
        data: body,
        options: Options(
          responseType: ResponseType.stream,
          headers: {'Accept': 'text/event-stream'},
        ),
        cancelToken: cancelToken,
      );

      final buffer = StringBuffer();

      await for (final bytes in response.data!.stream) {
        buffer.write(utf8.decode(bytes));
        final raw = buffer.toString();

        // Split on double newline (SSE message separator)
        final parts = raw.split('\n\n');

        // Keep the last part as it may be incomplete
        buffer.clear();
        buffer.write(parts.last);

        for (int i = 0; i < parts.length - 1; i++) {
          final block = parts[i].trim();
          if (block.isEmpty) continue;

          // Extract the data line
          String? dataLine;
          for (final line in block.split('\n')) {
            if (line.startsWith('data:')) {
              dataLine = line.substring(5).trim();
              break;
            }
          }

          if (dataLine == null || dataLine.isEmpty) continue;

          try {
            final parsed = jsonDecode(dataLine) as Map<String, dynamic>;
            final metadata = parsed['metadata'];
            if (metadata is Map && metadata['session_token'] is String) {
              restoreAnonymousSession(metadata['session_token'] as String);
              onSessionToken?.call(sessionToken!);
            }
            final event = _parseEvent(parsed);
            if (event != null) {
              controller.add(event);
            }
          } catch (_) {
            // Ignore malformed SSE lines
          }
        }
      }
    } on DioException catch (e) {
      if (e.type != DioExceptionType.cancel) {
        controller.add(ErrorEvent(await _describeDioError(e)));
      }
    } catch (e) {
      controller.add(ErrorEvent(e.toString()));
    } finally {
      _activeCancelTokens.remove(cancelToken);
      await controller.close();
    }
  }

  SseEvent? _parseEvent(Map<String, dynamic> json) {
    final type = json['type'] as String?;
    switch (type) {
      case 'chunk':
        return TextChunkEvent(json['content'] as String? ?? '');
      case 'tool_status':
        return ToolStatusEvent(
          toolName: json['tool_name'] as String? ?? '',
          status: json['status'] as String? ?? '',
          description: json['description'] as String? ?? '',
          durationMs: json['duration_ms'] as int?,
        );
      case 'done':
        // conversation_id may be top-level or inside metadata
        final convId = json['conversation_id'] as String? ??
            (json['metadata'] as Map<String, dynamic>?)?['conversation_id']
                as String?;
        return DoneEvent(convId);
      case 'error':
        return ErrorEvent(json['message'] as String? ?? 'Unknown error');
      case 'approval_required':
        return ApprovalRequiredEvent(
          approvalId: json['approval_id'] as String? ?? '',
          toolName: json['tool_name'] as String? ?? '',
          toolArgs: (json['tool_args'] as Map<String, dynamic>?) ?? {},
          expiresAt: json['expires_at'] as String?,
          message: json['message'] as String? ?? '',
        );
      case 'handoff_initiated':
        return HandoffInitiatedEvent(json['summary'] as String? ?? '');
      case 'handoff_resolved':
        return HandoffResolvedEvent();
      default:
        return null;
    }
  }

  // ---------------------------------------------------------------------------
  // History
  // ---------------------------------------------------------------------------

  Future<WidgetChatHistory> loadHistoryBundle({
    String? userId,
    String? sessionId,
    String? conversationId,
    int limit = 50,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'limit': limit,
        if (conversationId != null) 'conversation_id': conversationId,
        if (conversationId == null && userId != null)
          'external_user_id': userId,
        if (conversationId == null && sessionId != null)
          'session_id': sessionId,
      };

      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/widgets/chat/history',
        queryParameters: queryParams,
      );

      final root = response.data ?? const <String, dynamic>{};
      final payload = (root['data'] as Map<String, dynamic>?) ?? root;
      final messages = (payload['messages'] as List<dynamic>? ?? [])
          .map((m) => _messageFromJson(m as Map<String, dynamic>))
          .toList();

      return WidgetChatHistory(
        conversationId: payload['conversation_id'] as String?,
        messages: messages,
      );
    } catch (_) {
      return const WidgetChatHistory(conversationId: null, messages: []);
    }
  }

  Future<List<ChatMessage>> loadHistory({
    String? userId,
    String? sessionId,
    int limit = 50,
  }) async {
    final history = await loadHistoryBundle(
      userId: userId,
      sessionId: sessionId,
      limit: limit,
    );
    return history.messages;
  }

  // ---------------------------------------------------------------------------
  // Sessions
  // ---------------------------------------------------------------------------

  Future<List<WidgetSession>> listSessions({
    required String userId,
    int page = 1,
    int pageSize = 20,
  }) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/widgets/sessions',
        queryParameters: {'page': page, 'page_size': pageSize},
        options: Options(headers: {
          'X-Widget-API-Key': widgetKey,
          'X-Widget-User-Id': userId,
        }),
      );
      final root = response.data ?? const <String, dynamic>{};
      final payload = (root['data'] as Map<String, dynamic>?) ?? root;
      final list = payload['sessions'] as List<dynamic>? ?? [];
      return list
          .map((e) => WidgetSession.fromJson(e as Map<String, dynamic>))
          .toList();
    } catch (_) {
      return [];
    }
  }

  Future<bool> closeSession({
    required String sessionId,
    required String userId,
  }) async {
    try {
      await _dio.post<void>(
        '/api/v1/widgets/sessions/$sessionId/close',
        options: Options(headers: {
          'X-Widget-API-Key': widgetKey,
          'X-Widget-User-Id': userId,
        }),
      );
      return true;
    } catch (_) {
      return false;
    }
  }

  // ---------------------------------------------------------------------------
  // Approvals
  // ---------------------------------------------------------------------------

  Future<void> respondApproval({
    required String approvalId,
    required String decision,
  }) async {
    await _dio.post<void>(
      '/api/v1/widgets/chat/approvals/$approvalId/respond',
      data: {'decision': decision},
    );
  }

  Future<String> _describeDioError(DioException error) async {
    final statusCode = error.response?.statusCode;
    final normalizedBase = baseUrl.replaceFirst(RegExp(r'^https?://'), '');

    if (error.type == DioExceptionType.connectionTimeout ||
        error.type == DioExceptionType.connectionError ||
        error.type == DioExceptionType.unknown) {
      return 'Cannot reach Synkora at $normalizedBase. Make sure the API is running and that this app can access $baseUrl.';
    }

    // The server's own {"detail": "..."} is always more specific and
    // accurate than anything we could guess from the status code alone —
    // prefer it whenever present.
    final serverDetail = await _extractErrorDetail(error.response?.data);

    if (statusCode == 401) {
      return serverDetail ??
          'Synkora rejected this widget key. Check that the widget key is valid and belongs to the target instance.';
    }

    if (statusCode == 403) {
      // 403 means the widget key WAS accepted — the rejection is a separate
      // check (domain allowlist, identity verification, rate limit). Do not
      // tell the caller the key is invalid here; that sends debugging in
      // exactly the wrong direction.
      return serverDetail ??
          "Synkora rejected this request (403). The widget key is valid, but the request failed a domain, "
              "identity, or permission check — check the widget's allowed domains, mobile_allowed setting, and "
              "identity verification requirements.";
    }

    if (statusCode == 404) {
      return 'Synkora responded, but the widget API route was not found at $normalizedBase. Check that your base URL points to the API server.';
    }

    if (statusCode != null && statusCode >= 500) {
      return serverDetail ??
          'Synkora is reachable, but returned a server error ($statusCode). Check the API logs and try again.';
    }

    return serverDetail ?? error.message ?? 'Network error';
  }

  /// Best-effort extraction of the FastAPI `{"detail": "..."}` body from a
  /// failed response, whichever shape Dio delivered it in — already-decoded
  /// JSON for normal requests, or a raw byte stream for the SSE chat call
  /// (which sets responseType: ResponseType.stream even for error responses).
  Future<String?> _extractErrorDetail(dynamic data) async {
    try {
      if (data is Map) {
        final detail = data['detail'];
        return detail is String ? detail : null;
      }
      if (data is ResponseBody) {
        final bytes = await data.stream
            .fold<List<int>>(<int>[], (acc, chunk) => acc..addAll(chunk));
        final decoded = jsonDecode(utf8.decode(bytes));
        if (decoded is Map && decoded['detail'] is String) {
          return decoded['detail'] as String;
        }
        return null;
      }
      if (data is String) {
        final decoded = jsonDecode(data);
        if (decoded is Map && decoded['detail'] is String) {
          return decoded['detail'] as String;
        }
        return null;
      }
    } catch (_) {
      // Malformed/non-JSON body — fall through to the generic message.
    }
    return null;
  }

  MessageRole _parseRole(String? role) {
    switch (role?.toUpperCase()) {
      case 'ASSISTANT':
        return MessageRole.assistant;
      case 'OPERATOR':
        return MessageRole.operator;
      default:
        return MessageRole.user;
    }
  }

  ChatMessage _messageFromJson(Map<String, dynamic> j) {
    return ChatMessage(
      id: j['id'] as String? ??
          j['message_id'] as String? ??
          DateTime.now().millisecondsSinceEpoch.toString(),
      role: _parseRole(j['role'] as String?),
      content: j['content'] as String? ?? '',
      timestamp:
          DateTime.tryParse(j['created_at'] as String? ?? '') ?? DateTime.now(),
    );
  }

  // ---------------------------------------------------------------------------
  // Lifecycle
  // ---------------------------------------------------------------------------

  final _activeCancelTokens = <CancelToken>{};

  void dispose() {
    for (final token in _activeCancelTokens) {
      token.cancel('SynkoraClient disposed');
    }
    _activeCancelTokens.clear();
    _dio.close();
  }
}
