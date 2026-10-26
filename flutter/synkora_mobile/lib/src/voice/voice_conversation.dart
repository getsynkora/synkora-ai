import 'dart:async';
import 'dart:collection';
import 'dart:typed_data';

import 'package:flutter/foundation.dart';

import '../models/synkora_models.dart';
import 'audio/pcm.dart';
import 'audio/vad.dart';
import 'ports.dart';
import 'text/speech_text.dart';
import 'voice_commands.dart';

enum VoicePhase {
  /// Microphone closed; nothing is happening.
  idle,

  /// Microphone open, waiting for the wake phrase (or a tap).
  armed,

  /// Waiting for / recording the user's turn.
  listening,

  /// Transcribing and waiting for the agent to start answering.
  thinking,

  /// The agent's reply is being spoken.
  speaking,

  /// Something went wrong that needs the user's attention.
  error,
}

/// Short audible/haptic moments the UI layer may want to mark.
enum VoiceCue { wake, listening, sent, error, ended }

class VoiceTurn {
  VoiceTurn({
    required this.isUser,
    required this.text,
    this.interrupted = false,
  }) : at = DateTime.now();

  final bool isUser;
  String text;
  bool interrupted;
  final DateTime at;
}

class VoiceConversationConfig {
  const VoiceConversationConfig({
    this.firstListenTimeout = const Duration(seconds: 10),
    this.followUpTimeout = const Duration(seconds: 9),
    this.turnEndpoint = const EndpointConfig(noSpeechTimeoutMs: 0),
    this.bargeInEndpoint = const EndpointConfig.bargeIn(),
    this.bargeInEnabled = true,
    this.maxSynthesisInFlight = 3,
    this.thinkingHintAfter = const Duration(seconds: 3),
    this.language,
  });

  /// How long to wait for the first words after the session opens or wakes.
  final Duration firstListenTimeout;

  /// How long to wait for a follow-up before going back to sleep.
  final Duration followUpTimeout;
  final EndpointConfig turnEndpoint;
  final EndpointConfig bargeInEndpoint;
  final bool bargeInEnabled;

  /// Sentences synthesized ahead of playback, to hide network latency.
  final int maxSynthesisInFlight;
  final Duration thinkingHintAfter;
  final String? language;
}

class _SpeechJob {
  _SpeechJob(this.text);

  final String text;
  final Completer<SynthesizedAudio?> audio = Completer();
  bool started = false;
}

/// Runs a hands-free spoken conversation with an agent.
///
/// It owns the turn-taking loop: listen (with end-of-speech detection),
/// transcribe, stream the agent's reply, speak it sentence by sentence while
/// the next sentences are still being synthesized, and let the user interrupt
/// at any time just by talking.
///
/// All hardware and network access goes through the interfaces in
/// `ports.dart`, so the whole loop is testable without audio devices.
class VoiceConversation extends ChangeNotifier {
  VoiceConversation({
    required this.mic,
    required this.recognizer,
    required this.synthesizer,
    required this.output,
    required this.gateway,
    this.wake,
    this.config = const VoiceConversationConfig(),
    this.onCue,
    this.agentsProvider,
  }) : _turnEndpointer = TurnEndpointer(config.turnEndpoint),
       _bargeInEndpointer = TurnEndpointer(config.bargeInEndpoint) {
    _outputLevelSub = output.level.listen((level) {
      outputLevel.value = _smooth(outputLevel.value, level, 0.5);
    });
  }

  final VoiceMic mic;
  final SpeechRecognizer recognizer;
  final SpeechSynthesizer synthesizer;
  final AudioOutput output;
  final VoiceAgentGateway gateway;
  final WakeWordDetector? wake;
  final VoiceConversationConfig config;
  final void Function(VoiceCue cue)? onCue;
  final List<AgentSummary> Function()? agentsProvider;

  /// 0..1 microphone loudness, for the UI. Separate notifiers so meters can
  /// repaint at audio rate without rebuilding the whole screen.
  final ValueNotifier<double> inputLevel = ValueNotifier(0);

  /// 0..1 loudness of what the assistant is currently saying.
  final ValueNotifier<double> outputLevel = ValueNotifier(0);

  final TurnEndpointer _turnEndpointer;
  final TurnEndpointer _bargeInEndpointer;
  final List<VoiceTurn> _turns = [];
  final Queue<_SpeechJob> _speechQueue = Queue();
  final SentenceChunker _chunker = SentenceChunker();

  StreamSubscription<Int16List>? _micSub;
  StreamSubscription<double>? _outputLevelSub;
  StreamSubscription<ChatEvent>? _agentSub;
  Timer? _listenTimer;
  Timer? _thinkingHintTimer;
  Completer<void>? _loopWake;

  VoicePhase _phase = VoicePhase.idle;
  AgentSummary? _agent;
  String? _conversationId;
  String _liveReply = '';
  String _lastReply = '';
  String _speaking = '';
  String _spokenText = '';
  String? _status;
  String? _error;
  bool _muted = false;
  bool _wakeEnabled = false;
  bool _agentDone = false;
  int _loopRun = -1;
  bool _spokeAnything = false;
  bool _disposed = false;
  int _run = 0;
  int _synthInFlight = 0;

  VoicePhase get phase => _phase;
  AgentSummary? get agent => _agent;
  String? get conversationId => _conversationId;
  List<VoiceTurn> get turns => List.unmodifiable(_turns);

  /// What the agent has said so far this turn, as speakable text (the whole
  /// reply received so far, not only the part already spoken).
  String get liveReply => toSpeakable(_liveReply);

  /// The part of the reply that has been spoken or is being spoken.
  String get spokenText => _spokenText;

  /// The sentence being spoken right now.
  String get speakingSentence => _speaking;

  /// Short status such as a tool the agent is running.
  String? get status => _status;
  String? get error => _error;
  bool get muted => _muted;
  bool get wakeEnabled => _wakeEnabled;
  bool get userSpeaking =>
      _phase == VoicePhase.listening && _turnEndpointer.inSpeech;

  /// True while a conversation is in progress (as opposed to idle/armed).
  bool get sessionActive =>
      _phase == VoicePhase.listening ||
      _phase == VoicePhase.thinking ||
      _phase == VoicePhase.speaking ||
      _phase == VoicePhase.error;

  /// Fires each time the wake phrase is heard.
  Stream<void> get wakeEvents => _wakeEvents.stream;
  final StreamController<void> _wakeEvents = StreamController.broadcast();

  // ---------------------------------------------------------------------------
  // Lifecycle
  // ---------------------------------------------------------------------------

  /// Starts (or stops) listening for the wake phrase in the background.
  Future<void> setWakeEnabled(bool enabled) async {
    _wakeEnabled = enabled && wake != null;
    if (_wakeEnabled) {
      if (_phase == VoicePhase.idle) await arm();
    } else if (_phase == VoicePhase.armed) {
      await _closeMic();
      _setPhase(VoicePhase.idle);
    }
    notifyListeners();
  }

  /// Opens the mic and waits for the wake phrase.
  Future<void> arm() async {
    if (!_wakeEnabled || wake == null || sessionActive) return;
    try {
      await _openMic();
    } catch (e) {
      _fail(_describe(e), fatal: false);
      return;
    }
    wake!.reset();
    _setPhase(VoicePhase.armed);
  }

  /// Starts talking now (screen opened, orb tapped, or wake phrase heard).
  Future<void> begin({AgentSummary? agent, String? conversationId}) async {
    if (agent != null && agent.id != _agent?.id) {
      _agent = agent;
      _conversationId = conversationId;
      _turns.clear();
    } else if (conversationId != null) {
      _conversationId = conversationId;
    }
    if (sessionActive && _phase != VoicePhase.error) return;
    _error = null;
    try {
      await _openMic();
    } catch (e) {
      _fail(_describe(e), fatal: true);
      return;
    }
    _turnEndpointer.reset();
    _bargeInEndpointer.reset();
    _setPhase(VoicePhase.listening);
    _startListenTimeout(config.firstListenTimeout);
    onCue?.call(VoiceCue.listening);
  }

  /// Leaves the conversation. Returns to wake listening if enabled, otherwise
  /// closes the microphone.
  Future<void> end({bool cue = false}) async {
    _cancelRun();
    _cancelListenTimeout();
    _liveReply = '';
    _speaking = '';
    _status = null;
    _error = null;
    if (cue) onCue?.call(VoiceCue.ended);
    if (_wakeEnabled && wake != null && !_disposed) {
      wake!.reset();
      _setPhase(VoicePhase.armed);
    } else {
      await _closeMic();
      _setPhase(VoicePhase.idle);
    }
  }

  void toggleMute() {
    _muted = !_muted;
    if (_muted) inputLevel.value = 0;
    notifyListeners();
  }

  /// Switches the agent being talked to and starts a fresh conversation.
  Future<void> switchAgent(AgentSummary agent) async {
    if (agent.id == _agent?.id) return;
    _cancelRun();
    _agent = agent;
    _conversationId = null;
    _turns.clear();
    _liveReply = '';
    _spokenText = '';
    _lastReply = '';
    notifyListeners();
  }

  /// Handles a tap on the orb: interrupt the agent, finish the user's
  /// utterance early, or wake the assistant.
  void interrupt() {
    switch (_phase) {
      case VoicePhase.speaking:
      case VoicePhase.thinking:
        _markLastAgentInterrupted();
        _cancelRun();
        _resumeListening();
      case VoicePhase.listening:
        if (_turnEndpointer.inSpeech) {
          final taken = _turnEndpointer.takeInProgress();
          if (taken.speechMs >= config.turnEndpoint.minSpeechMs) {
            unawaited(
              _runTurn(taken.audio, Duration(milliseconds: taken.speechMs)),
            );
          }
        }
      case VoicePhase.armed:
      case VoicePhase.idle:
      case VoicePhase.error:
        unawaited(begin());
    }
  }

  /// Sends typed text as the user's turn (keyboard fallback).
  Future<void> sendText(String text) async {
    final trimmed = text.trim();
    if (trimmed.isEmpty) return;
    if (!sessionActive || _phase == VoicePhase.error) {
      await begin();
    }
    _cancelListenTimeout();
    final run = _cancelRun();
    _setPhase(VoicePhase.thinking);
    _addTurn(isUser: true, text: trimmed);
    await _converse(trimmed, run);
  }

  @override
  void dispose() {
    _disposed = true;
    _cancelRun();
    _cancelListenTimeout();
    _outputLevelSub?.cancel();
    _micSub?.cancel();
    unawaited(mic.stop());
    unawaited(wake?.dispose());
    unawaited(output.dispose());
    _wakeEvents.close();
    inputLevel.dispose();
    outputLevel.dispose();
    super.dispose();
  }

  // ---------------------------------------------------------------------------
  // Microphone frames
  // ---------------------------------------------------------------------------

  Future<void> _openMic() async {
    if (!mic.isRunning) await mic.start();
    _micSub ??= mic.frames.listen(
      _onFrame,
      onError: (Object e) {
        _fail(_describe(e), fatal: true);
      },
    );
  }

  Future<void> _closeMic() async {
    // Not awaited: cancelling only detaches our listener, nothing depends on it.
    unawaited(_micSub?.cancel());
    _micSub = null;
    if (mic.isRunning) await mic.stop();
    inputLevel.value = 0;
  }

  void _onFrame(Int16List frame) {
    if (_disposed) return;
    if (!_muted) {
      inputLevel.value = _smooth(
        inputLevel.value,
        dbToLevel(frameDb(frame)),
        0.4,
      );
    }
    if (_muted) return;

    switch (_phase) {
      case VoicePhase.armed:
        if (wake?.process(frame) ?? false) _onWakeHeard();
      case VoicePhase.listening:
        _feedListening(frame);
      case VoicePhase.thinking:
      case VoicePhase.speaking:
        _feedBargeIn(frame);
      case VoicePhase.idle:
      case VoicePhase.error:
        break;
    }
  }

  void _onWakeHeard() {
    onCue?.call(VoiceCue.wake);
    if (!_wakeEvents.isClosed) _wakeEvents.add(null);
    unawaited(begin());
  }

  void _feedListening(Int16List frame) {
    final event = _turnEndpointer.feed(frame);
    if (event == null) return;
    switch (event.type) {
      case EndpointEventType.speechStart:
        _cancelListenTimeout();
        notifyListeners();
      case EndpointEventType.speechEnd:
      case EndpointEventType.maxLength:
        unawaited(_runTurn(event.audio!, event.speechDuration!));
      case EndpointEventType.noSpeech:
        break;
    }
  }

  void _feedBargeIn(Int16List frame) {
    if (!config.bargeInEnabled) return;
    // While audio is audible, require speech to stand clearly above it.
    final playback = outputLevel.value;
    final extra = playback > 0.03 ? (playback * 50 - 60) - 12 : null;
    final event = _bargeInEndpointer.feed(frame, extraThresholdDb: extra);
    if (event?.type != EndpointEventType.speechStart) return;

    final carried = _bargeInEndpointer.takeInProgress();
    _markLastAgentInterrupted();
    _cancelRun();
    _turnEndpointer.reset();
    _turnEndpointer.adoptInProgress(carried.audio, speechMs: carried.speechMs);
    _setPhase(VoicePhase.listening);
  }

  // ---------------------------------------------------------------------------
  // One turn: transcribe -> agent -> speech
  // ---------------------------------------------------------------------------

  Future<void> _runTurn(Int16List audio, Duration speechDuration) async {
    final run = _cancelRun();
    _cancelListenTimeout();
    _setPhase(VoicePhase.thinking);
    onCue?.call(VoiceCue.sent);

    String text;
    try {
      text = await recognizer.transcribe(
        pcm16ToWav(audio),
        language: config.language,
      );
    } on VoiceUnavailableException catch (e) {
      if (_isCurrent(run)) _fail(e.message, fatal: true);
      return;
    } catch (_) {
      if (!_isCurrent(run)) return;
      _status = "Sorry, I didn't catch that.";
      _resumeListening();
      return;
    }
    if (!_isCurrent(run)) return;

    text = text.trim();
    if (isLikelyTranscriptionHallucination(
      text,
      speechDuration: speechDuration,
    )) {
      _resumeListening();
      return;
    }

    final command = parseVoiceCommand(text);
    if (command != null && await _handleCommand(command, text, run)) return;
    if (!_isCurrent(run)) return;

    _addTurn(isUser: true, text: text);
    await _converse(text, run);
  }

  /// Returns true if the command consumed the utterance.
  Future<bool> _handleCommand(
    VoiceCommand command,
    String text,
    int run,
  ) async {
    switch (command) {
      case EndSessionCommand():
        _addTurn(isUser: true, text: text);
        await end(cue: true);
        return true;
      case CancelCommand():
        _resumeListening();
        return true;
      case RepeatCommand():
        if (_lastReply.isEmpty) {
          _resumeListening();
        } else {
          _speakOnly(_lastReply, run);
        }
        return true;
      case SwitchAgentCommand():
        final candidates = agentsProvider?.call() ?? const <AgentSummary>[];
        final match = matchAgentByName<AgentSummary>(
          command.agentName,
          candidates,
          (a) => a.name,
        );
        if (match == null) {
          if (!command.explicit) return false;
          _speakOnly(
            "I couldn't find an agent called ${command.agentName}.",
            run,
          );
          return true;
        }
        await switchAgent(match);
        final next = _cancelRun();
        _setPhase(VoicePhase.thinking);
        _speakOnly("Okay, you're now talking to ${match.name}.", next);
        return true;
    }
  }

  Future<void> _converse(String text, int run) async {
    final agent = _agent;
    if (agent == null) {
      _fail('No agent selected.', fatal: true);
      return;
    }
    _beginReply();
    _thinkingHintTimer = Timer(config.thinkingHintAfter, () {
      if (_isCurrent(run) && _phase == VoicePhase.thinking && _status == null) {
        _status = 'Still working on it…';
        notifyListeners();
      }
    });

    try {
      _conversationId ??= await gateway.createConversation(
        agent,
        name: 'Voice chat',
      );
    } catch (e) {
      if (_isCurrent(run)) _failTurn(_describe(e), run);
      return;
    }
    if (!_isCurrent(run)) return;

    final stream = gateway.stream(
      agent: agent,
      message: text,
      conversationId: _conversationId!,
    );
    _agentSub = stream.listen(
      (event) => _onAgentEvent(event, run),
      onError: (Object e) {
        if (_isCurrent(run)) _failTurn(_describe(e), run);
      },
      onDone: () {
        if (_isCurrent(run)) _finishAgentStream(run);
      },
      cancelOnError: true,
    );
    unawaited(_playLoop(run));
  }

  void _onAgentEvent(ChatEvent event, int run) {
    if (!_isCurrent(run)) return;
    switch (event.type) {
      case 'chunk':
        final delta = event.content ?? '';
        if (delta.isEmpty) return;
        _liveReply += delta;
        for (final sentence in _chunker.add(delta)) {
          _enqueueSpeech(sentence, run);
        }
        notifyListeners();
      case 'tool_status':
        final tool = event.toolName;
        final state = event.status;
        _status = [tool, state].whereType<String>().join(' · ');
        notifyListeners();
      case 'done':
        _finishAgentStream(run);
      case 'error':
        _failTurn(event.error ?? 'The agent ran into a problem.', run);
    }
  }

  void _finishAgentStream(int run) {
    if (!_isCurrent(run) || _agentDone) return;
    for (final sentence in _chunker.flush()) {
      _enqueueSpeech(sentence, run);
    }
    if (_liveReply.trim().isNotEmpty &&
        !_spokeAnything &&
        _speechQueue.isEmpty) {
      // The reply had nothing speakable (for example only code or a table).
      _enqueueSpeech("I've put the details in the chat.", run);
    }
    if (_liveReply.trim().isEmpty && !_spokeAnything) {
      _status = "I didn't get a response.";
    }
    _agentDone = true;
    _wakePlayLoop();
  }

  void _beginReply() {
    _chunker.reset();
    _speechQueue.clear();
    _synthInFlight = 0;
    _liveReply = '';
    _speaking = '';
    _spokenText = '';
    _status = null;
    _agentDone = false;
    _spokeAnything = false;
    notifyListeners();
  }

  // ---------------------------------------------------------------------------
  // Speech output
  // ---------------------------------------------------------------------------

  /// Speaks a fixed line (no agent call) and then resumes listening.
  void _speakOnly(String text, int run) {
    _beginReply();
    _liveReply = text;
    _enqueueSpeech(text, run);
    _agentDone = true;
    _setPhase(VoicePhase.thinking);
    unawaited(_playLoop(run));
  }

  void _enqueueSpeech(String text, int run) {
    final job = _SpeechJob(text);
    _speechQueue.add(job);
    _pumpSynthesis(run);
    _wakePlayLoop();
  }

  void _pumpSynthesis(int run) {
    if (!_isCurrent(run)) return;
    for (final job in _speechQueue) {
      if (_synthInFlight >= config.maxSynthesisInFlight) return;
      if (job.started) continue;
      job.started = true;
      _synthInFlight++;
      unawaited(_synthesize(job, run));
    }
  }

  Future<void> _synthesize(_SpeechJob job, int run) async {
    SynthesizedAudio? result;
    try {
      result = await synthesizer.synthesize(
        job.text,
        language: config.language,
      );
    } on VoiceUnavailableException catch (e) {
      if (_isCurrent(run)) _fail(e.message, fatal: true);
    } catch (_) {
      result = null;
    } finally {
      _synthInFlight--;
    }
    if (!job.audio.isCompleted) job.audio.complete(result);
    _pumpSynthesis(run);
  }

  void _wakePlayLoop() {
    final waiter = _loopWake;
    if (waiter != null && !waiter.isCompleted) waiter.complete();
  }

  Future<void> _playLoop(int run) async {
    // One loop per run. A previous run's loop may still be unwinding after an
    // interruption; it must not stop this one from starting.
    if (_loopRun == run) return;
    _loopRun = run;
    {
      while (_isCurrent(run)) {
        if (_speechQueue.isEmpty) {
          if (_agentDone) break;
          _loopWake = Completer<void>();
          await _loopWake!.future;
          continue;
        }
        final job = _speechQueue.removeFirst();
        _pumpSynthesis(run);
        final audio = await job.audio.future;
        if (!_isCurrent(run)) return;
        if (audio == null) continue;

        if (_phase != VoicePhase.speaking) {
          _thinkingHintTimer?.cancel();
          _status = null;
          _setPhase(VoicePhase.speaking);
          _bargeInEndpointer.reset();
        }
        _spokeAnything = true;
        _speaking = job.text;
        _spokenText = _spokenText.isEmpty
            ? job.text
            : '$_spokenText ${job.text}';
        notifyListeners();
        await output.play(audio);
      }
    }
    if (_isCurrent(run)) _completeTurn(run);
  }

  void _completeTurn(int run) {
    if (!_isCurrent(run)) return;
    _thinkingHintTimer?.cancel();
    final reply = toSpeakable(_liveReply);
    if (reply.isNotEmpty) {
      _lastReply = reply;
      _addTurn(isUser: false, text: reply);
    }
    _speaking = '';
    _resumeListening();
  }

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  void _resumeListening() {
    _turnEndpointer.reset();
    _setPhase(VoicePhase.listening);
    _startListenTimeout(config.followUpTimeout);
  }

  void _startListenTimeout(Duration timeout) {
    _cancelListenTimeout();
    _listenTimer = Timer(timeout, () {
      if (_phase == VoicePhase.listening && !_turnEndpointer.inSpeech) {
        unawaited(end(cue: true));
      }
    });
  }

  void _cancelListenTimeout() {
    _listenTimer?.cancel();
    _listenTimer = null;
  }

  /// Invalidates everything in flight and returns the id of the new run.
  int _cancelRun() {
    _run++;
    _thinkingHintTimer?.cancel();
    final sub = _agentSub;
    _agentSub = null;
    unawaited(sub?.cancel());
    _speechQueue.clear();
    _synthInFlight = 0;
    _agentDone = true;
    _wakePlayLoop();
    unawaited(output.stop());
    return _run;
  }

  bool _isCurrent(int run) => run == _run && !_disposed;

  void _markLastAgentInterrupted() {
    if (_phase == VoicePhase.speaking && _spokenText.isNotEmpty) {
      // Keep only what was actually said so far in the transcript.
      _lastReply = toSpeakable(_liveReply);
      _addTurn(isUser: false, text: _spokenText, interrupted: true);
      _liveReply = '';
      _spokenText = '';
      _speaking = '';
    }
  }

  void _addTurn({
    required bool isUser,
    required String text,
    bool interrupted = false,
  }) {
    _turns.add(VoiceTurn(isUser: isUser, text: text, interrupted: interrupted));
    notifyListeners();
  }

  void _failTurn(String message, int run) {
    if (!_isCurrent(run)) return;
    _cancelRun();
    onCue?.call(VoiceCue.error);
    _status = message;
    _resumeListening();
  }

  void _fail(String message, {required bool fatal}) {
    _error = message;
    onCue?.call(VoiceCue.error);
    if (fatal) {
      _cancelRun();
      _cancelListenTimeout();
      _setPhase(VoicePhase.error);
    } else {
      notifyListeners();
    }
  }

  String _describe(Object e) => e.toString().replaceFirst('Exception: ', '');

  void _setPhase(VoicePhase phase) {
    if (_phase == phase && phase != VoicePhase.error) {
      notifyListeners();
      return;
    }
    _phase = phase;
    if (phase != VoicePhase.error) _error = null;
    notifyListeners();
  }

  static double _smooth(double previous, double next, double rise) {
    // Fast attack, slower release, so meters feel natural.
    final alpha = next > previous ? rise : rise * 0.4;
    return previous + (next - previous) * alpha;
  }

  @override
  void notifyListeners() {
    if (!_disposed) super.notifyListeners();
  }
}
