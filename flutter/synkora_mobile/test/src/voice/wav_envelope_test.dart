import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:synkora_mobile/src/voice/audio/pcm.dart';
import 'package:synkora_mobile/src/voice/audio/wav_envelope.dart';

import 'support/signals.dart';

void main() {
  test('parseWav reads rate, channels and duration', () {
    final wav = pcm16ToWav(speech(1000), sampleRate: 24000);
    final info = parseWav(wav)!;

    expect(info.sampleRate, 24000);
    expect(info.channels, 1);
    // speech() makes 16 kHz samples; at 24 kHz that is 2/3 s.
    expect(info.duration.inMilliseconds, closeTo(667, 5));
  });

  test('parseWav rejects non-wav and non-16-bit data', () {
    expect(parseWav(Uint8List.fromList(List.filled(100, 7))), isNull);
    expect(parseWav(Uint8List.fromList([0xFF, 0xFB, 0x90, 0x00])), isNull);
  });

  test('parseWav tolerates streaming headers with unknown data size', () {
    final wav = pcm16ToWav(speech(500));
    ByteData.sublistView(wav).setUint32(40, 0xFFFFFFFF, Endian.little);
    final info = parseWav(wav)!;

    expect(info.dataLength, speech(500).length * 2);
  });

  test(
    'envelope is loud for speech, quiet for silence, one value per step',
    () {
      final pcm = concat([speech(500, db: -20), noise(500, db: -70)]);
      final env = wavEnvelope(pcm16ToWav(pcm));

      expect(env.length, 20); // 1 s at 50 ms
      expect(env.take(8).every((v) => v > 0.6), isTrue);
      expect(env.skip(12).every((v) => v < 0.1), isTrue);
    },
  );

  test('envelope of a non-wav payload is empty', () {
    expect(wavEnvelope(Uint8List.fromList([1, 2, 3, 4])), isEmpty);
  });

  test('wrapRawPcm produces a playable wav at the given rate', () {
    final raw = Uint8List(4800); // 100 ms @ 24 kHz mono
    final info = parseWav(wrapRawPcm(raw, sampleRate: 24000))!;

    expect(info.sampleRate, 24000);
    expect(info.duration.inMilliseconds, 100);
  });
}
