// Shared stand-in backend for the preview entrypoints in this folder.
import 'dart:math' as math;
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

import '../src/models/synkora_models.dart';
import '../src/services/api_client.dart';
import '../src/voice/audio/chime.dart';
import '../src/voice/audio/pcm.dart';

final demoAgents = [
  demoAgent('muse', 'Muse', 'Your personal creative assistant'),
  demoAgent('grokbot', 'GrokBot', 'Fast answers and live research'),
];

AgentSummary demoAgent(String slug, String name, String description) =>
    AgentSummary(
      id: slug,
      name: name,
      slug: slug,
      description: description,
      agentType: 'assistant',
      avatarUrl: null,
      status: 'ACTIVE',
      category: null,
      tags: const [],
      isPublic: false,
      isSubAgent: false,
      subAgentsCount: 0,
      executionCount: 0,
      successRate: null,
      createdAt: null,
    );

/// A stand-in Synkora backend for previews: agents, an agent that answers
/// about the weather, and (for the cloud-voice demo) speech endpoints.
class DemoApi extends SynkoraApiClient {
  DemoApi({this.voiceConfig = const {}, this.voiceEnabled = true})
    : super(baseUrl: 'http://demo');

  /// The agent's own voice settings, as the real detail endpoint returns them.
  final Map<String, dynamic> voiceConfig;
  final bool voiceEnabled;

  int _turn = 0;

  @override
  Future<Map<String, dynamic>> getJson(
    String path, {
    Map<String, dynamic>? queryParameters,
    bool authenticated = true,
  }) async {
    if (path.endsWith('/voice/api-keys')) {
      return {
        'data': {
          'api_keys': [
            {'provider': 'openai_whisper', 'is_active': true},
            {'provider': 'openai_tts', 'is_active': true},
          ],
        },
      };
    }
    return {
      'data': {
        'id': 'muse',
        'agent_name': 'Muse',
        'slug': 'muse',
        'voice_enabled': voiceEnabled,
        'voice_config': voiceConfig,
      },
    };
  }

  @override
  Future<Map<String, dynamic>> postJson(
    String path, {
    Object? data,
    bool authenticated = true,
    Map<String, dynamic>? headers,
  }) async => {
    'data': {
      'id': 'demo-conversation',
      'name': 'Voice chat',
      'status': 'active',
    },
  };

  @override
  Future<Map<String, dynamic>> postMultipart(
    String path, {
    required FormData data,
    Map<String, dynamic>? queryParameters,
    bool authenticated = true,
    Map<String, dynamic>? headers,
  }) async {
    debugPrint('DEMO stt call #$_turn');
    final said = _turn == 0
        ? 'What’s the weather like in Paris today?'
        : 'That’s all, thanks. Goodbye.';
    _turn++;
    return {
      'data': {'text': said},
    };
  }

  @override
  Future<Uint8List> postForBytes(
    String path, {
    required Object data,
    bool authenticated = true,
    Duration receiveTimeout = const Duration(seconds: 60),
  }) async {
    final text = (data as Map)['text'] as String;
    await Future<void>.delayed(const Duration(milliseconds: 350));
    final ms = (text.length * 62).clamp(700, 6000);
    final n = kChimeSampleRate * ms ~/ 1000;
    final samples = Int16List(n);
    for (var i = 0; i < n; i++) {
      final t = i / kChimeSampleRate;
      final syl = 0.5 + 0.5 * math.sin(2 * math.pi * 3.4 * t);
      final phrase = 0.7 + 0.3 * math.sin(2 * math.pi * 0.7 * t + 1);
      final v =
          (math.sin(2 * math.pi * 170 * t) * 0.6 +
              math.sin(2 * math.pi * 510 * t) * 0.3) *
          syl *
          phrase;
      samples[i] = (v * 9000).round();
    }
    return pcm16ToWav(samples, sampleRate: kChimeSampleRate);
  }

  @override
  Stream<ChatEvent> postEventStream(
    String path, {
    required Map<String, dynamic> data,
    bool authenticated = true,
  }) async* {
    debugPrint('DEMO agent stream: ${data['message']}');
    await Future<void>.delayed(const Duration(milliseconds: 500));
    yield const ChatEvent(
      type: 'tool_status',
      toolName: 'Checking the forecast',
      status: 'running',
    );
    await Future<void>.delayed(const Duration(milliseconds: 1800));
    for (final part in const [
      'It’s a pleasant day in Paris right now. ',
      'Around twenty-two degrees with a light breeze and mostly sunny skies. ',
      'You might want a light jacket for this evening, when it cools down to about fifteen.',
    ]) {
      yield ChatEvent(type: 'chunk', content: part);
      await Future<void>.delayed(const Duration(milliseconds: 700));
    }
    yield const ChatEvent(type: 'done');
  }
}
