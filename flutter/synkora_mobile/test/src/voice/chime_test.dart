import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:synkora_mobile/src/voice/audio/chime.dart';
import 'package:synkora_mobile/src/voice/audio/wav_envelope.dart';

void main() {
  test('chime is a valid wav of the expected length', () {
    final wav = buildChime(const [Tone(660, 100), Tone(880, 200)]);
    final info = parseWav(wav)!;

    expect(info.sampleRate, kChimeSampleRate);
    expect(info.duration.inMilliseconds, 300);
  });

  test('chime is quiet and starts and ends without a click', () {
    final wav = buildChime(const [Tone(660, 150)], volume: 0.2);
    final info = parseWav(wav)!;
    final view = ByteData.sublistView(wav);
    var peak = 0;
    for (var o = info.dataOffset; o < wav.length - 1; o += 2) {
      final v = view.getInt16(o, Endian.little).abs();
      if (v > peak) peak = v;
    }

    expect(peak, lessThan(32767 * 0.25));
    expect(view.getInt16(info.dataOffset, Endian.little).abs(), lessThan(200));
    expect(view.getInt16(wav.length - 2, Endian.little).abs(), lessThan(900));
  });

  group('levelAt', () {
    const step = Duration(milliseconds: 50);
    const env = [0.0, 1.0, 0.5];

    test('interpolates between samples', () {
      expect(levelAt(env, step, const Duration(milliseconds: 25)), 0.5);
      expect(levelAt(env, step, const Duration(milliseconds: 50)), 1.0);
      expect(levelAt(env, step, const Duration(milliseconds: 75)), 0.75);
    });

    test('is zero before the start, past the end, and with no envelope', () {
      expect(levelAt(env, step, const Duration(milliseconds: -5)), 0);
      expect(levelAt(env, step, const Duration(seconds: 5)), 0);
      expect(levelAt(const [], step, Duration.zero), 0);
    });
  });

  test('synthetic speech level stays within 0..1 and varies', () {
    final values = [
      for (var ms = 0; ms < 3000; ms += 33)
        syntheticSpeechLevel(Duration(milliseconds: ms)),
    ];
    expect(values.every((v) => v >= 0 && v <= 1), isTrue);
    expect(
      values.reduce((a, b) => a > b ? a : b) -
          values.reduce((a, b) => a < b ? a : b),
      greaterThan(0.3),
    );
  });
}
