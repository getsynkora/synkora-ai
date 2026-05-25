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

class WidgetConfig {
  final String widgetId;
  final String agentName;
  final String agentDescription;
  final String? agentAvatarUrl;
  final WidgetTheme theme;
  final List<SuggestionPrompt> suggestionPrompts;

  const WidgetConfig({
    required this.widgetId,
    required this.agentName,
    required this.agentDescription,
    this.agentAvatarUrl,
    required this.theme,
    required this.suggestionPrompts,
  });

  factory WidgetConfig.fromJson(Map<String, dynamic> j) {
    final prompts =
        (j['suggestion_prompts'] as List<dynamic>?)
            ?.map((e) => SuggestionPrompt.fromJson(e as Map<String, dynamic>))
            .toList() ??
        [];
    final themeJson = j['theme'] as Map<String, dynamic>? ?? {};
    return WidgetConfig(
      widgetId: j['widget_id'] as String? ?? '',
      agentName: j['agent_name'] as String? ?? 'AI Assistant',
      agentDescription: j['agent_description'] as String? ?? '',
      agentAvatarUrl: j['agent_avatar'] as String?,
      theme: WidgetTheme.fromJson(themeJson),
      suggestionPrompts: prompts,
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

enum MessageRole { user, assistant }

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

// ---------------------------------------------------------------------------
// Widget user context (for identity verification / conversation continuity)
// ---------------------------------------------------------------------------

class WidgetUser {
  final String id;
  final String? name;
  final String? email;
  final String? orgId;

  const WidgetUser({required this.id, this.name, this.email, this.orgId});

  Map<String, dynamic> toJson() => {
    'id': id,
    if (name != null) 'name': name,
    if (email != null) 'email': email,
    if (orgId != null) 'org_id': orgId,
  };
}
