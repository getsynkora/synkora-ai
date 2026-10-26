import 'dart:typed_data';

import 'package:dio/dio.dart';

import '../../models/synkora_models.dart';
import '../../services/agent_service.dart';
import '../../services/api_client.dart';
import '../audio/wav_envelope.dart';
import '../ports.dart';

const _missingKeyMessage =
    'Voice needs a speech provider key. Add an OpenAI (or ElevenLabs) key '
    'under Voice settings in the Synkora dashboard.';

/// Which speech providers the workspace has configured.
class VoiceCapabilities {
  const VoiceCapabilities(this.providers);

  const VoiceCapabilities.none() : providers = const {};

  /// Active provider ids such as `openai_whisper`, `openai_tts`, `elevenlabs`.
  final Set<String> providers;

  bool get canTranscribe => providers.contains('openai_whisper');
  bool get canSpeak =>
      providers.contains('openai_tts') || providers.contains('elevenlabs');
  bool get ready => canTranscribe && canSpeak;

  static Future<VoiceCapabilities> load(SynkoraApiClient api) async {
    final response = await api.getJson('/api/v1/voice/api-keys');
    final data = (response['data'] as Map<String, dynamic>?) ?? const {};
    final keys = (data['api_keys'] as List<dynamic>? ?? const []);
    final providers = <String>{};
    for (final key in keys) {
      if (key is! Map) continue;
      if (key['is_active'] == false) continue;
      final raw = key['provider']?.toString().toLowerCase() ?? '';
      // Enum members may serialize as "VoiceProvider.OPENAI_TTS" or "openai_tts".
      providers.add(raw.split('.').last);
    }
    return VoiceCapabilities(providers);
  }

  /// Explains what is missing, or null when voice can work.
  String? get problem {
    if (!canTranscribe && !canSpeak) return _missingKeyMessage;
    if (!canTranscribe) {
      return 'Voice needs an OpenAI key for speech recognition. Add it under '
          'Voice settings in the Synkora dashboard.';
    }
    if (!canSpeak) {
      return 'Voice needs an OpenAI or ElevenLabs key for speech output. Add '
          'one under Voice settings in the Synkora dashboard.';
    }
    return null;
  }
}

/// How one agent should sound and be understood.
class VoiceProfile {
  const VoiceProfile({
    this.ttsProvider,
    this.voiceId,
    this.model,
    this.language,
    this.speed = 1.0,
    this.agentId,
    this.hint,
  });

  /// `openai_tts` or `elevenlabs`; null when no provider is available.
  final String? ttsProvider;
  final String? voiceId;
  final String? model;

  /// ISO-639-1 code (`en`) when the agent pins a language, else auto-detect.
  final String? language;
  final double speed;
  final String? agentId;

  /// Vocabulary hint for the recognizer (names it would otherwise misspell).
  final String? hint;

  static const empty = VoiceProfile();

  /// Picks the provider and voice for [agent] from what the workspace has.
  factory VoiceProfile.resolve(
    AgentSummary agent,
    VoiceCapabilities capabilities, {
    double speed = 1.0,
    List<String> knownNames = const [],
  }) {
    final config = agent.voiceConfig;
    final wanted = config['tts_provider']?.toString();

    String? provider;
    if (wanted != null && capabilities.providers.contains(wanted)) {
      provider = wanted;
    } else if (capabilities.providers.contains('openai_tts')) {
      provider = 'openai_tts';
    } else if (capabilities.providers.contains('elevenlabs')) {
      provider = 'elevenlabs';
    }

    // Voice ids are provider specific; only reuse the agent's when it was
    // chosen for the provider we ended up with.
    final voice = (provider == wanted) ? config['tts_voice']?.toString() : null;
    final model = (provider == wanted) ? config['tts_model']?.toString() : null;
    final language = config['language']?.toString();

    final names = <String>{'Synkora', agent.name, ...knownNames};
    return VoiceProfile(
      ttsProvider: provider,
      voiceId: (voice == null || voice.isEmpty) ? null : voice,
      model: (model == null || model.isEmpty) ? null : model,
      language: _isoLanguage(language),
      speed: speed,
      agentId: agent.id,
      hint:
          'Conversation with a voice assistant. Names: '
          '${names.take(8).join(', ')}.',
    );
  }

  static String? _isoLanguage(String? tag) {
    if (tag == null || tag.isEmpty) return null;
    final base = tag.split(RegExp('[-_]')).first.toLowerCase();
    return RegExp(r'^[a-z]{2}$').hasMatch(base) ? base : null;
  }
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
