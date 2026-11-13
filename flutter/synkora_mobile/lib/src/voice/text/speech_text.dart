/// Turns agent output (usually markdown) into text that sounds natural when a
/// voice reads it aloud, and splits a token stream into speakable sentences so
/// speech can start before the reply has finished generating.
library;

final _fencedBlock = RegExp(r'```[\s\S]*?```');
final _inlineCode = RegExp(r'`([^`]*)`');
final _image = RegExp(r'!\[[^\]]*\]\([^)]*\)');
final _link = RegExp(r'\[([^\]]+)\]\([^)]*\)');
final _bareUrl = RegExp(r'(?:https?://|www\.)\S+', caseSensitive: false);
final _htmlTag = RegExp(r'<[^>]+>');
final _heading = RegExp(r'^\s{0,3}#{1,6}\s*', multiLine: true);
final _blockquote = RegExp(r'^\s{0,3}>\s?', multiLine: true);
final _bullet = RegExp(r'^\s*[-*+•]\s+', multiLine: true);
final _numbered = RegExp(r'^\s*\d{1,3}[.)]\s+', multiLine: true);
final _rule = RegExp(r'^\s*([-*_]\s*){3,}$', multiLine: true);
final _tableRule = RegExp(r'^\s*\|?[\s:|-]+\|[\s:|-]*$', multiLine: true);
final _emphasis = RegExp(r'(\*\*|__|\*|_|~~)(?=\S)(.+?)(?<=\S)\1');
final _emoji = RegExp(
  r'[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE0F}\u{200D}\u{1F1E6}-\u{1F1FF}]',
  unicode: true,
);
final _spaces = RegExp(r'[ \t]+');
final _blankLines = RegExp(r'\n{2,}');

/// Returns [markdown] rewritten for text-to-speech.
///
/// Code blocks are dropped (reading code aloud is useless), links keep only
/// their label, URLs are removed, and list/heading/emphasis syntax is stripped.
String toSpeakable(String markdown) {
  var text = markdown;
  text = text.replaceAll(_fencedBlock, ' ');
  text = text.replaceAll(_image, ' ');
  text = text.replaceAllMapped(_link, (m) => m.group(1)!);
  text = text.replaceAll(_bareUrl, ' ');
  text = text.replaceAll(_htmlTag, ' ');
  text = text.replaceAllMapped(_inlineCode, (m) => m.group(1)!);
  text = text.replaceAll(_rule, ' ');
  text = text.replaceAll(_tableRule, ' ');
  text = text.replaceAll(_heading, '');
  text = text.replaceAll(_blockquote, '');
  text = text.replaceAll(_bullet, '');
  text = text.replaceAll(_numbered, '');
  // Emphasis can nest (`**_x_**`), so peel it until nothing changes.
  for (var i = 0; i < 3; i++) {
    final next = text.replaceAllMapped(_emphasis, (m) => m.group(2)!);
    if (next == text) break;
    text = next;
  }
  text = text.replaceAll('|', ', ');
  text = text.replaceAll(_emoji, '');
  text = text.replaceAll(_spaces, ' ');
  text = text.replaceAll(RegExp(r' *\n *'), '\n');
  text = text.replaceAll(_blankLines, '\n');
  return text.trim();
}

const _abbreviations = {
  'mr', 'mrs', 'ms', 'dr', 'prof', 'sr', 'jr', 'st', 'vs', 'etc', 'inc', 'ltd',
  'co', 'no', 'fig', 'approx', 'e.g', 'i.e', 'u.s', 'u.k', 'a.m', 'p.m', //
};

/// Incrementally splits streamed text into sentences that are ready to speak.
///
/// Feed token deltas with [add]; each call returns the sentences that became
/// complete. Call [flush] when the stream ends to get the remainder.
///
/// To keep time-to-first-audio low, the very first chunk is allowed to break
/// at a clause boundary (comma, semicolon, colon, dash) once it is long
/// enough, instead of waiting for a full stop.
class SentenceChunker {
  SentenceChunker({
    this.firstChunkClauseMinChars = 60,
    this.maxChunkChars = 260,
  });

  final int firstChunkClauseMinChars;
  final int maxChunkChars;

  final StringBuffer _buffer = StringBuffer();
  bool _emittedAny = false;
  bool _inFence = false;

  /// Adds [delta] and returns any newly completed, speakable sentences.
  List<String> add(String delta) {
    _buffer.write(delta);
    return _drain(final_: false);
  }

  /// Returns whatever is left once the stream has ended.
  List<String> flush() => _drain(final_: true);

  void reset() {
    _buffer.clear();
    _emittedAny = false;
    _inFence = false;
  }

  List<String> _drain({required bool final_}) {
    final out = <String>[];
    var text = _buffer.toString();
    _buffer.clear();

    while (true) {
      // Skip fenced code entirely; it can span many token deltas.
      if (_inFence) {
        final end = text.indexOf('```');
        if (end == -1) {
          // Still inside the fence: keep a possible partial closing marker.
          text = text.endsWith('`') ? text.substring(text.length - 1) : '';
          break;
        }
        text = text.substring(end + 3);
        _inFence = false;
        continue;
      }
      final fence = text.indexOf('```');
      final cut = _findCut(text, fence == -1 ? text.length : fence);
      if (cut != null) {
        _emit(out, text.substring(0, cut));
        text = text.substring(cut);
        continue;
      }
      if (fence != -1) {
        _emit(out, text.substring(0, fence));
        text = text.substring(fence + 3);
        _inFence = true;
        continue;
      }
      break;
    }

    if (final_) {
      _emit(out, text);
    } else {
      _buffer.write(text);
    }
    return out;
  }

  void _emit(List<String> out, String raw) {
    final spoken = toSpeakable(raw);
    if (spoken.isEmpty ||
        !RegExp(r'[\p{L}\p{N}]', unicode: true).hasMatch(spoken)) {
      return;
    }
    _emittedAny = true;
    out.add(spoken.replaceAll('\n', ' '));
  }

  /// Index just past the first complete sentence in [text] (looking only at
  /// the first [limit] characters), or null if none is complete yet.
  int? _findCut(String text, int limit) {
    for (var i = 0; i < limit; i++) {
      final c = text[i];
      if (c == '\n') {
        // A line break after real content ends a spoken unit (list items,
        // paragraphs); leading blank lines do not.
        if (text.substring(0, i).trim().isNotEmpty) return i + 1;
        continue;
      }
      if (c == '.' || c == '!' || c == '?' || c == '…') {
        // Need to see what follows to know the sentence really ended.
        if (i + 1 >= text.length) return null;
        var j = i + 1;
        while (j < text.length && '"\'”’)]*_'.contains(text[j])) {
          j++;
        }
        if (j >= text.length) return null;
        if (text[j] != ' ' && text[j] != '\n') continue;
        if (c == '.' && _isAbbreviationOrNumber(text, i)) continue;
        return j;
      }
    }
    final soft = _softCut(text, limit);
    if (soft != null) return soft;
    if (limit > maxChunkChars) {
      final space = text.lastIndexOf(' ', maxChunkChars);
      return space > 0 ? space + 1 : maxChunkChars;
    }
    return null;
  }

  int? _softCut(String text, int limit) {
    if (_emittedAny) return null;
    if (limit < firstChunkClauseMinChars) return null;
    for (var i = firstChunkClauseMinChars - 1; i < limit; i++) {
      final c = text[i];
      if ((c == ',' || c == ';' || c == ':' || c == '—') &&
          i + 1 < text.length &&
          text[i + 1] == ' ') {
        return i + 2;
      }
    }
    return null;
  }

  bool _isAbbreviationOrNumber(String text, int dot) {
    // Decimal like 3.5 is handled by the "next char must be space" rule, but
    // "3. " (list numbering) and abbreviations need a look back.
    var start = dot;
    while (start > 0 && !' \n'.contains(text[start - 1])) {
      start--;
    }
    final word = text.substring(start, dot).toLowerCase();
    if (word.isEmpty) return false;
    if (_abbreviations.contains(word)) return true;
    if (RegExp(r'^\d{1,2}$').hasMatch(word) && start == 0) return true;
    // Single capital initial: "J. Smith".
    if (word.length == 1 && RegExp(r'[a-z]').hasMatch(word)) return true;
    return false;
  }
}
