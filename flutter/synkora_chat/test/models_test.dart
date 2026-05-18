import 'package:flutter_test/flutter_test.dart';
import 'package:synkora_chat/synkora_chat.dart';

void main() {
  group('WidgetTheme.fromJson', () {
    test('parses hex color correctly', () {
      final theme = WidgetTheme.fromJson({'primary_color': '#6366F1'});
      expect(theme.primaryColor.toARGB32(), 0xFF6366F1);
    });

    test('falls back to default color on empty string', () {
      final theme = WidgetTheme.fromJson({'primary_color': ''});
      expect(theme.primaryColor.toARGB32(), 0xFF79DFBC);
    });

    test('falls back to default color on invalid hex', () {
      final theme = WidgetTheme.fromJson({'primary_color': 'notacolor'});
      expect(theme.primaryColor.toARGB32(), 0xFF79DFBC);
    });

    test('parses welcome_message and placeholder', () {
      final theme = WidgetTheme.fromJson({
        'primary_color': '#FF0000',
        'welcome_message': 'Hello!',
        'placeholder': 'Ask me...',
      });
      expect(theme.welcomeMessage, 'Hello!');
      expect(theme.placeholder, 'Ask me...');
    });

    test('uses default placeholder when missing', () {
      final theme = WidgetTheme.fromJson({});
      expect(theme.placeholder, 'Type a message...');
    });
  });

  group('WidgetConfig.fromJson', () {
    test('parses full config', () {
      final config = WidgetConfig.fromJson({
        'widget_id': 'wid_123',
        'agent_name': 'Test Agent',
        'agent_description': 'A helpful agent',
        'agent_avatar': 'https://example.com/avatar.png',
        'suggestion_prompts': [
          {'title': 'Help', 'description': 'Get help', 'icon': '🆘', 'prompt': 'I need help'},
        ],
        'theme': {'primary_color': '#FF5733'},
      });
      expect(config.widgetId, 'wid_123');
      expect(config.agentName, 'Test Agent');
      expect(config.agentAvatarUrl, 'https://example.com/avatar.png');
      expect(config.suggestionPrompts.length, 1);
      expect(config.suggestionPrompts[0].title, 'Help');
      expect(config.theme.primaryColor.toARGB32(), 0xFFFF5733);
    });

    test('handles missing optional fields', () {
      final config = WidgetConfig.fromJson({});
      expect(config.agentName, 'AI Assistant');
      expect(config.agentAvatarUrl, null);
      expect(config.suggestionPrompts, isEmpty);
    });
  });

  group('SuggestionPrompt.fromJson', () {
    test('parses all fields', () {
      final p = SuggestionPrompt.fromJson({
        'title': 'Summary',
        'description': 'Get a summary',
        'icon': '📄',
        'prompt': 'Summarize this',
      });
      expect(p.title, 'Summary');
      expect(p.prompt, 'Summarize this');
    });

    test('handles missing fields gracefully', () {
      final p = SuggestionPrompt.fromJson({});
      expect(p.title, '');
      expect(p.prompt, '');
    });
  });

  group('ChatMessage.copyWith', () {
    test('updates content and isStreaming', () {
      final msg = ChatMessage(
        id: '1',
        role: MessageRole.assistant,
        content: 'Hello',
        timestamp: DateTime(2026),
      );
      final updated = msg.copyWith(content: 'Hello world', isStreaming: true);
      expect(updated.content, 'Hello world');
      expect(updated.isStreaming, true);
      expect(updated.id, '1'); // unchanged
    });
  });

  group('WidgetUser.toJson', () {
    test('includes all non-null fields', () {
      final user = WidgetUser(id: 'u1', name: 'Alice', email: 'alice@test.com', orgId: 'org1');
      final json = user.toJson();
      expect(json['id'], 'u1');
      expect(json['name'], 'Alice');
      expect(json['org_id'], 'org1');
    });

    test('excludes null optional fields', () {
      final user = WidgetUser(id: 'u1');
      final json = user.toJson();
      expect(json.containsKey('name'), false);
      expect(json.containsKey('email'), false);
      expect(json.containsKey('org_id'), false);
    });
  });
}
