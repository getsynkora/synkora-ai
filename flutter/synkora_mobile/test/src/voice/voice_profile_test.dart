import 'package:flutter_test/flutter_test.dart';
import 'package:synkora_mobile/src/models/synkora_models.dart';
import 'package:synkora_mobile/src/voice/voice_profile.dart';

import 'support/fakes.dart';

AgentSummary agent(Map<String, dynamic> voice, {bool? enabled = true}) =>
    fakeAgent('Muse', voice: voice).withVoice(voiceEnabled: enabled);

VoiceCapabilities caps([List<String> providers = const []]) =>
    VoiceCapabilities(providers.toSet());

void main() {
  group('defaults follow the agent settings page', () {
    test(
      'web_speech (the default) means the phone\'s own voice, no key needed',
      () {
        final p = VoiceProfile.resolve(
          agent({'stt_provider': 'web_speech', 'tts_provider': 'web_speech'}),
          capabilities: caps(),
        );

        expect(p.listen, SpeechSource.device);
        expect(p.speak, SpeechSource.device);
        expect(p.usesCloud, isFalse);
        expect(p.issue, isNull);
      },
    );

    test('an agent with no voice settings at all behaves like web_speech', () {
      final p = VoiceProfile.resolve(agent({}), capabilities: caps());

      expect(p.listen, SpeechSource.device);
      expect(p.speak, SpeechSource.device);
      expect(p.issue, isNull);
    });

    test('paid providers are used only when the agent chooses them', () {
      final p = VoiceProfile.resolve(
        agent({
          'stt_provider': 'openai_whisper',
          'tts_provider': 'elevenlabs',
          'tts_voice': 'rachel',
          'tts_model': 'eleven_turbo_v2',
        }),
        capabilities: caps(['openai_whisper', 'elevenlabs']),
      );

      expect(p.listen, SpeechSource.cloud);
      expect(p.speak, SpeechSource.cloud);
      expect(p.ttsProvider, 'elevenlabs');
      expect(p.voiceId, 'rachel');
      expect(p.model, 'eleven_turbo_v2');
      expect(p.issue, isNull);
    });

    test(
      'workspace keys never upgrade an agent that chose built-in speech',
      () {
        final p = VoiceProfile.resolve(
          agent({'stt_provider': 'web_speech', 'tts_provider': 'web_speech'}),
          capabilities: caps(['openai_whisper', 'openai_tts', 'elevenlabs']),
        );

        expect(p.listen, SpeechSource.device);
        expect(p.speak, SpeechSource.device);
        expect(p.ttsProvider, isNull);
      },
    );

    test('listening and speaking are chosen independently', () {
      final p = VoiceProfile.resolve(
        agent({'stt_provider': 'web_speech', 'tts_provider': 'openai_tts'}),
        capabilities: caps(['openai_tts']),
      );

      expect(p.listen, SpeechSource.device);
      expect(p.speak, SpeechSource.cloud);
      expect(p.ttsProvider, 'openai_tts');
      expect(p.issue, isNull);
    });
  });

  group('issues', () {
    test('voice turned off is reported first, with the agent name', () {
      final p = VoiceProfile.resolve(
        agent({'tts_provider': 'openai_tts'}, enabled: false),
        capabilities: caps(),
      );

      expect(p.issue!.kind, VoiceIssueKind.voiceDisabled);
      expect(p.issue!.message, contains('Muse'));
    });

    test('unknown voice_enabled (agent list entry) is not treated as off', () {
      final p = VoiceProfile.resolve(agent({}, enabled: null));
      expect(p.issue, isNull);
    });

    test(
      'a paid provider without a saved key names exactly what is missing',
      () {
        final p = VoiceProfile.resolve(
          agent({
            'stt_provider': 'openai_whisper',
            'tts_provider': 'elevenlabs',
          }),
          capabilities: caps(['openai_tts']),
        );

        expect(p.issue!.kind, VoiceIssueKind.missingKey);
        expect(p.issue!.message, contains('OpenAI Whisper'));
        expect(p.issue!.message, contains('ElevenLabs'));
        expect(p.issue!.message, contains('built-in voice'));
      },
    );

    test('only the missing provider is mentioned', () {
      final p = VoiceProfile.resolve(
        agent({'stt_provider': 'openai_whisper', 'tts_provider': 'openai_tts'}),
        capabilities: caps(['openai_whisper']),
      );

      expect(p.issue!.message, contains('OpenAI text-to-speech'));
      expect(p.issue!.message, isNot(contains('Whisper')));
    });

    test('unknown keys (not loaded or unreachable) are optimistic', () {
      final p = VoiceProfile.resolve(
        agent({'stt_provider': 'openai_whisper', 'tts_provider': 'openai_tts'}),
      );

      expect(p.issue, isNull);
      expect(p.usesCloud, isTrue);
    });

    test('choosing the phone\'s voice clears a missing-key issue', () {
      final p = VoiceProfile.resolve(
        agent({'stt_provider': 'openai_whisper', 'tts_provider': 'openai_tts'}),
        capabilities: caps(),
        useBuiltIn: true,
      );

      expect(p.issue, isNull);
      expect(p.listen, SpeechSource.device);
      expect(p.speak, SpeechSource.device);
      expect(p.ttsProvider, isNull);
    });

    test('voice off still blocks even when built-in voice was chosen', () {
      final p = VoiceProfile.resolve(
        agent({}, enabled: false),
        useBuiltIn: true,
      );
      expect(p.issue!.kind, VoiceIssueKind.voiceDisabled);
    });
  });

  group('language', () {
    test('the agent language is the device locale and the Whisper hint', () {
      final p = VoiceProfile.resolve(agent({'language': 'fr-FR'}));

      expect(p.locale, 'fr-FR');
      expect(p.language, 'fr');
    });

    test('no language means the device default and auto-detect', () {
      final p = VoiceProfile.resolve(agent({}));

      expect(p.locale, isNull);
      expect(p.language, isNull);
    });

    test('the recognizer hint lists Synkora and agent names', () {
      final p = VoiceProfile.resolve(agent({}), knownNames: ['GrokBot']);

      expect(
        p.hint,
        allOf(contains('Synkora'), contains('Muse'), contains('GrokBot')),
      );
    });
  });

  group('VoiceCapabilities.fromApiKeys', () {
    test('reads active providers, tolerating enum-style names', () {
      final c = VoiceCapabilities.fromApiKeys({
        'data': {
          'api_keys': [
            {'provider': 'openai_whisper', 'is_active': true},
            {'provider': 'VoiceProvider.OPENAI_TTS', 'is_active': true},
            {'provider': 'elevenlabs', 'is_active': false},
          ],
        },
      });

      expect(c.providers, {'openai_whisper', 'openai_tts'});
      expect(c.has('elevenlabs'), isFalse);
    });

    test('an empty or odd response means no providers', () {
      expect(VoiceCapabilities.fromApiKeys({}).providers, isEmpty);
      expect(
        VoiceCapabilities.fromApiKeys({
          'data': {'api_keys': 'x'},
        }).providers,
        isEmpty,
      );
    });
  });

  group('AgentSummary voice fields', () {
    test('are read from the agent detail JSON', () {
      final a = AgentSummary.fromJson({
        'id': '1',
        'agent_name': 'Muse',
        'slug': 'muse',
        'voice_enabled': true,
        'voice_config': {'tts_provider': 'openai_tts'},
      });

      expect(a.voiceEnabled, isTrue);
      expect(a.voiceConfig['tts_provider'], 'openai_tts');
    });

    test('are unknown when the list endpoint omits them', () {
      final a = AgentSummary.fromJson({
        'id': '1',
        'agent_name': 'Muse',
        'slug': 'muse',
      });

      expect(a.voiceEnabled, isNull);
      expect(a.voiceConfig, isEmpty);
    });
  });
}
