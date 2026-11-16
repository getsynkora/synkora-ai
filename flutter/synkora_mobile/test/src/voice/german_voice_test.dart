import 'package:flutter_test/flutter_test.dart';
import 'package:synkora_mobile/src/voice/voice_commands.dart';
import 'package:synkora_mobile/src/voice/voice_messages.dart';
import 'package:synkora_mobile/src/voice/voice_profile.dart';

import 'support/fakes.dart';

VoiceCommand? de(String text) => parseVoiceCommand(text, language: 'de');

void main() {
  group('folding letters', () {
    test('umlauts and accents compare as plain letters', () {
      expect(normalizeTranscript('Tschüss!'), 'tschuss');
      expect(normalizeTranscript('Gesprächs beenden'), 'gesprachs beenden');
      expect(normalizeTranscript('Straße'), 'strasse');
      expect(normalizeTranscript('Café'), 'cafe');
    });
  });

  group('German voice commands', () {
    test('end the conversation', () {
      for (final text in [
        'Tschüss!',
        'Auf Wiedersehen.',
        'Das war\'s.',
        'Das ist alles',
        'Bis später',
        'Gute Nacht',
        'Ich bin fertig',
        'Gespräch beenden',
        'Hey Synkora, tschüss',
        'ok danke, das war\'s, tschüss',
        'Danke, bis später',
      ]) {
        expect(de(text), isA<EndSessionCommand>(), reason: text);
      }
    });

    test('cancel the turn', () {
      for (final text in [
        'Stopp!',
        'Halt',
        'Vergiss es',
        'Abbrechen',
        'Moment mal',
      ]) {
        expect(de(text), isA<CancelCommand>(), reason: text);
      }
    });

    test('repeat the last answer', () {
      for (final text in [
        'Sag das nochmal',
        'Wie bitte?',
        'Wiederhole das',
        'Noch mal',
      ]) {
        expect(de(text), isA<RepeatCommand>(), reason: text);
      }
    });

    test('switch agents', () {
      for (final text in [
        'Wechsle zu Muse',
        'Wechsel zu Muse',
        'Geh zu Muse',
        'Zu Muse wechseln',
        'Ich möchte mit Muse sprechen',
        'Sprich mit Muse',
        'Verbinde mich mit Muse',
        'Bitte wechsle zu dem Agenten Muse',
      ]) {
        final command = de(text);
        expect(command, isA<SwitchAgentCommand>(), reason: text);
        expect((command as SwitchAgentCommand).agentName, 'muse', reason: text);
        expect(command.explicit, isTrue, reason: text);
      }
    });

    test('a casual "hallo name" is only a guess', () {
      final command = de('Hallo Muse') as SwitchAgentCommand;

      expect(command.agentName, 'muse');
      expect(command.explicit, isFalse);
    });

    test('plain thanks, or a real request, are not commands', () {
      for (final text in [
        'Danke',
        'Vielen Dank',
        'Wie stoppe ich einen Docker Container',
        'Das ist alles was ich über das Projekt weiß, kannst du es zusammenfassen',
        'Wie spät ist es in Tokio heute Abend',
      ]) {
        expect(de(text), isNull, reason: text);
      }
    });

    test('English commands still work in a German conversation', () {
      expect(de('goodbye'), isA<EndSessionCommand>());
      expect(de('stop'), isA<CancelCommand>());
      expect(de('switch to Muse'), isA<SwitchAgentCommand>());
    });

    test('German phrases are not commands in an English conversation', () {
      expect(parseVoiceCommand('Tschüss'), isNull);
      expect(parseVoiceCommand('Wechsle zu Muse'), isNull);
      expect(parseVoiceCommand('Tschüss', language: 'en'), isNull);
    });

    test('the language can carry a region', () {
      expect(
        parseVoiceCommand('Tschüss', language: 'de-DE'),
        isA<EndSessionCommand>(),
      );
    });
  });

  group('German recognizer hallucinations', () {
    const brief = Duration(milliseconds: 500);

    test('stock phrases from silence are dropped', () {
      for (final text in [
        'Vielen Dank.',
        'Untertitel der Amara.org-Community',
        'Untertitel im Auftrag des ZDF, 2020',
        'Tschüss',
      ]) {
        expect(
          isLikelyTranscriptionHallucination(
            text,
            speechDuration: brief,
            language: 'de',
          ),
          isTrue,
          reason: text,
        );
      }
    });

    test('real German speech is kept', () {
      expect(
        isLikelyTranscriptionHallucination(
          'Wie wird das Wetter morgen in Berlin',
          speechDuration: brief,
          language: 'de',
        ),
        isFalse,
      );
    });

    test('a long, deliberate "vielen dank" is kept', () {
      expect(
        isLikelyTranscriptionHallucination(
          'Vielen Dank',
          speechDuration: const Duration(seconds: 2),
          language: 'de',
        ),
        isFalse,
      );
    });
  });

  group('voice messages', () {
    test('pick the language of the conversation, English when unknown', () {
      expect(VoiceMessages.forLanguage('de').language, 'de');
      expect(VoiceMessages.forLanguage('de-DE').language, 'de');
      expect(VoiceMessages.forLanguage('en-US').language, 'en');
      expect(VoiceMessages.forLanguage('fr').language, 'en');
      expect(VoiceMessages.forLanguage(null).language, 'en');
    });

    test('German says what English says', () {
      const en = EnglishVoiceMessages();
      const de = GermanVoiceMessages();

      expect(de.noAgentNamed('Muse'), contains('Muse'));
      expect(de.noAgentNamed('Muse'), isNot(en.noAgentNamed('Muse')));
      expect(de.nowTalkingTo('Muse'), contains('Muse'));
      expect(de.voiceDisabled('Muse'), contains('Muse'));
      expect(de.turnOnFailed('Muse'), contains('Muse'));
      expect(de.recognizerNotWorking('error_x'), contains('error_x'));
      expect(
        de.missingKey('Muse', ['A', 'B']),
        allOf(contains('A und B'), contains('Muse')),
      );
      expect(en.missingKey('Muse', ['A', 'B']), contains('A and B'));
      expect(de.hints, hasLength(en.hints.length));
      expect(de.hints.last, contains('tschüss'));
    });

    test('every text is filled in for both languages', () {
      for (final m in <VoiceMessages>[
        const EnglishVoiceMessages(),
        const GermanVoiceMessages(),
      ]) {
        for (final text in [
          m.voiceDisabled('X'),
          m.whisperProvider,
          m.ttsProvider(elevenLabs: true),
          m.ttsProvider(elevenLabs: false),
          m.missingKey('X', ['Y']),
          m.missingKeyShort,
          m.turnOnFailed('X'),
          m.sessionExpired,
          m.noAudio,
          m.recognitionHint(['X']),
          m.microphoneOff,
          m.noMicrophone,
          m.speechRecognitionOff,
          m.recognizerNotWorking('c'),
          m.didntCatch,
          m.noAgentNamed('X'),
          m.nowTalkingTo('X'),
          m.noAgentSelected,
          m.stillWorking,
          m.voiceChatName,
          m.agentProblem,
          m.detailsInChat,
          m.noResponse,
          m.switchHint,
          ...m.hints,
        ]) {
          expect(text.trim(), isNotEmpty);
        }
      }
    });
  });

  group('a German agent', () {
    test('explains setup problems in German', () {
      final agent = fakeAgent(
        'Muse',
        voice: {
          'stt_provider': 'openai_whisper',
          'tts_provider': 'openai_tts',
          'language': 'de-DE',
        },
      );

      final profile = VoiceProfile.resolve(
        agent,
        capabilities: VoiceCapabilities({}),
      );

      expect(profile.issue?.kind, VoiceIssueKind.missingKey);
      expect(profile.issue?.message, contains('Schlüssel'));
      expect(
        profile.issue?.message,
        contains('OpenAI Whisper (Spracherkennung)'),
      );
      expect(profile.hint, startsWith('Gespräch mit einem Sprachassistenten'));
    });

    test('an English agent stays English', () {
      final agent = fakeAgent(
        'Muse',
        voice: {'stt_provider': 'openai_whisper', 'language': 'en-US'},
      );

      final profile = VoiceProfile.resolve(
        agent,
        capabilities: VoiceCapabilities({}),
      );

      expect(profile.issue?.message, contains('no key'));
      expect(profile.hint, startsWith('Conversation with a voice assistant'));
    });

    test('a turned-off voice says so in German', () {
      final agent = fakeAgent(
        'Muse',
        voice: {'language': 'de-DE'},
      ).withVoice(voiceEnabled: false);

      expect(
        VoiceProfile.resolve(agent).issue?.message,
        contains('ausgeschaltet'),
      );
    });
  });
}
