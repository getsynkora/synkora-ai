// A preview with REAL speech and a stand-in backend, for an agent left on the
// default `web_speech` voice settings (so: no keys needed).
//
//   flutter run -t lib/dev/voice_live.dart
//
// The microphone, the "Hey Synkora" wake word, the phone's own speech
// recognizer and the phone's own voice are all real. Only the agent is faked:
// it answers every question with a short weather reply. Say "Hey Synkora",
// then ask something, and listen to it answer.
import 'dart:async';

import 'package:flutter/material.dart';

import '../src/services/agent_service.dart';
import '../src/theme/app_theme.dart';
import '../src/ui/voice/voice_entry_card.dart';
import '../src/ui/voice/voice_hub_scope.dart';
import '../src/ui/voice/voice_mode_screen.dart';
import '../src/voice/voice_hub.dart';
import '../src/voice/voice_settings.dart';
import '../src/voice/wake/sherpa_wake_word_detector.dart';
import 'demo_backend.dart';

void main() => runApp(
  MaterialApp(
    debugShowCheckedModeBanner: false,
    theme: buildSynkoraTheme(),
    home: const _LiveRoot(),
  ),
);

class _LiveRoot extends StatefulWidget {
  const _LiveRoot();

  @override
  State<_LiveRoot> createState() => _LiveRootState();
}

class _LiveRootState extends State<_LiveRoot> {
  VoiceHub? _hub;

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
        'stt_provider': 'web_speech',
        'tts_provider': 'web_speech',
        'language': 'en-US',
      },
    );
    final hub = VoiceHub(
      api: api,
      agentService: SynkoraAgentService(api),
      settings: settings,
      wake: SherpaWakeWordDetector(sensitivity: settings.wakeSensitivity),
    );
    hub.updateAgents(demoAgents);
    await hub.prepareDefaultAgent();
    await hub.start();
    hub.wakeEvents.listen((_) {
      if (!mounted) return;
      debugPrint('LIVE wake heard');
      // LIVE_TYPE: also type a question after waking, which exercises the
      // phone's voice without needing the recognizer.
      if (const bool.fromEnvironment('LIVE_TYPE')) {
        Future<void>.delayed(const Duration(seconds: 2), () {
          debugPrint('LIVE typing a question');
          unawaited(
            hub.conversation.sendText(
              'What is the weather like in Paris today?',
            ),
          );
        });
      }
      Navigator.of(context).push(
        VoiceModeScreen.route(
          hub: hub,
          agent: hub.conversation.agent ?? demoAgents.first,
          alreadyListening: true,
        ),
      );
    });
    hub.conversation.addListener(() {
      final c = hub.conversation;
      debugPrint(
        'LIVE phase=${c.phase.name} heard="${c.liveTranscript}" '
        'speaking="${c.speakingSentence}" error=${c.error}',
      );
    });
    if (mounted) setState(() => _hub = hub);
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
                'Say “Hey Synkora”',
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
