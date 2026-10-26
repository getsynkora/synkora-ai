import 'package:flutter_test/flutter_test.dart';
import 'package:speech_to_text/speech_recognition_result.dart';
import 'package:speech_to_text/speech_to_text.dart';
import 'package:speech_to_text_platform_interface/speech_to_text_platform_interface.dart';
import 'package:synkora_mobile/src/voice/engines/device_speech.dart';
import 'package:synkora_mobile/src/voice/ports.dart';

/// A stand-in for the phone's speech recognizer.
class FakeSttPlatform extends SpeechToTextPlatform {
  bool available = true;
  bool listening = false;
  int listenCalls = 0;
  String? listenLocale;
  List<String> localeList = const ['en_US:English US', 'fr_CA:French Canada'];

  @override
  Future<bool> hasPermission() async => true;

  @override
  Future<bool> initialize({
    debugLogging = false,
    List<SpeechConfigOption>? options,
  }) async => available;

  @override
  Future<bool> listen({
    String? localeId,
    partialResults = true,
    onDevice = false,
    int listenMode = 0,
    sampleRate = 0,
    SpeechListenOptions? options,
  }) async {
    listenCalls++;
    listenLocale = localeId;
    listening = true;
    onStatus?.call(SpeechToText.listeningStatus);
    return true;
  }

  @override
  Future<void> stop() async {
    listening = false;
    onStatus?.call(SpeechToText.doneStatus);
  }

  @override
  Future<void> cancel() async {
    listening = false;
    onStatus?.call(SpeechToText.notListeningStatus);
  }

  @override
  Future<List<dynamic>> locales() async => localeList;

  String _json(String words, ResultType type) =>
      '{"alternates":[{"recognizedWords":"$words","confidence":0.9}],"resultType":${type.value}}';

  void hear(String words) =>
      onTextRecognition?.call(_json(words, ResultType.partial));

  void hearFinal(String words) {
    listening = false;
    onTextRecognition?.call(_json(words, ResultType.finalResult));
    onStatus?.call(SpeechToText.doneStatus);
  }

  void fail(String code, {bool permanent = false}) =>
      onError?.call('{"errorMsg":"$code","permanent":$permanent}');
}

Future<void> pump() => Future<void>.delayed(const Duration(milliseconds: 5));

void main() {
  late FakeSttPlatform platform;
  late DeviceSpeechRecognizer recognizer;

  setUp(() {
    platform = FakeSttPlatform();
    SpeechToTextPlatform.instance = platform;
    recognizer = DeviceSpeechRecognizer(
      speech: SpeechToText.withMethodChannel(),
    );
  });

  test(
    'returns the final words and streams partial words while listening',
    () async {
      final partials = <String>[];
      recognizer.partials.listen(partials.add);

      final result = recognizer.listenOnce();
      await pump();
      platform.hear('what is');
      platform.hear('what is the weather');
      platform.hearFinal('what is the weather');

      expect(await result, 'what is the weather');
      await pump(); // let the broadcast stream deliver its last events
      expect(partials, [
        'what is',
        'what is the weather',
        'what is the weather',
      ]);
    },
  );

  test('maps the agent language onto the phone\'s locale ids', () async {
    var result = recognizer.listenOnce(locale: 'fr-CA');
    await pump();
    expect(platform.listenLocale, 'fr_CA');
    platform.hearFinal('bonjour');
    await result;

    // No exact match for en-GB: fall back to any English locale.
    result = recognizer.listenOnce(locale: 'en-GB');
    await pump();
    expect(platform.listenLocale, 'en_US');
    platform.hearFinal('hello');
    await result;
  });

  test('with no requested locale it uses the system locale', () async {
    final result = recognizer.listenOnce();
    await pump();

    expect(platform.listenLocale, 'en_US');
    platform.hearFinal('hi');
    await result;
  });

  test('stop() delivers what was heard so far', () async {
    final result = recognizer.listenOnce();
    await pump();
    platform.hear('send this now');

    await recognizer.stop();

    expect(await result, 'send this now');
  });

  test('silence ends with null rather than an error', () async {
    final result = recognizer.listenOnce();
    await pump();

    platform.fail('error_no_match');

    expect(await result, isNull);
  });

  test('cancel() discards the turn', () async {
    final result = recognizer.listenOnce();
    await pump();
    platform.hear('never mind');

    await recognizer.cancel();

    expect(await result, isNull);
  });

  test(
    'a recognizer that is not allowed or available is a clear error',
    () async {
      platform.available = false;

      expect(
        recognizer.listenOnce(),
        throwsA(
          isA<VoiceUnavailableException>().having(
            (e) => e.message,
            'message',
            contains('Speech Recognition'),
          ),
        ),
      );
    },
  );

  test('a permission error mid-listen is reported, not swallowed', () async {
    final result = recognizer.listenOnce();
    await pump();

    platform.fail('error_permission', permanent: true);

    expect(result, throwsA(isA<VoiceUnavailableException>()));
  });

  test(
    'Android rate limiting backs off instead of hammering the recognizer',
    () async {
      final first = recognizer.listenOnce();
      await pump();
      platform.fail('error_too_many_requests');
      expect(await first, isNull);
      final callsAfterLimit = platform.listenCalls;

      // Asking again straight away does not start another recognition.
      expect(await recognizer.listenOnce(), isNull);
      expect(platform.listenCalls, callsAfterLimit);
    },
  );

  group('a recognizer that keeps failing', () {
    Future<String?> attempt(
      FakeSttPlatform p,
      DeviceSpeechRecognizer r,
      String code,
    ) async {
      final result = r.listenOnce();
      await pump();
      p.fail(code, permanent: true);
      return result;
    }

    test(
      'is reported after three real failures in a row, with what to do',
      () async {
        expect(
          await attempt(platform, recognizer, 'error_unknown (300)'),
          isNull,
        );
        expect(
          await attempt(platform, recognizer, 'error_unknown (300)'),
          isNull,
        );

        final third = recognizer.listenOnce();
        await pump();
        platform.fail('error_unknown (300)', permanent: true);

        await expectLater(
          third,
          throwsA(
            isA<VoiceUnavailableException>().having(
              (e) => e.message,
              'message',
              allOf(contains('error_unknown'), contains('Voice settings')),
            ),
          ),
        );
      },
    );

    test('silence is not a failure, however often it happens', () async {
      for (var i = 0; i < 6; i++) {
        expect(await attempt(platform, recognizer, 'error_no_match'), isNull);
        expect(
          await attempt(platform, recognizer, 'error_speech_timeout'),
          isNull,
        );
      }
    });

    test('hearing something resets the count', () async {
      await attempt(platform, recognizer, 'error_unknown (300)');
      await attempt(platform, recognizer, 'error_unknown (300)');

      final ok = recognizer.listenOnce();
      await pump();
      platform.hearFinal('hello');
      expect(await ok, 'hello');

      // Two more failures are fine again; it takes three in a row.
      expect(
        await attempt(platform, recognizer, 'error_unknown (300)'),
        isNull,
      );
      expect(
        await attempt(platform, recognizer, 'error_unknown (300)'),
        isNull,
      );
    });
  });
}
