// Smoke test for the REAL audio stack (no fakes):
//
//   flutter run -t lib/dev/voice_smoke.dart
//
// Opens the real microphone, loads the bundled wake-word model, and plays a
// chime through the real player. It prints SMOKE lines to the log and shows the
// same facts on screen, so a human or a script can confirm that capture,
// playback and "Hey Synkora" detection work on a given device.
import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../src/voice/audio/chime.dart';
import '../src/voice/audio/pcm.dart';
import '../src/voice/audio/wav_envelope.dart';
import '../src/voice/engines/just_audio_output.dart';
import '../src/voice/engines/record_mic.dart';
import '../src/voice/ports.dart';
import '../src/voice/wake/sherpa_wake_word_detector.dart';

void main() => runApp(const MaterialApp(home: _Smoke()));

class _Smoke extends StatefulWidget {
  const _Smoke();

  @override
  State<_Smoke> createState() => _SmokeState();
}

class _SmokeState extends State<_Smoke> {
  final _mic = RecordMic();
  final _output = JustAudioOutput();
  final _wake = SherpaWakeWordDetector();
  final _lines = <String>[];
  var _frames = 0;
  var _peakDb = -90.0;
  var _wakes = 0;

  void _log(String line) {
    debugPrint('SMOKE $line');
    if (mounted) setState(() => _lines.insert(0, line));
  }

  @override
  void initState() {
    super.initState();
    unawaited(_run());
  }

  /// Feeds a recorded phrase (a 16 kHz mono WAV on the host) to the wake
  /// detector, proving the bundled model and native library work on this
  /// device even when no microphone is available (for example a simulator).
  Future<void> _feedRecording() async {
    const path = String.fromEnvironment('SMOKE_WAV');
    if (path.isEmpty) return;
    final file = File(path);
    if (!file.existsSync()) {
      _log('SMOKE_WAV not found: $path');
      return;
    }
    final bytes = file.readAsBytesSync();
    final info = parseWav(bytes);
    if (info == null) {
      _log('SMOKE_WAV is not a 16-bit PCM wav');
      return;
    }
    _log('wake: loading model from the app bundle');
    await _wake.start();
    _log('wake model ${_wake.isReady ? "READY" : "FAILED: ${_wake.failure}"}');
    if (!_wake.isReady) return;
    final view = ByteData.sublistView(bytes);
    final pcm = Int16List.fromList([
      ...Int16List(8000),
      for (
        var o = info.dataOffset;
        o + 1 < info.dataOffset + info.dataLength;
        o += 2
      )
        view.getInt16(o, Endian.little),
      ...Int16List(16000),
    ]);
    var woke = 0;
    for (
      var o = 0;
      o + kVoiceFrameSamples <= pcm.length;
      o += kVoiceFrameSamples
    ) {
      if (_wake.process(
        Int16List.sublistView(pcm, o, o + kVoiceFrameSamples),
      )) {
        woke++;
      }
      if ((o ~/ kVoiceFrameSamples) % 25 == 0) {
        await Future<void>.delayed(const Duration(milliseconds: 5));
      }
    }
    await Future<void>.delayed(const Duration(milliseconds: 800));
    // The detector replies asynchronously; poll once more.
    if (_wake.process(Int16List(kVoiceFrameSamples))) woke++;
    _log('RECORDING RESULT: wake detected=${woke > 0} (count $woke)');
  }

  Future<void> _run() async {
    try {
      await _feedRecording();
      _log('starting microphone');
      await _mic.start();
      _log('microphone running');
      _mic.frames.listen((frame) {
        _frames++;
        final db = frameDb(frame);
        if (db > _peakDb) _peakDb = db;
        if (_wake.process(frame)) {
          _wakes++;
          _log('WAKE detected (#$_wakes)');
        }
        if (_frames % 250 == 0) {
          _log(
            'frames=$_frames peakDb=${_peakDb.toStringAsFixed(1)} '
            'wakeReady=${_wake.isReady} wakeFailure=${_wake.failure}',
          );
          _peakDb = -90;
        }
      });
      unawaited(
        _wake.start().then(
          (_) => _log(
            'wake model ${_wake.isReady ? "READY" : "FAILED: ${_wake.failure}"}',
          ),
        ),
      );
      await Future<void>.delayed(const Duration(seconds: 2));
      await _playChime();
      await _measureGaps();
    } catch (e) {
      _log('ERROR $e');
    }
  }

  Future<void> _playChime() async {
    _log('playing chime');
    final wav = buildChime(const [Tone(660, 150), Tone(990, 250)]);
    final audio = SynthesizedAudio(
      bytes: wav,
      mimeType: 'audio/wav',
      duration: parseWav(wav)!.duration,
      envelope: wavEnvelope(wav),
    );
    final levels = <double>[];
    final sub = _output.level.listen(levels.add);
    await _output.play(audio);
    await sub.cancel();
    final peak = levels.isEmpty ? 0.0 : levels.reduce((a, b) => a > b ? a : b);
    _log(
      'chime finished; level samples=${levels.length} peak=${peak.toStringAsFixed(2)}',
    );
  }

  /// Plays several clips back to back, as the assistant does for consecutive
  /// sentences, and reports the silence added between them.
  Future<void> _measureGaps() async {
    final wav = buildChime(const [Tone(700, 400)], volume: 0.05);
    final info = parseWav(wav)!;
    final audio = SynthesizedAudio(
      bytes: wav,
      mimeType: 'audio/wav',
      duration: info.duration,
      envelope: wavEnvelope(wav),
    );
    const clips = 6;
    final starts = <int>[];
    final clock = Stopwatch()..start();
    for (var i = 0; i < clips; i++) {
      starts.add(clock.elapsedMilliseconds);
      await _output.play(audio);
    }
    final total = clock.elapsedMilliseconds;
    final clipMs = info.duration.inMilliseconds;
    final gaps = [
      for (var i = 1; i < clips; i++) starts[i] - starts[i - 1] - clipMs,
    ];
    _log('GAPS between clips (ms, clip=$clipMs): $gaps  total=$total');
  }

  @override
  void dispose() {
    _wake.dispose();
    _output.dispose();
    _mic.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Voice smoke test')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(
            'wakes: $_wakes   frames: $_frames',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 12),
          for (final l in _lines) Text(l, style: const TextStyle(fontSize: 13)),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: _playChime,
        child: const Icon(Icons.volume_up),
      ),
    );
  }
}
