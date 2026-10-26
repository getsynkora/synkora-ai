import 'package:flutter_test/flutter_test.dart';
import 'package:synkora_mobile/src/voice/voice_commands.dart';

void main() {
  group('parseVoiceCommand', () {
    test('recognizes ending phrases, including a leaked wake phrase', () {
      for (final text in [
        'Goodbye!',
        "That's all.",
        'ok thanks bye',
        'Hey Synkora, stop listening',
        'Go to sleep',
      ]) {
        expect(parseVoiceCommand(text), isA<EndSessionCommand>(), reason: text);
      }
    });

    test('compound goodbyes end the session', () {
      for (final text in [
        'That’s all, thanks. Goodbye.',
        'Thanks, that is all for now',
        'ok thank you so much, bye',
        'alright talk to you later',
        'Okay we are done, thanks',
        'Good night, thank you',
        'thanks for your help, goodbye',
      ]) {
        expect(parseVoiceCommand(text), isA<EndSessionCommand>(), reason: text);
      }
    });

    test(
      'thanks alone, or goodbye words inside a real request, do not end it',
      () {
        for (final text in [
          'Thank you so much',
          'thanks',
          'That is all I know about the project, can you summarize it',
          'Tell me when all the tests are done',
          'What time is it in Tokyo tonight',
          'Is the build done',
        ]) {
          expect(
            parseVoiceCommand(text),
            isNot(isA<EndSessionCommand>()),
            reason: text,
          );
        }
      },
    );

    test('recognizes cancel and repeat', () {
      expect(parseVoiceCommand('Stop.'), isA<CancelCommand>());
      expect(parseVoiceCommand('never mind'), isA<CancelCommand>());
      expect(parseVoiceCommand('Can you repeat that?'), isA<RepeatCommand>());
      expect(parseVoiceCommand('say that again'), isA<RepeatCommand>());
    });

    test(
      'does not treat ordinary requests containing command words as commands',
      () {
        for (final text in [
          'How do I stop a docker container from restarting automatically?',
          'Tell me about the end of the Roman empire',
          "What's the weather like in Paris?",
          'Repeat the last three commit messages for me please thank you',
        ]) {
          expect(parseVoiceCommand(text), isNull, reason: text);
        }
      },
    );

    test('parses explicit agent switches', () {
      final a = parseVoiceCommand('Switch to Muse');
      expect(a, isA<SwitchAgentCommand>());
      expect((a as SwitchAgentCommand).agentName, 'muse');
      expect(a.explicit, isTrue);

      final b =
          parseVoiceCommand('let me talk to grok bot please')
              as SwitchAgentCommand;
      expect(b.agentName, 'grok bot');

      final c =
          parseVoiceCommand('Talk to the research agent') as SwitchAgentCommand;
      expect(c.agentName, 'research');
    });

    test('a casual "hey <name>" is flagged as not explicit', () {
      final c = parseVoiceCommand('hey are you there') as SwitchAgentCommand;
      expect(c.explicit, isFalse);
      expect(c.agentName, 'are you there');
      // Four or more words cannot be a name, so it is a normal request.
      expect(parseVoiceCommand('hey can you help me'), isNull);
    });

    test('long utterances are never commands', () {
      expect(
        parseVoiceCommand(
          'switch to muse and then tell me everything about my schedule tomorrow',
        ),
        isNull,
      );
    });
  });

  group('matchAgentByName', () {
    final agents = ['GrokBot', 'Muse - Personal Assistant', 'Research Agent'];
    String name(String s) => s;

    test('matches ignoring spaces, case and punctuation', () {
      expect(matchAgentByName('grok bot', agents, name), 'GrokBot');
      expect(
        matchAgentByName('muse', agents, name),
        'Muse - Personal Assistant',
      );
      expect(matchAgentByName('research', agents, name), 'Research Agent');
    });

    test('prefers an exact match over a partial one', () {
      expect(matchAgentByName('muse', ['Muse Pro', 'Muse'], name), 'Muse');
    });

    test('returns null when nothing matches', () {
      expect(matchAgentByName('jarvis', agents, name), isNull);
      expect(matchAgentByName('', agents, name), isNull);
    });
  });

  group('isLikelyTranscriptionHallucination', () {
    const short = Duration(milliseconds: 600);
    const long = Duration(seconds: 3);

    test('flags stock phrases on short audio', () {
      expect(
        isLikelyTranscriptionHallucination('Thank you.', speechDuration: short),
        isTrue,
      );
      expect(
        isLikelyTranscriptionHallucination(
          'Thanks for watching!',
          speechDuration: short,
        ),
        isTrue,
      );
      expect(
        isLikelyTranscriptionHallucination('', speechDuration: short),
        isTrue,
      );
    });

    test('keeps a genuine thank-you said at length', () {
      expect(
        isLikelyTranscriptionHallucination('thank you', speechDuration: long),
        isFalse,
      );
    });

    test('flags subtitle credits and decoding loops', () {
      expect(
        isLikelyTranscriptionHallucination(
          'Subtitles by the Amara.org community',
          speechDuration: long,
        ),
        isTrue,
      );
      expect(
        isLikelyTranscriptionHallucination(
          'no no no no no no no',
          speechDuration: long,
        ),
        isTrue,
      );
    });

    test('passes real requests', () {
      expect(
        isLikelyTranscriptionHallucination(
          "What's on my calendar today?",
          speechDuration: long,
        ),
        isFalse,
      );
    });
  });
}
