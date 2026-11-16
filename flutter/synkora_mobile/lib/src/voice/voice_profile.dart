import '../models/synkora_models.dart';
import 'voice_messages.dart';

/// Where listening or speaking happens for one agent.
enum SpeechSource {
  /// The workspace's speech provider (Whisper, OpenAI TTS, ElevenLabs).
  cloud,

  /// The phone's built-in speech engines. Free, needs no key.
  device,
}

enum VoiceIssueKind {
  /// The agent's owner has not enabled voice for it.
  voiceDisabled,

  /// The agent is set to a paid speech provider that has no key saved.
  missingKey,
}

/// A reason voice cannot start yet, with something the user can do about it.
class VoiceIssue {
  const VoiceIssue(this.kind, this.message);

  final VoiceIssueKind kind;
  final String message;
}

/// Which speech providers the workspace has keys for.
class VoiceCapabilities {
  const VoiceCapabilities(this.providers);

  /// Active provider ids such as `openai_whisper`, `openai_tts`, `elevenlabs`.
  final Set<String> providers;

  bool has(String provider) => providers.contains(provider);

  /// Reads the `/voice/api-keys` response.
  factory VoiceCapabilities.fromApiKeys(Map<String, dynamic> response) {
    final data = response['data'];
    final keys = data is Map ? data['api_keys'] : null;
    final providers = <String>{};
    for (final key in keys is List ? keys : const []) {
      if (key is! Map) continue;
      if (key['is_active'] == false) continue;
      final raw = key['provider']?.toString().toLowerCase() ?? '';
      // Enum members may serialize as "VoiceProvider.OPENAI_TTS" or "openai_tts".
      providers.add(raw.split('.').last);
    }
    return VoiceCapabilities(providers);
  }
}

/// How one agent should be heard and spoken to, following the agent's own
/// voice settings (`voice_enabled` and `voice_config`) exactly.
///
/// `web_speech`, the default for both directions, means built-in speech: on a
/// phone that is the device's own recognizer and voice, which needs no key.
/// The paid providers are used only when the agent is set to them.
class VoiceProfile {
  const VoiceProfile({
    this.listen = SpeechSource.device,
    this.speak = SpeechSource.device,
    this.ttsProvider,
    this.voiceId,
    this.model,
    this.language,
    this.locale,
    this.speed = 1.0,
    this.agentId,
    this.hint,
    this.issue,
  });

  final SpeechSource listen;
  final SpeechSource speak;

  /// `openai_tts` or `elevenlabs` when [speak] is cloud.
  final String? ttsProvider;
  final String? voiceId;
  final String? model;

  /// ISO-639-1 code (`en`) for Whisper when the agent pins a language.
  final String? language;

  /// BCP-47 locale (`en-US`) for the built-in engines.
  final String? locale;
  final double speed;
  final String? agentId;

  /// Vocabulary hint for the cloud recognizer (names it would misspell).
  final String? hint;

  /// Why voice cannot start, or null.
  final VoiceIssue? issue;

  static const empty = VoiceProfile();

  bool get usesCloud =>
      listen == SpeechSource.cloud || speak == SpeechSource.cloud;

  /// Plans listening and speaking for [agent].
  ///
  /// [capabilities] is null while unknown (not loaded or unreachable); that is
  /// treated optimistically and a real request will report any problem. Set
  /// [useBuiltIn] to ignore the paid providers (the user chose to continue with
  /// the phone's voice).
  factory VoiceProfile.resolve(
    AgentSummary agent, {
    VoiceCapabilities? capabilities,
    double speed = 1.0,
    List<String> knownNames = const [],
    bool useBuiltIn = false,
    VoiceMessages? messages,
  }) {
    final config = agent.voiceConfig;
    // What the assistant says follows the language of the agent's voice setting.
    final text =
        messages ?? VoiceMessages.forLanguage(config['language']?.toString());
    final sttWanted = config['stt_provider']?.toString();
    final ttsWanted = config['tts_provider']?.toString();

    final cloudListen = !useBuiltIn && sttWanted == 'openai_whisper';
    final cloudSpeak =
        !useBuiltIn && (ttsWanted == 'openai_tts' || ttsWanted == 'elevenlabs');

    VoiceIssue? issue;
    if (agent.voiceEnabled == false) {
      issue = VoiceIssue(
        VoiceIssueKind.voiceDisabled,
        text.voiceDisabled(agent.name),
      );
    } else if (capabilities != null) {
      final missing = <String>[
        if (cloudListen && !capabilities.has('openai_whisper'))
          text.whisperProvider,
        if (cloudSpeak && !capabilities.has(ttsWanted!))
          text.ttsProvider(elevenLabs: ttsWanted == 'elevenlabs'),
      ];
      if (missing.isNotEmpty) {
        issue = VoiceIssue(
          VoiceIssueKind.missingKey,
          text.missingKey(agent.name, missing),
        );
      }
    }

    String? clean(Object? value) {
      final text = value?.toString();
      return (text == null || text.isEmpty) ? null : text;
    }

    final names = <String>{'Synkora', agent.name, ...knownNames};
    final locale = clean(config['language']);
    return VoiceProfile(
      listen: cloudListen ? SpeechSource.cloud : SpeechSource.device,
      speak: cloudSpeak ? SpeechSource.cloud : SpeechSource.device,
      ttsProvider: cloudSpeak ? ttsWanted : null,
      voiceId: cloudSpeak ? clean(config['tts_voice']) : null,
      model: cloudSpeak ? clean(config['tts_model']) : null,
      language: _isoLanguage(locale),
      locale: locale,
      speed: speed,
      agentId: agent.id,
      hint: text.recognitionHint(names.take(8).toList()),
      issue: issue,
    );
  }

  static String? _isoLanguage(String? tag) {
    if (tag == null || tag.isEmpty) return null;
    final base = tag.split(RegExp('[-_]')).first.toLowerCase();
    return RegExp(r'^[a-z]{2}$').hasMatch(base) ? base : null;
  }
}
