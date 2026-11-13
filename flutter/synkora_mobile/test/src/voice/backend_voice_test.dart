import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:synkora_mobile/src/services/api_client.dart';
import 'package:synkora_mobile/src/voice/audio/pcm.dart';
import 'package:synkora_mobile/src/voice/engines/backend_voice.dart';
import 'package:synkora_mobile/src/voice/engines/device_speech.dart';
import 'package:synkora_mobile/src/voice/ports.dart';
import 'package:synkora_mobile/src/voice/voice_profile.dart';

import 'support/fake_api.dart';
import 'support/fakes.dart';
import 'support/signals.dart';

VoiceCapabilities caps(List<String> providers) =>
    VoiceCapabilities(providers.toSet());

VoiceProfile profile(
  Map<String, dynamic> voice,
  List<String> keys, {
  double speed = 1.0,
}) => VoiceProfile.resolve(
  fakeAgentWithVoice(voice).withVoice(voiceEnabled: true),
  capabilities: caps(keys),
  speed: speed,
);

void main() {
  test('loadVoiceCapabilities reads the workspace keys', () async {
    final api = RecordingApi()
      ..jsonByPath['/api/v1/voice/api-keys'] = {
        'data': {
          'api_keys': [
            {'provider': 'openai_whisper', 'is_active': true},
          ],
        },
      };

    final c = await loadVoiceCapabilities(api);

    expect(c.has('openai_whisper'), isTrue);
    expect(api.lastPath, '/api/v1/voice/api-keys');
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
          ..profile = profile(
            {'stt_provider': 'openai_whisper', 'language': 'en-US'},
            ['openai_whisper'],
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
        ..profile = profile(
          {'tts_voice': 'shimmer', 'tts_provider': 'openai_tts'},
          ['openai_tts'],
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
        ..profile = profile({'tts_provider': 'openai_tts'}, ['openai_tts']);

      await tts.synthesize('Hi');

      final body = api.lastBody! as Map<String, dynamic>;
      expect(body['voice_id'], 'nova');
      expect(body.containsKey('speed'), isFalse);
    });

    test('ElevenLabs uses mp3 and passes its model', () async {
      final api = RecordingApi()
        ..bytesResponse = Uint8List.fromList([0x49, 0x44, 0x33, 4, 0, 0]);
      final tts = BackendSpeechSynthesizer(api)
        ..profile = profile(
          {
            'tts_provider': 'elevenlabs',
            'tts_voice': 'abc',
            'tts_model': 'eleven_turbo_v2',
          },
          ['elevenlabs'],
        );

      final audio = await tts.synthesize('Hi');

      final config = (api.lastBody! as Map)['config'] as Map;
      expect(config['format'], startsWith('mp3'));
      expect(config['model_id'], 'eleven_turbo_v2');
      expect(audio.mimeType, 'audio/mpeg');
      expect(audio.envelope, isEmpty);
    });

    test('without a cloud provider in the profile it refuses to guess', () {
      final tts = BackendSpeechSynthesizer(RecordingApi());
      expect(tts.synthesize('Hi'), throwsA(isA<VoiceUnavailableException>()));
    });

    test('empty audio is an error, not silence', () {
      final api = RecordingApi();
      final tts = BackendSpeechSynthesizer(api)
        ..profile = profile({'tts_provider': 'openai_tts'}, ['openai_tts']);
      expect(tts.synthesize('Hi'), throwsA(isA<SynkoraApiException>()));
    });
  });

  group('RoutingSpeechSynthesizer', () {
    test(
      'built-in speech yields a text clip for the phone voice, with locale and speed',
      () async {
        final cloud = RecordingApi();
        final router = RoutingSpeechSynthesizer(BackendSpeechSynthesizer(cloud))
          ..profile = profile({'language': 'fr-FR'}, [], speed: 1.2);

        final clip = await router.synthesize('Bonjour');

        expect(clip.deviceSpeech!.text, 'Bonjour');
        expect(clip.deviceSpeech!.locale, 'fr-FR');
        expect(clip.deviceSpeech!.speed, 1.2);
        expect(clip.bytes, isEmpty);
        expect(
          cloud.lastPath,
          isNull,
          reason: 'no network call for built-in speech',
        );
      },
    );

    test('a cloud profile delegates to the cloud voice', () async {
      final api = RecordingApi()..bytesResponse = pcm16ToWav(speech(100));
      final cloud = BackendSpeechSynthesizer(api);
      final p = profile({'tts_provider': 'openai_tts'}, ['openai_tts']);
      cloud.profile = p;
      final router = RoutingSpeechSynthesizer(cloud)..profile = p;

      final clip = await router.synthesize('Hello');

      expect(clip.deviceSpeech, isNull);
      expect(api.lastPath, '/api/v1/voice/synthesize');
    });
  });

  group('RoutingAudioOutput', () {
    test(
      'text clips go to the phone voice and audio clips to the player',
      () async {
        final audio = FakeOutput();
        final device = FakeOutput();
        final router = RoutingAudioOutput(audio: audio, device: device);

        await router.play(
          SynthesizedAudio.device(const DeviceSpeech(text: 'spoken by phone')),
        );
        await router.play(
          SynthesizedAudio(
            bytes: Uint8List.fromList([97]),
            mimeType: 'audio/wav',
          ),
        );

        expect(device.playedDevice, ['spoken by phone']);
        expect(audio.played, ['a']);
      },
    );

    test('stop reaches both players', () async {
      final audio = FakeOutput();
      final device = FakeOutput();
      await RoutingAudioOutput(audio: audio, device: device).stop();

      expect(audio.stopCount, 1);
      expect(device.stopCount, 1);
    });

    test('levels from either player are forwarded', () async {
      final audio = FakeOutput();
      final device = FakeOutput();
      final router = RoutingAudioOutput(audio: audio, device: device);
      final seen = <double>[];
      router.level.listen(seen.add);

      audio.emitLevel(0.3);
      device.emitLevel(0.8);
      await Future<void>.delayed(Duration.zero);

      expect(seen, [0.3, 0.8]);
    });
  });
}
