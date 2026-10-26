import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:synkora_mobile/src/services/api_client.dart';
import 'package:synkora_mobile/src/voice/voice_conversation.dart';
import 'package:synkora_mobile/src/voice/voice_settings.dart';

import 'support/hub_fixture.dart';
import 'support/fakes.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('open() starts listening and loads the agent voice profile', () async {
    final f = await HubFixture.create();
    final muse = fakeAgent('Muse');
    f.hub.updateAgents([muse, fakeAgent('GrokBot')]);

    await f.hub.open(muse);

    expect(f.hub.conversation.phase, VoicePhase.listening);
    expect(f.mic.running, isTrue);
    // The detail endpoint was consulted for the agent's own voice settings.
    expect(f.api.lastPath, isNotNull);
    f.hub.dispose();
  });

  test(
    'hands-free wake (no open() call) still resolves the agent voice',
    () async {
      final f = await HubFixture.create();
      f.hub.updateAgents([fakeAgent('Muse')]);

      // This is the path taken when the app is armed and "Hey Synkora" is heard:
      // the default agent is prepared without anyone calling open().
      await f.hub.prepareDefaultAgent();

      expect(f.hub.activeProfile.ttsProvider, 'openai_tts');
      expect(f.hub.activeProfile.voiceId, 'shimmer');
      f.hub.dispose();
    },
  );

  test('capabilities are cached between opens', () async {
    final f = await HubFixture.create();
    final muse = fakeAgent('Muse');

    await f.hub.open(muse);
    await f.hub.close();
    final callsAfterFirst = f.api.getCount;
    await f.hub.open(muse);

    final keyLookups = f.api.getCount - callsAfterFirst;
    expect(
      keyLookups,
      lessThanOrEqualTo(1),
      reason: 'only an agent-detail lookup',
    );
    f.hub.dispose();
  });

  test(
    'a workspace without speech keys gets a clear setup error, not silence',
    () async {
      final f = await HubFixture.create(providers: const []);

      await f.hub.open(fakeAgent('Muse'));

      expect(f.hub.conversation.phase, VoicePhase.error);
      expect(f.hub.conversation.error, contains('speech provider key'));
      expect(f.mic.running, isFalse, reason: 'must not open the mic');
      f.hub.dispose();
    },
  );

  test('only recognition configured is called out specifically', () async {
    final f = await HubFixture.create(providers: const ['openai_tts']);

    await f.hub.open(fakeAgent('Muse'));

    expect(f.hub.conversation.error, contains('speech recognition'));
    f.hub.dispose();
  });

  test('if the key lookup fails it stays optimistic and still tries', () async {
    final f = await HubFixture.create();
    // Every GET fails (offline, server hiccup): the capability check and the
    // agent-detail lookup. Neither may stop the conversation from starting.
    f.api.failure = const SynkoraApiException('offline', statusCode: 503);

    await f.hub.open(fakeAgent('Muse'));

    expect(f.hub.setupProblem, isNull, reason: 'unknown is not a problem');
    expect(f.hub.conversation.phase, VoicePhase.listening);
    expect(f.mic.running, isTrue);
    f.hub.dispose();
  });

  test('turning wake on in settings arms the microphone', () async {
    final f = await HubFixture.create();

    await f.settings.setWakeEnabled(true);
    await Future<void>.delayed(Duration.zero);
    await Future<void>.delayed(Duration.zero);

    expect(f.hub.conversation.phase, VoicePhase.armed);
    expect(f.mic.running, isTrue);

    await f.settings.setWakeEnabled(false);
    await Future<void>.delayed(Duration.zero);
    await Future<void>.delayed(Duration.zero);
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
      await Future<void>.delayed(Duration.zero);
      await Future<void>.delayed(Duration.zero);
      expect(f.mic.running, isFalse);

      f.hub.didChangeAppLifecycleState(AppLifecycleState.resumed);
      await Future<void>.delayed(Duration.zero);
      await Future<void>.delayed(Duration.zero);
      expect(f.hub.conversation.phase, VoicePhase.armed);
      expect(f.mic.running, isTrue);
      f.hub.dispose();
    },
  );

  test('defaultAgent is the last used one, else the first', () async {
    final f = await HubFixture.create(prefs: {'voice.lastAgentId': 'grokbot'});
    f.hub.updateAgents([fakeAgent('Muse'), fakeAgent('GrokBot')]);
    expect(f.hub.defaultAgent!.name, 'GrokBot');

    final g = await HubFixture.create();
    g.hub.updateAgents([fakeAgent('Muse'), fakeAgent('GrokBot')]);
    expect(g.hub.defaultAgent!.name, 'Muse');
    f.hub.dispose();
    g.hub.dispose();
  });

  test('settings clamp speed and persist values', () async {
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
}
