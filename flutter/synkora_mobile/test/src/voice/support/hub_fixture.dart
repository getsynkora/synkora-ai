import 'package:shared_preferences/shared_preferences.dart';
import 'package:synkora_mobile/src/services/agent_service.dart';
import 'package:synkora_mobile/src/voice/voice_hub.dart';
import 'package:synkora_mobile/src/voice/voice_settings.dart';

import 'fake_api.dart';
import 'fakes.dart';

Map<String, dynamic> keys(List<String> providers) => {
  'data': {
    'api_keys': [
      for (final p in providers) {'provider': p, 'is_active': true},
    ],
  },
};

Map<String, dynamic> agentDetail(
  String name,
  Map<String, dynamic> voice, {
  bool enabled = true,
}) => {
  'data': {
    'id': name.toLowerCase(),
    'agent_name': name,
    'slug': name.toLowerCase(),
    'voice_enabled': enabled,
    'voice_config': voice,
  },
};

/// A cloud-voice agent: Whisper to listen, OpenAI to speak.
const cloudVoice = {
  'stt_provider': 'openai_whisper',
  'tts_provider': 'openai_tts',
  'tts_voice': 'shimmer',
  'language': 'en-US',
};

/// The default `web_speech` settings: the phone's own voice, no keys.
const builtInVoice = {
  'stt_provider': 'web_speech',
  'tts_provider': 'web_speech',
  'language': 'en-US',
};

class HubFixture {
  HubFixture._(
    this.hub,
    this.api,
    this.mic,
    this.wake,
    this.settings,
    this.output,
    this.live,
  );

  final VoiceHub hub;
  final RecordingApi api;
  final FakeMic mic;
  final FakeWake wake;
  final VoiceSettings settings;
  final FakeOutput output;
  final FakeLive live;

  static Future<HubFixture> create({
    List<String> providers = const ['openai_whisper', 'openai_tts'],
    Map<String, Object> prefs = const {},
    Map<String, dynamic> agentVoice = cloudVoice,
    bool voiceEnabled = true,
  }) async {
    SharedPreferences.setMockInitialValues(prefs);
    final settings = await VoiceSettings.load();
    final api = RecordingApi()
      ..jsonByPath['/api/v1/voice/api-keys'] = keys(providers)
      ..jsonByPath['/api/v1/agents/muse'] = agentDetail(
        'Muse',
        agentVoice,
        enabled: voiceEnabled,
      );
    final mic = FakeMic();
    final wake = FakeWake();
    final output = FakeOutput();
    final live = FakeLive();
    final hub = VoiceHub(
      api: api,
      agentService: SynkoraAgentService(api),
      settings: settings,
      mic: mic,
      output: output,
      liveRecognizer: live,
      wake: wake,
    );
    return HubFixture._(hub, api, mic, wake, settings, output, live);
  }
}
