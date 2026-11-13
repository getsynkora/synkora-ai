import 'dart:math' as math;
import 'dart:typed_data';

import 'package:synkora_mobile/src/voice/audio/pcm.dart';

final _rng = math.Random(7);

/// Low-level broadband room noise around [db] dBFS.
Int16List noise(int ms, {double db = -62}) {
  final n = kVoiceSampleRate * ms ~/ 1000;
  final amp = math.pow(10, db / 20) * 32768 * math.sqrt(3);
  return Int16List.fromList(
    List.generate(n, (_) => ((_rng.nextDouble() * 2 - 1) * amp).round()),
  );
}

/// Speech-like signal: harmonics with a ~4 Hz syllable envelope at [db] dBFS.
Int16List speech(int ms, {double db = -24}) {
  final n = kVoiceSampleRate * ms ~/ 1000;
  final amp = math.pow(10, db / 20) * 32768;
  final out = Int16List(n);
  for (var i = 0; i < n; i++) {
    final t = i / kVoiceSampleRate;
    final env = 0.65 + 0.35 * math.sin(2 * math.pi * 4 * t).abs();
    final s =
        math.sin(2 * math.pi * 140 * t) * 0.6 +
        math.sin(2 * math.pi * 420 * t) * 0.3 +
        math.sin(2 * math.pi * 1500 * t) * 0.2;
    out[i] = (s * env * amp / 0.75).round().clamp(-32768, 32767);
  }
  return out;
}

Int16List concat(List<Int16List> parts) {
  final out = <int>[];
  for (final p in parts) {
    out.addAll(p);
  }
  return Int16List.fromList(out);
}
