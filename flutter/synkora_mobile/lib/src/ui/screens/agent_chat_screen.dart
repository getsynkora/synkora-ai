import 'dart:io';
import 'dart:math' as math;
import 'dart:async';
import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:speech_to_text/speech_recognition_error.dart';
import 'package:speech_to_text/speech_recognition_result.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;

import '../../models/synkora_models.dart';
import '../../services/agent_service.dart';
import '../../theme/app_theme.dart';
import '../widgets/mesh_background.dart';
import '../widgets/rich_chat_message.dart';

enum AgentChatLaunchIntent { none, talk, scan }

class AgentChatScreen extends StatefulWidget {
  const AgentChatScreen({
    super.key,
    required this.agent,
    required this.agentService,
    this.initialConversation,
    this.initialIntent = AgentChatLaunchIntent.none,
  });

  final AgentSummary agent;
  final SynkoraAgentService agentService;
  final ConversationSummary? initialConversation;
  final AgentChatLaunchIntent initialIntent;

  @override
  State<AgentChatScreen> createState() => _AgentChatScreenState();
}

class _AgentChatScreenState extends State<AgentChatScreen> {
  final _composerController = TextEditingController();
  final _scrollController = ScrollController();
  final _imagePicker = ImagePicker();
  final _speechToText = stt.SpeechToText();

  List<ConversationSummary> _conversations = const [];
  ConversationSummary? _activeConversation;
  List<ChatMessage> _messages = const [];
  List<String> _toolStatuses = const [];
  List<_DraftAttachment> _draftAttachments = const [];
  bool _isLoading = true;
  bool _isSending = false;
  bool _isListening = false;
  bool _isStartingVoiceInput = false;
  bool _speechInitialized = false;
  double _soundLevel = 0;
  bool _heardSoundDuringSession = false;
  String? _speechLocaleId;
  String? _error;
  String? _voiceHint;
  String _dictationPrefix = '';
  AgentChatLaunchIntent? _pendingLaunchIntent;
  DateTime? _nextSpeechStartAllowedAt;
  Timer? _voiceSessionTimer;

  bool get _canSend =>
      !_isSending && _composerController.text.trim().isNotEmpty;

  @override
  void initState() {
    super.initState();
    _pendingLaunchIntent = widget.initialIntent;
    _composerController.addListener(_handleComposerChanged);
    _bootstrap();
  }

  @override
  void dispose() {
    _voiceSessionTimer?.cancel();
    _speechToText.cancel();
    _composerController
      ..removeListener(_handleComposerChanged)
      ..dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _handleComposerChanged() {
    if (mounted) {
      setState(() {});
    }
  }

  Future<void> _bootstrap() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });
    try {
      final conversations = await widget.agentService.loadConversations(
        widget.agent.id,
        source: 'flutter',
      );
      final initialConversation =
          widget.initialConversation ??
          (conversations.isNotEmpty ? conversations.first : null);
      final messages = initialConversation == null
          ? const <ChatMessage>[]
          : await widget.agentService.loadMessages(initialConversation.id);

      if (!mounted) return;
      setState(() {
        _conversations = conversations;
        _activeConversation = initialConversation;
        _messages = messages;
      });
      _scrollToBottom(immediate: true);
      _runInitialIntentIfNeeded();
    } catch (error) {
      if (!mounted) return;
      setState(() => _error = error.toString());
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  Future<void> _selectConversation(ConversationSummary conversation) async {
    setState(() {
      _activeConversation = conversation;
      _isLoading = true;
      _error = null;
      _toolStatuses = const [];
    });
    try {
      final messages = await widget.agentService.loadMessages(conversation.id);
      if (!mounted) return;
      setState(() => _messages = messages);
      _scrollToBottom(immediate: true);
    } catch (error) {
      if (!mounted) return;
      setState(() => _error = error.toString());
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  Future<void> _pickImages() async {
    try {
      final files = await _imagePicker.pickMultiImage(
        imageQuality: 92,
        maxWidth: 2400,
      );
      if (!mounted || files.isEmpty) return;

      final attachments = <_DraftAttachment>[];
      for (final file in files) {
        attachments.add(
          _DraftAttachment(
            id: 'image_${DateTime.now().microsecondsSinceEpoch}_${file.name}',
            fileName: file.name,
            path: file.path,
            bytes: null,
            sizeBytes: await file.length(),
            mimeType: _guessMimeType(file.name),
          ),
        );
      }
      setState(() {
        _draftAttachments = _mergeDraftAttachments(attachments);
      });
    } catch (error) {
      _showSnackBar('Image selection failed: $error');
    }
  }

  Future<void> _scanDocument() async {
    try {
      final file = await _imagePicker.pickImage(
        source: ImageSource.camera,
        imageQuality: 92,
        maxWidth: 2400,
        preferredCameraDevice: CameraDevice.rear,
      );
      if (!mounted || file == null) return;

      final attachment = _DraftAttachment(
        id: 'scan_${DateTime.now().microsecondsSinceEpoch}_${file.name}',
        fileName: file.name,
        path: file.path,
        bytes: null,
        sizeBytes: await file.length(),
        mimeType: _guessMimeType(file.name) ?? 'image/jpeg',
      );

      setState(() {
        _draftAttachments = _mergeDraftAttachments([attachment]);
        _voiceHint = 'Scan attached. Add instructions and send it to the agent.';
      });
      _showSnackBar('Scan attached. Add instructions and send.');
    } catch (error) {
      _showSnackBar('Camera scan failed: $error');
    }
  }

  Future<void> _toggleVoiceInput() async {
    if (_isListening) {
      await _stopVoiceInput();
      return;
    }

    if (_isStartingVoiceInput) {
      if (mounted) {
        setState(() {
          _voiceHint = 'Voice input is still starting. Wait a moment.';
        });
      }
      return;
    }

    final now = DateTime.now();
    final cooldownUntil = _nextSpeechStartAllowedAt;
    if (cooldownUntil != null && now.isBefore(cooldownUntil)) {
      final remainingSeconds = cooldownUntil.difference(now).inSeconds + 1;
      if (mounted) {
        setState(() {
          _voiceHint =
              'Speech recognition is temporarily rate-limited by Android. Try again in ${remainingSeconds}s.';
        });
      }
      _showSnackBar(
        'Speech recognition is cooling down. Try again in ${remainingSeconds}s.',
      );
      return;
    }

    _isStartingVoiceInput = true;
    final available = await _initializeSpeechIfNeeded();
    if (!available || !mounted) {
      _isStartingVoiceInput = false;
      return;
    }

    _dictationPrefix = _composerController.text.trim();
    _startVoiceSessionTimer();

    try {
      await _speechToText.listen(
        onResult: _handleSpeechResult,
        onSoundLevelChange: _handleSoundLevelChange,
        listenOptions: stt.SpeechListenOptions(
          partialResults: true,
          cancelOnError: false,
          listenMode: stt.ListenMode.dictation,
          listenFor: const Duration(seconds: 45),
          pauseFor: const Duration(seconds: 8),
          localeId: _speechLocaleId,
        ),
      );
      if (!mounted) return;
      setState(() {
        _isListening = true;
        _soundLevel = 0;
        _heardSoundDuringSession = false;
        _voiceHint =
            'Listening... speak now. If the meter stays flat, the emulator is not receiving mic audio.';
      });
    } catch (error) {
      _cancelVoiceSessionTimer();
      if (mounted) {
        setState(() {
          _voiceHint =
              'Voice input failed to start. Wait a moment, then try again.';
        });
      }
      _showSnackBar('Voice input failed to start: $error');
    } finally {
      _isStartingVoiceInput = false;
    }
  }

  Future<bool> _initializeSpeechIfNeeded() async {
    if (_speechInitialized) {
      return true;
    }

    final available = await _speechToText.initialize(
      onStatus: _handleSpeechStatus,
      onError: _handleSpeechError,
      debugLogging: true,
      options: [
        stt.SpeechToText.androidIntentLookup,
        stt.SpeechToText.androidAlwaysUseStop,
        stt.SpeechToText.androidNoBluetooth,
      ],
    );

    if (!mounted) return false;

    if (!available) {
      _showSnackBar('Speech recognition is not available on this device.');
      return false;
    }

    final systemLocale = await _speechToText.systemLocale();
    if (!mounted) return false;

    setState(() {
      _speechInitialized = true;
      _speechLocaleId = systemLocale?.localeId;
    });
    return true;
  }

  void _handleSpeechResult(SpeechRecognitionResult result) {
    if (!mounted) return;
    _startVoiceSessionTimer();
    final transcript = result.recognizedWords.trim();
    if (transcript.isEmpty) return;

    final separator = _dictationPrefix.isEmpty
        ? ''
        : (_dictationPrefix.endsWith(' ') ? '' : ' ');
    final nextText = '$_dictationPrefix$separator$transcript';

    _composerController.value = TextEditingValue(
      text: nextText,
      selection: TextSelection.collapsed(offset: nextText.length),
    );

    if (result.finalResult) {
      setState(() {
        _voiceHint = 'Voice draft ready. Review it, then send.';
      });
    }
  }

  void _handleSpeechStatus(String status) {
    if (!mounted) return;
    final normalized = status.toLowerCase();
    if (normalized == 'listening') {
      _startVoiceSessionTimer();
      if (!_isListening) {
        setState(() {
          _isListening = true;
        });
      }
      return;
    }
    if (normalized == 'done' ||
        normalized == 'notlistening' ||
        normalized == 'not listening') {
      _cancelVoiceSessionTimer();
      final hint = _resolveVoiceOutcomeHint();
      setState(() {
        _isListening = false;
        _isStartingVoiceInput = false;
        _soundLevel = 0;
        _heardSoundDuringSession = false;
        _voiceHint = hint;
      });
    }
  }

  void _handleSoundLevelChange(double level) {
    if (!mounted) return;
    setState(() {
      _soundLevel = level;
      if (_isListening && level > 2) {
        _startVoiceSessionTimer();
        _heardSoundDuringSession = true;
        _voiceHint = 'Audio detected. Keep speaking.';
      }
    });
  }

  void _handleSpeechError(SpeechRecognitionError error) {
    if (!mounted) return;
    _cancelVoiceSessionTimer();
    final errorCode = error.errorMsg.toLowerCase().trim();
    final hint = _resolveVoiceOutcomeHint();

    if (errorCode == 'error_too_many_requests') {
      _speechToText.cancel();
      setState(() {
        _isListening = false;
        _isStartingVoiceInput = false;
        _soundLevel = 0;
        _heardSoundDuringSession = false;
        _nextSpeechStartAllowedAt = DateTime.now().add(
          const Duration(seconds: 15),
        );
        _voiceHint =
            'Android speech recognition is rate-limited. Wait 15s, then try Talk again.';
      });
      _showSnackBar(
        'Android speech recognition is rate-limited. Wait 15 seconds and try again.',
      );
      return;
    }

    if (!error.permanent ||
        errorCode == 'error_client' ||
        errorCode == 'error_audio_error' ||
        errorCode == 'error_speech_timeout' ||
        errorCode == 'error_no_match') {
      setState(() {
        _isListening = false;
        _isStartingVoiceInput = false;
        _soundLevel = 0;
        _voiceHint = hint;
        _heardSoundDuringSession = false;
      });
      return;
    }

    setState(() {
      _isListening = false;
      _isStartingVoiceInput = false;
      _soundLevel = 0;
      _heardSoundDuringSession = false;
      _voiceHint = 'Voice input unavailable right now. You can keep typing.';
    });
    _showSnackBar('Voice input failed: ${error.errorMsg}');
  }

  Future<void> _stopVoiceInput() async {
    _cancelVoiceSessionTimer();
    await _speechToText.stop();
    if (!mounted) return;
    final hint = _resolveVoiceOutcomeHint();
    setState(() {
      _isListening = false;
      _isStartingVoiceInput = false;
      _soundLevel = 0;
      _heardSoundDuringSession = false;
      _voiceHint = hint;
    });
  }

  bool _hasCapturedVoiceDraft() {
    final current = _composerController.text.trim();
    final original = _dictationPrefix.trim();
    return current.isNotEmpty && current != original;
  }

  String _resolveVoiceOutcomeHint() {
    if (_hasCapturedVoiceDraft()) {
      return 'Voice draft ready. Review it, then send.';
    }
    if (_heardSoundDuringSession) {
      return 'Audio was detected, but Android returned no transcript. This emulator recognizer is unreliable.';
    }
    return 'No speech detected. Tap Talk and start speaking right away.';
  }

  void _startVoiceSessionTimer() {
    _voiceSessionTimer?.cancel();
    _voiceSessionTimer = Timer(const Duration(seconds: 14), () async {
      if (!mounted || !_isListening) {
        return;
      }
      await _speechToText.stop();
      if (!mounted) return;
      setState(() {
        _isListening = false;
        _isStartingVoiceInput = false;
        _soundLevel = 0;
        _heardSoundDuringSession = false;
        _voiceHint = _resolveVoiceOutcomeHint();
      });
    });
  }

  void _cancelVoiceSessionTimer() {
    _voiceSessionTimer?.cancel();
    _voiceSessionTimer = null;
  }

  void _runInitialIntentIfNeeded() {
    final intent = _pendingLaunchIntent;
    if (intent == null || intent == AgentChatLaunchIntent.none) {
      return;
    }

    _pendingLaunchIntent = AgentChatLaunchIntent.none;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      switch (intent) {
        case AgentChatLaunchIntent.talk:
          setState(() {
            _voiceHint = 'Tap Talk once to start voice input.';
          });
          break;
        case AgentChatLaunchIntent.scan:
          _scanDocument();
          break;
        case AgentChatLaunchIntent.none:
          break;
      }
    });
  }

  Future<void> _pickFiles() async {
    try {
      final result = await FilePicker.platform.pickFiles(
        allowMultiple: true,
        withData: true,
      );
      if (!mounted || result == null || result.files.isEmpty) return;

      final attachments = result.files
          .where((file) => file.path != null || file.bytes != null)
          .map(
            (file) => _DraftAttachment(
              id: 'file_${DateTime.now().microsecondsSinceEpoch}_${file.name}',
              fileName: file.name,
              path: file.path,
              bytes: file.bytes,
              sizeBytes: file.size,
              mimeType: _guessMimeType(file.name),
            ),
          )
          .toList();

      if (attachments.isEmpty) {
        _showSnackBar('No supported files were selected.');
        return;
      }

      setState(() {
        _draftAttachments = _mergeDraftAttachments(attachments);
      });
    } catch (error) {
      _showSnackBar('File selection failed: $error');
    }
  }

  List<_DraftAttachment> _mergeDraftAttachments(
    List<_DraftAttachment> additions,
  ) {
    final merged = [..._draftAttachments];
    for (final candidate in additions) {
      final exists = merged.any(
        (current) =>
            current.fileName == candidate.fileName &&
            current.sizeBytes == candidate.sizeBytes,
      );
      if (!exists) {
        merged.add(candidate);
      }
    }
    return merged;
  }

  Future<void> _send() async {
    final text = _composerController.text.trim();
    if ((text.isEmpty && _draftAttachments.isEmpty) || _isSending) {
      return;
    }

    if (text.isEmpty) {
      _showSnackBar('Add a message before sending attachments.');
      return;
    }

    final draftAttachments = List<_DraftAttachment>.from(_draftAttachments);
    final previousConversation = _activeConversation;
    var messageCommitted = false;
    _composerController.clear();
    setState(() {
      _isSending = true;
      _error = null;
      _toolStatuses = const [];
      _draftAttachments = const [];
    });

    try {
      final conversation = await _ensureConversation(seedText: text);
      final uploadedAttachments = await _uploadDraftAttachments(
        conversation.id,
        draftAttachments,
      );

      final userMessage = ChatMessage(
        id: 'local_user_${DateTime.now().microsecondsSinceEpoch}',
        role: 'user',
        content: text,
        createdAt: DateTime.now(),
        attachments: uploadedAttachments,
      );
      final placeholderId =
          'local_assistant_${DateTime.now().microsecondsSinceEpoch}';
      setState(() {
        _messages = [
          ..._messages,
          userMessage,
          ChatMessage(
            id: placeholderId,
            role: 'assistant',
            content: '',
            createdAt: DateTime.now(),
            isStreaming: true,
          ),
        ];
      });
      messageCommitted = true;
      _scrollToBottom();

      await for (final event in widget.agentService.streamChat(
        agentSlug: widget.agent.slug,
        message: text,
        conversationId: conversation.id,
        attachments: uploadedAttachments,
      )) {
        if (!mounted) return;
        switch (event.type) {
          case 'chunk':
            _patchMessage(placeholderId, append: event.content ?? '');
            break;
          case 'tool_status':
            setState(() {
              _toolStatuses = [
                '${event.toolName ?? 'Agent'} • ${event.status ?? 'working'}',
                ..._toolStatuses,
              ].take(4).toList();
            });
            break;
          case 'done':
            _finalizeMessage(placeholderId);
            break;
          case 'error':
            _markMessageError(
              placeholderId,
              event.error ?? 'The agent returned an error.',
            );
            break;
          default:
            break;
        }
        _scrollToBottom();
      }

      await _refreshConversationState(activeConversationId: conversation.id);
    } catch (error) {
      if (!mounted) return;
      final message = error.toString().replaceFirst('Exception: ', '');
      if (!messageCommitted) {
        setState(() {
          _error = message;
          _draftAttachments = [...draftAttachments, ..._draftAttachments];
          _activeConversation = previousConversation;
        });
      } else {
        setState(() => _error = message);
        if (_messages.isNotEmpty && _messages.last.isStreaming) {
          _markMessageError(_messages.last.id, message);
        }
      }
    } finally {
      if (mounted) {
        setState(() => _isSending = false);
      }
    }
  }

  Future<ConversationSummary> _ensureConversation({
    required String seedText,
  }) async {
    if (_activeConversation != null) {
      return _activeConversation!;
    }

    final conversation = await widget.agentService.createConversation(
      widget.agent.id,
      name: seedText.length > 42 ? '${seedText.substring(0, 42)}...' : seedText,
      source: 'flutter',
    );

    if (mounted) {
      setState(() {
        _activeConversation = conversation;
        _conversations = [conversation, ..._conversations];
      });
    }
    return conversation;
  }

  Future<List<ChatAttachment>> _uploadDraftAttachments(
    String conversationId,
    List<_DraftAttachment> drafts,
  ) async {
    if (drafts.isEmpty) return const [];

    final uploaded = <ChatAttachment>[];
    for (var index = 0; index < drafts.length; index += 1) {
      final draft = drafts[index];
      setState(() {
        _toolStatuses = [
          'Uploading ${index + 1}/${drafts.length} • ${draft.fileName}',
          ..._toolStatuses,
        ].take(4).toList();
      });

      if (draft.path == null && draft.bytes == null) {
        throw Exception('Selected file "${draft.fileName}" is not readable.');
      }

      final attachment = await widget.agentService.uploadAttachment(
        conversationId: conversationId,
        filePath: draft.path ?? '',
        fileName: draft.fileName,
        bytes: draft.bytes,
      );
      uploaded.add(attachment);
    }

    return uploaded;
  }

  Future<void> _refreshConversationState({
    required String activeConversationId,
  }) async {
    final refreshedConversations = await widget.agentService.loadConversations(
      widget.agent.id,
      source: 'flutter',
    );
    final refreshedMessages = await widget.agentService.loadMessages(
      activeConversationId,
    );

    if (!mounted) return;
    final matchingConversation = refreshedConversations.where(
      (conversation) => conversation.id == activeConversationId,
    );
    setState(() {
      _conversations = refreshedConversations;
      _activeConversation = matchingConversation.isNotEmpty
          ? matchingConversation.first
          : _activeConversation;
      _messages = refreshedMessages;
    });
    _scrollToBottom();
  }

  void _patchMessage(String id, {required String append}) {
    setState(() {
      _messages = _messages.map((message) {
        if (message.id != id) return message;
        return message.copyWith(content: '${message.content}$append');
      }).toList();
    });
  }

  void _finalizeMessage(String id) {
    setState(() {
      _messages = _messages.map((message) {
        if (message.id != id) return message;
        return message.copyWith(isStreaming: false);
      }).toList();
    });
  }

  void _markMessageError(String id, String error) {
    setState(() {
      _messages = _messages.map((message) {
        if (message.id != id) return message;
        return message.copyWith(
          content: error,
          isStreaming: false,
          isError: true,
        );
      }).toList();
    });
  }

  void _scrollToBottom({bool immediate = false}) {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scrollController.hasClients) return;
      final target = _scrollController.position.maxScrollExtent;
      if (immediate) {
        _scrollController.jumpTo(target);
        return;
      }
      _scrollController.animateTo(
        target,
        duration: const Duration(milliseconds: 220),
        curve: Curves.easeOutCubic,
      );
    });
  }

  void _removeDraftAttachment(String id) {
    setState(() {
      _draftAttachments = _draftAttachments
          .where((attachment) => attachment.id != id)
          .toList();
    });
  }

  void _startNewChat() {
    setState(() {
      _activeConversation = null;
      _messages = const [];
      _toolStatuses = const [];
      _error = null;
      _draftAttachments = const [];
      _voiceHint = null;
      _composerController.clear();
    });
  }

  void _showSnackBar(String message) {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        titleSpacing: 16,
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(widget.agent.name),
            Text(
              _activeConversation?.name ?? 'Fresh conversation',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: SynkoraColors.muted,
              ),
            ),
          ],
        ),
        actions: [
          IconButton(
            onPressed: _isSending ? null : _startNewChat,
            icon: const Icon(Icons.edit_square),
            tooltip: 'New chat',
          ),
        ],
      ),
      body: Stack(
        children: [
          const Positioned.fill(child: MeshBackground()),
          Column(
            children: [
              if (_conversations.isNotEmpty) _ConversationRail(
                conversations: _conversations,
                activeConversationId: _activeConversation?.id,
                onSelect: _selectConversation,
              ),
              if (_toolStatuses.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 10, 16, 0),
                  child: Column(
                    children: _toolStatuses
                        .map(
                          (status) => Container(
                            width: double.infinity,
                            margin: const EdgeInsets.only(bottom: 8),
                            padding: const EdgeInsets.symmetric(
                              horizontal: 14,
                              vertical: 12,
                            ),
                            decoration: BoxDecoration(
                              color: Colors.white.withValues(alpha: 0.78),
                              borderRadius: BorderRadius.circular(18),
                              border: Border.all(
                                color: SynkoraColors.border,
                              ),
                            ),
                            child: Row(
                              children: [
                                const SizedBox(
                                  width: 14,
                                  height: 14,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                  ),
                                ),
                                const SizedBox(width: 12),
                                Expanded(
                                  child: Text(
                                    status,
                                    style: Theme.of(context)
                                        .textTheme
                                        .bodyMedium
                                        ?.copyWith(
                                          color: SynkoraColors.ink,
                                        ),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        )
                        .toList(),
                  ),
                ),
              Expanded(
                child: _isLoading
                    ? const Center(child: CircularProgressIndicator())
                    : _messages.isEmpty
                    ? _EmptyConversationState(
                        agentName: widget.agent.name,
                        onPrompt: (prompt) {
                          _composerController.text = prompt;
                          _send();
                        },
                      )
                    : ListView.builder(
                        controller: _scrollController,
                        keyboardDismissBehavior:
                            ScrollViewKeyboardDismissBehavior.onDrag,
                        padding: const EdgeInsets.fromLTRB(16, 18, 16, 28),
                        itemCount: _messages.length,
                        itemBuilder: (context, index) {
                          final message = _messages[index];
                          return RichChatMessage(
                            message: message,
                            agentAvatarUrl: widget.agent.avatarUrl,
                          );
                        },
                      ),
              ),
              if (_error != null)
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
                  child: Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: const Color(0xFFFFF1F2),
                      borderRadius: BorderRadius.circular(18),
                      border: Border.all(
                        color: SynkoraColors.danger.withValues(alpha: 0.16),
                      ),
                    ),
                    child: Text(
                      _error!,
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: SynkoraColors.danger,
                      ),
                    ),
                  ),
                ),
              SafeArea(
                top: false,
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
                  child: _ComposerCard(
                    controller: _composerController,
                    draftAttachments: _draftAttachments,
                    isSending: _isSending,
                    isListening: _isListening,
                    soundLevel: _soundLevel,
                    canSend: _canSend,
                    voiceHint: _voiceHint,
                    onSend: _send,
                    onPickFiles: _pickFiles,
                    onPickImages: _pickImages,
                    onScan: _scanDocument,
                    onToggleTalk: _toggleVoiceInput,
                    onRemoveAttachment: _removeDraftAttachment,
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _ConversationRail extends StatelessWidget {
  const _ConversationRail({
    required this.conversations,
    required this.activeConversationId,
    required this.onSelect,
  });

  final List<ConversationSummary> conversations;
  final String? activeConversationId;
  final ValueChanged<ConversationSummary> onSelect;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 92,
      child: ListView.separated(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
        scrollDirection: Axis.horizontal,
        itemCount: conversations.length,
        separatorBuilder: (_, _) => const SizedBox(width: 10),
        itemBuilder: (context, index) {
          final conversation = conversations[index];
          final isActive = conversation.id == activeConversationId;
          return GestureDetector(
            onTap: () => onSelect(conversation),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 160),
              width: 172,
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: isActive
                    ? SynkoraColors.ink
                    : Colors.white.withValues(alpha: 0.8),
                borderRadius: BorderRadius.circular(20),
                border: Border.all(
                  color: isActive
                      ? Colors.transparent
                      : SynkoraColors.border,
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    conversation.name,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                      color: isActive ? Colors.white : SynkoraColors.ink,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  Text(
                    formatRelativeTimestamp(conversation.updatedAt),
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: isActive
                          ? Colors.white.withValues(alpha: 0.72)
                          : SynkoraColors.muted,
                    ),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}

class _ComposerCard extends StatelessWidget {
  const _ComposerCard({
    required this.controller,
    required this.draftAttachments,
    required this.isSending,
    required this.isListening,
    required this.soundLevel,
    required this.canSend,
    required this.voiceHint,
    required this.onSend,
    required this.onPickFiles,
    required this.onPickImages,
    required this.onScan,
    required this.onToggleTalk,
    required this.onRemoveAttachment,
  });

  final TextEditingController controller;
  final List<_DraftAttachment> draftAttachments;
  final bool isSending;
  final bool isListening;
  final double soundLevel;
  final bool canSend;
  final String? voiceHint;
  final VoidCallback onSend;
  final VoidCallback onPickFiles;
  final VoidCallback onPickImages;
  final VoidCallback onScan;
  final VoidCallback onToggleTalk;
  final ValueChanged<String> onRemoveAttachment;

  @override
  Widget build(BuildContext context) {
    final hasAttachments = draftAttachments.isNotEmpty;
    final needsMessage = hasAttachments && controller.text.trim().isEmpty;

    return Container(
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.86),
        borderRadius: BorderRadius.circular(30),
        border: Border.all(color: Colors.white.withValues(alpha: 0.64)),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFF0F172A).withValues(alpha: 0.1),
            blurRadius: 42,
            offset: const Offset(0, 24),
          ),
        ],
      ),
      child: Stack(
        children: [
          Positioned.fill(
            child: DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [
                    Colors.white.withValues(alpha: 0.92),
                    const Color(0xFFF4FBF8).withValues(alpha: 0.96),
                    const Color(0xFFFFFAF5).withValues(alpha: 0.92),
                  ],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
              ),
            ),
          ),
          Positioned(
            top: -48,
            right: -18,
            child: IgnorePointer(
              child: Container(
                width: 152,
                height: 152,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: RadialGradient(
                    colors: [
                      SynkoraColors.primary.withValues(alpha: 0.24),
                      SynkoraColors.primary.withValues(alpha: 0),
                    ],
                  ),
                ),
              ),
            ),
          ),
          Positioned(
            bottom: -56,
            left: -16,
            child: IgnorePointer(
              child: Container(
                width: 164,
                height: 164,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: RadialGradient(
                    colors: [
                      SynkoraColors.accentWarm.withValues(alpha: 0.18),
                      SynkoraColors.accentWarm.withValues(alpha: 0),
                    ],
                  ),
                ),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 12, 12, 10),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (hasAttachments)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: SizedBox(
                      height: 88,
                      child: ListView.separated(
                        scrollDirection: Axis.horizontal,
                        itemCount: draftAttachments.length,
                        separatorBuilder: (_, _) => const SizedBox(width: 10),
                        itemBuilder: (context, index) {
                          final attachment = draftAttachments[index];
                          return _DraftAttachmentCard(
                            attachment: attachment,
                            onRemove: () => onRemoveAttachment(attachment.id),
                          );
                        },
                      ),
                    ),
                  ),
                if (voiceHint != null)
                  Padding(
                    padding: const EdgeInsets.fromLTRB(0, 0, 0, 10),
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 220),
                      padding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 10,
                      ),
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          colors: isListening
                              ? [
                                  SynkoraColors.primary.withValues(alpha: 0.22),
                                  Colors.white.withValues(alpha: 0.82),
                                ]
                              : [
                                  Colors.white.withValues(alpha: 0.76),
                                  const Color(0xFFF8FAFC).withValues(alpha: 0.9),
                                ],
                        ),
                        borderRadius: BorderRadius.circular(18),
                        border: Border.all(
                          color: isListening
                              ? SynkoraColors.primaryDeep.withValues(alpha: 0.18)
                              : const Color(0x160F172A),
                        ),
                      ),
                      child: Row(
                        children: [
                          Icon(
                            isListening
                                ? Icons.graphic_eq_rounded
                                : Icons.auto_awesome_rounded,
                            size: 16,
                            color: isListening
                                ? SynkoraColors.primaryDeep
                                : SynkoraColors.muted,
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              voiceHint!,
                              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                color: isListening
                                    ? SynkoraColors.primaryDeep
                                    : SynkoraColors.muted,
                                fontWeight: isListening
                                    ? FontWeight.w700
                                    : FontWeight.w600,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                if (isListening)
                  Padding(
                    padding: const EdgeInsets.fromLTRB(0, 0, 0, 10),
                    child: Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.72),
                        borderRadius: BorderRadius.circular(18),
                        border: Border.all(
                          color: SynkoraColors.primaryDeep.withValues(alpha: 0.12),
                        ),
                      ),
                      child: _VoiceLevelMeter(level: soundLevel),
                    ),
                  ),
                Row(
                  children: [
                    Expanded(
                      child: _ComposerFeatureButton(
                        icon: isListening ? Icons.mic_rounded : Icons.mic_none_rounded,
                        label: isListening ? 'Listening' : 'Talk',
                        tooltip: isListening ? 'Stop voice input' : 'Talk',
                        onPressed: isSending ? null : onToggleTalk,
                        tone: _ComposerFeatureTone.mint,
                        isActive: isListening,
                        animate: isListening,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: _ComposerFeatureButton(
                        icon: Icons.document_scanner_outlined,
                        label: 'Scan',
                        tooltip: 'Scan',
                        onPressed: isSending ? null : onScan,
                        tone: _ComposerFeatureTone.gold,
                      ),
                    ),
                    const SizedBox(width: 8),
                    _ComposerIconButton(
                      icon: Icons.image_outlined,
                      tooltip: 'Attach image',
                      onPressed: isSending ? null : onPickImages,
                    ),
                    const SizedBox(width: 8),
                    _ComposerIconButton(
                      icon: Icons.attach_file_rounded,
                      tooltip: 'Attach file',
                      onPressed: isSending ? null : onPickFiles,
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                Container(
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.82),
                    borderRadius: BorderRadius.circular(24),
                    border: Border.all(color: const Color(0x170F172A)),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.white.withValues(alpha: 0.46),
                        blurRadius: 24,
                        offset: const Offset(0, -2),
                      ),
                    ],
                  ),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Expanded(
                        child: TextField(
                          controller: controller,
                          minLines: 1,
                          maxLines: 6,
                          textInputAction: TextInputAction.send,
                          onSubmitted: (_) => canSend ? onSend() : null,
                          decoration: const InputDecoration(
                            hintText: 'Message this agent',
                            border: InputBorder.none,
                            enabledBorder: InputBorder.none,
                            focusedBorder: InputBorder.none,
                            filled: false,
                            contentPadding: EdgeInsets.symmetric(
                              horizontal: 14,
                              vertical: 16,
                            ),
                          ),
                        ),
                      ),
                      Padding(
                        padding: const EdgeInsets.fromLTRB(0, 6, 6, 6),
                        child: FilledButton(
                          onPressed: canSend ? onSend : null,
                          style: FilledButton.styleFrom(
                            backgroundColor: SynkoraColors.ink,
                            foregroundColor: SynkoraColors.primary,
                            minimumSize: const Size(56, 56),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(18),
                            ),
                          ),
                          child: isSending
                              ? const SizedBox(
                                  width: 18,
                                  height: 18,
                                  child: CircularProgressIndicator(strokeWidth: 2),
                                )
                              : const Icon(Icons.arrow_upward_rounded),
                        ),
                      ),
                    ],
                  ),
                ),
                if (needsMessage)
                  Padding(
                    padding: const EdgeInsets.fromLTRB(8, 10, 8, 0),
                    child: Row(
                      children: [
                        const Icon(
                          Icons.info_outline,
                          size: 16,
                          color: SynkoraColors.muted,
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            'Add a message so the agent knows what to do with your attachments.',
                            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                              color: SynkoraColors.muted,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

enum _ComposerFeatureTone { mint, gold }

class _ComposerFeatureButton extends StatefulWidget {
  const _ComposerFeatureButton({
    required this.icon,
    required this.label,
    required this.tooltip,
    required this.onPressed,
    required this.tone,
    this.isActive = false,
    this.animate = false,
  });

  final IconData icon;
  final String label;
  final String tooltip;
  final VoidCallback? onPressed;
  final _ComposerFeatureTone tone;
  final bool isActive;
  final bool animate;

  @override
  State<_ComposerFeatureButton> createState() => _ComposerFeatureButtonState();
}

class _ComposerFeatureButtonState extends State<_ComposerFeatureButton>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1800),
  );

  @override
  void initState() {
    super.initState();
    _syncAnimation();
  }

  @override
  void didUpdateWidget(covariant _ComposerFeatureButton oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.animate != widget.animate) {
      _syncAnimation();
    }
  }

  void _syncAnimation() {
    if (widget.animate) {
      _controller.repeat();
    } else {
      _controller
        ..stop()
        ..value = 0;
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final scheme = switch (widget.tone) {
      _ComposerFeatureTone.mint => (
          background: [
            const Color(0xFFEFFCF6),
            SynkoraColors.primary.withValues(alpha: widget.isActive ? 0.82 : 0.48),
          ],
          foreground: SynkoraColors.primaryDeep,
        ),
      _ComposerFeatureTone.gold => (
          background: [
            const Color(0xFFFFF4E7),
            SynkoraColors.accentWarm.withValues(alpha: 0.9),
          ],
          foreground: const Color(0xFF8A4A12),
        ),
    };

    return Tooltip(
      message: widget.tooltip,
      child: AnimatedBuilder(
        animation: _controller,
        builder: (context, child) {
          final pulse = widget.animate
              ? (math.sin(_controller.value * math.pi * 2) + 1) / 2
              : 0.0;
          final scale = 1 + (pulse * 0.025);

          return Transform.scale(scale: scale, child: child);
        },
        child: Opacity(
          opacity: widget.onPressed == null ? 0.48 : 1,
          child: Material(
            color: Colors.transparent,
            child: InkWell(
              onTap: widget.onPressed,
              borderRadius: BorderRadius.circular(20),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 220),
                height: 52,
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: scheme.background,
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(
                    color: scheme.foreground.withValues(
                      alpha: widget.isActive ? 0.28 : 0.16,
                    ),
                  ),
                  boxShadow: [
                    if (widget.isActive)
                      BoxShadow(
                        color: SynkoraColors.primary.withValues(alpha: 0.22),
                        blurRadius: 20,
                        offset: const Offset(0, 10),
                      ),
                  ],
                ),
                child: Stack(
                  children: [
                    if (widget.animate)
                      Positioned.fill(
                        child: IgnorePointer(
                          child: AnimatedBuilder(
                            animation: _controller,
                            builder: (context, _) {
                              return Transform.translate(
                                offset: Offset(
                                  -26 + (_controller.value * 90),
                                  0,
                                ),
                                child: Transform.rotate(
                                  angle: -0.35,
                                  child: Align(
                                    alignment: Alignment.centerLeft,
                                    child: Container(
                                      width: 34,
                                      decoration: BoxDecoration(
                                        gradient: LinearGradient(
                                          colors: [
                                            Colors.white.withValues(alpha: 0),
                                            Colors.white.withValues(alpha: 0.26),
                                            Colors.white.withValues(alpha: 0),
                                          ],
                                        ),
                                      ),
                                    ),
                                  ),
                                ),
                              );
                            },
                          ),
                        ),
                      ),
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 12),
                      child: Row(
                        children: [
                          Container(
                            width: 30,
                            height: 30,
                            decoration: BoxDecoration(
                              color: Colors.white.withValues(alpha: 0.62),
                              borderRadius: BorderRadius.circular(11),
                            ),
                            child: Icon(
                              widget.icon,
                              size: 18,
                              color: scheme.foreground,
                            ),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Text(
                              widget.label,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                                color: scheme.foreground,
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                          ),
                          Icon(
                            widget.isActive
                                ? Icons.graphic_eq_rounded
                                : Icons.arrow_outward_rounded,
                            size: 18,
                            color: scheme.foreground.withValues(alpha: 0.9),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _ComposerIconButton extends StatelessWidget {
  const _ComposerIconButton({
    required this.icon,
    required this.tooltip,
    required this.onPressed,
  });

  final IconData icon;
  final String tooltip;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: tooltip,
      child: InkResponse(
        onTap: onPressed,
        radius: 28,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 220),
          width: 48,
          height: 48,
          decoration: BoxDecoration(
            gradient: LinearGradient(
              colors: [
                Colors.white.withValues(alpha: 0.78),
                const Color(0xFFF8FAFC),
              ],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: const Color(0x140F172A),
            ),
            boxShadow: [
              BoxShadow(
                color: const Color(0xFF0F172A).withValues(alpha: 0.05),
                blurRadius: 16,
                offset: const Offset(0, 8),
              ),
            ],
          ),
          child: Icon(
            icon,
            color: SynkoraColors.ink,
          ),
        ),
      ),
    );
  }
}

class _VoiceLevelMeter extends StatelessWidget {
  const _VoiceLevelMeter({required this.level});

  final double level;

  @override
  Widget build(BuildContext context) {
    final normalized = ((level + 2) / 12).clamp(0.05, 1.0);
    return ClipRRect(
      borderRadius: BorderRadius.circular(999),
      child: SizedBox(
        height: 10,
        child: Stack(
          fit: StackFit.expand,
          children: [
            Container(color: const Color(0x120F172A)),
            Align(
              alignment: Alignment.centerLeft,
              child: FractionallySizedBox(
                widthFactor: normalized,
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      colors: [
                        SynkoraColors.primary,
                        SynkoraColors.primaryDeep,
                      ],
                    ),
                    borderRadius: BorderRadius.circular(999),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _DraftAttachmentCard extends StatelessWidget {
  const _DraftAttachmentCard({
    required this.attachment,
    required this.onRemove,
  });

  final _DraftAttachment attachment;
  final VoidCallback onRemove;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 184,
      child: Stack(
        children: [
          Container(
            decoration: BoxDecoration(
              color: const Color(0xFFF8FAFC),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: const Color(0x160F172A)),
            ),
            child: attachment.isImage
                ? Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      ClipRRect(
                        borderRadius: const BorderRadius.vertical(
                          top: Radius.circular(19),
                        ),
                        child: SizedBox(
                          height: 48,
                          width: double.infinity,
                          child: attachment.path != null
                              ? Image.file(
                                  File(attachment.path!),
                                  fit: BoxFit.cover,
                                  errorBuilder: (_, _, _) => _DraftFallback(
                                    attachment: attachment,
                                  ),
                                )
                              : attachment.bytes != null
                              ? Image.memory(
                                  attachment.bytes!,
                                  fit: BoxFit.cover,
                                  errorBuilder: (_, _, _) => _DraftFallback(
                                    attachment: attachment,
                                  ),
                                )
                              : _DraftFallback(attachment: attachment),
                        ),
                      ),
                      Padding(
                        padding: const EdgeInsets.all(10),
                        child: _DraftAttachmentMeta(attachment: attachment),
                      ),
                    ],
                  )
                : Padding(
                    padding: const EdgeInsets.all(12),
                    child: Row(
                      children: [
                        Container(
                          width: 40,
                          height: 40,
                          decoration: BoxDecoration(
                            color: Colors.white,
                            borderRadius: BorderRadius.circular(14),
                          ),
                          child: Icon(
                            attachment.icon,
                            color: SynkoraColors.ink,
                          ),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: _DraftAttachmentMeta(attachment: attachment),
                        ),
                      ],
                    ),
                  ),
          ),
          Positioned(
            top: 8,
            right: 8,
            child: GestureDetector(
              onTap: onRemove,
              child: Container(
                width: 24,
                height: 24,
                decoration: BoxDecoration(
                  color: SynkoraColors.ink.withValues(alpha: 0.88),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Icon(
                  Icons.close,
                  size: 14,
                  color: Colors.white,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _DraftAttachmentMeta extends StatelessWidget {
  const _DraftAttachmentMeta({required this.attachment});

  final _DraftAttachment attachment;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Text(
          attachment.fileName,
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
            color: SynkoraColors.ink,
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          '${attachment.label} • ${formatByteSize(attachment.sizeBytes)}',
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
            color: SynkoraColors.muted,
          ),
        ),
      ],
    );
  }
}

class _DraftFallback extends StatelessWidget {
  const _DraftFallback({required this.attachment});

  final _DraftAttachment attachment;

  @override
  Widget build(BuildContext context) {
    return Container(
      color: const Color(0xFFF8FAFC),
      alignment: Alignment.center,
      child: Icon(attachment.icon, color: SynkoraColors.ink),
    );
  }
}

class _EmptyConversationState extends StatelessWidget {
  const _EmptyConversationState({
    required this.agentName,
    required this.onPrompt,
  });

  final String agentName;
  final ValueChanged<String> onPrompt;

  @override
  Widget build(BuildContext context) {
    final prompts = [
      'Summarize what this agent is best at.',
      'Help me turn a rough task into a concrete plan.',
      'Review the latest context and tell me what needs attention.',
    ];

    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 86,
              height: 86,
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [Color(0xFF79DFBC), Color(0xFFF6C794)],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: BorderRadius.circular(28),
              ),
              child: const Icon(
                Icons.auto_awesome_rounded,
                color: SynkoraColors.ink,
                size: 38,
              ),
            ),
            const SizedBox(height: 20),
            Text(
              'Start a premium conversation with $agentName',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 10),
            Text(
              'Ask for structured analysis, send files, or drop in screenshots and let the agent work from real context.',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyLarge,
            ),
            const SizedBox(height: 24),
            Column(
              children: prompts
                  .map(
                    (prompt) => GestureDetector(
                      onTap: () => onPrompt(prompt),
                      child: Container(
                        width: double.infinity,
                        margin: const EdgeInsets.only(bottom: 10),
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: Colors.white.withValues(alpha: 0.82),
                          borderRadius: BorderRadius.circular(22),
                          border: Border.all(color: SynkoraColors.border),
                        ),
                        child: Row(
                          children: [
                            const Icon(
                              Icons.arrow_outward_rounded,
                              color: SynkoraColors.primaryDeep,
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Text(
                                prompt,
                                style: Theme.of(context)
                                    .textTheme
                                    .bodyLarge
                                    ?.copyWith(fontWeight: FontWeight.w600),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  )
                  .toList(),
            ),
          ],
        ),
      ),
    );
  }
}

class _DraftAttachment {
  const _DraftAttachment({
    required this.id,
    required this.fileName,
    required this.path,
    required this.bytes,
    required this.sizeBytes,
    required this.mimeType,
  });

  final String id;
  final String fileName;
  final String? path;
  final Uint8List? bytes;
  final int sizeBytes;
  final String? mimeType;

  bool get isImage =>
      mimeType?.startsWith('image/') ?? _guessMimeType(fileName)?.startsWith('image/') == true;

  String get label {
    final type = mimeType ?? _guessMimeType(fileName) ?? 'file';
    return type.split('/').last.toUpperCase();
  }

  IconData get icon {
    final type = mimeType ?? _guessMimeType(fileName) ?? '';
    if (type == 'application/pdf') return Icons.picture_as_pdf_outlined;
    if (type.contains('sheet') || type.contains('csv')) {
      return Icons.table_chart_outlined;
    }
    if (type.contains('word') || type.contains('document')) {
      return Icons.description_outlined;
    }
    if (type.startsWith('image/')) return Icons.image_outlined;
    return Icons.attach_file_rounded;
  }
}

String? _guessMimeType(String fileName) {
  final extension = fileName.split('.').last.toLowerCase();
  return switch (extension) {
    'png' => 'image/png',
    'jpg' || 'jpeg' => 'image/jpeg',
    'gif' => 'image/gif',
    'webp' => 'image/webp',
    'pdf' => 'application/pdf',
    'txt' => 'text/plain',
    'md' || 'markdown' => 'text/markdown',
    'csv' => 'text/csv',
    'json' => 'application/json',
    'doc' => 'application/msword',
    'docx' =>
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'xls' => 'application/vnd.ms-excel',
    'xlsx' =>
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'ppt' => 'application/vnd.ms-powerpoint',
    'pptx' =>
      'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'zip' => 'application/zip',
    _ => null,
  };
}
