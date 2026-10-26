import 'dart:math' as math;
import 'dart:typed_data';

import 'pcm.dart';

/// Basic facts about a PCM WAV file.
class WavInfo {
  const WavInfo({
    required this.sampleRate,
    required this.channels,
    required this.dataOffset,
    required this.dataLength,
  });

  final int sampleRate;
  final int channels;
  final int dataOffset;
  final int dataLength;

  Duration get duration => Duration(
    microseconds: dataLength * 1000000 ~/ (sampleRate * channels * 2),
  );
}

/// Parses a 16-bit PCM WAV header, or returns null if [bytes] is not one.
WavInfo? parseWav(Uint8List bytes) {
  if (bytes.length < 44) return null;
  final view = ByteData.sublistView(bytes);
  String tag(int o) => String.fromCharCodes(bytes.sublist(o, o + 4));
  if (tag(0) != 'RIFF' || tag(8) != 'WAVE') return null;

  var offset = 12;
  int? sampleRate;
  int? channels;
  while (offset + 8 <= bytes.length) {
    final id = tag(offset);
    var size = view.getUint32(offset + 4, Endian.little);
    final body = offset + 8;
    if (id == 'fmt ') {
      if (body + 16 > bytes.length) return null;
      final format = view.getUint16(body, Endian.little);
      final bits = view.getUint16(body + 14, Endian.little);
      if ((format != 1 && format != 0xFFFE) || bits != 16) return null;
      channels = view.getUint16(body + 2, Endian.little);
      sampleRate = view.getUint32(body + 4, Endian.little);
    } else if (id == 'data') {
      if (sampleRate == null || channels == null) return null;
      // Streaming encoders may leave the size as 0 or 0xFFFFFFFF.
      if (size == 0 || size == 0xFFFFFFFF || body + size > bytes.length) {
        size = bytes.length - body;
      }
      return WavInfo(
        sampleRate: sampleRate,
        channels: channels,
        dataOffset: body,
        dataLength: size - (size % (channels * 2)),
      );
    }
    offset = body + size + (size % 2);
  }
  return null;
}

/// Loudness (0..1) of a WAV file every [step], for animating UI in sync with
/// playback. Returns an empty list for anything that is not 16-bit PCM WAV.
List<double> wavEnvelope(
  Uint8List bytes, {
  Duration step = const Duration(milliseconds: 50),
}) {
  final info = parseWav(bytes);
  if (info == null) return const [];
  final view = ByteData.sublistView(bytes);
  final frameBytes = info.channels * 2;
  final framesPerStep = math.max(
    1,
    info.sampleRate * step.inMicroseconds ~/ 1000000,
  );
  final totalFrames = info.dataLength ~/ frameBytes;
  final out = <double>[];

  for (var start = 0; start < totalFrames; start += framesPerStep) {
    final end = math.min(totalFrames, start + framesPerStep);
    var sum = 0.0;
    for (var f = start; f < end; f++) {
      // Use the first channel; speech is mono in practice.
      final sample = view.getInt16(
        info.dataOffset + f * frameBytes,
        Endian.little,
      );
      sum += sample * sample;
    }
    final rms = math.sqrt(sum / (end - start)) / 32768.0;
    final db = rms < 1e-5 ? -90.0 : 20 * math.log(rms) / math.ln10;
    out.add(dbToLevel(db));
  }
  return out;
}

/// Wraps headerless 16-bit mono PCM (such as ElevenLabs `pcm_24000`) in a
/// WAV container so a normal audio player can play it.
Uint8List wrapRawPcm(Uint8List pcm, {required int sampleRate}) {
  final samples = Int16List(pcm.length ~/ 2);
  final view = ByteData.sublistView(pcm);
  for (var i = 0; i < samples.length; i++) {
    samples[i] = view.getInt16(i * 2, Endian.little);
  }
  return pcm16ToWav(samples, sampleRate: sampleRate);
}
