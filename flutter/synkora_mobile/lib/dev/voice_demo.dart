// A scripted, backend-free preview of the voice experience.
//
//   flutter run -t lib/dev/voice_demo.dart
//
// It drives the real VoiceHub and VoiceModeScreen with a simulated microphone,
// agent and voice, so the whole flow (wake, listen, think, speak, interrupt)
// can be reviewed and screenshotted without a server or speech keys.
import 'dart:async';
import 'dart:math' as math;
import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../src/services/agent_service.dart';
import 'demo_backend.dart';
import '../src/theme/app_theme.dart';
import '../src/ui/voice/voice_entry_card.dart';
import '../src/ui/voice/voice_hub_scope.dart';
import '../src/ui/voice/voice_mode_screen.dart';
import '../src/voice/audio/chime.dart';
import '../src/voice/audio/pcm.dart';
import '../src/voice/ports.dart';
import '../src/voice/voice_hub.dart';
import '../src/voice/voice_settings.dart';

void main() => runApp(const _DemoApp());

class _DemoApp extends StatelessWidget {
  const _DemoApp();

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      theme: buildSynkoraTheme(),
      home: const _DemoRoot(),
    );
  }
}

class _DemoRoot extends StatefulWidget {
  const _DemoRoot();

  @override
  State<_DemoRoot> createState() => _DemoRootState();
}

class _DemoRootState extends State<_DemoRoot> {
  VoiceHub? _hub;
  late final _DemoMic _mic = _DemoMic();
  late final _DemoWake _wake = _DemoWake();

  @override
  void initState() {
    super.initState();
    unawaited(_boot());
  }

  Future<void> _boot() async {
    final settings = await VoiceSettings.load();
    await settings.setWakeEnabled(true);
    final api = DemoApi(
      voiceConfig: const {
        'stt_provider': 'openai_whisper',
        'tts_provider': 'openai_tts',
        'tts_voice': 'nova',
      },
    );
    final hub = VoiceHub(
      api: api,
      agentService: SynkoraAgentService(api),
      settings: settings,
      mic: _mic,
      output: _DemoOutput(),
      wake: _wake,
    );
    hub.updateAgents(demoAgents);
    await hub.prepareDefaultAgent();
    await hub.start();
    hub.wakeEvents.listen((_) {
      if (!mounted) return;
      Navigator.of(context).push(
        VoiceModeScreen.route(
          hub: hub,
          agent: hub.conversation.agent ?? demoAgents.first,
          alreadyListening: true,
        ),
      );
    });
    if (!mounted) return;
    setState(() => _hub = hub);
    unawaited(_runScript(hub));
  }

  /// Walks through one whole conversation.
  Future<void> _runScript(VoiceHub hub) async {
    Future<void> wait(double s) =>
        Future<void>.delayed(Duration(milliseconds: (s * 1000).round()));
    await wait(3.5); // resting on the home screen, listening for the phrase
    _wake.trigger();
    await wait(2.5); // screen opens, "I'm listening"
    await _mic.speak(const Duration(milliseconds: 1700));
    await wait(0.4);
    // Now thinking, then the reply is spoken.
    await wait(11);
    await _mic.speak(const Duration(milliseconds: 1500)); // follow-up
  }

  @override
  Widget build(BuildContext context) {
    final hub = _hub;
    if (hub == null) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    return VoiceHubScope(
      hub: hub,
      child: Scaffold(
        backgroundColor: SynkoraColors.background,
        body: SafeArea(
          child: ListView(
            padding: const EdgeInsets.all(20),
            children: [
              const SizedBox(height: 12),
              Text(
                'Welcome back, Raju',
                style: Theme.of(context).textTheme.displayMedium,
              ),
              const SizedBox(height: 24),
              const VoiceEntryCard(),
            ],
          ),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Simulated agents, microphone, wake word, API and speaker
// ---------------------------------------------------------------------------

class _DemoMic implements VoiceMic {
  final _frames = StreamController<Int16List>.broadcast();
  Timer? _timer;
  bool _running = false;
  int _speechFramesLeft = 0;
  final _rng = math.Random(3);
  int _n = 0;

  @override
  Stream<Int16List> get frames => _frames.stream;

  @override
  bool get isRunning => _running;

  /// Pretend the user talks for [duration].
  Future<void> speak(Duration duration) async {
    _speechFramesLeft = duration.inMilliseconds ~/ 20;
    await Future<void>.delayed(duration);
  }

  @override
  Future<void> start() async {
    _running = true;
    _timer = Timer.periodic(const Duration(milliseconds: 20), (_) {
      final frame = Int16List(kVoiceFrameSamples);
      final talking = _speechFramesLeft > 0;
      if (talking) _speechFramesLeft--;
      for (var i = 0; i < frame.length; i++) {
        final t = (_n * kVoiceFrameSamples + i) / kVoiceSampleRate;
        if (talking) {
          final env = 0.6 + 0.4 * math.sin(2 * math.pi * 3.7 * t).abs();
          frame[i] =
              (math.sin(2 * math.pi * 150 * t) * 5200 * env +
                      math.sin(2 * math.pi * 480 * t) * 2400 * env)
                  .round();
        } else {
          frame[i] = ((_rng.nextDouble() - 0.5) * 60).round();
        }
      }
      _n++;
      _frames.add(frame);
    });
  }

  @override
  Future<void> stop() async {
    _running = false;
    _timer?.cancel();
  }
}

class _DemoWake implements WakeWordDetector {
  bool _fire = false;

  void trigger() => _fire = true;

  @override
  bool process(Int16List frame) {
    if (!_fire) return false;
    _fire = false;
    return true;
  }

  @override
  void reset() {}

  @override
  Future<void> dispose() async {}
}

class _DemoOutput implements AudioOutput {
  final _level = StreamController<double>.broadcast();
  Completer<void>? _current;
  Timer? _timer;

  @override
  Stream<double> get level => _level.stream;

  @override
  Future<void> play(SynthesizedAudio audio) {
    final completer = Completer<void>();
    _current = completer;
    final started = DateTime.now();
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(milliseconds: 33), (timer) {
      final elapsed = DateTime.now().difference(started);
      final length = audio.duration ?? const Duration(seconds: 1);
      if (elapsed >= length) {
        timer.cancel();
        _level.add(0);
        if (!completer.isCompleted) completer.complete();
        return;
      }
      _level.add(levelAt(audio.envelope, audio.envelopeStep, elapsed));
    });
    return completer.future;
  }

  @override
  Future<void> stop() async {
    _timer?.cancel();
    _level.add(0);
    final c = _current;
    if (c != null && !c.isCompleted) c.complete();
  }

  @override
  Future<void> dispose() async => _level.close();
}
