import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:synkora_mobile/src/services/api_client.dart';
import 'package:synkora_mobile/src/voice/voice_conversation.dart';
import 'package:synkora_mobile/src/voice/voice_profile.dart';
import 'package:synkora_mobile/src/voice/voice_settings.dart';
import 'package:synkora_mobile/src/voice/wake/wake_keywords.dart';

import 'support/fakes.dart';
import 'support/hub_fixture.dart';

Future<void> tick() async {
  await Future<void>.delayed(Duration.zero);
  await Future<void>.delayed(Duration.zero);
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('following the agent\'s own voice settings', () {
    test(
      'a default (web_speech) agent works with no keys and uses the phone',
      () async {
        final f = await HubFixture.create(
          providers: const [],
          agentVoice: builtInVoice,
        );
        final muse = fakeAgent('Muse');
        f.hub.updateAgents([muse]);

        await f.hub.open(muse);
        await tick();

        expect(f.hub.issue, isNull);
        expect(f.hub.conversation.phase, VoicePhase.listening);
        expect(f.hub.conversation.useDeviceListening, isTrue);
        expect(f.hub.activeProfile.listen, SpeechSource.device);
        expect(f.hub.activeProfile.speak, SpeechSource.device);
        expect(
          f.api.getPaths,
          isNot(contains('/api/v1/voice/api-keys')),
          reason: 'built-in speech never asks about workspace keys',
        );
        // The phone's recognizer owns the microphone, so ours stays closed.
        expect(f.mic.running, isFalse);
        expect(f.live.listenCalls, 1);
        f.hub.dispose();
      },
    );

    test(
      'the agent language reaches the phone recognizer as its locale',
      () async {
        final f = await HubFixture.create(
          agentVoice: {...builtInVoice, 'language': 'fr-FR'},
        );
        await f.hub.open(fakeAgent('Muse'));
        await tick();

        expect(f.live.lastLocale, 'fr-FR');
        expect(f.hub.activeProfile.locale, 'fr-FR');
        f.hub.dispose();
      },
    );

    test('a cloud agent with keys listens through our microphone', () async {
      final f = await HubFixture.create();
      final muse = fakeAgent('Muse');
      f.hub.updateAgents([muse]);

      await f.hub.open(muse);

      expect(f.hub.issue, isNull);
      expect(f.hub.conversation.useDeviceListening, isFalse);
      expect(f.hub.activeProfile.ttsProvider, 'openai_tts');
      expect(f.hub.activeProfile.voiceId, 'shimmer');
      expect(f.mic.running, isTrue);
      expect(f.live.listenCalls, 0);
      f.hub.dispose();
    });

    test(
      'workspace keys do not override an agent set to built-in speech',
      () async {
        final f = await HubFixture.create(
          providers: const ['openai_whisper', 'openai_tts', 'elevenlabs'],
          agentVoice: builtInVoice,
        );
        await f.hub.open(fakeAgent('Muse'));

        expect(f.hub.activeProfile.speak, SpeechSource.device);
        expect(f.hub.activeProfile.ttsProvider, isNull);
        f.hub.dispose();
      },
    );

    test(
      'workspace keys are loaded once and cached for cloud agents',
      () async {
        final f = await HubFixture.create();
        final muse = fakeAgent('Muse');

        await f.hub.open(muse);
        await f.hub.close();
        await f.hub.open(muse);

        expect(
          f.api.getPaths.where((p) => p == '/api/v1/voice/api-keys').length,
          1,
        );
        expect(
          f.api.getPaths.where((p) => p == '/api/v1/agents/muse').length,
          1,
          reason: 'agent details are fetched once per session',
        );
        f.hub.dispose();
      },
    );

    test(
      'if the key lookup fails it stays optimistic and still tries',
      () async {
        final f = await HubFixture.create();
        f.api.failure = const SynkoraApiException('offline', statusCode: 503);

        await f.hub.open(fakeAgent('Muse'));

        expect(f.hub.issue, isNull);
        expect(f.hub.conversation.phase, VoicePhase.listening);
        f.hub.dispose();
      },
    );
  });

  group('issues and their one-tap fixes', () {
    test(
      'a paid provider without a key explains it and does not open the mic',
      () async {
        final f = await HubFixture.create(providers: const []);

        await f.hub.open(fakeAgent('Muse'));

        expect(f.hub.issue!.kind, VoiceIssueKind.missingKey);
        expect(f.hub.conversation.phase, VoicePhase.error);
        expect(f.hub.conversation.error, contains('OpenAI Whisper'));
        expect(f.mic.running, isFalse);
        f.hub.dispose();
      },
    );

    test('"use my phone\'s voice" continues with built-in speech', () async {
      final f = await HubFixture.create(providers: const []);
      await f.hub.open(fakeAgent('Muse'));

      await f.hub.resolveIssue();
      await tick();

      expect(f.hub.issue, isNull);
      expect(f.hub.conversation.phase, VoicePhase.listening);
      expect(f.hub.activeProfile.speak, SpeechSource.device);
      expect(f.hub.conversation.useDeviceListening, isTrue);
      expect(f.live.listenCalls, 1);
      f.hub.dispose();
    });

    test('voice turned off is reported, not silently ignored', () async {
      final f = await HubFixture.create(
        agentVoice: builtInVoice,
        voiceEnabled: false,
      );

      await f.hub.open(fakeAgent('Muse'));

      expect(f.hub.issue!.kind, VoiceIssueKind.voiceDisabled);
      expect(
        f.hub.conversation.error,
        contains('Voice is turned off for Muse'),
      );
      expect(f.mic.running, isFalse);
      f.hub.dispose();
    });

    test(
      '"turn on voice" enables it for the agent and starts the conversation',
      () async {
        final f = await HubFixture.create(
          agentVoice: builtInVoice,
          voiceEnabled: false,
        );
        await f.hub.open(fakeAgent('Muse'));

        await f.hub.resolveIssue();

        expect(f.api.puts.single.path, '/api/v1/agents/muse');
        expect(f.api.puts.single.body, {'voice_enabled': true});
        expect(f.hub.issue, isNull);
        expect(f.hub.conversation.phase, VoicePhase.listening);
        f.hub.dispose();
      },
    );

    test(
      'if only the owner can enable voice, it says so instead of failing silently',
      () async {
        final f = await HubFixture.create(
          agentVoice: builtInVoice,
          voiceEnabled: false,
        );
        f.api.putFailure = const SynkoraApiException(
          'forbidden',
          statusCode: 403,
        );
        await f.hub.open(fakeAgent('Muse'));

        await f.hub.resolveIssue();

        expect(f.hub.conversation.phase, VoicePhase.error);
        expect(f.hub.conversation.error, contains('Only its owner'));
        f.hub.dispose();
      },
    );
  });

  group('hands-free wake', () {
    test('wake resolves the agent voice without open() being called', () async {
      final f = await HubFixture.create();
      f.hub.updateAgents([fakeAgent('Muse')]);

      await f.hub.prepareDefaultAgent();

      expect(f.hub.activeProfile.ttsProvider, 'openai_tts');
      expect(f.hub.activeProfile.voiceId, 'shimmer');
      f.hub.dispose();
    });

    test('turning wake on in settings arms the microphone', () async {
      final f = await HubFixture.create();

      await f.settings.setWakeEnabled(true);
      await tick();

      expect(f.hub.conversation.phase, VoicePhase.armed);
      expect(f.mic.running, isTrue);

      await f.settings.setWakeEnabled(false);
      await tick();
      expect(f.hub.conversation.phase, VoicePhase.idle);
      expect(f.mic.running, isFalse);
      f.hub.dispose();
    });

    test(
      'going to the background releases the mic; returning re-arms it',
      () async {
        final f = await HubFixture.create(prefs: {'voice.wakeEnabled': true});
        await f.hub.start();
        expect(f.hub.conversation.phase, VoicePhase.armed);

        f.hub.didChangeAppLifecycleState(AppLifecycleState.paused);
        await tick();
        expect(f.mic.running, isFalse);

        f.hub.didChangeAppLifecycleState(AppLifecycleState.resumed);
        await tick();
        expect(f.hub.conversation.phase, VoicePhase.armed);
        expect(f.mic.running, isTrue);
        f.hub.dispose();
      },
    );

    test('defaultAgent is the last used one, else the first', () async {
      final f = await HubFixture.create(
        prefs: {'voice.lastAgentId': 'grokbot'},
      );
      f.hub.updateAgents([fakeAgent('Muse'), fakeAgent('GrokBot')]);
      expect(f.hub.defaultAgent!.name, 'GrokBot');

      final g = await HubFixture.create();
      g.hub.updateAgents([fakeAgent('Muse'), fakeAgent('GrokBot')]);
      expect(g.hub.defaultAgent!.name, 'Muse');
      f.hub.dispose();
      g.hub.dispose();
    });

    test(
      'the saved sensitivity is applied to the wake detector, and changes follow',
      () async {
        final f = await HubFixture.create(
          prefs: {'voice.wakeSensitivity': WakeSensitivity.high.index},
        );
        expect(f.wake.sensitivity, WakeSensitivity.high);

        await f.settings.setWakeSensitivity(WakeSensitivity.low);

        expect(f.wake.sensitivity, WakeSensitivity.low);
        f.hub.dispose();
      },
    );

    test(
      'the wake model is loaded up front so problems show before first use',
      () async {
        final f = await HubFixture.create(prefs: {'voice.wakeEnabled': true});
        f.wake.failure = 'model file missing';
        var notified = 0;
        f.hub.addListener(() => notified++);

        await f.hub.start();
        await tick();

        expect(f.wake.startCalls, greaterThan(0));
        expect(f.hub.wakeProblem, 'model file missing');
        expect(notified, greaterThan(0), reason: 'the UI must be told');
        f.hub.dispose();
      },
    );

    test(
      'no wake problem when healthy, and no model load when wake is off',
      () async {
        final f = await HubFixture.create(prefs: {'voice.wakeEnabled': true});
        await f.hub.start();
        expect(f.hub.wakeProblem, isNull);

        final off = await HubFixture.create();
        off.wake.failure = 'ignored until enabled';
        await off.hub.start();
        expect(off.wake.startCalls, 0);
        f.hub.dispose();
        off.hub.dispose();
      },
    );
  });

  group('VoiceSettings', () {
    test('clamp speed and persist values', () async {
      SharedPreferences.setMockInitialValues({});
      final s = await VoiceSettings.load();
      await s.setSpeed(3);
      expect(s.speed, 1.4);
      await s.setSpeed(0.1);
      expect(s.speed, 0.8);
      expect(s.wakeEnabled, isFalse, reason: 'wake is opt-in');
      await s.setBargeIn(false);
      expect(s.bargeIn, isFalse);
    });

    test(
      'wake sensitivity defaults to balanced and survives a bad stored value',
      () async {
        SharedPreferences.setMockInitialValues({});
        expect(
          (await VoiceSettings.load()).wakeSensitivity,
          WakeSensitivity.balanced,
        );

        SharedPreferences.setMockInitialValues({'voice.wakeSensitivity': 99});
        expect(
          (await VoiceSettings.load()).wakeSensitivity,
          WakeSensitivity.balanced,
        );

        SharedPreferences.setMockInitialValues({});
        final s = await VoiceSettings.load();
        await s.setWakeSensitivity(WakeSensitivity.low);
        expect(s.wakeSensitivity, WakeSensitivity.low);
      },
    );
  });
}
