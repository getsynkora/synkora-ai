/// Texts the voice engine speaks or shows by itself (replies like "I couldn't
/// find an agent called …", permission problems, setup hints).
///
/// They follow the language the person talks in, not the app language: it is the
/// language of the agent's voice setting, so a German-speaking conversation is
/// answered in German even if the app is in English. English and German are
/// built in; anything else falls back to English.
library;

abstract class VoiceMessages {
  const VoiceMessages();

  /// Messages for a language code ("de", "de-DE"); English if there are none.
  factory VoiceMessages.forLanguage(String? language) {
    final code = (language ?? '').toLowerCase().split(RegExp('[-_]')).first;
    return code == 'de'
        ? const GermanVoiceMessages()
        : const EnglishVoiceMessages();
  }

  /// The two-letter language these messages are written in.
  String get language;

  // Setup problems.
  String voiceDisabled(String agent);
  String get whisperProvider;
  String ttsProvider({required bool elevenLabs});
  String missingKey(String agent, List<String> providers);
  String get missingKeyShort;
  String turnOnFailed(String agent);
  String get sessionExpired;
  String get noAudio;

  /// A hint for the speech recognizer: what the conversation is about.
  String recognitionHint(List<String> names);

  // Device permissions and hardware.
  String get microphoneOff;
  String get noMicrophone;
  String get speechRecognitionOff;
  String recognizerNotWorking(String code);

  // The assistant's own lines.
  String get didntCatch;
  String noAgentNamed(String name);
  String nowTalkingTo(String name);
  String get noAgentSelected;
  String get stillWorking;
  String get voiceChatName;
  String get agentProblem;
  String get detailsInChat;
  String get noResponse;

  // Tips shown while idle; they name the spoken commands of this language.
  List<String> get hints;
  String get switchHint;
}

class EnglishVoiceMessages extends VoiceMessages {
  const EnglishVoiceMessages();

  @override
  String get language => 'en';

  @override
  String voiceDisabled(String agent) =>
      'Voice is turned off for $agent. Turn it on to talk to it.';

  @override
  String get whisperProvider => 'OpenAI Whisper (speech recognition)';

  @override
  String ttsProvider({required bool elevenLabs}) =>
      elevenLabs ? 'ElevenLabs' : 'OpenAI text-to-speech';

  @override
  String missingKey(String agent, List<String> providers) =>
      '$agent is set to use ${providers.join(' and ')}, but no key '
      'is saved for it. Add one under Voice settings, or use your '
      "phone's built-in voice for now.";

  @override
  String get missingKeyShort =>
      'This agent is set to a paid speech provider, but no key is saved for it. '
      "Add one under Voice settings, or use your phone's built-in voice.";

  @override
  String turnOnFailed(String agent) =>
      'Could not turn voice on for $agent. Only its owner can; '
      'open Voice settings on the web to enable it.';

  @override
  String get sessionExpired =>
      'Your session expired. Sign in again to keep talking.';

  @override
  String get noAudio => 'The voice service returned no audio.';

  @override
  String recognitionHint(List<String> names) =>
      'Conversation with a voice assistant. Names: ${names.join(', ')}.';

  @override
  String get microphoneOff =>
      'Microphone access is turned off. Enable it for Synkora in your '
      'phone settings to talk to your agents.';

  @override
  String get noMicrophone =>
      'No microphone is available right now. Check that nothing else is '
      'using it, or plug in a headset, then try again.';

  @override
  String get speechRecognitionOff =>
      'Speech recognition is turned off. Allow Microphone and Speech '
      'Recognition for Synkora in your phone settings to talk to this agent.';

  @override
  String recognizerNotWorking(String code) =>
      "Your phone's speech recognition isn't working right now "
      '($code). Check Settings > Siri & Dictation, or switch '
      'this agent to a cloud voice in its Voice settings.';

  @override
  String get didntCatch => "Sorry, I didn't catch that.";

  @override
  String noAgentNamed(String name) => "I couldn't find an agent called $name.";

  @override
  String nowTalkingTo(String name) => "Okay, you're now talking to $name.";

  @override
  String get noAgentSelected => 'No agent selected.';

  @override
  String get stillWorking => 'Still working on it…';

  @override
  String get voiceChatName => 'Voice chat';

  @override
  String get agentProblem => 'The agent ran into a problem.';

  @override
  String get detailsInChat => "I've put the details in the chat.";

  @override
  String get noResponse => "I didn't get a response.";

  @override
  List<String> get hints => const [
    'Ask me anything',
    'Say “switch to” and an agent’s name',
    'Talk over me to interrupt',
    'Say “goodbye” when you’re done',
  ];

  @override
  String get switchHint => 'You can also say “switch to” followed by a name.';
}

class GermanVoiceMessages extends VoiceMessages {
  const GermanVoiceMessages();

  @override
  String get language => 'de';

  @override
  String voiceDisabled(String agent) =>
      'Sprache ist für $agent ausgeschaltet. Schalten Sie sie ein, um mit dem Agenten zu sprechen.';

  @override
  String get whisperProvider => 'OpenAI Whisper (Spracherkennung)';

  @override
  String ttsProvider({required bool elevenLabs}) =>
      elevenLabs ? 'ElevenLabs' : 'OpenAI Sprachausgabe';

  @override
  String missingKey(String agent, List<String> providers) =>
      '$agent ist auf ${providers.join(' und ')} eingestellt, aber dafür ist '
      'kein Schlüssel gespeichert. Hinterlegen Sie einen unter den '
      'Spracheinstellungen oder nutzen Sie vorerst die integrierte Stimme Ihres Telefons.';

  @override
  String get missingKeyShort =>
      'Dieser Agent nutzt einen kostenpflichtigen Sprachdienst, aber dafür ist kein '
      'Schlüssel gespeichert. Hinterlegen Sie einen unter den Spracheinstellungen '
      'oder nutzen Sie die integrierte Stimme Ihres Telefons.';

  @override
  String turnOnFailed(String agent) =>
      'Sprache konnte für $agent nicht eingeschaltet werden. Das kann nur der Besitzer; '
      'öffnen Sie dazu die Spracheinstellungen im Web.';

  @override
  String get sessionExpired =>
      'Ihre Sitzung ist abgelaufen. Melden Sie sich erneut an, um weiterzusprechen.';

  @override
  String get noAudio => 'Der Sprachdienst hat kein Audio geliefert.';

  @override
  String recognitionHint(List<String> names) =>
      'Gespräch mit einem Sprachassistenten. Namen: ${names.join(', ')}.';

  @override
  String get microphoneOff =>
      'Der Mikrofonzugriff ist ausgeschaltet. Erlauben Sie ihn für Synkora in den '
      'Einstellungen Ihres Telefons, um mit Ihren Agenten zu sprechen.';

  @override
  String get noMicrophone =>
      'Derzeit ist kein Mikrofon verfügbar. Prüfen Sie, ob es nicht von einer anderen '
      'App genutzt wird, oder schließen Sie ein Headset an, und versuchen Sie es erneut.';

  @override
  String get speechRecognitionOff =>
      'Die Spracherkennung ist ausgeschaltet. Erlauben Sie Synkora in den Einstellungen '
      'Ihres Telefons den Zugriff auf Mikrofon und Spracherkennung, um mit diesem Agenten zu sprechen.';

  @override
  String recognizerNotWorking(String code) =>
      'Die Spracherkennung Ihres Telefons funktioniert gerade nicht '
      '($code). Prüfen Sie Einstellungen > Siri & Diktieren oder stellen Sie '
      'diesen Agenten in seinen Spracheinstellungen auf eine Cloud-Stimme um.';

  @override
  String get didntCatch => 'Entschuldigung, das habe ich nicht verstanden.';

  @override
  String noAgentNamed(String name) =>
      'Ich konnte keinen Agenten namens $name finden.';

  @override
  String nowTalkingTo(String name) =>
      'In Ordnung, Sie sprechen jetzt mit $name.';

  @override
  String get noAgentSelected => 'Kein Agent ausgewählt.';

  @override
  String get stillWorking => 'Ich arbeite noch daran …';

  @override
  String get voiceChatName => 'Sprachchat';

  @override
  String get agentProblem => 'Beim Agenten ist ein Problem aufgetreten.';

  @override
  String get detailsInChat => 'Ich habe die Details in den Chat gestellt.';

  @override
  String get noResponse => 'Ich habe keine Antwort erhalten.';

  @override
  List<String> get hints => const [
    'Fragen Sie mich alles',
    'Sagen Sie „wechsle zu“ und den Namen eines Agenten',
    'Sprechen Sie dazwischen, um mich zu unterbrechen',
    'Sagen Sie „tschüss“, wenn Sie fertig sind',
  ];

  @override
  String get switchHint =>
      'Sie können auch „wechsle zu“ und einen Namen sagen.';
}
