import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:synkora_mobile/src/voice/audio/pcm.dart';
import 'package:synkora_mobile/src/voice/audio/vad.dart';

import 'support/signals.dart';

/// Feeds [signal] to [endpointer] in 20 ms frames, collecting events with the
/// time (ms) at which each fired.
List<(int, EndpointEvent)> run(TurnEndpointer endpointer, Int16List signal) {
  final events = <(int, EndpointEvent)>[];
  for (
    var offset = 0;
    offset + kVoiceFrameSamples <= signal.length;
    offset += kVoiceFrameSamples
  ) {
    final frame = Int16List.sublistView(
      signal,
      offset,
      offset + kVoiceFrameSamples,
    );
    final event = endpointer.feed(frame);
    if (event != null) {
      events.add((offset * 1000 ~/ kVoiceSampleRate, event));
    }
  }
  return events;
}

void main() {
  group('pcm helpers', () {
    test('frameDb reports silence and full scale sensibly', () {
      expect(frameDb(Int16List(320)), -90);
      final loud = Int16List.fromList(List.filled(320, 32767));
      expect(frameDb(loud), closeTo(0, 0.1));
    });

    test('pcm16ToWav writes a valid header', () {
      final wav = pcm16ToWav(Int16List.fromList([1, -1, 2, -2]));
      final text = String.fromCharCodes;
      expect(text(wav.sublist(0, 4)), 'RIFF');
      expect(text(wav.sublist(8, 12)), 'WAVE');
      expect(text(wav.sublist(36, 40)), 'data');
      final view = ByteData.sublistView(wav);
      expect(view.getUint32(24, Endian.little), 16000);
      expect(view.getUint32(40, Endian.little), 8);
      expect(wav.length, 44 + 8);
    });

    test('ring buffer keeps only the most recent samples in order', () {
      final ring = PcmRingBuffer(5);
      ring.push(Int16List.fromList([1, 2, 3]));
      ring.push(Int16List.fromList([4, 5, 6, 7]));
      expect(ring.tail().toList(), [3, 4, 5, 6, 7]);
      expect(ring.tail(2).toList(), [6, 7]);
    });

    test('framer re-chunks arbitrary byte boundaries into whole frames', () {
      final framer = PcmFramer(frameSamples: 4);
      final bytes = ByteData(24); // 12 samples
      for (var i = 0; i < 12; i++) {
        bytes.setInt16(i * 2, i, Endian.little);
      }
      final all = bytes.buffer.asUint8List();
      final frames = <Int16List>[
        ...framer.add(all.sublist(0, 5)),
        ...framer.add(all.sublist(5, 17)),
        ...framer.add(all.sublist(17)),
      ];
      expect(frames.map((f) => f.toList()).toList(), [
        [0, 1, 2, 3],
        [4, 5, 6, 7],
        [8, 9, 10, 11],
      ]);
    });
  });

  group('EnergyVad', () {
    test('quiet room noise is not speech and teaches the floor', () {
      final vad = EnergyVad();
      final room = noise(1000, db: -55);
      var speechFrames = 0;
      for (var o = 0; o + 320 <= room.length; o += 320) {
        if (vad.process(Int16List.sublistView(room, o, o + 320))) {
          speechFrames++;
        }
      }
      expect(speechFrames, lessThan(3));
      expect(vad.calibrated, isTrue);
      expect(vad.noiseFloorDb, greaterThan(-62));
    });

    test('speech well above the floor is detected once calibrated', () {
      final vad = EnergyVad();
      final room = noise(400);
      for (var o = 0; o + 320 <= room.length; o += 320) {
        vad.process(Int16List.sublistView(room, o, o + 320));
      }
      final s = speech(200);
      expect(vad.process(Int16List.sublistView(s, 0, 320)), isTrue);
    });

    test('never reports speech while still calibrating', () {
      final vad = EnergyVad();
      final s = speech(200);
      expect(vad.process(Int16List.sublistView(s, 0, 320)), isFalse);
    });

    test('a steady hum is learned as background, not speech', () {
      final vad = EnergyVad();
      final hum = noise(4000, db: -44);
      var late = 0;
      for (var o = 0; o + 320 <= hum.length; o += 320) {
        final speech = vad.process(Int16List.sublistView(hum, o, o + 320));
        if (o > 16000 * 2 && speech) late++;
      }
      expect(late, 0);
      expect(vad.noiseFloorDb, greaterThan(-50));
    });

    test('learn:false keeps long speech from raising the floor', () {
      final vad = EnergyVad();
      final room = noise(600);
      for (var o = 0; o + 320 <= room.length; o += 320) {
        vad.process(Int16List.sublistView(room, o, o + 320));
      }
      final before = vad.noiseFloorDb;
      final talk = speech(5000);
      for (var o = 0; o + 320 <= talk.length; o += 320) {
        vad.process(Int16List.sublistView(talk, o, o + 320), learn: false);
      }
      expect(vad.noiseFloorDb, closeTo(before, 0.001));
    });
  });

  group('TurnEndpointer', () {
    test('detects start and end of one utterance with lead-in audio', () {
      final ep = TurnEndpointer();
      final signal = concat([noise(600), speech(1200), noise(1500)]);
      final events = run(ep, signal);

      expect(events.map((e) => e.$2.type).toList(), [
        EndpointEventType.speechStart,
        EndpointEventType.speechEnd,
      ]);
      final start = events[0].$1;
      expect(
        start,
        inInclusiveRange(600, 760),
      ); // onset ~80 ms after speech begins
      final end = events[1].$2;
      // ~1.2 s of speech + lead-in + ~0.85 s trailing silence.
      final audioMs = end.audio!.length * 1000 ~/ kVoiceSampleRate;
      expect(audioMs, inInclusiveRange(2000, 2800));
      expect(end.speechDuration!.inMilliseconds, inInclusiveRange(1000, 1400));
    });

    test('a short pause inside a sentence does not end the turn', () {
      final ep = TurnEndpointer();
      final signal = concat([
        noise(400),
        speech(700),
        noise(500), // thinking pause, shorter than endSilence
        speech(700),
        noise(1500),
      ]);
      final events = run(ep, signal);

      final ends = events.where(
        (e) => e.$2.type == EndpointEventType.speechEnd,
      );
      expect(ends.length, 1);
      expect(ends.first.$2.speechDuration!.inMilliseconds, greaterThan(1200));
    });

    test('a click or cough is discarded and does not end up as a turn', () {
      final ep = TurnEndpointer();
      final signal = concat([noise(500), speech(120), noise(1500)]);
      final events = run(ep, signal);

      expect(
        events.any((e) => e.$2.type == EndpointEventType.speechEnd),
        isFalse,
      );
    });

    test('reports noSpeech when the user never talks', () {
      final ep = TurnEndpointer(const EndpointConfig(noSpeechTimeoutMs: 3000));
      final events = run(ep, noise(3500));

      expect(events.map((e) => e.$2.type), [EndpointEventType.noSpeech]);
      expect(events.first.$1, inInclusiveRange(2900, 3100));
    });

    test('cuts off a monologue at maxUtteranceMs', () {
      final ep = TurnEndpointer(const EndpointConfig(maxUtteranceMs: 2000));
      final events = run(ep, concat([noise(300), speech(4000)]));

      // The cut is followed by a fresh speechStart because speech continues.
      expect(
        events.map((e) => e.$2.type),
        containsAllInOrder([
          EndpointEventType.speechStart,
          EndpointEventType.maxLength,
        ]),
      );
    });

    test('keeps the first syllable via pre-roll', () {
      final ep = TurnEndpointer();
      final events = run(ep, concat([noise(800), speech(800), noise(1200)]));
      final audio = events.last.$2.audio!;
      // Pre-roll (up to 480 ms) means the audio is longer than speech + tail alone.
      expect(audio.length * 1000 ~/ kVoiceSampleRate, greaterThan(800 + 850));
    });

    test(
      'barge-in profile ignores a short loud blip but catches real speech',
      () {
        final blip = TurnEndpointer(const EndpointConfig.bargeIn());
        expect(
          run(blip, concat([noise(500), speech(150, db: -20), noise(500)])),
          isEmpty,
        );

        final real = TurnEndpointer(const EndpointConfig.bargeIn());
        final events = run(real, concat([noise(500), speech(900, db: -22)]));
        expect(events.first.$2.type, EndpointEventType.speechStart);
      },
    );

    test('adapts to a noisy room instead of treating it as speech', () {
      final ep = TurnEndpointer();
      // Constant fan hum at -46 dBFS for 6 s, then someone speaks over it.
      final signal = concat([
        noise(6000, db: -46),
        speech(900, db: -22),
        noise(1800, db: -46),
      ]);
      final events = run(ep, signal);

      final starts = events.where(
        (e) => e.$2.type == EndpointEventType.speechStart,
      );
      expect(starts.length, 1);
      expect(starts.first.$1, greaterThan(5900));
    });

    test('reset forgets an utterance in progress', () {
      final ep = TurnEndpointer();
      run(ep, concat([noise(300), speech(500)]));
      expect(ep.inSpeech, isTrue);
      ep.reset();
      expect(ep.inSpeech, isFalse);
    });
  });
}
