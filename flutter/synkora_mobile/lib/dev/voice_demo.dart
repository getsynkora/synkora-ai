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

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';

import '../src/models/synkora_models.dart';
import '../src/services/agent_service.dart';
import '../src/services/api_client.dart';
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
    final api = _DemoApi();
    final hub = VoiceHub(
      api: api,
      agentService: SynkoraAgentService(api),
      settings: settings,
      mic: _mic,
      output: _DemoOutput(),
      wake: _wake,
    );
    hub.updateAgents(_demoAgents);
    await hub.prepareDefaultAgent();
    await hub.start();
    hub.wakeEvents.listen((_) {
      if (!mounted) return;
      Navigator.of(context).push(
        VoiceModeScreen.route(
          hub: hub,
          agent: hub.conversation.agent ?? _demoAgents.first,
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

final _demoAgents = [
  _agent('muse', 'Muse', 'Your personal creative assistant'),
  _agent('grokbot', 'GrokBot', 'Fast answers and live research'),
];

AgentSummary _agent(String slug, String name, String description) =>
    AgentSummary(
      id: slug,
      name: name,
      slug: slug,
      description: description,
      agentType: 'assistant',
      avatarUrl: null,
      status: 'ACTIVE',
      category: null,
      tags: const [],
      isPublic: false,
      isSubAgent: false,
      subAgentsCount: 0,
      executionCount: 0,
      successRate: null,
      createdAt: null,
    );

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

class _DemoApi extends SynkoraApiClient {
  _DemoApi() : super(baseUrl: 'http://demo');

  int _turn = 0;

  @override
  Future<Map<String, dynamic>> getJson(
    String path, {
    Map<String, dynamic>? queryParameters,
    bool authenticated = true,
  }) async {
    if (path.endsWith('/voice/api-keys')) {
      return {
        'data': {
          'api_keys': [
            {'provider': 'openai_whisper', 'is_active': true},
            {'provider': 'openai_tts', 'is_active': true},
          ],
        },
      };
    }
    return {
      'data': {
        'id': 'muse',
        'agent_name': 'Muse',
        'slug': 'muse',
        'voice_config': {'tts_provider': 'openai_tts', 'tts_voice': 'nova'},
      },
    };
  }

  @override
  Future<Map<String, dynamic>> postJson(
    String path, {
    Object? data,
    bool authenticated = true,
    Map<String, dynamic>? headers,
  }) async => {
    'data': {
      'id': 'demo-conversation',
      'name': 'Voice chat',
      'status': 'active',
    },
  };

  @override
  Future<Map<String, dynamic>> postMultipart(
    String path, {
    required FormData data,
    Map<String, dynamic>? queryParameters,
    bool authenticated = true,
    Map<String, dynamic>? headers,
  }) async {
    debugPrint('DEMO stt call #$_turn');
    final said = _turn == 0
        ? 'What’s the weather like in Paris today?'
        : 'That’s all, thanks. Goodbye.';
    _turn++;
    return {
      'data': {'text': said},
    };
  }

  @override
  Future<Uint8List> postForBytes(
    String path, {
    required Object data,
    bool authenticated = true,
    Duration receiveTimeout = const Duration(seconds: 60),
  }) async {
    final text = (data as Map)['text'] as String;
    await Future<void>.delayed(const Duration(milliseconds: 350));
    final ms = (text.length * 62).clamp(700, 6000);
    final n = kChimeSampleRate * ms ~/ 1000;
    final samples = Int16List(n);
    for (var i = 0; i < n; i++) {
      final t = i / kChimeSampleRate;
      final syl = 0.5 + 0.5 * math.sin(2 * math.pi * 3.4 * t);
      final phrase = 0.7 + 0.3 * math.sin(2 * math.pi * 0.7 * t + 1);
      final v =
          (math.sin(2 * math.pi * 170 * t) * 0.6 +
              math.sin(2 * math.pi * 510 * t) * 0.3) *
          syl *
          phrase;
      samples[i] = (v * 9000).round();
    }
    return pcm16ToWav(samples, sampleRate: kChimeSampleRate);
  }

  @override
  Stream<ChatEvent> postEventStream(
    String path, {
    required Map<String, dynamic> data,
    bool authenticated = true,
  }) async* {
    debugPrint('DEMO agent stream: ${data['message']}');
    await Future<void>.delayed(const Duration(milliseconds: 500));
    yield const ChatEvent(
      type: 'tool_status',
      toolName: 'Checking the forecast',
      status: 'running',
    );
    await Future<void>.delayed(const Duration(milliseconds: 1800));
    for (final part in const [
      'It’s a pleasant day in Paris right now. ',
      'Around twenty-two degrees with a light breeze and mostly sunny skies. ',
      'You might want a light jacket for this evening, when it cools down to about fifteen.',
    ]) {
      yield ChatEvent(type: 'chunk', content: part);
      await Future<void>.delayed(const Duration(milliseconds: 700));
    }
    yield const ChatEvent(type: 'done');
  }
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
