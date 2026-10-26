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

Map<String, dynamic> agentDetail(String name, Map<String, dynamic> voice) => {
  'data': {
    'id': name.toLowerCase(),
    'agent_name': name,
    'slug': name.toLowerCase(),
    'voice_config': voice,
  },
};

class HubFixture {
  HubFixture._(
    this.hub,
    this.api,
    this.mic,
    this.wake,
    this.settings,
    this.output,
  );

  final VoiceHub hub;
  final RecordingApi api;
  final FakeMic mic;
  final FakeWake wake;
  final VoiceSettings settings;
  final FakeOutput output;

  static Future<HubFixture> create({
    List<String> providers = const ['openai_whisper', 'openai_tts'],
    Map<String, Object> prefs = const {},
  }) async {
    SharedPreferences.setMockInitialValues(prefs);
    final settings = await VoiceSettings.load();
    final api = RecordingApi()
      ..jsonByPath['/api/v1/voice/api-keys'] = keys(providers)
      ..jsonByPath['/api/v1/agents/muse'] = agentDetail('Muse', {
        'tts_provider': 'openai_tts',
        'tts_voice': 'shimmer',
        'language': 'en-US',
      });
    final mic = FakeMic();
    final wake = FakeWake();
    final output = FakeOutput();
    final hub = VoiceHub(
      api: api,
      agentService: SynkoraAgentService(api),
      settings: settings,
      mic: mic,
      output: output,
      wake: wake,
    );
    return HubFixture._(hub, api, mic, wake, settings, output);
  }
}
