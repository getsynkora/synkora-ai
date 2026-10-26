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

String normalizeTranscript(String text) {
  var t = text.toLowerCase();
  t = t.replaceAll(RegExp(r"[’‘`]"), "'");
  t = t.replaceAll(RegExp(r"[^a-z0-9' ]"), ' ');
  return t.replaceAll(RegExp(r'\s+'), ' ').trim();
}

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

/// Returns the control command in [transcript], if the whole utterance is one.
///
/// Only short utterances are considered so ordinary requests that merely
/// contain a word like "stop" ("how do I stop a docker container?") still
/// reach the agent.
VoiceCommand? parseVoiceCommand(String transcript) {
  var t = normalizeTranscript(transcript);
  t = t.replaceFirst(_leadingWake, '').trim();
  if (t.isEmpty) return null;
  final words = t.split(' ');
  if (words.length > 8) return null;

  if (_endPhrases.contains(t)) return const EndSessionCommand();
  if (_cancelPhrases.contains(t)) return const CancelCommand();
  if (_repeatPhrases.contains(t)) return const RepeatCommand();

  // "ok thanks bye" style endings: peel off any leading filler words.
  final stripped = t.replaceAll(
    RegExp(r'^(?:(?:ok|okay|alright|all right|thanks|thank you|well|so)\s+)+'),
    '',
  );
  if (stripped != t && stripped.isNotEmpty) {
    if (_endPhrases.contains(stripped)) return const EndSessionCommand();
    if (_cancelPhrases.contains(stripped)) return const CancelCommand();
  }

  String? agentNameFrom(RegExpMatch match) {
    final name = match
        .group(1)!
        .split(' ')
        .where((w) => !_switchStopWords.contains(w))
        .join(' ')
        .trim();
    if (name.isEmpty || name.split(' ').length > 3) return null;
    return name;
  }

  for (final pattern in _explicitSwitchPatterns) {
    final match = pattern.firstMatch(t);
    if (match == null) continue;
    final name = agentNameFrom(match);
    if (name != null) return SwitchAgentCommand(name);
  }
  final casual = _casualSwitchPattern.firstMatch(t);
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
}) {
  final t = normalizeTranscript(transcript);
  if (t.isEmpty) return true;
  if (t.replaceAll(' ', '').length < 2) return true;

  const stock = {
    'you',
    'thank you',
    'thanks',
    'thanks for watching',
    'thank you for watching',
    'thank you so much for watching',
    'please subscribe',
    'subscribe',
    'bye',
    'bye bye',
    'the end',
    'okay',
    'ok',
    'uh',
    'um',
    'hmm',
    'mm hmm',
    'oh',
    'ah',
    'so',
    'yeah',
  };
  if (stock.contains(t) &&
      speechDuration < const Duration(milliseconds: 1200)) {
    return true;
  }
  // Subtitle-credit style hallucinations.
  if (RegExp(
    r'(subtitles? by|translated by|captions? by|www\.|amara\.org)',
  ).hasMatch(t)) {
    return true;
  }
  // The same word repeated many times is a decoding loop, not speech.
  final words = t.split(' ');
  if (words.length >= 6 && words.toSet().length <= 2) return true;
  return false;
}
