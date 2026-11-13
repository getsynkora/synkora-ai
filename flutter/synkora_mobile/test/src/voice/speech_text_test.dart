import 'package:flutter_test/flutter_test.dart';
import 'package:synkora_mobile/src/voice/text/speech_text.dart';

List<String> chunk(Iterable<String> deltas, {SentenceChunker? chunker}) {
  final c = chunker ?? SentenceChunker();
  final out = <String>[];
  for (final d in deltas) {
    out.addAll(c.add(d));
  }
  out.addAll(c.flush());
  return out;
}

/// Splits [text] into tiny pieces to mimic token streaming.
Iterable<String> tokens(String text, {int size = 3}) sync* {
  for (var i = 0; i < text.length; i += size) {
    yield text.substring(i, i + size > text.length ? text.length : i + size);
  }
}

void main() {
  group('toSpeakable', () {
    test('strips markdown emphasis, headings and bullets', () {
      const md = '## Plan\n- **Bold** item\n- _soft_ item\n1. first step';
      expect(toSpeakable(md), 'Plan\nBold item\nsoft item\nfirst step');
    });

    test('keeps link labels and drops urls', () {
      expect(
        toSpeakable(
          'See [the docs](https://example.com/a) or https://x.io/y now',
        ),
        'See the docs or now',
      );
    });

    test('drops fenced code and images but keeps inline code text', () {
      const md =
          'Run `npm test` first.\n```js\nconsole.log(1)\n```\n![chart](a.png)';
      expect(toSpeakable(md), 'Run npm test first.');
    });

    test('removes emoji and html', () {
      expect(toSpeakable('Great job 🎉 <b>team</b>'), 'Great job team');
    });

    test('turns table pipes into pauses and removes the divider row', () {
      const md = '| a | b |\n|---|---|\n| 1 | 2 |';
      final out = toSpeakable(md);
      expect(out.contains('---'), isFalse);
      expect(out.contains('|'), isFalse);
    });

    test('handles nested emphasis', () {
      expect(
        toSpeakable('This is **_very_ important**'),
        'This is very important',
      );
    });
  });

  group('SentenceChunker', () {
    test('emits sentences as soon as they complete', () {
      final c = SentenceChunker();
      expect(c.add('Hello there'), isEmpty);
      expect(c.add('. How are'), ['Hello there.']);
      expect(c.add(' you today? I am fine.'), ['How are you today?']);
      expect(c.flush(), ['I am fine.']);
    });

    test('does not split on abbreviations, initials or decimals', () {
      final out = chunk(
        tokens('Dr. Smith paid 3.5 dollars at 5 p.m. today. Done.'),
      );
      expect(out, ['Dr. Smith paid 3.5 dollars at 5 p.m. today.', 'Done.']);
    });

    test('splits paragraphs and list items on line breaks', () {
      final out = chunk(tokens('First item\nSecond item\n\nThird.'));
      expect(out, ['First item', 'Second item', 'Third.']);
    });

    test('streaming in tiny pieces gives the same result as one piece', () {
      const text = 'Sure thing! The meeting is at nine. Want me to add it?';
      expect(chunk(tokens(text, size: 2)), chunk([text]));
      expect(chunk([text]), [
        'Sure thing!',
        'The meeting is at nine.',
        'Want me to add it?',
      ]);
    });

    test('skips code fences even when split across deltas', () {
      final out = chunk([
        'Here you go. ``',
        '`py\nprint(1)\n`',
        '``\nThat is it.',
      ]);
      expect(out, ['Here you go.', 'That is it.']);
    });

    test('first chunk may break at a clause to cut time to first audio', () {
      final c = SentenceChunker(firstChunkClauseMinChars: 30);
      final first = c.add(
        'Well, since you asked about the weather, it looks sunny with a light breeze later',
      );
      expect(first, ['Well, since you asked about the weather,']);
    });

    test('later chunks do not break at clauses', () {
      final c = SentenceChunker(firstChunkClauseMinChars: 20);
      c.add('Short opening sentence. ');
      expect(
        c.add('This one has a comma, and keeps going without a full stop yet'),
        isEmpty,
      );
    });

    test('long run-on text is force-split at a space', () {
      final c = SentenceChunker(maxChunkChars: 40);
      final out = c.add('word ' * 30);
      expect(out, isNotEmpty);
      expect(out.every((s) => s.length <= 45), isTrue);
    });

    test('ignores chunks with no letters or digits', () {
      expect(chunk(['...\n---\n']), isEmpty);
    });

    test('closing quotes stay with their sentence', () {
      expect(chunk(['He said "go." Then left.']), [
        'He said "go."',
        'Then left.',
      ]);
    });

    test('reset clears pending text and the first-chunk rule', () {
      final c = SentenceChunker();
      c.add('Half a sent');
      c.reset();
      expect(c.flush(), isEmpty);
    });
  });
}
