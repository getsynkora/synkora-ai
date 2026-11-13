import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:wakelock_plus/wakelock_plus.dart';

import '../../models/synkora_models.dart';
import '../../voice/voice_conversation.dart';
import '../../voice/voice_hub.dart';
import '../../voice/voice_profile.dart';
import 'voice_backdrop.dart';
import 'voice_orb.dart';
import 'voice_palette.dart';
import 'voice_sheets.dart';

/// Full-screen, hands-free conversation with an agent.
class VoiceModeScreen extends StatefulWidget {
  const VoiceModeScreen({
    super.key,
    required this.hub,
    required this.agent,
    this.conversationId,
    this.alreadyListening = false,
  });

  final VoiceHub hub;
  final AgentSummary agent;

  /// Continue an existing chat conversation by voice.
  final String? conversationId;

  /// True when opened by the wake phrase: the session is already running.
  final bool alreadyListening;

  /// A soft fade-and-rise transition suited to an immersive screen.
  static Route<void> route({
    required VoiceHub hub,
    required AgentSummary agent,
    String? conversationId,
    bool alreadyListening = false,
  }) {
    return PageRouteBuilder<void>(
      opaque: true,
      transitionDuration: const Duration(milliseconds: 420),
      reverseTransitionDuration: const Duration(milliseconds: 300),
      pageBuilder: (_, _, _) => VoiceModeScreen(
        hub: hub,
        agent: agent,
        conversationId: conversationId,
        alreadyListening: alreadyListening,
      ),
      transitionsBuilder: (_, animation, _, child) {
        final curved = CurvedAnimation(
          parent: animation,
          curve: Curves.easeOutCubic,
          reverseCurve: Curves.easeInCubic,
        );
        return FadeTransition(
          opacity: curved,
          child: SlideTransition(
            position: Tween<Offset>(
              begin: const Offset(0, 0.04),
              end: Offset.zero,
            ).animate(curved),
            child: child,
          ),
        );
      },
    );
  }

  @override
  State<VoiceModeScreen> createState() => _VoiceModeScreenState();
}

class _VoiceModeScreenState extends State<VoiceModeScreen> {
  late final VoiceConversation _c = widget.hub.conversation;
  final _typeController = TextEditingController();
  final _typeFocus = FocusNode();
  Timer? _hintTimer;
  var _hintIndex = 0;
  var _typing = false;
  var _wasActive = false;
  var _closing = false;

  static const _hints = [
    'Ask me anything',
    'Say “switch to” and an agent’s name',
    'Talk over me to interrupt',
    'Say “goodbye” when you’re done',
  ];

  @override
  void initState() {
    super.initState();
    unawaited(WakelockPlus.enable().catchError((Object _) {}));
    _c.addListener(_onChanged);
    _hintTimer = Timer.periodic(const Duration(seconds: 5), (_) {
      if (!mounted) return;
      setState(() => _hintIndex = (_hintIndex + 1) % _hints.length);
    });
    _wasActive = _c.sessionActive;
    if (!widget.alreadyListening && !_c.sessionActive) {
      unawaited(
        widget.hub.open(widget.agent, conversationId: widget.conversationId),
      );
    }
  }

  @override
  void dispose() {
    _c.removeListener(_onChanged);
    _hintTimer?.cancel();
    _typeController.dispose();
    _typeFocus.dispose();
    unawaited(WakelockPlus.disable().catchError((Object _) {}));
    if (_c.sessionActive) unawaited(widget.hub.close());
    super.dispose();
  }

  void _onChanged() {
    if (!mounted) return;
    final active = _c.sessionActive;
    if (active) _wasActive = true;
    // The session ended by itself (goodbye, or nobody spoke): leave quietly.
    if (_wasActive && !active && _c.phase != VoicePhase.error) {
      unawaited(_close(endSession: false));
      return;
    }
    setState(() {});
  }

  Future<void> _close({bool endSession = true}) async {
    if (_closing) return;
    _closing = true;
    if (endSession) await widget.hub.close();
    // pop(), not maybePop(): our own PopScope would veto maybePop().
    if (mounted) Navigator.of(context).pop();
  }

  void _onOrbTap() {
    HapticFeedback.selectionClick();
    _c.interrupt();
  }

  Future<void> _submitTyped() async {
    final text = _typeController.text.trim();
    if (text.isEmpty) return;
    _typeController.clear();
    setState(() => _typing = false);
    FocusScope.of(context).unfocus();
    await _c.sendText(text);
  }

  @override
  Widget build(BuildContext context) {
    final phase = _c.phase;
    final agent = _c.agent ?? widget.agent;
    final size = MediaQuery.sizeOf(context);
    final orbSize = (size.shortestSide * 0.92).clamp(240.0, 420.0);

    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) unawaited(_close());
      },
      child: Scaffold(
        backgroundColor: const Color(0xFF060A12),
        resizeToAvoidBottomInset: true,
        body: AnnotatedRegion<SystemUiOverlayStyle>(
          value: SystemUiOverlayStyle.light,
          child: Stack(
            children: [
              Positioned.fill(child: VoiceBackdrop(phase: phase)),
              SafeArea(
                child: Column(
                  children: [
                    _TopBar(
                      agent: agent,
                      phase: phase,
                      onClose: () => unawaited(_close()),
                      onPickAgent: () => showAgentPicker(
                        context,
                        hub: widget.hub,
                        current: agent,
                      ),
                      onTranscript: () => showTranscript(context, _c),
                      onSettings: () => showVoiceSettings(context, widget.hub),
                    ),
                    Expanded(
                      child: LayoutBuilder(
                        builder: (context, box) {
                          final orb = orbSize.clamp(0.0, box.maxHeight * 0.78);
                          return Center(
                            child: GestureDetector(
                              behavior: HitTestBehavior.opaque,
                              onTap: _onOrbTap,
                              child: Semantics(
                                button: true,
                                label: _semanticLabel(phase),
                                child: VoiceOrb(
                                  phase: phase,
                                  inputLevel: _c.inputLevel,
                                  outputLevel: _c.outputLevel,
                                  size: orb,
                                  userSpeaking: _c.userSpeaking,
                                ),
                              ),
                            ),
                          );
                        },
                      ),
                    ),
                    _StatusBlock(
                      controller: _c,
                      hint: _hints[_hintIndex],
                      wakeEnabled: widget.hub.settings.wakeEnabled,
                      issueKind: widget.hub.issue?.kind,
                      onResolve: () => unawaited(widget.hub.resolveIssue()),
                      onRetry: () => unawaited(
                        widget.hub.open(
                          agent,
                          conversationId: _c.conversationId,
                        ),
                      ),
                    ),
                    const SizedBox(height: 14),
                    if (_typing)
                      _TypeBar(
                        controller: _typeController,
                        focusNode: _typeFocus,
                        onSend: _submitTyped,
                      ),
                    _Controls(
                      muted: _c.muted,
                      typing: _typing,
                      onMute: _c.toggleMute,
                      onEnd: () => unawaited(_close()),
                      onType: () {
                        setState(() => _typing = !_typing);
                        if (_typing) {
                          WidgetsBinding.instance.addPostFrameCallback(
                            (_) => _typeFocus.requestFocus(),
                          );
                        }
                      },
                    ),
                    const SizedBox(height: 18),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _semanticLabel(VoicePhase phase) => switch (phase) {
    VoicePhase.speaking => 'Assistant is speaking. Double tap to interrupt.',
    VoicePhase.thinking => 'Assistant is thinking. Double tap to cancel.',
    VoicePhase.listening => 'Listening. Double tap to send what you said now.',
    VoicePhase.error => 'There was a problem. Double tap to retry.',
    VoicePhase.armed || VoicePhase.idle => 'Double tap to start talking.',
  };
}

class _TopBar extends StatelessWidget {
  const _TopBar({
    required this.agent,
    required this.phase,
    required this.onClose,
    required this.onPickAgent,
    required this.onTranscript,
    required this.onSettings,
  });

  final AgentSummary agent;
  final VoicePhase phase;
  final VoidCallback onClose;
  final VoidCallback onPickAgent;
  final VoidCallback onTranscript;
  final VoidCallback onSettings;

  @override
  Widget build(BuildContext context) {
    final palette = VoicePalette.of(phase);
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 6, 12, 0),
      child: Row(
        children: [
          _RoundIcon(
            icon: Icons.keyboard_arrow_down_rounded,
            tooltip: 'Close',
            onTap: onClose,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Center(
              child: Material(
                color: Colors.white.withValues(alpha: 0.07),
                shape: StadiumBorder(
                  side: BorderSide(color: Colors.white.withValues(alpha: 0.10)),
                ),
                child: InkWell(
                  customBorder: const StadiumBorder(),
                  onTap: onPickAgent,
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(6, 6, 14, 6),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        AgentAvatar(agent: agent, size: 30, glow: palette.glow),
                        const SizedBox(width: 10),
                        Flexible(
                          child: Text(
                            agent.name,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: Theme.of(context).textTheme.titleSmall
                                ?.copyWith(
                                  color: Colors.white,
                                  fontWeight: FontWeight.w700,
                                ),
                          ),
                        ),
                        const SizedBox(width: 4),
                        Icon(
                          Icons.unfold_more_rounded,
                          size: 18,
                          color: Colors.white.withValues(alpha: 0.6),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(width: 8),
          _RoundIcon(
            icon: Icons.subject_rounded,
            tooltip: 'Transcript',
            onTap: onTranscript,
          ),
          const SizedBox(width: 6),
          _RoundIcon(
            icon: Icons.tune_rounded,
            tooltip: 'Voice settings',
            onTap: onSettings,
          ),
        ],
      ),
    );
  }
}

class _StatusBlock extends StatelessWidget {
  const _StatusBlock({
    required this.controller,
    required this.hint,
    required this.wakeEnabled,
    required this.issueKind,
    required this.onResolve,
    required this.onRetry,
  });

  final VoiceConversation controller;
  final String hint;
  final bool wakeEnabled;

  /// Set when the agent cannot be spoken to yet and there is a one-tap fix.
  final VoiceIssueKind? issueKind;
  final VoidCallback onResolve;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final c = controller;
    final theme = Theme.of(context).textTheme;
    final phase = c.phase;
    final palette = VoicePalette.of(phase);

    final title = switch (phase) {
      VoicePhase.armed ||
      VoicePhase.idle => wakeEnabled ? 'Say “Hey Synkora”' : 'Tap to talk',
      VoicePhase.listening =>
        c.muted
            ? 'Mic is muted'
            : (c.userSpeaking ? 'Listening…' : 'I’m listening'),
      VoicePhase.thinking => 'Thinking…',
      VoicePhase.speaking => 'Speaking',
      VoicePhase.error => 'Something went wrong',
    };

    final lastUser = c.turns.reversed.where((t) => t.isUser).firstOrNull;
    final caption = switch (phase) {
      VoicePhase.thinking =>
        c.status ?? (lastUser == null ? '' : '“${lastUser.text}”'),
      VoicePhase.speaking => c.speakingSentence,
      VoicePhase.listening =>
        c.liveTranscript.isNotEmpty
            ? c.liveTranscript
            : (c.status ?? (c.turns.isEmpty && !c.userSpeaking ? hint : '')),
      VoicePhase.error => c.error ?? '',
      _ => '',
    };

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 28),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          AnimatedSwitcher(
            duration: const Duration(milliseconds: 260),
            child: Text(
              title,
              key: ValueKey(title),
              textAlign: TextAlign.center,
              style: theme.headlineSmall?.copyWith(
                color: Colors.white,
                fontWeight: FontWeight.w700,
                letterSpacing: -0.2,
              ),
            ),
          ),
          const SizedBox(height: 10),
          ConstrainedBox(
            constraints: BoxConstraints(
              minHeight: 84,
              // Error explanations can be long; do not cut off what to do.
              maxHeight: phase == VoicePhase.error ? 190 : 132,
            ),
            child: Center(
              child: AnimatedSwitcher(
                duration: const Duration(milliseconds: 320),
                transitionBuilder: (child, animation) => FadeTransition(
                  opacity: animation,
                  child: SlideTransition(
                    position: Tween<Offset>(
                      begin: const Offset(0, 0.12),
                      end: Offset.zero,
                    ).animate(animation),
                    child: child,
                  ),
                ),
                child: caption.isEmpty
                    ? const SizedBox(key: ValueKey('empty'), height: 1)
                    : Text(
                        caption,
                        key: ValueKey(caption),
                        textAlign: TextAlign.center,
                        maxLines: phase == VoicePhase.error ? 7 : 4,
                        overflow: TextOverflow.fade,
                        style:
                            (phase == VoicePhase.speaking
                                    ? theme.titleLarge
                                    : theme.bodyLarge)
                                ?.copyWith(
                                  color: phase == VoicePhase.speaking
                                      ? Colors.white
                                      : Colors.white.withValues(alpha: 0.62),
                                  height: 1.35,
                                  fontWeight: phase == VoicePhase.speaking
                                      ? FontWeight.w600
                                      : FontWeight.w500,
                                ),
                      ),
              ),
            ),
          ),
          if (phase == VoicePhase.error) ...[
            const SizedBox(height: 6),
            TextButton.icon(
              onPressed: issueKind == null ? onRetry : onResolve,
              icon: Icon(switch (issueKind) {
                VoiceIssueKind.voiceDisabled =>
                  Icons.power_settings_new_rounded,
                VoiceIssueKind.missingKey => Icons.phone_iphone_rounded,
                null => Icons.refresh_rounded,
              }, color: palette.core),
              label: Text(
                switch (issueKind) {
                  VoiceIssueKind.voiceDisabled => 'Turn on voice',
                  VoiceIssueKind.missingKey => 'Use my phone’s voice',
                  null => 'Try again',
                },
                style: TextStyle(
                  color: palette.core,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _Controls extends StatelessWidget {
  const _Controls({
    required this.muted,
    required this.typing,
    required this.onMute,
    required this.onEnd,
    required this.onType,
  });

  final bool muted;
  final bool typing;
  final VoidCallback onMute;
  final VoidCallback onEnd;
  final VoidCallback onType;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        _GlassButton(
          icon: muted ? Icons.mic_off_rounded : Icons.mic_rounded,
          label: muted ? 'Unmute microphone' : 'Mute microphone',
          active: muted,
          onTap: onMute,
        ),
        const SizedBox(width: 26),
        Semantics(
          button: true,
          label: 'End conversation',
          child: GestureDetector(
            onTap: onEnd,
            child: Container(
              width: 76,
              height: 76,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: const LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [Color(0xFFFF6B7A), Color(0xFFE5384F)],
                ),
                boxShadow: [
                  BoxShadow(
                    color: const Color(0xFFFF4D5E).withValues(alpha: 0.45),
                    blurRadius: 26,
                    spreadRadius: 1,
                  ),
                ],
              ),
              child: const Icon(
                Icons.call_end_rounded,
                color: Colors.white,
                size: 32,
              ),
            ),
          ),
        ),
        const SizedBox(width: 26),
        _GlassButton(
          icon: Icons.keyboard_alt_outlined,
          label: 'Type a message',
          active: typing,
          onTap: onType,
        ),
      ],
    );
  }
}

class _GlassButton extends StatelessWidget {
  const _GlassButton({
    required this.icon,
    required this.label,
    required this.onTap,
    this.active = false,
  });

  final IconData icon;
  final String label;
  final bool active;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: label,
      child: GestureDetector(
        onTap: () {
          HapticFeedback.selectionClick();
          onTap();
        },
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          width: 58,
          height: 58,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: active
                ? Colors.white.withValues(alpha: 0.92)
                : Colors.white.withValues(alpha: 0.09),
            border: Border.all(color: Colors.white.withValues(alpha: 0.14)),
          ),
          child: Icon(
            icon,
            size: 26,
            color: active ? const Color(0xFF0B1220) : Colors.white,
          ),
        ),
      ),
    );
  }
}

class _RoundIcon extends StatelessWidget {
  const _RoundIcon({
    required this.icon,
    required this.tooltip,
    required this.onTap,
  });

  final IconData icon;
  final String tooltip;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: tooltip,
      child: Material(
        color: Colors.white.withValues(alpha: 0.07),
        shape: const CircleBorder(),
        child: InkWell(
          customBorder: const CircleBorder(),
          onTap: onTap,
          child: SizedBox(
            width: 42,
            height: 42,
            child: Icon(
              icon,
              size: 22,
              color: Colors.white.withValues(alpha: 0.9),
            ),
          ),
        ),
      ),
    );
  }
}

class _TypeBar extends StatelessWidget {
  const _TypeBar({
    required this.controller,
    required this.focusNode,
    required this.onSend,
  });

  final TextEditingController controller;
  final FocusNode focusNode;
  final VoidCallback onSend;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 0, 20, 14),
      child: Container(
        padding: const EdgeInsets.fromLTRB(18, 4, 6, 4),
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.09),
          borderRadius: BorderRadius.circular(28),
          border: Border.all(color: Colors.white.withValues(alpha: 0.14)),
        ),
        child: Row(
          children: [
            Expanded(
              child: TextField(
                controller: controller,
                focusNode: focusNode,
                style: const TextStyle(color: Colors.white),
                cursorColor: Colors.white,
                textInputAction: TextInputAction.send,
                onSubmitted: (_) => onSend(),
                decoration: InputDecoration(
                  hintText: 'Type instead…',
                  hintStyle: TextStyle(
                    color: Colors.white.withValues(alpha: 0.45),
                  ),
                  border: InputBorder.none,
                  enabledBorder: InputBorder.none,
                  focusedBorder: InputBorder.none,
                  filled: false,
                ),
              ),
            ),
            IconButton(
              onPressed: onSend,
              icon: const Icon(Icons.arrow_upward_rounded),
              color: const Color(0xFF0B1220),
              style: IconButton.styleFrom(backgroundColor: Colors.white),
              tooltip: 'Send',
            ),
          ],
        ),
      ),
    );
  }
}
