import 'dart:math' as math;
import 'dart:typed_data';

import 'pcm.dart';

/// One note of a [buildChime] sequence.
class Tone {
  const Tone(this.frequency, this.milliseconds);

  final double frequency;
  final int milliseconds;
}

const int kChimeSampleRate = 24000;

/// A soft, click-free sequence of sine notes as a WAV file.
///
/// Each note gets a short attack and an exponential decay so it sounds like a
/// gentle bell rather than a beep.
Uint8List buildChime(List<Tone> tones, {double volume = 0.22}) {
  final samples = <int>[];
  for (final tone in tones) {
    final count = kChimeSampleRate * tone.milliseconds ~/ 1000;
    final attack = (kChimeSampleRate * 0.008).round();
    for (var i = 0; i < count; i++) {
      final t = i / kChimeSampleRate;
      final rise = i < attack ? i / attack : 1.0;
      final fall = math.exp(-4.5 * i / count);
      final fundamental = math.sin(2 * math.pi * tone.frequency * t);
      final overtone = 0.25 * math.sin(2 * math.pi * tone.frequency * 2 * t);
      final value = (fundamental + overtone) / 1.25 * rise * fall * volume;
      samples.add((value * 32767).round());
    }
  }
  return pcm16ToWav(Int16List.fromList(samples), sampleRate: kChimeSampleRate);
}

/// Loudness (0..1) at [position] of an envelope sampled every [step], with
/// linear interpolation between samples. Returns 0 past the end.
double levelAt(List<double> envelope, Duration step, Duration position) {
  if (envelope.isEmpty || step.inMicroseconds <= 0) return 0;
  final index = position.inMicroseconds / step.inMicroseconds;
  if (index < 0 || index >= envelope.length) return 0;
  final lower = index.floor();
  final upper = math.min(lower + 1, envelope.length - 1);
  final fraction = index - lower;
  return envelope[lower] + (envelope[upper] - envelope[lower]) * fraction;
}

/// A believable speech-like level for audio with no known envelope (for
/// example MP3), so the visualiser still moves in time with playback.
double syntheticSpeechLevel(Duration position) {
  final t = position.inMicroseconds / 1e6;
  final syllables = 0.5 + 0.5 * math.sin(2 * math.pi * 3.3 * t);
  final phrasing = 0.65 + 0.35 * math.sin(2 * math.pi * 0.6 * t + 1.3);
  final detail = 0.85 + 0.15 * math.sin(2 * math.pi * 7.9 * t);
  return (0.18 + 0.62 * syllables * phrasing * detail).clamp(0.0, 1.0);
}
