import 'dart:math' as math;
import 'dart:typed_data';

/// Sample rate used for the whole capture pipeline (wake word, VAD, STT).
const int kVoiceSampleRate = 16000;

/// Samples in one processing frame (20 ms at 16 kHz).
const int kVoiceFrameSamples = 320;

/// Wraps raw little-endian PCM16 [samples] in a RIFF/WAV container.
Uint8List pcm16ToWav(
  Int16List samples, {
  int sampleRate = kVoiceSampleRate,
  int channels = 1,
}) {
  final dataLength = samples.length * 2;
  final bytes = ByteData(44 + dataLength);
  void ascii(int offset, String text) {
    for (var i = 0; i < text.length; i++) {
      bytes.setUint8(offset + i, text.codeUnitAt(i));
    }
  }

  ascii(0, 'RIFF');
  bytes.setUint32(4, 36 + dataLength, Endian.little);
  ascii(8, 'WAVE');
  ascii(12, 'fmt ');
  bytes.setUint32(16, 16, Endian.little);
  bytes.setUint16(20, 1, Endian.little); // PCM
  bytes.setUint16(22, channels, Endian.little);
  bytes.setUint32(24, sampleRate, Endian.little);
  bytes.setUint32(28, sampleRate * channels * 2, Endian.little);
  bytes.setUint16(32, channels * 2, Endian.little);
  bytes.setUint16(34, 16, Endian.little);
  ascii(36, 'data');
  bytes.setUint32(40, dataLength, Endian.little);
  for (var i = 0; i < samples.length; i++) {
    bytes.setInt16(44 + i * 2, samples[i], Endian.little);
  }
  return bytes.buffer.asUint8List();
}

/// Loudness of [frame] in dBFS (0 is full scale, silence is about -90).
double frameDb(Int16List frame) {
  if (frame.isEmpty) return -90;
  var sum = 0.0;
  for (final s in frame) {
    sum += s * s;
  }
  final rms = math.sqrt(sum / frame.length) / 32768.0;
  if (rms < 1e-5) return -90;
  return 20 * math.log(rms) / math.ln10;
}

/// Maps a dBFS value onto 0..1 for UI meters (-60 dB to -10 dB).
double dbToLevel(double db) => ((db + 60) / 50).clamp(0.0, 1.0);

/// Fixed-size rolling window of the most recent samples.
///
/// Kept so that when speech is detected the audio just *before* the detection
/// point (the first syllable the detector needed time to confirm) is not lost.
class PcmRingBuffer {
  PcmRingBuffer(this.capacitySamples) : _data = Int16List(capacitySamples);

  final int capacitySamples;
  final Int16List _data;
  int _write = 0;
  int _filled = 0;

  int get length => _filled;

  void push(Int16List samples) {
    for (final s in samples) {
      _data[_write] = s;
      _write = (_write + 1) % capacitySamples;
    }
    _filled = math.min(capacitySamples, _filled + samples.length);
  }

  /// The last [count] samples (or fewer if not that many have arrived), oldest first.
  Int16List tail([int? count]) {
    final n = math.min(count ?? _filled, _filled);
    final out = Int16List(n);
    var index = (_write - n) % capacitySamples;
    if (index < 0) index += capacitySamples;
    for (var i = 0; i < n; i++) {
      out[i] = _data[index];
      index = (index + 1) % capacitySamples;
    }
    return out;
  }

  void clear() {
    _write = 0;
    _filled = 0;
  }
}

/// Growable PCM16 accumulator.
class PcmBuilder {
  final BytesBuilder _bytes = BytesBuilder(copy: false);
  int _samples = 0;

  int get sampleCount => _samples;

  Duration get duration =>
      Duration(microseconds: _samples * 1000000 ~/ kVoiceSampleRate);

  void add(Int16List samples) {
    _bytes.add(
      samples.buffer.asUint8List(samples.offsetInBytes, samples.lengthInBytes),
    );
    _samples += samples.length;
  }

  Int16List takeSamples() {
    final raw = _bytes.takeBytes();
    _samples = 0;
    // Copy so the result is aligned regardless of how bytes were chunked.
    final out = Int16List(raw.length ~/ 2);
    final view = ByteData.sublistView(raw);
    for (var i = 0; i < out.length; i++) {
      out[i] = view.getInt16(i * 2, Endian.host);
    }
    return out;
  }
}

/// Re-chunks an arbitrary stream of little-endian PCM16 bytes into fixed
/// [kVoiceFrameSamples]-sample frames.
class PcmFramer {
  PcmFramer({this.frameSamples = kVoiceFrameSamples});

  final int frameSamples;
  final BytesBuilder _pending = BytesBuilder(copy: false);
  int _pendingBytes = 0;

  List<Int16List> add(Uint8List bytes) {
    _pending.add(bytes);
    _pendingBytes += bytes.length;
    final frameBytes = frameSamples * 2;
    if (_pendingBytes < frameBytes) return const [];

    final all = _pending.takeBytes();
    final frames = <Int16List>[];
    final usable = (all.length ~/ frameBytes) * frameBytes;
    final view = ByteData.sublistView(all);
    for (var offset = 0; offset < usable; offset += frameBytes) {
      final frame = Int16List(frameSamples);
      for (var i = 0; i < frameSamples; i++) {
        frame[i] = view.getInt16(offset + i * 2, Endian.little);
      }
      frames.add(frame);
    }
    if (usable < all.length) {
      _pending.add(Uint8List.sublistView(all, usable));
    }
    _pendingBytes = all.length - usable;
    return frames;
  }

  void reset() {
    _pending.clear();
    _pendingBytes = 0;
  }
}
