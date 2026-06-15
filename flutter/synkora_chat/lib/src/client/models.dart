import 'package:flutter/material.dart';

// ---------------------------------------------------------------------------
// Widget config (from GET /api/v1/widgets/config)
// ---------------------------------------------------------------------------

class SuggestionPrompt {
  final String title;
  final String description;
  final String icon;
  final String prompt;

  const SuggestionPrompt({
    required this.title,
    required this.description,
    required this.icon,
    required this.prompt,
  });

  factory SuggestionPrompt.fromJson(Map<String, dynamic> j) => SuggestionPrompt(
    title: j['title'] as String? ?? '',
    description: j['description'] as String? ?? '',
    icon: j['icon'] as String? ?? '',
    prompt: j['prompt'] as String? ?? '',
  );
}

class WidgetTheme {
  final Color primaryColor;
  final String welcomeMessage;
  final String placeholder;
  final String title;

  const WidgetTheme({
    required this.primaryColor,
    required this.welcomeMessage,
    required this.placeholder,
    required this.title,
  });

  factory WidgetTheme.fromJson(Map<String, dynamic> j) {
    Color primary = const Color(0xFF79DFBC);
    final hex = j['primary_color'] as String?;
    if (hex != null && hex.isNotEmpty) {
      try {
        final cleaned = hex.replaceFirst('#', '');
        final value = int.parse(
          cleaned.length == 6 ? 'FF$cleaned' : cleaned,
          radix: 16,
        );
        primary = Color(value);
      } catch (_) {}
    }
    return WidgetTheme(
      primaryColor: primary,
      welcomeMessage: j['welcome_message'] as String? ?? '',
      placeholder: j['placeholder'] as String? ?? 'Type a message...',
      title: j['title'] as String? ?? '',
    );
  }

  static WidgetTheme get defaults => const WidgetTheme(
    primaryColor: Color(0xFF79DFBC),
    welcomeMessage: '',
    placeholder: 'Type a message...',
    title: '',
  );
}

class PreChatFormConfig {
  final bool enabled;
  final bool showName;
  final bool showEmail;
  final bool showPhone;
  final bool skippable;

  const PreChatFormConfig({
    required this.enabled,
    required this.showName,
    required this.showEmail,
    required this.showPhone,
    required this.skippable,
  });

  factory PreChatFormConfig.fromJson(Map<String, dynamic> j) => PreChatFormConfig(
    enabled: j['enabled'] as bool? ?? false,
    showName: j['show_name'] as bool? ?? true,
    showEmail: j['show_email'] as bool? ?? true,
    showPhone: j['show_phone'] as bool? ?? false,
    skippable: j['skippable'] as bool? ?? true,
  );

  static PreChatFormConfig get disabled => const PreChatFormConfig(
    enabled: false,
    showName: false,
    showEmail: false,
    showPhone: false,
    skippable: true,
  );
}

class WidgetConfig {
  final String widgetId;
  final String agentName;
  final String agentDescription;
  final String? agentAvatarUrl;
  final WidgetTheme theme;
  final List<SuggestionPrompt> suggestionPrompts;
  final PreChatFormConfig preChatForm;

  const WidgetConfig({
    required this.widgetId,
    required this.agentName,
    required this.agentDescription,
    this.agentAvatarUrl,
    required this.theme,
    required this.suggestionPrompts,
    required this.preChatForm,
  });

  factory WidgetConfig.fromJson(Map<String, dynamic> j) {
    final prompts =
        (j['suggestion_prompts'] as List<dynamic>?)
            ?.map((e) => SuggestionPrompt.fromJson(e as Map<String, dynamic>))
            .toList() ??
        [];
    final themeJson = j['theme'] as Map<String, dynamic>? ?? {};
    final preChatJson = j['pre_chat_form'] as Map<String, dynamic>? ?? {};
    return WidgetConfig(
      widgetId: j['widget_id'] as String? ?? '',
      agentName: j['agent_name'] as String? ?? 'AI Assistant',
      agentDescription: j['agent_description'] as String? ?? '',
      agentAvatarUrl: j['agent_avatar'] as String?,
      theme: WidgetTheme.fromJson(themeJson),
      suggestionPrompts: prompts,
      preChatForm: PreChatFormConfig.fromJson(preChatJson),
    );
  }
}

class WidgetChatHistory {
  final String? conversationId;
  final List<ChatMessage> messages;

  const WidgetChatHistory({
    required this.conversationId,
    required this.messages,
  });
}

// ---------------------------------------------------------------------------
// Chat message
// ---------------------------------------------------------------------------

enum MessageRole { user, assistant, operator }

class ChatMessage {
  final String id;
  final MessageRole role;
  final String content;
  final DateTime timestamp;
  final bool isStreaming;

  const ChatMessage({
    required this.id,
    required this.role,
    required this.content,
    required this.timestamp,
    this.isStreaming = false,
  });

  bool get isOperator => role == MessageRole.operator;

  ChatMessage copyWith({String? content, bool? isStreaming}) => ChatMessage(
    id: id,
    role: role,
    content: content ?? this.content,
    timestamp: timestamp,
    isStreaming: isStreaming ?? this.isStreaming,
  );
}

// ---------------------------------------------------------------------------
// SSE events (from POST /api/v1/widgets/chat stream)
// ---------------------------------------------------------------------------

sealed class SseEvent {}

class TextChunkEvent extends SseEvent {
  final String content;
  TextChunkEvent(this.content);
}

class ToolStatusEvent extends SseEvent {
  final String toolName;
  final String status;
  final String description;
  final int? durationMs;
  ToolStatusEvent({
    required this.toolName,
    required this.status,
    required this.description,
    this.durationMs,
  });
}

class DoneEvent extends SseEvent {
  final String? conversationId;
  DoneEvent(this.conversationId);
}

class ErrorEvent extends SseEvent {
  final String message;
  ErrorEvent(this.message);
}

class ApprovalRequiredEvent extends SseEvent {
  final String approvalId;
  final String toolName;
  final Map<String, dynamic> toolArgs;
  final String? expiresAt;
  final String message;
  ApprovalRequiredEvent({
    required this.approvalId,
    required this.toolName,
    required this.toolArgs,
    this.expiresAt,
    required this.message,
  });
}

class HandoffInitiatedEvent extends SseEvent {
  final String summary;
  HandoffInitiatedEvent(this.summary);
}

class HandoffResolvedEvent extends SseEvent {}

class OperatorMessageEvent extends SseEvent {
  final String content;
  final String messageId;
  OperatorMessageEvent({required this.content, required this.messageId});
}

// ---------------------------------------------------------------------------
// Widget user context (for identity verification / conversation continuity)
// ---------------------------------------------------------------------------

class WidgetUser {
  final String id;
  final String? name;
  final String? email;
  final String? phone;
  final String? orgId;

  const WidgetUser({required this.id, this.name, this.email, this.phone, this.orgId});

  Map<String, dynamic> toJson() => {
    'id': id,
    if (name != null) 'name': name,
    if (email != null) 'email': email,
    if (phone != null) 'phone': phone,
    if (orgId != null) 'org_id': orgId,
  };
}

// ---------------------------------------------------------------------------
// Widget session (from GET /api/v1/widgets/sessions)
// ---------------------------------------------------------------------------

class WidgetSession {
  final String id;
  final String? firstMessage;
  final DateTime lastActivityAt;
  final String status; // "active" | "closed"
  final DateTime createdAt;

  const WidgetSession({
    required this.id,
    this.firstMessage,
    required this.lastActivityAt,
    required this.status,
    required this.createdAt,
  });

  bool get isActive => status == 'active';

  factory WidgetSession.fromJson(Map<String, dynamic> j) {
    return WidgetSession(
      id: j['id'] as String,
      firstMessage: j['first_message'] as String?,
      lastActivityAt:
          DateTime.tryParse(j['last_activity_at'] as String? ?? '') ??
          DateTime.now(),
      status: j['status'] as String? ?? 'active',
      createdAt:
          DateTime.tryParse(j['created_at'] as String? ?? '') ?? DateTime.now(),
    );
  }
}
