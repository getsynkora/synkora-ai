/// Spoken commands that control the voice session itself and are handled on
/// the device instead of being sent to the agent.
library;

sealed class VoiceCommand {
  const VoiceCommand();
}

/// "goodbye", "that's all", "stop listening": leave the conversation.
class EndSessionCommand extends VoiceCommand {
  const EndSessionCommand();
}

/// "stop", "never mind": drop the current turn and listen again.
class CancelCommand extends VoiceCommand {
  const CancelCommand();
}

/// "say that again": speak the last reply again.
class RepeatCommand extends VoiceCommand {
  const RepeatCommand();
}

/// "switch to Muse", "talk to GrokBot".
class SwitchAgentCommand extends VoiceCommand {
  const SwitchAgentCommand(this.agentName, {this.explicit = true});

  final String agentName;

  /// False for a casual "hey `name`": if no agent has that name the words
  /// were probably a normal request and should go to the agent unchanged.
  final bool explicit;
}

/// Lower-cases, drops punctuation and folds accented letters to plain ones
/// ("Tschüss!" -> "tschuss"), so phrases in any supported language compare the
/// same way however the recognizer wrote them.
String normalizeTranscript(String text) {
  var t = text.toLowerCase();
  t = t.replaceAll(RegExp(r"[’‘`]"), "'");
  for (final fold in _folds.entries) {
    t = t.replaceAll(fold.key, fold.value);
  }
  t = t.replaceAll(RegExp(r"[^a-z0-9' ]"), ' ');
  return t.replaceAll(RegExp(r'\s+'), ' ').trim();
}

const _folds = {
  'ä': 'a', 'ö': 'o', 'ü': 'u', 'ß': 'ss', //
  'à': 'a', 'á': 'a', 'â': 'a', 'ã': 'a', 'å': 'a', //
  'è': 'e', 'é': 'e', 'ê': 'e', 'ë': 'e', //
  'ì': 'i', 'í': 'i', 'î': 'i', 'ï': 'i', //
  'ò': 'o', 'ó': 'o', 'ô': 'o', 'õ': 'o', //
  'ù': 'u', 'ú': 'u', 'û': 'u', 'ç': 'c', 'ñ': 'n', //
};

// Wake-phrase fragments that can leak into the start of an utterance.
final _leadingWake = RegExp(
  r"^(?:(?:hey|hay|hi|ok|okay)\s+)?(?:syn?c?k?ora|sin?c?k?ora|sink\s?ora|sync\s?ora|cora)\b[\s,]*",
);

const _endPhrases = {
  'goodbye',
  'good bye',
  'bye',
  'bye bye',
  'bye for now',
  'see you',
  'see you later',
  'talk to you later',
  'thats all',
  "that's all",
  "that's all thanks",
  "that's all thank you",
  'that is all',
  "that's it",
  'thats it',
  'stop listening',
  'go to sleep',
  'end conversation',
  'end the conversation',
  'end call',
  'hang up',
  'we are done',
  "we're done",
  'i am done',
  "i'm done",
  'goodnight',
  'good night',
};

// Words that, on their own, mean the user is wrapping up. An utterance made
// only of these (plus at least one real goodbye word) ends the conversation, so
// "thanks, that's all, goodbye" works as well as just "goodbye".
const _farewellKeywords = {
  'goodbye', 'bye', 'all', 'done', 'finished', 'later', 'night', 'enough',
  'sleep', 'thanks', 'cheers', //
};
const _farewellFiller = {
  'ok', 'okay', 'alright', 'right', 'so', 'well', 'thank', 'you', 'thanks',
  'much', 'very', 'that', "that's", 'thats', 'is', 'it', "it's", 'for', 'now',
  'see', 'talk', 'to', 'good', 'we', "we're", 'are', 'am', "i'm", 'i', 'all',
  'cheers', 'take', 'care', 'have', 'a', 'great', 'nice', 'day', 'bye',
  'goodbye', 'done', 'finished', 'later', 'night', 'enough', 'sleep', 'the',
  'help', 'your', 'appreciate', //
};

bool _isFarewell(_Lexicon lex, List<String> words) {
  if (words.isEmpty || words.length > 9) return false;
  if (!words.every(lex.farewellFiller.contains)) return false;
  // "thank you so much" alone is a thanks, not necessarily goodbye.
  return words.any(
    (w) => lex.farewellKeywords.contains(w) && !lex.thanksOnly.contains(w),
  );
}

const _cancelPhrases = {
  'stop',
  'stop it',
  'stop talking',
  'be quiet',
  'quiet',
  'shut up',
  'cancel',
  'cancel that',
  'never mind',
  'nevermind',
  'forget it',
  'forget that',
  'enough',
  'ok stop',
  'okay stop',
  'hold on',
  'wait',
  'wait wait',
  'hang on',
};

const _repeatPhrases = {
  'say that again',
  'repeat that',
  'repeat',
  'what was that',
  'say it again',
  'can you repeat that',
  'could you repeat that',
  'come again',
  'pardon',
  'sorry what',
};

final _explicitSwitchPatterns = [
  RegExp(r'^(?:please )?(?:switch|change|go) (?:over )?to (.+)$'),
  RegExp(
    r'^(?:please )?(?:let me|i want to|i wanna|can i|i would like to) (?:talk|speak|chat) (?:to|with) (.+)$',
  ),
  RegExp(r'^(?:please )?(?:talk|speak|chat) (?:to|with) (.+)$'),
  RegExp(
    r'^(?:please )?(?:use|open|get me|put me through to|connect me to) (.+)$',
  ),
];
final _casualSwitchPattern = RegExp(r'^(?:hey|hi|ok|okay) (.+)$');

const _switchStopWords = {'agent', 'assistant', 'please', 'now', 'the'};

/// The phrases of one language that control the session.
class _Lexicon {
  const _Lexicon({
    required this.endPhrases,
    required this.cancelPhrases,
    required this.repeatPhrases,
    required this.farewellKeywords,
    required this.farewellFiller,
    required this.thanksOnly,
    required this.leadingFiller,
    required this.explicitSwitch,
    required this.casualSwitch,
    required this.switchStopWords,
    required this.stockHallucinations,
    required this.creditHallucination,
  });

  final Set<String> endPhrases;
  final Set<String> cancelPhrases;
  final Set<String> repeatPhrases;
  final Set<String> farewellKeywords;
  final Set<String> farewellFiller;

  /// Farewell keywords that on their own are only a thank-you.
  final Set<String> thanksOnly;
  final RegExp leadingFiller;
  final List<RegExp> explicitSwitch;
  final RegExp casualSwitch;
  final Set<String> switchStopWords;

  /// Stock phrases a recognizer invents from near-silence.
  final Set<String> stockHallucinations;

  /// Subtitle-credit style hallucinations.
  final RegExp creditHallucination;
}

final _english = _Lexicon(
  endPhrases: _endPhrases,
  cancelPhrases: _cancelPhrases,
  repeatPhrases: _repeatPhrases,
  farewellKeywords: _farewellKeywords,
  farewellFiller: _farewellFiller,
  thanksOnly: const {'thanks', 'cheers'},
  leadingFiller: RegExp(
    r'^(?:(?:ok|okay|alright|all right|thanks|thank you|well|so)\s+)+',
  ),
  explicitSwitch: _explicitSwitchPatterns,
  casualSwitch: _casualSwitchPattern,
  switchStopWords: _switchStopWords,
  stockHallucinations: const {
    'you', 'thank you', 'thanks', 'thanks for watching', //
    'thank you for watching', 'thank you so much for watching', //
    'please subscribe', 'subscribe', 'bye', 'bye bye', 'the end', //
    'okay', 'ok', 'uh', 'um', 'hmm', 'mm hmm', 'oh', 'ah', 'so', 'yeah', //
  },
  creditHallucination: RegExp(
    r'(subtitles? by|translated by|captions? by|www\.|amara\.org)',
  ),
);

// German. Written without umlauts: transcripts are folded the same way.
final _german = _Lexicon(
  endPhrases: const {
    'tschuss', 'tschus', 'ciao', 'auf wiedersehen', 'wiedersehen', //
    'bis spater', 'bis bald', 'bis dann', 'bis zum nachsten mal', //
    'das wars', "das war's", 'das ist alles', 'das ware alles', //
    'das ware es', 'danke das wars', "danke das war's", //
    'gute nacht', 'schlaf gut', 'ich bin fertig', 'wir sind fertig', //
    'gesprach beenden', 'das gesprach beenden', 'beenden', 'auflegen', //
    'schluss', 'schluss jetzt', 'ende', 'hor auf zuzuhoren', //
    'nicht mehr zuhoren', //
  },
  cancelPhrases: const {
    'stopp', 'stop', 'halt', 'halt stopp', 'hor auf', 'hor auf damit', //
    'sei still', 'ruhe', 'abbrechen', 'vergiss es', 'vergiss das', //
    'schon gut', 'egal', 'warte', 'warte mal', 'moment', //
    'einen moment', 'moment mal', 'augenblick', 'lass gut sein', //
    'nicht so wichtig', 'okay stopp', 'ok stopp', //
  },
  repeatPhrases: const {
    'sag das nochmal', 'sag das noch mal', 'sag es nochmal', //
    'sag es noch mal', 'noch einmal', 'nochmal', 'noch mal', //
    'wiederhole das', 'wiederhole', 'bitte wiederholen', //
    'kannst du das wiederholen', 'konnen sie das wiederholen', //
    'kannst du das nochmal sagen', 'konnen sie das nochmal sagen', //
    'wie bitte', 'was war das', 'wie war das', 'bitte nochmal', //
  },
  farewellKeywords: const {
    'tschuss', 'tschus', 'wiedersehen', 'fertig', 'schluss', 'nacht', //
    'alles', 'spater', 'bald', 'danke', 'ciao', //
  },
  farewellFiller: const {
    'ok', 'okay', 'gut', 'also', 'dann', 'ja', 'na', 'danke', 'vielen', //
    'dank', 'schon', 'das', 'ist', 'war', 'es', 'wars', "war's", 'alles', //
    'fur', 'heute', 'jetzt', 'ich', 'wir', 'bin', 'sind', 'fertig', 'bis', //
    'spater', 'bald', 'nachsten', 'mal', 'auf', 'wiedersehen', 'tschuss', //
    'tschus', 'gute', 'nacht', 'schluss', 'sehr', 'nett', 'tag', 'einen', //
    'schonen', 'noch', 'nichts', 'hilfe', 'deine', 'ihre', 'du', 'sie', //
    'ciao', 'mach', 'pass', 'dich', 'euch', 'ware', //
  },
  thanksOnly: const {'danke'},
  leadingFiller: RegExp(r'^(?:(?:ok|okay|also|gut|danke|dann|ja|na)\s+)+'),
  explicitSwitch: [
    RegExp(
      r'^(?:bitte )?(?:wechsle|wechsel|wechseln|schalte|schalt|geh|gehe) (?:bitte )?(?:uber )?(?:zu|auf) (.+)$',
    ),
    RegExp(r'^(?:bitte )?(?:zu|auf) (.+?) wechseln$'),
    RegExp(
      r'^(?:bitte )?(?:ich mochte|ich will|ich moechte|lass mich|kann ich|darf ich|ich wurde gern|ich wurde gerne) mit (.+?) (?:sprechen|reden|chatten)$',
    ),
    RegExp(
      r'^(?:bitte )?(?:sprich|sprechen|rede|reden|chatte) (?:bitte )?mit (.+)$',
    ),
    RegExp(
      r'^(?:bitte )?(?:verbinde mich mit|verbinde mich zu|stell mich durch zu|offne|nutze|benutze|nimm) (.+)$',
    ),
  ],
  casualSwitch: RegExp(r'^(?:hey|hi|hallo|ok|okay) (.+)$'),
  switchStopWords: const {
    'agent', 'agenten', 'assistent', 'bitte', 'jetzt', 'den', 'der', 'die', //
    'das', 'dem', //
  },
  stockHallucinations: const {
    'danke', 'vielen dank', 'vielen dank furs zuschauen', //
    'danke furs zuschauen', 'tschuss', 'bis zum nachsten mal', 'ende', //
    'untertitel', 'ja', 'ok', 'okay', 'hm', 'mhm', 'ah', 'oh', 'also', //
    'na ja', //
  },
  creditHallucination: RegExp(
    r'(untertitel(?: der| von| im auftrag)?|amara\.org|www\.|zdf)',
  ),
);

/// The phrase sets to try for [language]: its own, then English, since people
/// often say "stop" or "goodbye" whatever language they are speaking.
List<_Lexicon> _lexiconsFor(String language) =>
    language.toLowerCase().startsWith('de') ? [_german, _english] : [_english];

/// Returns the control command in [transcript], if the whole utterance is one.
///
/// Only short utterances are considered so ordinary requests that merely
/// contain a word like "stop" ("how do I stop a docker container?") still
/// reach the agent. [language] ("en", "de") picks the phrases to listen for.
VoiceCommand? parseVoiceCommand(String transcript, {String language = 'en'}) {
  var t = normalizeTranscript(transcript);
  t = t.replaceFirst(_leadingWake, '').trim();
  if (t.isEmpty) return null;
  final words = t.split(' ');
  if (words.length > 8) return null;

  for (final lex in _lexiconsFor(language)) {
    final command = _parseWith(lex, t, words);
    if (command != null) return command;
  }
  return null;
}

VoiceCommand? _parseWith(_Lexicon lex, String t, List<String> words) {
  if (lex.endPhrases.contains(t)) return const EndSessionCommand();
  if (lex.cancelPhrases.contains(t)) return const CancelCommand();
  if (lex.repeatPhrases.contains(t)) return const RepeatCommand();
  if (_isFarewell(lex, words)) return const EndSessionCommand();

  // "ok thanks bye" style endings: peel off any leading filler words.
  final stripped = t.replaceAll(lex.leadingFiller, '');
  if (stripped != t && stripped.isNotEmpty) {
    if (lex.endPhrases.contains(stripped)) return const EndSessionCommand();
    if (lex.cancelPhrases.contains(stripped)) return const CancelCommand();
  }

  String? agentNameFrom(RegExpMatch match) {
    final name = match
        .group(1)!
        .split(' ')
        .where((w) => !lex.switchStopWords.contains(w))
        .join(' ')
        .trim();
    if (name.isEmpty || name.split(' ').length > 3) return null;
    return name;
  }

  for (final pattern in lex.explicitSwitch) {
    final match = pattern.firstMatch(t);
    if (match == null) continue;
    final name = agentNameFrom(match);
    if (name != null) return SwitchAgentCommand(name);
  }
  final casual = lex.casualSwitch.firstMatch(t);
  if (casual != null) {
    final name = agentNameFrom(casual);
    if (name != null) return SwitchAgentCommand(name, explicit: false);
  }
  return null;
}

/// Finds the agent whose name best matches a spoken [spoken] name, or null.
///
/// Compares ignoring case, spaces and punctuation so "grok bot" finds
/// "GrokBot" and "muse" finds "Muse - Personal Assistant".
T? matchAgentByName<T>(
  String spoken,
  Iterable<T> agents,
  String Function(T) nameOf,
) {
  String squash(String s) =>
      s.toLowerCase().replaceAll(RegExp(r'[^a-z0-9]'), '');
  final target = squash(spoken);
  if (target.isEmpty) return null;

  T? contains;
  for (final agent in agents) {
    final name = squash(nameOf(agent));
    if (name == target) return agent;
    if (contains == null &&
        (name.startsWith(target) || name.contains(target))) {
      contains = agent;
    }
  }
  return contains;
}

/// Whisper tends to invent stock phrases when it is fed near-silence or
/// breath noise. Returns true for transcripts that are very likely such
/// hallucinations, so the assistant ignores them instead of answering.
bool isLikelyTranscriptionHallucination(
  String transcript, {
  required Duration speechDuration,
  String language = 'en',
}) {
  final t = normalizeTranscript(transcript);
  if (t.isEmpty) return true;
  if (t.replaceAll(' ', '').length < 2) return true;

  final lexicons = _lexiconsFor(language);
  if (lexicons.any((lex) => lex.stockHallucinations.contains(t)) &&
      speechDuration < const Duration(milliseconds: 1200)) {
    return true;
  }
  // Subtitle-credit style hallucinations.
  if (lexicons.any((lex) => lex.creditHallucination.hasMatch(t))) return true;
  // The same word repeated many times is a decoding loop, not speech.
  final words = t.split(' ');
  if (words.length >= 6 && words.toSet().length <= 2) return true;
  return false;
}
