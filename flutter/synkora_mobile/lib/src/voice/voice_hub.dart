import 'dart:async';

import 'package:flutter/widgets.dart';

import '../models/synkora_models.dart';
import '../services/agent_service.dart';
import '../services/api_client.dart';
import 'engines/backend_voice.dart';
import 'engines/device_speech.dart';
import 'engines/just_audio_output.dart';
import 'engines/record_mic.dart';
import 'engines/voice_cue_player.dart';
import 'ports.dart';
import 'voice_conversation.dart';
import 'voice_profile.dart';
import 'voice_settings.dart';

/// App-level voice service: wires the real microphone, speaker and Synkora
/// backend into one [VoiceConversation], plans each agent's voice from the
/// agent's own settings, and releases the microphone when the app goes to the
/// background.
class VoiceHub extends ChangeNotifier with WidgetsBindingObserver {
  VoiceHub({
    required SynkoraApiClient api,
    required SynkoraAgentService agentService,
    required this.settings,
    VoiceMic? mic,
    AudioOutput? output,
    LiveSpeechRecognizer? liveRecognizer,
    WakeWordDetector? wake,
    VoiceCuePlayer? cues,
  }) : _api = api,
       _agentService = agentService,
       _recognizer = BackendSpeechRecognizer(api),
       _cloudSynthesizer = BackendSpeechSynthesizer(api),
       _cues =
           cues ??
           VoiceCuePlayer(
             sounds: settings.cueSounds,
             haptics: settings.cueHaptics,
           ) {
    _synthesizer = RoutingSpeechSynthesizer(_cloudSynthesizer);
    conversation = VoiceConversation(
      mic: mic ?? RecordMic(),
      recognizer: _recognizer,
      synthesizer: _synthesizer,
      output:
          output ??
          RoutingAudioOutput(
            audio: JustAudioOutput(),
            device: DeviceSpeechOutput(),
          ),
      liveRecognizer: liveRecognizer ?? DeviceSpeechRecognizer(),
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
  final BackendSpeechSynthesizer _cloudSynthesizer;
  late final RoutingSpeechSynthesizer _synthesizer;
  final VoiceCuePlayer _cues;
  late final VoiceConversation conversation;

  List<AgentSummary> _agents = const [];
  VoiceProfile _profile = VoiceProfile.empty;

  /// Agent details (voice settings), fetched once per agent per session.
  final Map<String, AgentSummary> _details = {};

  /// Agents the user chose to talk to with the phone's built-in voice even
  /// though they are set to a paid provider with no key.
  final Set<String> _useBuiltIn = {};

  VoiceCapabilities? _capabilities;
  DateTime? _capabilitiesLoadedAt;

  List<AgentSummary> get agents => _agents;

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

  /// Why the current agent cannot be spoken to yet, with the way to fix it.
  VoiceIssue? get issue => _profile.issue;

  /// Opens a spoken conversation with [agent] and starts listening.
  Future<void> open(AgentSummary agent, {String? conversationId}) async {
    unawaited(settings.setLastAgentId(agent.id));
    await _applyProfile(agent);
    final problem = _profile.issue;
    if (problem != null) {
      await conversation.switchAgent(agent);
      conversation.reportProblem(problem.message);
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

  /// Fixes the current [issue] with one tap, then starts the conversation:
  /// turns voice on for the agent, or continues with the phone's own voice.
  Future<void> resolveIssue() async {
    final agent = conversation.agent;
    final problem = _profile.issue;
    if (agent == null || problem == null) return;
    switch (problem.kind) {
      case VoiceIssueKind.voiceDisabled:
        try {
          await _agentService.setVoiceEnabled(agent.slug, true);
        } catch (_) {
          conversation.reportProblem(
            'Could not turn voice on for ${agent.name}. Only its owner can; '
            'open Voice settings on the web to enable it.',
          );
          return;
        }
        _details[agent.id] = (_details[agent.id] ?? agent).withVoice(
          voiceEnabled: true,
        );
      case VoiceIssueKind.missingKey:
        _useBuiltIn.add(agent.id);
    }
    await _applyProfile(agent);
    if (_profile.issue == null) {
      await conversation.begin(agent: agent);
    }
  }

  /// Loads which paid speech providers the workspace has keys for (cached).
  Future<VoiceCapabilities?> _loadCapabilities() async {
    final loadedAt = _capabilitiesLoadedAt;
    if (_capabilities != null &&
        loadedAt != null &&
        DateTime.now().difference(loadedAt) < const Duration(minutes: 1)) {
      return _capabilities;
    }
    try {
      _capabilities = await loadVoiceCapabilities(_api);
      _capabilitiesLoadedAt = DateTime.now();
    } catch (_) {
      // Unknown: stay optimistic and let a real request report any problem.
      _capabilities = null;
    }
    return _capabilities;
  }

  /// The voice profile currently in use (exposed for tests).
  @visibleForTesting
  VoiceProfile get activeProfile => _profile;

  /// Plans how to hear and speak to [agent] from the agent's own settings.
  Future<void> _applyProfile(AgentSummary agent) async {
    var detailed = _details[agent.id];
    if (detailed == null) {
      try {
        // The agent list does not carry voice settings; the detail does.
        detailed = await _agentService.getAgent(agent.slug);
        _details[agent.id] = detailed;
      } catch (_) {
        detailed = agent;
      }
    }

    final builtIn = _useBuiltIn.contains(agent.id);
    final names = [for (final a in _agents) a.name];
    var profile = VoiceProfile.resolve(
      detailed,
      speed: settings.speed,
      knownNames: names,
      useBuiltIn: builtIn,
    );
    // Only agents on a paid provider need to know what the workspace has.
    if (profile.usesCloud && profile.issue == null) {
      profile = VoiceProfile.resolve(
        detailed,
        capabilities: await _loadCapabilities(),
        speed: settings.speed,
        knownNames: names,
        useBuiltIn: builtIn,
      );
    }

    _profile = profile;
    _recognizer.profile = profile;
    _cloudSynthesizer.profile = profile;
    _synthesizer.profile = profile;
    conversation.deviceLocale = profile.locale;
    conversation.useDeviceListening = profile.listen == SpeechSource.device;
    notifyListeners();
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
