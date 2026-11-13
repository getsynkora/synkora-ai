import 'dart:typed_data';

import 'package:dio/dio.dart';

import '../../models/synkora_models.dart';
import '../../services/agent_service.dart';
import '../../services/api_client.dart';
import '../audio/wav_envelope.dart';
import '../ports.dart';
import '../voice_profile.dart';

const _missingKeyMessage =
    'This agent is set to a paid speech provider, but no key is saved for it. '
    'Add one under Voice settings, or use your phone\'s built-in voice.';

/// Loads which speech providers the workspace has keys for.
Future<VoiceCapabilities> loadVoiceCapabilities(SynkoraApiClient api) async {
  final response = await api.getJson('/api/v1/voice/api-keys');
  return VoiceCapabilities.fromApiKeys(response);
}

VoiceUnavailableException? _asUnavailable(SynkoraApiException error) {
  final text = error.message.toLowerCase();
  final missingKey =
      text.contains('api key') ||
      text.contains('unknown stt provider') ||
      text.contains('unknown tts provider');
  if (error.statusCode == 400 && missingKey) {
    return const VoiceUnavailableException(_missingKeyMessage);
  }
  if (error.statusCode == 401 || error.statusCode == 403) {
    return const VoiceUnavailableException(
      'Your session expired. Sign in again to keep talking.',
    );
  }
  return null;
}

/// Speech recognition through the workspace's Whisper key.
class BackendSpeechRecognizer implements SpeechRecognizer {
  BackendSpeechRecognizer(this._api, {this.model});

  final SynkoraApiClient _api;

  /// Optional model override, e.g. `gpt-4o-transcribe`.
  final String? model;

  /// Updated whenever the active agent changes.
  VoiceProfile profile = VoiceProfile.empty;

  @override
  Future<String> transcribe(Uint8List wav, {String? language}) async {
    final form = FormData.fromMap({
      'file': MultipartFile.fromBytes(
        wav,
        filename: 'speech.wav',
        contentType: DioMediaType('audio', 'wav'),
      ),
    });
    try {
      final response = await _api.postMultipart(
        '/api/v1/voice/transcribe',
        data: form,
        queryParameters: {
          'provider': 'openai_whisper',
          if ((language ?? profile.language) != null)
            'language': language ?? profile.language,
          if (profile.hint != null) 'prompt': profile.hint,
          if (model != null) 'model': model,
          if (profile.agentId != null) 'agent_id': profile.agentId,
        },
      );
      final data = (response['data'] as Map<String, dynamic>?) ?? const {};
      return (data['text'] ?? '').toString();
    } on SynkoraApiException catch (e) {
      throw _asUnavailable(e) ?? e;
    }
  }
}

/// Speech synthesis through the workspace's OpenAI or ElevenLabs key.
class BackendSpeechSynthesizer implements SpeechSynthesizer {
  BackendSpeechSynthesizer(this._api);

  final SynkoraApiClient _api;

  /// Updated whenever the active agent changes.
  VoiceProfile profile = VoiceProfile.empty;

  @override
  Future<SynthesizedAudio> synthesize(String text, {String? language}) async {
    final p = profile;
    final provider = p.ttsProvider;
    if (provider == null) {
      // The profile routes to the built-in voice unless the agent chose a
      // cloud provider, so this only happens if routing is bypassed.
      throw const VoiceUnavailableException(_missingKeyMessage);
    }

    final isOpenAi = provider == 'openai_tts';
    final body = <String, dynamic>{
      'text': text,
      'provider': provider,
      'voice_id': p.voiceId ?? (isOpenAi ? 'nova' : null),
      'agent_id': p.agentId,
      if (isOpenAi && p.speed != 1.0) 'speed': p.speed,
      'config': isOpenAi
          // WAV is the lowest-latency format and carries a real loudness
          // envelope for the on-screen visualiser.
          ? {'format': 'wav', 'model': p.model ?? 'tts-1'}
          : {
              'format': 'mp3_44100_128',
              if (p.model != null) 'model_id': p.model,
            },
    }..removeWhere((_, v) => v == null);

    final Uint8List bytes;
    try {
      bytes = await _api.postForBytes('/api/v1/voice/synthesize', data: body);
    } on SynkoraApiException catch (e) {
      throw _asUnavailable(e) ?? e;
    }
    if (bytes.isEmpty) {
      throw const SynkoraApiException('The voice service returned no audio.');
    }
    return describeAudio(bytes);
  }
}

/// Works out what [bytes] are and attaches loudness/duration where possible.
SynthesizedAudio describeAudio(Uint8List bytes) {
  final wav = parseWav(bytes);
  if (wav != null) {
    return SynthesizedAudio(
      bytes: bytes,
      mimeType: 'audio/wav',
      duration: wav.duration,
      envelope: wavEnvelope(bytes),
    );
  }
  final isMp3 =
      (bytes.length > 3 &&
          bytes[0] == 0x49 &&
          bytes[1] == 0x44 &&
          bytes[2] == 0x33) ||
      (bytes.length > 1 && bytes[0] == 0xFF && (bytes[1] & 0xE0) == 0xE0);
  return SynthesizedAudio(
    bytes: bytes,
    mimeType: isMp3 ? 'audio/mpeg' : 'audio/mp4',
  );
}

/// Bridges the voice loop to the existing agent chat service.
class ServiceVoiceAgentGateway implements VoiceAgentGateway {
  const ServiceVoiceAgentGateway(this._service);

  final SynkoraAgentService _service;

  @override
  Future<String> createConversation(
    AgentSummary agent, {
    required String name,
  }) async {
    final conversation = await _service.createConversation(
      agent.id,
      name: name,
    );
    return conversation.id;
  }

  @override
  Stream<ChatEvent> stream({
    required AgentSummary agent,
    required String message,
    required String conversationId,
  }) {
    return _service.streamChat(
      agentSlug: agent.slug,
      message: message,
      conversationId: conversationId,
      voiceMode: true,
    );
  }
}
