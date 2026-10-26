import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:synkora_mobile/src/models/synkora_models.dart';
import 'package:synkora_mobile/src/ui/voice/voice_hub_scope.dart';
import 'package:synkora_mobile/src/ui/voice/voice_mode_screen.dart';
import 'package:synkora_mobile/src/voice/audio/pcm.dart';
import 'package:synkora_mobile/src/voice/voice_conversation.dart';
import 'package:synkora_mobile/src/voice/wake/wake_keywords.dart';

import '../voice/support/fakes.dart';
import '../voice/support/hub_fixture.dart';
import '../voice/support/signals.dart';

/// Hosts a button that opens the voice screen, like the real app does.
Widget host(HubFixture f, AgentSummary agent, {bool alreadyListening = false}) {
  return MaterialApp(
    theme: ThemeData.dark(),
    home: VoiceHubScope(
      hub: f.hub,
      child: Builder(
        builder: (context) => Scaffold(
          body: Center(
            child: ElevatedButton(
              onPressed: () => Navigator.of(context).push(
                VoiceModeScreen.route(
                  hub: f.hub,
                  agent: agent,
                  alreadyListening: alreadyListening,
                ),
              ),
              child: const Text('open voice'),
            ),
          ),
        ),
      ),
    ),
  );
}

Future<void> settle(WidgetTester tester, [int ms = 600]) async {
  for (var i = 0; i < ms ~/ 50; i++) {
    await tester.pump(const Duration(milliseconds: 50));
  }
}

void main() {
  final muse = fakeAgent('Muse');

  testWidgets('opening the screen starts listening and shows the agent', (
    tester,
  ) async {
    final f = await HubFixture.create();
    f.hub.updateAgents([muse]);
    await tester.pumpWidget(host(f, muse));

    await tester.tap(find.text('open voice'));
    await settle(tester, 1000);

    expect(find.text('Muse'), findsWidgets);
    expect(find.text('I’m listening'), findsOneWidget);
    expect(f.hub.conversation.phase, VoicePhase.listening);
    expect(f.mic.running, isTrue);

    // Leave the tree cleanly.
    await tester.tap(find.bySemanticsLabel('End conversation'));
    await settle(tester, 800);
  });

  testWidgets('saying goodbye closes the screen and returns to where you were', (
    tester,
  ) async {
    final f = await HubFixture.create();
    f.hub.updateAgents([muse]);
    f.api.jsonResponse = {
      'data': {'text': 'That’s all, thanks. Goodbye.'},
    };
    await tester.pumpWidget(host(f, muse));
    await tester.tap(find.text('open voice'));
    await settle(tester, 1000);
    expect(find.text('I’m listening'), findsOneWidget);

    f.mic.feed(noise(600));
    f.mic.feed(speech(1500));
    f.mic.feed(noise(1200));
    await settle(tester, 1500);

    // Regression: the screen used to stay open (its own PopScope vetoed the pop).
    expect(find.text('open voice'), findsOneWidget);
    expect(find.text('I’m listening'), findsNothing);
    expect(f.mic.running, isFalse);
  });

  testWidgets('a missing speech key shows a clear message with a retry', (
    tester,
  ) async {
    final f = await HubFixture.create(providers: const []);
    f.hub.updateAgents([muse]);
    await tester.pumpWidget(host(f, muse));

    await tester.tap(find.text('open voice'));
    await settle(tester, 1000);

    expect(find.text('Something went wrong'), findsOneWidget);
    expect(find.textContaining('speech provider key'), findsOneWidget);
    expect(find.text('Try again'), findsOneWidget);

    await tester.tap(find.bySemanticsLabel('End conversation'));
    await settle(tester, 800);
    expect(find.text('open voice'), findsOneWidget);
  });

  testWidgets('the end button closes the conversation and releases the mic', (
    tester,
  ) async {
    final f = await HubFixture.create();
    f.hub.updateAgents([muse]);
    await tester.pumpWidget(host(f, muse));
    await tester.tap(find.text('open voice'));
    await settle(tester, 1000);
    expect(f.mic.running, isTrue);

    await tester.tap(find.bySemanticsLabel('End conversation'));
    await settle(tester, 800);

    expect(find.text('open voice'), findsOneWidget);
    expect(f.mic.running, isFalse);
    expect(f.hub.conversation.phase, VoicePhase.idle);
  });

  testWidgets('mute toggles the microphone label', (tester) async {
    final f = await HubFixture.create();
    f.hub.updateAgents([muse]);
    await tester.pumpWidget(host(f, muse));
    await tester.tap(find.text('open voice'));
    await settle(tester, 1000);

    await tester.tap(find.bySemanticsLabel('Mute microphone'));
    await settle(tester, 200);

    expect(find.text('Mic is muted'), findsOneWidget);
    expect(find.bySemanticsLabel('Unmute microphone'), findsOneWidget);

    await tester.tap(find.bySemanticsLabel('End conversation'));
    await settle(tester, 800);
  });

  testWidgets('typing a message sends it as a turn', (tester) async {
    final f = await HubFixture.create();
    f.hub.updateAgents([muse]);
    f.api.bytesResponse = pcm16ToWav(speech(300));
    await tester.pumpWidget(host(f, muse));
    await tester.tap(find.text('open voice'));
    await settle(tester, 1000);

    await tester.tap(find.bySemanticsLabel('Type a message'));
    await settle(tester, 300);
    await tester.enterText(find.byType(TextField), 'What time is it?');
    await tester.testTextInput.receiveAction(TextInputAction.send);
    await settle(tester, 300);

    expect(f.hub.conversation.turns.first.text, 'What time is it?');
    expect(f.hub.conversation.turns.first.isUser, isTrue);

    await tester.tap(find.bySemanticsLabel('End conversation'));
    await settle(tester, 800);
  });

  testWidgets(
    'the settings sheet offers hands-free only when a wake engine exists',
    (tester) async {
      final f = await HubFixture.create();
      f.hub.updateAgents([muse]);
      await tester.pumpWidget(host(f, muse));
      await tester.tap(find.text('open voice'));
      await settle(tester, 1000);

      await tester.tap(find.byTooltip('Voice settings'));
      await settle(tester, 600);

      expect(find.text('Voice settings'), findsOneWidget);
      expect(
        find.text('Wake with “Hey Synkora”'),
        findsOneWidget,
      ); // fixture has a wake fake
      expect(find.text('Interrupt by speaking'), findsOneWidget);
      expect(find.textContaining('Speaking speed'), findsOneWidget);

      await tester.tapAt(const Offset(10, 10)); // dismiss the sheet
      await settle(tester, 500);
      await tester.tap(find.bySemanticsLabel('End conversation'));
      await settle(tester, 800);
    },
  );

  testWidgets(
    'wake sensitivity is offered once hands-free is on and can be changed',
    (tester) async {
      final f = await HubFixture.create(prefs: {'voice.wakeEnabled': true});
      f.hub.updateAgents([muse]);
      await tester.pumpWidget(host(f, muse));
      await tester.tap(find.text('open voice'));
      await settle(tester, 1000);

      await tester.tap(find.byTooltip('Voice settings'));
      await settle(tester, 600);

      expect(find.text('Wake sensitivity'), findsOneWidget);
      expect(find.text('Balanced'), findsOneWidget);
      await tester.tap(find.text('Fewer wakes'));
      await settle(tester, 300);

      expect(f.settings.wakeSensitivity, WakeSensitivity.low);
      expect(f.wake.sensitivity, WakeSensitivity.low);

      await tester.tapAt(const Offset(10, 10));
      await settle(tester, 500);
      await tester.tap(find.bySemanticsLabel('End conversation'));
      await settle(tester, 800);
    },
  );

  testWidgets('a wake problem is explained instead of silently not working', (
    tester,
  ) async {
    final f = await HubFixture.create(prefs: {'voice.wakeEnabled': true});
    f.wake.failure = 'could not load the speech model';
    f.hub.updateAgents([muse]);
    await tester.pumpWidget(host(f, muse));
    await f.hub.start();
    await tester.tap(find.text('open voice'));
    await settle(tester, 1000);

    await tester.tap(find.byTooltip('Voice settings'));
    await settle(tester, 600);

    expect(find.textContaining('unavailable on this device'), findsOneWidget);
    expect(
      find.textContaining('could not load the speech model'),
      findsOneWidget,
    );
    expect(find.textContaining('tap the orb'), findsOneWidget);

    await tester.tapAt(const Offset(10, 10));
    await settle(tester, 500);
    await tester.tap(find.bySemanticsLabel('End conversation'));
    await settle(tester, 800);
  });
}
