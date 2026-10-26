import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:synkora_mobile/src/services/api_client.dart';
import 'package:synkora_mobile/src/voice/audio/pcm.dart';
import 'package:synkora_mobile/src/voice/engines/backend_voice.dart';
import 'package:synkora_mobile/src/voice/ports.dart';

import 'support/fake_api.dart';
import 'support/fakes.dart';
import 'support/signals.dart';

VoiceCapabilities caps(List<String> providers) =>
    VoiceCapabilities(providers.toSet());

void main() {
  group('VoiceCapabilities.load', () {
    test('reads active providers, tolerating enum-style names', () async {
      final api = RecordingApi()
        ..jsonResponse = {
          'data': {
            'api_keys': [
              {'provider': 'openai_whisper', 'is_active': true},
              {'provider': 'VoiceProvider.OPENAI_TTS', 'is_active': true},
              {'provider': 'elevenlabs', 'is_active': false},
            ],
          },
        };

      final c = await VoiceCapabilities.load(api);

      expect(c.providers, {'openai_whisper', 'openai_tts'});
      expect(c.ready, isTrue);
      expect(c.problem, isNull);
    });

    test('explains what is missing', () {
      expect(caps([]).problem, contains('speech provider key'));
      expect(caps(['openai_tts']).problem, contains('speech recognition'));
      expect(caps(['openai_whisper']).problem, contains('speech output'));
    });
  });

  group('VoiceProfile.resolve', () {
    test('uses the agent\'s configured provider, voice and language', () {
      final agent = fakeAgentWithVoice({
        'tts_provider': 'elevenlabs',
        'tts_voice': 'rachel-id',
        'tts_model': 'eleven_turbo_v2',
        'language': 'fr-FR',
      });
      final p = VoiceProfile.resolve(
        agent,
        caps(['openai_whisper', 'openai_tts', 'elevenlabs']),
      );

      expect(p.ttsProvider, 'elevenlabs');
      expect(p.voiceId, 'rachel-id');
      expect(p.model, 'eleven_turbo_v2');
      expect(p.language, 'fr');
    });

    test(
      'falls back to a configured provider and drops the foreign voice id',
      () {
        final agent = fakeAgentWithVoice({
          'tts_provider': 'elevenlabs',
          'tts_voice': 'rachel-id',
        });
        final p = VoiceProfile.resolve(
          agent,
          caps(['openai_whisper', 'openai_tts']),
        );

        expect(p.ttsProvider, 'openai_tts');
        expect(
          p.voiceId,
          isNull,
          reason: 'an ElevenLabs id is invalid for OpenAI',
        );
      },
    );

    test('browser-only "web_speech" is replaced by an available provider', () {
      final p = VoiceProfile.resolve(
        fakeAgentWithVoice({'tts_provider': 'web_speech'}),
        caps(['openai_tts']),
      );
      expect(p.ttsProvider, 'openai_tts');
    });

    test('no provider when none is configured; language auto-detects', () {
      final p = VoiceProfile.resolve(fakeAgent('Muse'), caps([]));
      expect(p.ttsProvider, isNull);
      expect(p.language, isNull);
    });

    test('hint lists Synkora and agent names for the recognizer', () {
      final p = VoiceProfile.resolve(
        fakeAgent('Muse'),
        caps(['openai_tts']),
        knownNames: ['GrokBot'],
      );
      expect(
        p.hint,
        allOf(contains('Synkora'), contains('Muse'), contains('GrokBot')),
      );
    });
  });

  group('BackendSpeechRecognizer', () {
    test(
      'uploads a wav with provider, language and hint as query parameters',
      () async {
        final api = RecordingApi()
          ..jsonResponse = {
            'data': {'text': 'hello there'},
          };
        final stt = BackendSpeechRecognizer(api, model: 'gpt-4o-transcribe')
          ..profile = VoiceProfile.resolve(
            fakeAgentWithVoice({'language': 'en-US'}),
            caps(['openai_tts']),
          );

        final text = await stt.transcribe(pcm16ToWav(speech(300)));

        expect(text, 'hello there');
        expect(api.lastPath, '/api/v1/voice/transcribe');
        expect(api.lastQuery!['provider'], 'openai_whisper');
        expect(api.lastQuery!['language'], 'en');
        expect(api.lastQuery!['model'], 'gpt-4o-transcribe');
        expect(api.lastQuery!['prompt'], contains('Synkora'));
        final file = api.lastForm!.files.single.value;
        expect(file.filename, 'speech.wav');
        expect(file.contentType.toString(), 'audio/wav');
      },
    );

    test('a missing provider key becomes VoiceUnavailableException', () async {
      final api = RecordingApi()
        ..failure = const SynkoraApiException(
          'OpenAI API key is required',
          statusCode: 400,
        );

      expect(
        BackendSpeechRecognizer(api).transcribe(Uint8List(10)),
        throwsA(isA<VoiceUnavailableException>()),
      );
    });

    test(
      'other failures stay ordinary errors so the turn is retried',
      () async {
        final api = RecordingApi()
          ..failure = const SynkoraApiException('boom', statusCode: 500);

        expect(
          BackendSpeechRecognizer(api).transcribe(Uint8List(10)),
          throwsA(isA<SynkoraApiException>()),
        );
      },
    );
  });

  group('BackendSpeechSynthesizer', () {
    test('asks OpenAI for wav and returns a loudness envelope', () async {
      final api = RecordingApi()
        ..bytesResponse = pcm16ToWav(speech(500), sampleRate: 24000);
      final tts = BackendSpeechSynthesizer(api)
        ..profile = VoiceProfile.resolve(
          fakeAgentWithVoice({
            'tts_voice': 'shimmer',
            'tts_provider': 'openai_tts',
          }),
          caps(['openai_tts']),
          speed: 1.15,
        );

      final audio = await tts.synthesize('Hello');

      final body = api.lastBody! as Map<String, dynamic>;
      expect(api.lastPath, '/api/v1/voice/synthesize');
      expect(body['provider'], 'openai_tts');
      expect(body['voice_id'], 'shimmer');
      expect(body['speed'], 1.15);
      expect((body['config'] as Map)['format'], 'wav');
      expect(audio.mimeType, 'audio/wav');
      expect(audio.envelope, isNotEmpty);
      expect(audio.duration, isNotNull);
    });

    test('defaults the OpenAI voice and omits speed at normal rate', () async {
      final api = RecordingApi()..bytesResponse = pcm16ToWav(speech(100));
      final tts = BackendSpeechSynthesizer(api)
        ..profile = VoiceProfile.resolve(
          fakeAgent('Muse'),
          caps(['openai_tts']),
        );

      await tts.synthesize('Hi');

      final body = api.lastBody! as Map<String, dynamic>;
      expect(body['voice_id'], 'nova');
      expect(body.containsKey('speed'), isFalse);
    });

    test('ElevenLabs uses mp3 and passes its model', () async {
      final api = RecordingApi()
        ..bytesResponse = Uint8List.fromList([0x49, 0x44, 0x33, 4, 0, 0]);
      final tts = BackendSpeechSynthesizer(api)
        ..profile = VoiceProfile.resolve(
          fakeAgentWithVoice({
            'tts_provider': 'elevenlabs',
            'tts_voice': 'abc',
            'tts_model': 'eleven_turbo_v2',
          }),
          caps(['elevenlabs']),
        );

      final audio = await tts.synthesize('Hi');

      final config = (api.lastBody! as Map)['config'] as Map;
      expect(config['format'], startsWith('mp3'));
      expect(config['model_id'], 'eleven_turbo_v2');
      expect(audio.mimeType, 'audio/mpeg');
      expect(audio.envelope, isEmpty);
    });

    test('no configured provider is VoiceUnavailable', () {
      final tts = BackendSpeechSynthesizer(RecordingApi());
      expect(tts.synthesize('Hi'), throwsA(isA<VoiceUnavailableException>()));
    });

    test('empty audio is an error, not silence', () {
      final api = RecordingApi();
      final tts = BackendSpeechSynthesizer(api)
        ..profile = VoiceProfile.resolve(
          fakeAgent('Muse'),
          caps(['openai_tts']),
        );
      expect(tts.synthesize('Hi'), throwsA(isA<SynkoraApiException>()));
    });
  });
}
