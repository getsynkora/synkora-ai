import 'package:intl/intl.dart';

import '../config/app_environment.dart';

class SynkoraAccount {
  const SynkoraAccount({
    required this.id,
    required this.email,
    required this.name,
    required this.status,
  });

  final String id;
  final String email;
  final String name;
  final String status;

  factory SynkoraAccount.fromJson(Map<String, dynamic> json) {
    return SynkoraAccount(
      id: _stringValue(json['id']),
      email: _stringValue(json['email']),
      name: _stringValue(json['name'], fallback: 'Synkora User'),
      status: _stringValue(json['status'], fallback: 'UNKNOWN'),
    );
  }
}

class TenantMembership {
  const TenantMembership({
    required this.tenantId,
    required this.tenantName,
    required this.role,
    required this.isOwner,
    required this.isAdmin,
    required this.canEdit,
  });

  final String tenantId;
  final String tenantName;
  final String role;
  final bool isOwner;
  final bool isAdmin;
  final bool canEdit;

  factory TenantMembership.fromJson(Map<String, dynamic> json) {
    return TenantMembership(
      tenantId: _stringValue(json['tenant_id']),
      tenantName: _stringValue(json['tenant_name'], fallback: 'Workspace'),
      role: _stringValue(json['role'], fallback: 'member'),
      isOwner: json['is_owner'] == true,
      isAdmin: json['is_admin'] == true,
      canEdit: json['can_edit'] == true,
    );
  }
}

class TokenEnvelope {
  const TokenEnvelope({
    required this.accessToken,
    this.refreshToken,
    required this.expiresIn,
    this.tenantId,
  });

  final String accessToken;
  final String? refreshToken;
  final int expiresIn;
  final String? tenantId;

  factory TokenEnvelope.fromJson(Map<String, dynamic> json) {
    return TokenEnvelope(
      accessToken: _stringValue(json['access_token']),
      refreshToken: _nullableStringValue(json['refresh_token']),
      expiresIn: _intValue(json['expires_in'], fallback: 3600),
      tenantId: _nullableStringValue(json['tenant_id']),
    );
  }
}

class SocialAuthCallback {
  const SocialAuthCallback({
    required this.status,
    this.provider,
    this.exchangeCode,
    this.errorMessage,
  });

  final String status;
  final String? provider;
  final String? exchangeCode;
  final String? errorMessage;

  bool get isSuccess => status == 'success' && exchangeCode != null;

  factory SocialAuthCallback.fromUri(Uri uri) {
    final params = uri.queryParameters;
    return SocialAuthCallback(
      status: _stringValue(params['login'], fallback: 'error'),
      provider: _nullableStringValue(params['provider']),
      exchangeCode: _nullableStringValue(params['exchange_code']),
      errorMessage: _nullableStringValue(params['message']),
    );
  }
}

class SessionIdentity {
  const SessionIdentity({required this.account, required this.tenants});

  final SynkoraAccount account;
  final List<TenantMembership> tenants;
}

class AuthSession extends SessionIdentity {
  const AuthSession({
    required super.account,
    required super.tenants,
    required this.tokens,
  });

  final TokenEnvelope tokens;

  factory AuthSession.fromJson(Map<String, dynamic> json) {
    final data = (json['data'] as Map<String, dynamic>?) ?? json;
    final tenants = (data['tenants'] as List<dynamic>? ?? [])
        .map(
          (tenant) => TenantMembership.fromJson(tenant as Map<String, dynamic>),
        )
        .toList();
    return AuthSession(
      account: SynkoraAccount.fromJson(
        (data['account'] as Map<String, dynamic>?) ?? const {},
      ),
      tenants: tenants,
      tokens: TokenEnvelope.fromJson(data),
    );
  }
}

class AgentSummary {
  const AgentSummary({
    required this.id,
    required this.name,
    required this.slug,
    required this.description,
    required this.agentType,
    required this.avatarUrl,
    required this.status,
    required this.category,
    required this.tags,
    required this.isPublic,
    required this.isSubAgent,
    required this.subAgentsCount,
    required this.executionCount,
    required this.successRate,
    required this.createdAt,
  });

  final String id;
  final String name;
  final String slug;
  final String description;
  final String agentType;
  final String? avatarUrl;
  final String status;
  final String? category;
  final List<String> tags;
  final bool isPublic;
  final bool isSubAgent;
  final int subAgentsCount;
  final int executionCount;
  final double? successRate;
  final DateTime? createdAt;

  factory AgentSummary.fromJson(Map<String, dynamic> json) {
    return AgentSummary(
      id: _stringValue(json['id']),
      name: _stringValue(
        json['agent_name'],
        fallback: _stringValue(json['name']),
      ),
      slug: _stringValue(
        json['slug'],
        fallback: _stringValue(json['agent_name']),
      ),
      description: _stringValue(
        json['description'],
        fallback: 'No description has been added for this agent yet.',
      ),
      agentType: _stringValue(json['agent_type'], fallback: 'assistant'),
      avatarUrl: _nullableRemoteUrlValue(json['avatar']),
      status: _stringValue(json['status'], fallback: 'ACTIVE'),
      category: _nullableStringValue(json['category']),
      tags: (json['tags'] as List<dynamic>? ?? [])
          .map((tag) => tag.toString())
          .toList(),
      isPublic: json['is_public'] == true,
      isSubAgent: json['is_sub_agent'] == true,
      subAgentsCount: _intValue(json['sub_agents_count']),
      executionCount: _intValue(json['execution_count']),
      successRate: _doubleValue(json['success_rate']),
      createdAt: _dateValue(json['created_at']),
    );
  }
}

class ConversationSummary {
  const ConversationSummary({
    required this.id,
    required this.name,
    required this.status,
    required this.source,
    required this.updatedAt,
    this.preview,
  });

  final String id;
  final String name;
  final String status;
  final String? source;
  final DateTime? updatedAt;
  final String? preview;

  factory ConversationSummary.fromJson(Map<String, dynamic> json) {
    return ConversationSummary(
      id: _stringValue(json['id']),
      name: _stringValue(json['name'], fallback: 'New conversation'),
      status: _stringValue(json['status'], fallback: 'ACTIVE'),
      source: _nullableStringValue(json['source']),
      updatedAt:
          _dateValue(json['updated_at']) ?? _dateValue(json['created_at']),
      preview:
          _nullableStringValue(json['summary']) ??
          _nullableStringValue(json['first_message']),
    );
  }
}

class ChatMessage {
  const ChatMessage({
    required this.id,
    required this.role,
    required this.content,
    required this.createdAt,
    this.attachments = const [],
    this.isStreaming = false,
    this.isError = false,
  });

  final String id;
  final String role;
  final String content;
  final DateTime? createdAt;
  final List<ChatAttachment> attachments;
  final bool isStreaming;
  final bool isError;

  ChatMessage copyWith({
    String? content,
    List<ChatAttachment>? attachments,
    bool? isStreaming,
    bool? isError,
  }) {
    return ChatMessage(
      id: id,
      role: role,
      content: content ?? this.content,
      createdAt: createdAt,
      attachments: attachments ?? this.attachments,
      isStreaming: isStreaming ?? this.isStreaming,
      isError: isError ?? this.isError,
    );
  }

  factory ChatMessage.fromJson(Map<String, dynamic> json) {
    return ChatMessage(
      id: _stringValue(
        json['id'],
        fallback: _stringValue(
          json['message_id'],
          fallback: DateTime.now().microsecondsSinceEpoch.toString(),
        ),
      ),
      role: _stringValue(json['role'], fallback: 'assistant').toLowerCase(),
      content: _stringValue(json['content']),
      createdAt: _dateValue(json['created_at']),
      attachments: (json['attachments'] as List<dynamic>? ?? const [])
          .map(
            (attachment) => ChatAttachment.fromJson(
              (attachment as Map).cast<String, dynamic>(),
            ),
          )
          .toList(),
    );
  }
}

class ChatAttachment {
  const ChatAttachment({
    required this.fileId,
    required this.fileName,
    required this.fileType,
    required this.fileSize,
    this.fileUrl,
    this.downloadUrl,
    this.thumbnailUrl,
    this.extractedText,
    this.uploadedAt,
  });

  final String fileId;
  final String fileName;
  final String fileType;
  final int fileSize;
  final String? fileUrl;
  final String? downloadUrl;
  final String? thumbnailUrl;
  final String? extractedText;
  final DateTime? uploadedAt;

  String? get previewUrl => thumbnailUrl ?? downloadUrl ?? fileUrl;
  String? get openUrl => downloadUrl ?? fileUrl;
  bool get isImage => fileType.startsWith('image/');
  bool get isPdf => fileType == 'application/pdf';

  factory ChatAttachment.fromJson(Map<String, dynamic> json) {
    return ChatAttachment(
      fileId: _stringValue(
        json['file_id'],
        fallback: _stringValue(
          json['id'],
          fallback: DateTime.now().microsecondsSinceEpoch.toString(),
        ),
      ),
      fileName: _stringValue(json['file_name'], fallback: 'Attachment'),
      fileType: _stringValue(
        json['file_type'],
        fallback: 'application/octet-stream',
      ),
      fileSize: _intValue(json['file_size']),
      fileUrl: _nullableRemoteUrlValue(json['file_url']),
      downloadUrl: _nullableRemoteUrlValue(json['download_url']),
      thumbnailUrl: _nullableRemoteUrlValue(json['thumbnail_url']),
      extractedText: _nullableStringValue(json['extracted_text']),
      uploadedAt: _dateValue(json['uploaded_at']),
    );
  }
}

class ChatEvent {
  const ChatEvent({
    required this.type,
    this.content,
    this.error,
    this.toolName,
    this.status,
    this.conversationId,
  });

  final String type;
  final String? content;
  final String? error;
  final String? toolName;
  final String? status;
  final String? conversationId;

  factory ChatEvent.fromJson(Map<String, dynamic> json) {
    final metadata = json['metadata'] as Map<String, dynamic>?;
    return ChatEvent(
      type: _stringValue(json['type']),
      content:
          _nullableStringValue(json['content']) ??
          _nullableStringValue(json['description']),
      error:
          _nullableStringValue(json['error']) ??
          _nullableStringValue(json['message']),
      toolName: _nullableStringValue(json['tool_name']),
      status: _nullableStringValue(json['status']),
      conversationId:
          _nullableStringValue(json['conversation_id']) ??
          _nullableStringValue(metadata?['conversation_id']),
    );
  }
}

String formatRelativeTimestamp(DateTime? value) {
  if (value == null) return 'Unknown';
  final now = DateTime.now();
  final difference = now.difference(value);
  if (difference.inMinutes < 1) return 'Just now';
  if (difference.inHours < 1) return '${difference.inMinutes}m ago';
  if (difference.inDays < 1) return '${difference.inHours}h ago';
  if (difference.inDays < 7) return '${difference.inDays}d ago';
  return DateFormat('MMM d').format(value);
}

String formatByteSize(int bytes) {
  if (bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  var size = bytes.toDouble();
  var unitIndex = 0;

  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }

  final decimals = size >= 10 || unitIndex == 0 || size == size.roundToDouble()
      ? 0
      : 1;
  return '${size.toStringAsFixed(decimals)} ${units[unitIndex]}';
}

String _stringValue(dynamic value, {String fallback = ''}) {
  final resolved = _nullableStringValue(value);
  return resolved == null || resolved.isEmpty ? fallback : resolved;
}

String? _nullableStringValue(dynamic value) {
  if (value == null) return null;
  final resolved = value.toString().trim();
  return resolved.isEmpty ? null : resolved;
}

String? _nullableRemoteUrlValue(dynamic value) =>
    AppEnvironment.normalizeRemoteUrl(_nullableStringValue(value));

int _intValue(dynamic value, {int fallback = 0}) {
  if (value is int) return value;
  if (value is double) return value.round();
  return int.tryParse(value?.toString() ?? '') ?? fallback;
}

double? _doubleValue(dynamic value) {
  if (value is num) return value.toDouble();
  return double.tryParse(value?.toString() ?? '');
}

DateTime? _dateValue(dynamic value) {
  if (value == null) return null;
  return DateTime.tryParse(value.toString())?.toLocal();
}
