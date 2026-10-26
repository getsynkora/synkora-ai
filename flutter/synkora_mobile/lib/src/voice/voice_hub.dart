import 'dart:async';

import 'package:flutter/widgets.dart';

import '../models/synkora_models.dart';
import '../services/agent_service.dart';
import '../services/api_client.dart';
import 'engines/backend_voice.dart';
import 'engines/just_audio_output.dart';
import 'engines/record_mic.dart';
import 'engines/voice_cue_player.dart';
import 'ports.dart';
import 'voice_conversation.dart';
import 'voice_settings.dart';

/// App-level voice service: wires the real microphone, speaker and Synkora
/// backend into one [VoiceConversation], keeps each agent's voice profile in
/// sync, and releases the microphone when the app goes to the background.
class VoiceHub extends ChangeNotifier with WidgetsBindingObserver {
  VoiceHub({
    required SynkoraApiClient api,
    required SynkoraAgentService agentService,
    required this.settings,
    VoiceMic? mic,
    AudioOutput? output,
    WakeWordDetector? wake,
    VoiceCuePlayer? cues,
  }) : _api = api,
       _agentService = agentService,
       _recognizer = BackendSpeechRecognizer(api),
       _synthesizer = BackendSpeechSynthesizer(api),
       _cues =
           cues ??
           VoiceCuePlayer(
             sounds: settings.cueSounds,
             haptics: settings.cueHaptics,
           ) {
    conversation = VoiceConversation(
      mic: mic ?? RecordMic(),
      recognizer: _recognizer,
      synthesizer: _synthesizer,
      output: output ?? JustAudioOutput(),
      gateway: ServiceVoiceAgentGateway(agentService),
      wake: wake,
      config: VoiceConversationConfig(bargeInEnabled: settings.bargeIn),
      onCue: _cues.cue,
      agentsProvider: () => _agents,
      prepareAgent: _applyProfile,
    );
    _applyWakeSensitivity();
    settings.addListener(_onSettingsChanged);
    WidgetsBinding.instance.addObserver(this);
  }

  /// Whether a wake-phrase engine is available on this device.
  bool get wakeSupported => conversation.wake != null;

  /// Why "Hey Synkora" cannot work right now, or null if it can.
  String? get wakeProblem {
    final wake = conversation.wake;
    return wake is WakeWordStatus ? (wake as WakeWordStatus).failure : null;
  }

  final SynkoraApiClient _api;
  final SynkoraAgentService _agentService;
  final VoiceSettings settings;
  final BackendSpeechRecognizer _recognizer;
  final BackendSpeechSynthesizer _synthesizer;
  final VoiceCuePlayer _cues;
  late final VoiceConversation conversation;

  List<AgentSummary> _agents = const [];
  VoiceCapabilities _capabilities = const VoiceCapabilities.none();
  bool _capabilitiesKnown = false;
  DateTime? _capabilitiesLoadedAt;

  List<AgentSummary> get agents => _agents;
  VoiceCapabilities get capabilities => _capabilities;

  /// Fires when the wake phrase is heard; the UI opens the voice screen.
  Stream<void> get wakeEvents => conversation.wakeEvents;

  /// Tells the hub which agents exist (for "switch to Muse" and the picker).
  void updateAgents(List<AgentSummary> agents) {
    _agents = List.unmodifiable(agents);
    notifyListeners();
  }

  /// The agent that answers when the wake phrase is heard from anywhere.
  AgentSummary? get defaultAgent {
    final id = settings.lastAgentId;
    for (final agent in _agents) {
      if (agent.id == id) return agent;
    }
    return _agents.isEmpty ? null : _agents.first;
  }

  /// Chooses the agent to answer a wake phrase, without starting to listen.
  Future<void> prepareDefaultAgent() async {
    final agent = defaultAgent;
    if (agent == null || conversation.sessionActive) return;
    await conversation.switchAgent(agent);
  }

  /// Loads which speech providers the workspace has (cached for a minute).
  Future<void> ensureCapabilities({bool force = false}) async {
    final loadedAt = _capabilitiesLoadedAt;
    if (!force &&
        _capabilitiesKnown &&
        loadedAt != null &&
        DateTime.now().difference(loadedAt) < const Duration(minutes: 1)) {
      return;
    }
    try {
      _capabilities = await VoiceCapabilities.load(_api);
      _capabilitiesKnown = true;
      _capabilitiesLoadedAt = DateTime.now();
      notifyListeners();
    } catch (_) {
      // Unknown: stay optimistic and let a real request report any problem.
      _capabilitiesKnown = false;
    }
  }

  /// Why voice cannot work right now, or null.
  String? get setupProblem => _capabilitiesKnown ? _capabilities.problem : null;

  /// Opens a spoken conversation with [agent] and starts listening.
  Future<void> open(AgentSummary agent, {String? conversationId}) async {
    unawaited(settings.setLastAgentId(agent.id));
    await ensureCapabilities();
    final problem = setupProblem;
    if (problem != null) {
      await conversation.switchAgent(agent);
      conversation.reportProblem(problem);
      return;
    }
    await conversation.begin(agent: agent, conversationId: conversationId);
  }

  Future<void> switchAgent(AgentSummary agent) async {
    unawaited(settings.setLastAgentId(agent.id));
    await conversation.switchAgent(agent);
  }

  /// Ends the session; returns to wake listening if enabled.
  Future<void> close() => conversation.end();

  /// The voice profile currently in use (exposed for tests).
  @visibleForTesting
  VoiceProfile get activeProfile => _synthesizer.profile;

  Future<void> _applyProfile(AgentSummary agent) async {
    // The profile depends on which providers the workspace has, so make sure
    // that is known first (cached). Hands-free wake reaches here without ever
    // going through open().
    await ensureCapabilities();
    var detailed = agent;
    if (agent.voiceConfig.isEmpty) {
      try {
        detailed = await _agentService.getAgent(agent.slug);
      } catch (_) {
        // The list entry is enough to talk; only the custom voice is lost.
      }
    }
    final profile = VoiceProfile.resolve(
      detailed,
      _capabilities,
      speed: settings.speed,
      knownNames: [for (final a in _agents) a.name],
    );
    _recognizer.profile = profile;
    _synthesizer.profile = profile;
  }

  void _onSettingsChanged() {
    _cues
      ..sounds = settings.cueSounds
      ..haptics = settings.cueHaptics;
    conversation.bargeInEnabled = settings.bargeIn;
    _applyWakeSensitivity();
    _prepareWake();
    unawaited(conversation.setWakeEnabled(settings.wakeEnabled));
    final agent = conversation.agent;
    if (agent != null) unawaited(_applyProfile(agent));
  }

  /// Loads the wake model right away so any problem is known (and shown) up
  /// front, instead of surfacing only after the first sound.
  void _prepareWake() {
    final wake = conversation.wake;
    if (wake is! WakeWordStatus || !settings.wakeEnabled) return;
    unawaited((wake as WakeWordStatus).start().whenComplete(notifyListeners));
  }

  void _applyWakeSensitivity() {
    final wake = conversation.wake;
    if (wake is WakeSensitivityControl) {
      (wake as WakeSensitivityControl).sensitivity = settings.wakeSensitivity;
    }
  }

  /// Applies saved settings; call once after construction.
  Future<void> start() async {
    unawaited(ensureCapabilities());
    _prepareWake();
    await conversation.setWakeEnabled(settings.wakeEnabled);
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    switch (state) {
      case AppLifecycleState.resumed:
        unawaited(conversation.resume());
      case AppLifecycleState.paused:
      case AppLifecycleState.hidden:
        // Mobile OSes do not allow always-on listening from a suspended app.
        unawaited(conversation.suspend());
      case AppLifecycleState.inactive:
      case AppLifecycleState.detached:
        break;
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    settings.removeListener(_onSettingsChanged);
    conversation.dispose();
    unawaited(_cues.dispose());
    super.dispose();
  }
}
