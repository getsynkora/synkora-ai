import 'package:dio/dio.dart';

import '../models/synkora_models.dart';
import 'api_client.dart';

class SynkoraAgentService {
  const SynkoraAgentService(this._client);

  final SynkoraApiClient _client;

  Future<List<AgentSummary>> loadAgents({String? search}) async {
    final response = await _client.getJson(
      '/api/v1/agents/',
      queryParameters: {
        'page': 1,
        'page_size': 100,
        if (search != null && search.isNotEmpty) 'search': search,
      },
    );
    final data = (response['data'] as Map<String, dynamic>?) ?? response;
    final agents = (data['agents_list'] as List<dynamic>? ?? [])
        .map((agent) => AgentSummary.fromJson(agent as Map<String, dynamic>))
        .toList();
    return agents;
  }

  Future<AgentSummary> getAgent(String slug) async {
    final response = await _client.getJson('/api/v1/agents/$slug');
    final data = (response['data'] as Map<String, dynamic>?) ?? response;
    return AgentSummary.fromJson(data);
  }

  Future<ConversationSummary> createConversation(
    String agentId, {
    required String name,
    String source = 'flutter',
  }) async {
    final response = await _client.postJson(
      '/api/v1/agents/conversations',
      data: {'agent_id': agentId, 'name': name, 'source': source},
    );
    final data = (response['data'] as Map<String, dynamic>?) ?? response;
    return ConversationSummary.fromJson(data);
  }

  Future<List<ConversationSummary>> loadConversations(
    String agentId, {
    String source = 'flutter',
  }) async {
    final response = await _client.getJson(
      '/api/v1/agents/$agentId/conversations',
      queryParameters: {'limit': 25, 'source': source},
    );
    final data = (response['data'] as Map<String, dynamic>?) ?? response;
    return (data['conversations'] as List<dynamic>? ?? [])
        .map(
          (conversation) => ConversationSummary.fromJson(
            conversation as Map<String, dynamic>,
          ),
        )
        .toList();
  }

  Future<List<ChatMessage>> loadMessages(String conversationId) async {
    final response = await _client.getJson(
      '/api/v1/agents/conversations/$conversationId/messages',
      queryParameters: const {'limit': 50},
    );
    final data = (response['data'] as Map<String, dynamic>?) ?? response;
    return (data['messages'] as List<dynamic>? ?? [])
        .map((message) => ChatMessage.fromJson(message as Map<String, dynamic>))
        .toList();
  }

  Future<ChatAttachment> uploadAttachment({
    required String conversationId,
    required String filePath,
    required String fileName,
    List<int>? bytes,
  }) async {
    final file = bytes != null
        ? MultipartFile.fromBytes(bytes, filename: fileName)
        : await MultipartFile.fromFile(filePath, filename: fileName);

    final response = await _client.postMultipart(
      '/api/v1/agents/chat/upload-attachment',
      data: FormData.fromMap({
        'conversation_id': conversationId,
        'file': file,
      }),
    );
    final data = (response['data'] as Map<String, dynamic>?) ?? response;
    final attachment =
        (data['attachment'] as Map<String, dynamic>?) ??
        const <String, dynamic>{};
    return ChatAttachment.fromJson(attachment);
  }

  Stream<ChatEvent> streamChat({
    required String agentSlug,
    required String message,
    String? conversationId,
    List<ChatAttachment> attachments = const [],
  }) {
    final data = <String, dynamic>{'agent_slug': agentSlug, 'message': message};
    if (conversationId != null) {
      data['conversation_id'] = conversationId;
    }
    if (attachments.isNotEmpty) {
      data['attachments'] = attachments
          .map(
            (attachment) => {
              'file_id': attachment.fileId,
              'file_name': attachment.fileName,
              'file_type': attachment.fileType,
              'file_size': attachment.fileSize,
              if (attachment.fileUrl != null) 'file_url': attachment.fileUrl,
              if (attachment.downloadUrl != null)
                'download_url': attachment.downloadUrl,
              if (attachment.thumbnailUrl != null)
                'thumbnail_url': attachment.thumbnailUrl,
              if (attachment.extractedText != null)
                'extracted_text': attachment.extractedText,
            },
          )
          .toList();
    }

    return _client.postEventStream('/api/v1/agents/chat/stream', data: data);
  }
}
