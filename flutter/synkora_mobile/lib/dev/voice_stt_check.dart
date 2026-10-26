// Isolates the phone's built-in speech recognizer: no wake word, no capture
// stream, no custom audio session. Prints STT lines to the log.
//
//   flutter run -t lib/dev/voice_stt_check.dart
import 'dart:async';

import 'package:flutter/material.dart';

import '../src/voice/engines/device_speech.dart';

void main() => runApp(const MaterialApp(home: _Check()));

class _Check extends StatefulWidget {
  const _Check();

  @override
  State<_Check> createState() => _CheckState();
}

class _CheckState extends State<_Check> {
  final _stt = DeviceSpeechRecognizer();
  final _lines = <String>[];

  void _log(String line) {
    debugPrint('STTCHECK $line');
    if (mounted) setState(() => _lines.insert(0, line));
  }

  @override
  void initState() {
    super.initState();
    unawaited(_run());
  }

  Future<void> _run() async {
    _stt.partials.listen((p) => _log('partial: $p'));
    for (var i = 1; i <= 4; i++) {
      _log('listen #$i');
      try {
        final text = await _stt.listenOnce(locale: 'en-US');
        _log('result #$i: ${text ?? "(nothing)"}');
      } catch (e) {
        _log('ERROR #$i: $e');
      }
      await Future<void>.delayed(const Duration(seconds: 1));
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('STT check')),
    body: ListView(
      children: [for (final l in _lines) ListTile(title: Text(l))],
    ),
  );
}
