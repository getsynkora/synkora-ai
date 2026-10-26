import 'package:fake_async/fake_async.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:synkora_mobile/src/models/synkora_models.dart';
import 'package:synkora_mobile/src/voice/ports.dart';
import 'package:synkora_mobile/src/voice/voice_conversation.dart';

import 'support/fakes.dart';
import 'support/signals.dart';

extension on FakeAsync {
  /// Advances fake time, then lets long chains of awaited futures finish.
  void settle(Duration duration) {
    elapse(duration);
    for (var i = 0; i < 8; i++) {
      flushMicrotasks();
    }
  }
}

class Harness {
  Harness({
    this.withWake = false,
    List<AgentSummary>? agents,
    VoiceConversationConfig config = const VoiceConversationConfig(),
  }) {
    final available = agents ?? [fakeAgent('Muse'), fakeAgent('GrokBot')];
    convo = VoiceConversation(
      mic: mic,
      recognizer: recognizer,
      synthesizer: synth,
      output: output,
      gateway: gateway,
      wake: withWake ? wake : null,
      config: config,
      onCue: cues.add,
      agentsProvider: () => available,
    );
    muse = available.first;
  }

  final bool withWake;
  final mic = FakeMic();
  final recognizer = FakeRecognizer();
  final synth = FakeSynth();
  final output = FakeOutput();
  final gateway = FakeGateway();
  final wake = FakeWake();
  final cues = <VoiceCue>[];
  late final VoiceConversation convo;
  late final AgentSummary muse;

  /// Opens a session and lets the microphone calibrate to the room.
  void open(FakeAsync async, {AgentSummary? agent}) {
    convo.begin(agent: agent ?? muse);
    async.flushMicrotasks();
    mic.feed(noise(600));
  }

  /// The user says something; recognizer will return [transcript].
  void userSays(FakeAsync async, String transcript, {int speechMs = 1200}) {
    recognizer.results.add(transcript);
    mic.feed(speech(speechMs));
    mic.feed(noise(1000));
    async.settle(Duration.zero);
  }

  void dispose() => convo.dispose();
}

void main() {
  test(
    'a full spoken turn: listen, transcribe, ask agent, speak, listen again',
    () {
      fakeAsync((async) {
        final h = Harness();
        h.open(async);
        expect(h.convo.phase, VoicePhase.listening);
        expect(h.mic.running, isTrue);

        h.userSays(async, 'What is the weather in Paris?');
        expect(h.convo.phase, VoicePhase.thinking);
        expect(
          h.gateway.requests.single.message,
          'What is the weather in Paris?',
        );
        expect(h.gateway.requests.single.agent, 'Muse');

        h.gateway.chunk('It is sunny and 22 degrees. ');
        h.gateway.chunk('Bring sunglasses.');
        h.gateway.done();
        async.flushMicrotasks();
        expect(h.convo.phase, VoicePhase.speaking);

        async.settle(const Duration(seconds: 2));
        expect(h.output.played, [
          'It is sunny and 22 degrees.',
          'Bring sunglasses.',
        ]);
        expect(h.convo.phase, VoicePhase.listening);
        expect(h.convo.turns.map((t) => (t.isUser, t.text)).toList(), [
          (true, 'What is the weather in Paris?'),
          (false, 'It is sunny and 22 degrees. Bring sunglasses.'),
        ]);
        h.dispose();
      });
    },
  );

  test('starts speaking the first sentence before the reply has finished', () {
    fakeAsync((async) {
      final h = Harness();
      h.open(async);
      h.userSays(async, 'Tell me a story');

      h.gateway.chunk('Once upon a time there was a robot. ');
      async.settle(const Duration(milliseconds: 100));

      // The stream is still open (no "done"), yet the first sentence plays.
      expect(h.output.played, ['Once upon a time there was a robot.']);
      expect(h.convo.phase, VoicePhase.speaking);

      h.gateway.chunk('It learned to talk.');
      h.gateway.done();
      async.settle(const Duration(seconds: 2));
      expect(h.output.played.length, 2);
      h.dispose();
    });
  });

  test('synthesizes ahead while the current sentence is playing', () {
    fakeAsync((async) {
      final h = Harness();
      h.open(async);
      h.userSays(async, 'Count');
      h.output.playTime = const Duration(seconds: 5);

      h.gateway.chunk('One. Two. Three. ');
      async.flushMicrotasks();

      // All three requested at once even though only one is playing.
      expect(h.synth.requested, ['One.', 'Two.', 'Three.']);
      expect(h.output.played, ['One.']);
      h.dispose();
    });
  });

  test(
    'talking over the assistant interrupts it and keeps the words spoken',
    () {
      fakeAsync((async) {
        final h = Harness();
        h.open(async);
        h.userSays(async, 'Tell me about Rome');
        h.output.playTime = const Duration(seconds: 10);
        h.gateway.chunk('Rome is the capital of Italy. ');
        h.gateway.chunk('It was founded long ago. ');
        async.flushMicrotasks();
        expect(h.convo.phase, VoicePhase.speaking);

        h.recognizer.results.add('Actually, tell me about Paris');
        h.mic.feed(speech(900, db: -20)); // user talks over the reply
        async.flushMicrotasks();

        expect(h.convo.phase, VoicePhase.listening);
        expect(h.output.stopCount, greaterThan(0));
        expect(h.gateway.cancelled, isTrue);
        final interrupted = h.convo.turns.last;
        expect(interrupted.isUser, isFalse);
        expect(interrupted.interrupted, isTrue);
        expect(interrupted.text, 'Rome is the capital of Italy.');

        // The interrupting speech becomes the next turn.
        h.mic.feed(noise(1200));
        async.flushMicrotasks();
        expect(
          h.gateway.requests.last.message,
          'Actually, tell me about Paris',
        );
        h.dispose();
      });
    },
  );

  test('the next turn is spoken after an interruption (no stuck playback)', () {
    fakeAsync((async) {
      final h = Harness();
      h.open(async);
      h.userSays(async, 'First question');
      h.output.playTime = const Duration(seconds: 10);
      h.gateway.chunk('A long first answer begins here. ');
      async.flushMicrotasks();

      h.recognizer.results.add('Second question');
      h.mic.feed(speech(900, db: -20));
      h.mic.feed(noise(1200));
      async.flushMicrotasks();
      expect(h.gateway.requests.last.message, 'Second question');

      h.output.playTime = const Duration(milliseconds: 300);
      h.gateway.chunk('Here is the second answer.');
      h.gateway.done();
      async.settle(const Duration(seconds: 1));

      expect(h.output.played.last, 'Here is the second answer.');
      expect(h.convo.phase, VoicePhase.listening);
      h.dispose();
    });
  });

  test(
    'loud playback raises the bar so the assistant does not hear itself',
    () {
      fakeAsync((async) {
        final h = Harness();
        h.open(async);
        h.userSays(async, 'Hello');
        h.output.playTime = const Duration(seconds: 10);
        h.gateway.chunk('This is a long reply that keeps going. ');
        async.flushMicrotasks();
        expect(h.convo.phase, VoicePhase.speaking);

        // Playback is loud; mic picks up an echo at -30 dBFS (above the default
        // barge-in floor but not clearly above the playback level).
        h.output.emitLevel(0.9); // ~ -15 dBFS playback
        h.output.emitLevel(0.9);
        h.output.emitLevel(0.9);
        h.mic.feed(speech(1000, db: -33));
        async.flushMicrotasks();

        expect(
          h.convo.phase,
          VoicePhase.speaking,
          reason: 'echo must not interrupt',
        );
        h.dispose();
      });
    },
  );

  test('a stock hallucination on a short clip is ignored', () {
    fakeAsync((async) {
      final h = Harness();
      h.open(async);
      h.userSays(async, 'Thanks for watching!', speechMs: 400);

      expect(h.gateway.requests, isEmpty);
      expect(h.convo.phase, VoicePhase.listening);
      h.dispose();
    });
  });

  test('"goodbye" ends the session without asking the agent', () {
    fakeAsync((async) {
      final h = Harness();
      h.open(async);
      h.userSays(async, 'Goodbye');

      expect(h.gateway.requests, isEmpty);
      expect(h.convo.phase, VoicePhase.idle);
      expect(h.mic.running, isFalse);
      expect(h.cues, contains(VoiceCue.ended));
      h.dispose();
    });
  });

  test('"switch to GrokBot" changes agent and confirms aloud', () {
    fakeAsync((async) {
      final h = Harness();
      h.open(async);
      h.userSays(async, 'Switch to grok bot');
      async.settle(const Duration(seconds: 2));

      expect(h.convo.agent!.name, 'GrokBot');
      expect(h.gateway.requests, isEmpty);
      expect(h.output.played, ["Okay, you're now talking to GrokBot."]);

      h.userSays(async, 'What is new?');
      expect(h.gateway.requests.single.agent, 'GrokBot');
      expect(h.gateway.created, ['GrokBot']);
      h.dispose();
    });
  });

  test(
    '"switch to" an unknown agent says so; a casual "hey ..." goes to the agent',
    () {
      fakeAsync((async) {
        final h = Harness();
        h.open(async);
        h.userSays(async, 'Switch to Jarvis');
        async.settle(const Duration(seconds: 2));
        expect(
          h.output.played.single,
          contains("couldn't find an agent called jarvis"),
        );
        expect(h.gateway.requests, isEmpty);

        h.userSays(async, 'Hey are you there');
        expect(h.gateway.requests.single.message, 'Hey are you there');
        h.dispose();
      });
    },
  );

  test('"say that again" repeats the last reply without calling the agent', () {
    fakeAsync((async) {
      final h = Harness();
      h.open(async);
      h.userSays(async, 'Capital of France?');
      h.gateway.chunk('The capital is Paris.');
      h.gateway.done();
      async.settle(const Duration(seconds: 2));
      h.output.played.clear();

      h.userSays(async, 'Say that again');
      async.settle(const Duration(seconds: 2));
      expect(h.output.played, ['The capital is Paris.']);
      expect(h.gateway.requests.length, 1);
      h.dispose();
    });
  });

  test('goes back to sleep when nobody speaks after the first prompt', () {
    fakeAsync((async) {
      final h = Harness();
      h.open(async);
      async.settle(const Duration(seconds: 11));

      expect(h.convo.phase, VoicePhase.idle);
      expect(h.mic.running, isFalse);
      h.dispose();
    });
  });

  test('stays in the conversation for a follow-up, then sleeps', () {
    fakeAsync((async) {
      final h = Harness();
      h.open(async);
      h.userSays(async, 'Hi');
      h.gateway.chunk('Hello!');
      h.gateway.done();
      async.settle(const Duration(seconds: 2));
      expect(h.convo.phase, VoicePhase.listening);

      async.settle(const Duration(seconds: 5));
      expect(
        h.convo.phase,
        VoicePhase.listening,
        reason: 'still within follow-up window',
      );
      async.settle(const Duration(seconds: 5));
      expect(h.convo.phase, VoicePhase.idle);
      h.dispose();
    });
  });

  test('wake word: armed -> hears the phrase -> starts listening', () {
    fakeAsync((async) {
      final h = Harness(withWake: true);
      h.convo.setWakeEnabled(true);
      async.flushMicrotasks();
      expect(h.convo.phase, VoicePhase.armed);
      expect(h.mic.running, isTrue);

      var woke = 0;
      h.convo.wakeEvents.listen((_) => woke++);
      h.mic.feed(noise(400));
      expect(h.convo.phase, VoicePhase.armed, reason: 'noise must not wake it');

      h.wake.triggerOnNextFrame = true;
      h.mic.feed(noise(40));
      async.flushMicrotasks();

      expect(woke, 1);
      expect(h.convo.phase, VoicePhase.listening);
      expect(h.cues, contains(VoiceCue.wake));
      h.dispose();
    });
  });

  test(
    'after a wake-initiated conversation it re-arms instead of closing the mic',
    () {
      fakeAsync((async) {
        final h = Harness(withWake: true);
        h.convo.switchAgent(h.muse);
        h.convo.setWakeEnabled(true);
        async.flushMicrotasks();
        h.wake.triggerOnNextFrame = true;
        h.mic.feed(noise(40));
        async.flushMicrotasks();
        expect(h.convo.phase, VoicePhase.listening);

        async.settle(const Duration(seconds: 11)); // nobody speaks
        expect(h.convo.phase, VoicePhase.armed);
        expect(h.mic.running, isTrue);
        h.dispose();
      });
    },
  );

  test('speech recognition that is not configured surfaces a clear error', () {
    fakeAsync((async) {
      final h = Harness();
      h.open(async);
      h.recognizer.results.add(
        const VoiceUnavailableException('Add an OpenAI key in Voice settings.'),
      );
      h.mic.feed(speech(1200));
      h.mic.feed(noise(1000));
      async.flushMicrotasks();

      expect(h.convo.phase, VoicePhase.error);
      expect(h.convo.error, 'Add an OpenAI key in Voice settings.');
      h.dispose();
    });
  });

  test('a transient transcription failure just asks again', () {
    fakeAsync((async) {
      final h = Harness();
      h.open(async);
      h.recognizer.results.add(Exception('network down'));
      h.mic.feed(speech(1200));
      h.mic.feed(noise(1000));
      async.flushMicrotasks();

      expect(h.convo.phase, VoicePhase.listening);
      expect(h.convo.status, contains("didn't catch"));
      h.dispose();
    });
  });

  test(
    'a sentence that fails to synthesize is skipped, the rest still plays',
    () {
      fakeAsync((async) {
        final h = Harness();
        h.synth.failing.add('Broken one.');
        h.open(async);
        h.userSays(async, 'Go');
        h.gateway.chunk('First. Broken one. Last.');
        h.gateway.done();
        async.settle(const Duration(seconds: 3));

        expect(h.output.played, ['First.', 'Last.']);
        expect(h.convo.phase, VoicePhase.listening);
        h.dispose();
      });
    },
  );

  test('text-to-speech not configured is reported as an error', () {
    fakeAsync((async) {
      final h = Harness();
      h.synth.failAllWith = const VoiceUnavailableException(
        'Voice output is not set up.',
      );
      h.open(async);
      h.userSays(async, 'Go');
      h.gateway.chunk('Anything at all.');
      h.gateway.done();
      async.settle(const Duration(seconds: 1));

      expect(h.convo.phase, VoicePhase.error);
      expect(h.convo.error, 'Voice output is not set up.');
      h.dispose();
    });
  });

  test('tool activity is shown as status while the agent works', () {
    fakeAsync((async) {
      final h = Harness();
      h.open(async);
      h.userSays(async, 'Search the news');
      h.gateway.tool('web_search', 'running');
      async.flushMicrotasks();

      expect(h.convo.phase, VoicePhase.thinking);
      expect(h.convo.status, 'web_search · running');
      h.dispose();
    });
  });

  test('shows a hint if the agent takes a long time to start answering', () {
    fakeAsync((async) {
      final h = Harness();
      h.open(async);
      h.userSays(async, 'Complicated question');
      async.settle(const Duration(seconds: 4));

      expect(h.convo.status, 'Still working on it…');
      h.dispose();
    });
  });

  test('an agent error recovers and keeps listening', () {
    fakeAsync((async) {
      final h = Harness();
      h.open(async);
      h.userSays(async, 'Do the thing');
      h.gateway.error('Model overloaded');
      async.flushMicrotasks();

      expect(h.convo.phase, VoicePhase.listening);
      expect(h.convo.status, 'Model overloaded');
      h.dispose();
    });
  });

  test('a reply with only code is acknowledged instead of staying silent', () {
    fakeAsync((async) {
      final h = Harness();
      h.open(async);
      h.userSays(async, 'Write a script');
      h.gateway.chunk('```py\nprint(1)\n```');
      h.gateway.done();
      async.settle(const Duration(seconds: 2));

      expect(h.output.played, ["I've put the details in the chat."]);
      h.dispose();
    });
  });

  test('muting ignores the microphone', () {
    fakeAsync((async) {
      final h = Harness();
      h.open(async);
      h.convo.toggleMute();
      h.userSays(async, 'Hello?');

      expect(h.recognizer.receivedBytes, isEmpty);
      expect(h.convo.muted, isTrue);
      h.dispose();
    });
  });

  test('tapping while the assistant speaks stops it and listens', () {
    fakeAsync((async) {
      final h = Harness();
      h.open(async);
      h.userSays(async, 'Hi');
      h.output.playTime = const Duration(seconds: 10);
      h.gateway.chunk('A very long answer follows here. ');
      async.flushMicrotasks();
      expect(h.convo.phase, VoicePhase.speaking);

      h.convo.interrupt();
      async.flushMicrotasks();
      expect(h.convo.phase, VoicePhase.listening);
      expect(h.output.stopCount, greaterThan(0));
      h.dispose();
    });
  });

  test('typed text is sent as a turn', () {
    fakeAsync((async) {
      final h = Harness();
      h.open(async);
      h.convo.sendText('Typed question');
      async.flushMicrotasks();

      expect(h.gateway.requests.single.message, 'Typed question');
      h.dispose();
    });
  });

  test('conversation is created once and reused across turns', () {
    fakeAsync((async) {
      final h = Harness();
      h.open(async);
      h.userSays(async, 'One');
      h.gateway.chunk('A.');
      h.gateway.done();
      async.settle(const Duration(seconds: 2));
      h.userSays(async, 'Two');

      expect(h.gateway.created.length, 1);
      expect(h.gateway.requests.map((r) => r.conversationId).toSet(), {
        'conv-1',
      });
      h.dispose();
    });
  });

  test(
    'failure to create the conversation is reported and listening resumes',
    () {
      fakeAsync((async) {
        final h = Harness();
        h.gateway.createFailure = Exception('server unavailable');
        h.open(async);
        h.userSays(async, 'Hello');
        async.flushMicrotasks();

        expect(h.convo.phase, VoicePhase.listening);
        expect(h.convo.status, 'server unavailable');
        h.dispose();
      });
    },
  );
}
