import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:synkora_mobile/src/voice/audio/pcm.dart';
import 'package:synkora_mobile/src/voice/audio/wav_envelope.dart';
import 'package:synkora_mobile/src/voice/wake/sherpa_wake_word_detector.dart';
import 'package:synkora_mobile/src/voice/wake/wake_keywords.dart';

String? _nativeLibraryRoot() {
  final home = Platform.environment['HOME'];
  if (home == null) return null;
  final cache = Directory('$home/.pub-cache/hosted/pub.dev');
  if (!cache.existsSync()) return null;
  for (final entry in cache.listSync()) {
    final name = entry.path.split('/').last;
    if (name.startsWith('sherpa_onnx_macos-')) {
      final root = '${entry.path}/macos';
      final lib = File(
        '$root/sherpa_onnx_macos/sherpa-onnx.xcframework/macos-arm64_x86_64/libsherpa-onnx-c-api.dylib',
      );
      if (lib.existsSync()) return root;
    }
  }
  return null;
}

bool _haveSay() =>
    Platform.isMacOS &&
    Process.runSync('which', ['say']).exitCode == 0 &&
    Process.runSync('which', ['afconvert']).exitCode == 0;

final _native = _nativeLibraryRoot();
final _canRun = _native != null && _haveSay();

late Directory _tmp;

/// Speaks [text] with macOS [voice] and returns 16 kHz mono PCM, or null if
/// that voice is not installed on this machine.
Int16List? say(String voice, String text) {
  final key = '${voice}_${text.hashCode}';
  final aiff = '${_tmp.path}/$key.aiff';
  final wav = '${_tmp.path}/$key.wav';
  final spoken = Process.runSync('say', ['-v', voice, '-o', aiff, text]);
  if (spoken.exitCode != 0) return null;
  final converted = Process.runSync('afconvert', [
    '-f',
    'WAVE',
    '-d',
    'LEI16@16000',
    '-c',
    '1',
    aiff,
    wav,
  ]);
  if (converted.exitCode != 0) return null;
  final bytes = File(wav).readAsBytesSync();
  final info = parseWav(bytes)!;
  final view = ByteData.sublistView(bytes);
  return Int16List.fromList([
    for (
      var o = info.dataOffset;
      o + 1 < info.dataOffset + info.dataLength;
      o += 2
    )
      view.getInt16(o, Endian.little),
  ]);
}

/// Feeds a realistic clip (lead-in and tail of silence) and reports whether
/// the phrase was detected.
Future<bool> detects(SherpaWakeWordDetector detector, Int16List speech) async {
  detector.reset();
  var heard = false;
  final sub = detector.detections.listen((_) => heard = true);
  final signal = Int16List(speech.length + 8000 + 14000)
    ..setRange(8000, 8000 + speech.length, speech);
  var frames = 0;
  for (
    var o = 0;
    o + kVoiceFrameSamples <= signal.length;
    o += kVoiceFrameSamples
  ) {
    detector.process(Int16List.sublistView(signal, o, o + kVoiceFrameSamples));
    if (++frames % 25 == 0) {
      await Future<void>.delayed(const Duration(milliseconds: 4));
    }
  }
  // The worker answers asynchronously; give it a moment to finish.
  for (var i = 0; i < 40 && !heard; i++) {
    await Future<void>.delayed(const Duration(milliseconds: 25));
  }
  await sub.cancel();
  return heard;
}

void main() {
  group('keyword list', () {
    test('every variant carries a score, threshold and the same label', () {
      final lines = buildWakeKeywords(WakeSensitivity.balanced).split('\n');

      expect(lines.length, kWakeKeywordTokens.length);
      for (final line in lines) {
        expect(line, contains(':2.5'));
        expect(line, contains('#0.03'));
        expect(line, endsWith('@$kWakeLabel'));
      }
    });

    test('sensitivity changes the boost and threshold, not the phrases', () {
      String phrases(WakeSensitivity s) => buildWakeKeywords(
        s,
      ).split('\n').map((l) => l.split(' :').first).join('|');

      expect(phrases(WakeSensitivity.low), phrases(WakeSensitivity.high));
      expect(buildWakeKeywords(WakeSensitivity.low), contains('#0.05'));
      expect(buildWakeKeywords(WakeSensitivity.low), contains(':2.0'));
      expect(buildWakeKeywords(WakeSensitivity.high), contains(':3.5'));
    });

    test('presets stay in the measured, safe range', () {
      for (final level in WakeSensitivity.values) {
        // Beam widths of 8+ let the bare name "Synkora" wake it.
        expect(level.maxActivePaths, lessThanOrEqualTo(7), reason: '$level');
      }
      expect(
        WakeSensitivity.high.score,
        greaterThan(WakeSensitivity.low.score),
      );
    });
  });

  group(
    'SherpaWakeWordDetector (real model, macOS synthetic speech)',
    () {
      late SherpaWakeWordDetector detector;

      setUpAll(() {
        if (!_canRun) return;
        _tmp = Directory.systemTemp.createTempSync('wake_test');
      });

      setUp(() {
        if (!_canRun) return;
        detector = SherpaWakeWordDetector(
          modelDirectory: 'assets/voice/wake',
          nativeLibraryPath: _native,
          cooldown: Duration.zero,
        );
      });

      tearDown(() async {
        if (_canRun) await detector.dispose();
      });

      tearDownAll(() {
        if (_canRun && _tmp.existsSync()) _tmp.deleteSync(recursive: true);
      });

      test(
        'wakes on "Hey Synkora" across voices and pronunciations',
        () async {
          const voices = [
            'Samantha', 'Alex', 'Daniel', 'Karen', 'Moira', 'Tessa', 'Rishi',
            'Fred', 'Victoria', 'Allison', //
          ];
          const phrases = [
            'Hey Synkora',
            'Hey Sinkora',
            'Hey Sink Ora',
            'Hey Sin Kora',
          ];
          var tried = 0;
          var woke = 0;
          final missed = <String>[];
          for (final voice in voices) {
            for (final phrase in phrases) {
              final pcm = say(voice, phrase);
              if (pcm == null) continue;
              tried++;
              if (await detects(detector, pcm)) {
                woke++;
              } else {
                missed.add('$voice: $phrase');
              }
            }
          }

          expect(detector.failure, isNull, reason: 'model must load');
          expect(
            tried,
            greaterThanOrEqualTo(8),
            reason: 'need installed voices',
          );
          final recall = woke / tried;
          // ignore: avoid_print
          print(
            'wake recall on synthetic speech: $woke/$tried '
            '(${(recall * 100).round()}%), missed: $missed',
          );
          expect(recall, greaterThanOrEqualTo(0.70));
        },
        timeout: const Timeout(Duration(minutes: 4)),
      );

      test(
        'stays silent for similar-sounding and unrelated speech',
        () async {
          const confusers = [
            'Hey Siri',
            'Hey Sandra',
            'Okay Google',
            'Hello everyone, can you tell me the weather today',
            'Synkora is a platform for building agents',
            'I use Synkora every day at work',
            'Welcome to Synkora',
            'Thanks Synkora for the update',
            'Hey Corra',
            'The cinema opens at seven tonight',
          ];
          final false_ = <String>[];
          var tried = 0;
          for (final voice in const ['Samantha', 'Daniel', 'Alex']) {
            for (final text in confusers) {
              final pcm = say(voice, text);
              if (pcm == null) continue;
              tried++;
              if (await detects(detector, pcm)) false_.add('$voice: $text');
            }
          }

          expect(tried, greaterThan(10));
          expect(false_, isEmpty, reason: 'false activations: $false_');
        },
        timeout: const Timeout(Duration(minutes: 4)),
      );

      test(
        'still wakes when words are spoken right after the phrase',
        () async {
          // Use a voice that wakes on the bare phrase, so this isolates the
          // effect of the trailing speech.
          for (final voice in const [
            'Alex',
            'Daniel',
            'Karen',
            'Moira',
            'Tessa',
          ]) {
            final phrase = say(voice, 'Hey Synkora');
            if (phrase == null || !await detects(detector, phrase)) continue;
            final follow = say(voice, 'what is on my calendar today')!;
            final pcm = Int16List.fromList([
              ...phrase,
              ...Int16List(2400),
              ...follow,
            ]);
            expect(await detects(detector, pcm), isTrue);
            return;
          }
          fail('no installed voice woke on the bare phrase');
        },
        timeout: const Timeout(Duration(minutes: 2)),
      );

      test(
        'a missing model fails safe instead of crashing',
        () async {
          final broken = SherpaWakeWordDetector(
            modelDirectory: '/nonexistent/model/dir',
            nativeLibraryPath: _native,
          );
          addTearDown(broken.dispose);

          expect(broken.process(Int16List(kVoiceFrameSamples)), isFalse);
          await broken.start();
          for (var i = 0; i < 20 && broken.failure == null; i++) {
            await Future<void>.delayed(const Duration(milliseconds: 50));
          }

          expect(broken.failure, isNotNull);
          expect(broken.process(Int16List(kVoiceFrameSamples)), isFalse);
        },
        timeout: const Timeout(Duration(minutes: 1)),
      );

      test(
        'changing sensitivity at runtime is accepted',
        () async {
          final pcm = say('Samantha', 'Hey Synkora');
          if (pcm == null) return;
          detector.sensitivity = WakeSensitivity.high;
          await detects(detector, pcm);
          detector.sensitivity = WakeSensitivity.low;

          expect(detector.sensitivity, WakeSensitivity.low);
          expect(detector.failure, isNull);
        },
        timeout: const Timeout(Duration(minutes: 1)),
      );
    },
    skip: _canRun ? false : 'needs macOS, `say`, and the sherpa macOS library',
  );
}
