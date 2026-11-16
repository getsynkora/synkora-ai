// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class AppLocalizationsEn extends AppLocalizations {
  AppLocalizationsEn([String locale = 'en']) : super(locale);

  @override
  String get appTitle => 'Synkora AI';

  @override
  String get signInTitle => 'Synkora AI';

  @override
  String get signInSubtitle =>
      'Use every agent in your workspace from a dedicated native app.';

  @override
  String get email => 'Email';

  @override
  String get password => 'Password';

  @override
  String get signIn => 'Sign in';

  @override
  String get orContinueWith => 'or continue with';

  @override
  String get continueWithGoogle => 'Continue with Google';

  @override
  String get signInFootnote =>
      'This app uses the same Synkora account and tenant access model as the web app.';

  @override
  String get chooseWorkspace => 'Choose workspace';

  @override
  String get chooseWorkspaceBody =>
      'Your account has access to multiple Synkora tenants. Pick the workspace you want to use on mobile.';

  @override
  String get bootBranding => 'Branded by Synkora';

  @override
  String get bootLoading =>
      'Loading your workspace, agents, and premium actions.';

  @override
  String get signInCancelled =>
      'Sign-in was cancelled or could not be completed.';

  @override
  String get signInNotCompleted => 'Sign-in was not completed.';

  @override
  String get authRequestFailed => 'Authentication request failed.';

  @override
  String get workspaceNotFound => 'Selected workspace was not found.';

  @override
  String get sessionIncomplete =>
      'Your session is incomplete. Please sign in again.';

  @override
  String streamFailed(String error) {
    return 'Failed to stream agent response: $error';
  }

  @override
  String get authRequired => 'Authentication required.';

  @override
  String get networkError => 'Unexpected network error';

  @override
  String get timeJustNow => 'Just now';

  @override
  String timeMinutesAgo(int count) {
    return '${count}m ago';
  }

  @override
  String timeHoursAgo(int count) {
    return '${count}h ago';
  }

  @override
  String timeDaysAgo(int count) {
    return '${count}d ago';
  }

  @override
  String get unknown => 'Unknown';

  @override
  String get navAgents => 'Agents';

  @override
  String get navInbox => 'Inbox';

  @override
  String get navActivity => 'Activity';

  @override
  String get navProfile => 'Profile';

  @override
  String get inboxSubtitle =>
      'Push replies, approvals, and completions will land here.';

  @override
  String get activitySubtitle =>
      'Operational activity and agent work logs will appear here.';

  @override
  String welcomeBack(String name) {
    return 'Welcome back, $name';
  }

  @override
  String get welcomeBackAnonymous => 'Welcome back';

  @override
  String workspaceName(String name) {
    return 'Workspace: $name';
  }

  @override
  String get searchAgents => 'Search your agents';

  @override
  String get filtersSoon => 'Filters land in the next mobile slice.';

  @override
  String get heroTitle => 'All tenant agents, one app';

  @override
  String get heroBody =>
      'Jump into any agent with full account auth and Flutter-native performance.';

  @override
  String get retry => 'Retry';

  @override
  String get spotlight => 'Spotlight';

  @override
  String get allAgents => 'All agents';

  @override
  String runsCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count runs',
      one: '$count run',
    );
    return '$_temp0';
  }

  @override
  String successPercent(int percent) {
    return '$percent% success';
  }

  @override
  String get profileTitle => 'Profile';

  @override
  String get synkoraUser => 'Synkora User';

  @override
  String get workspace => 'Workspace';

  @override
  String get role => 'Role';

  @override
  String get switchWorkspace => 'Switch workspace';

  @override
  String get switchWorkspaceHint => 'Use a different tenant on this device';

  @override
  String get signOut => 'Sign out';

  @override
  String get signOutHint => 'Clear the device session and return to login';

  @override
  String get language => 'Language';

  @override
  String get languageSystem => 'System default';

  @override
  String get agentTitle => 'Agent';

  @override
  String get actionMessage => 'Message';

  @override
  String get actionTalk => 'Talk';

  @override
  String get actionScan => 'Scan';

  @override
  String get capabilities => 'Capabilities';

  @override
  String get recentSessions => 'Recent mobile sessions';

  @override
  String get noSessions => 'No mobile sessions yet';

  @override
  String get noSessionsHint => 'Start a fresh conversation from this agent.';

  @override
  String imageSelectionFailed(String error) {
    return 'Image selection failed: $error';
  }

  @override
  String get scanAttachedHint =>
      'Scan attached. Add instructions and send it to the agent.';

  @override
  String get scanAttachedSnack => 'Scan attached. Add instructions and send.';

  @override
  String cameraScanFailed(String error) {
    return 'Camera scan failed: $error';
  }

  @override
  String get voiceStarting => 'Voice input is still starting. Wait a moment.';

  @override
  String speechRateLimitedHint(int seconds) {
    return 'Speech recognition is temporarily rate-limited by Android. Try again in ${seconds}s.';
  }

  @override
  String speechCoolingDown(int seconds) {
    return 'Speech recognition is cooling down. Try again in ${seconds}s.';
  }

  @override
  String get voiceListening =>
      'Listening... speak now. If the meter stays flat, the emulator is not receiving mic audio.';

  @override
  String get voiceStartFailedHint =>
      'Voice input failed to start. Wait a moment, then try again.';

  @override
  String voiceStartFailedSnack(String error) {
    return 'Voice input failed to start: $error';
  }

  @override
  String get speechUnavailable =>
      'Speech recognition is not available on this device.';

  @override
  String get voiceDraftReady => 'Voice draft ready. Review it, then send.';

  @override
  String get audioDetected => 'Audio detected. Keep speaking.';

  @override
  String get androidRateLimitedHint =>
      'Android speech recognition is rate-limited. Wait 15s, then try Talk again.';

  @override
  String get androidRateLimitedSnack =>
      'Android speech recognition is rate-limited. Wait 15 seconds and try again.';

  @override
  String get voiceUnavailable =>
      'Voice input unavailable right now. You can keep typing.';

  @override
  String voiceFailed(String error) {
    return 'Voice input failed: $error';
  }

  @override
  String get noTranscript =>
      'Audio was detected, but Android returned no transcript. This emulator recognizer is unreliable.';

  @override
  String get noSpeech =>
      'No speech detected. Tap Talk and start speaking right away.';

  @override
  String get tapTalkHint => 'Tap Talk once to start voice input.';

  @override
  String get noSupportedFiles => 'No supported files were selected.';

  @override
  String fileSelectionFailed(String error) {
    return 'File selection failed: $error';
  }

  @override
  String get addMessageFirst => 'Add a message before sending attachments.';

  @override
  String toolStatus(String tool, String status) {
    return '$tool • $status';
  }

  @override
  String get toolDefaultName => 'Agent';

  @override
  String get toolDefaultStatus => 'working';

  @override
  String get agentError => 'The agent returned an error.';

  @override
  String uploading(int current, int total, String name) {
    return 'Uploading $current/$total • $name';
  }

  @override
  String fileNotReadable(String name) {
    return 'Selected file \"$name\" is not readable.';
  }

  @override
  String get freshConversation => 'Fresh conversation';

  @override
  String get voiceConversation => 'Voice conversation';

  @override
  String get newChat => 'New chat';

  @override
  String get listening => 'Listening';

  @override
  String get stopVoiceInput => 'Stop voice input';

  @override
  String get attachImage => 'Attach image';

  @override
  String get attachFile => 'Attach file';

  @override
  String get messageHint => 'Message this agent';

  @override
  String get attachmentsNeedMessage =>
      'Add a message so the agent knows what to do with your attachments.';

  @override
  String get emptyPromptStrengths => 'Summarize what this agent is best at.';

  @override
  String get emptyPromptPlan =>
      'Help me turn a rough task into a concrete plan.';

  @override
  String get emptyPromptReview =>
      'Review the latest context and tell me what needs attention.';

  @override
  String emptyTitle(String agentName) {
    return 'Start a premium conversation with $agentName';
  }

  @override
  String get emptyBody =>
      'Ask for structured analysis, send files, or drop in screenshots and let the agent work from real context.';

  @override
  String get streaming => 'Streaming';

  @override
  String get voiceSemanticSpeaking =>
      'Assistant is speaking. Double tap to interrupt.';

  @override
  String get voiceSemanticThinking =>
      'Assistant is thinking. Double tap to cancel.';

  @override
  String get voiceSemanticListening =>
      'Listening. Double tap to send what you said now.';

  @override
  String get voiceSemanticError => 'There was a problem. Double tap to retry.';

  @override
  String get voiceSemanticIdle => 'Double tap to start talking.';

  @override
  String get close => 'Close';

  @override
  String get transcript => 'Transcript';

  @override
  String get voiceSettings => 'Voice settings';

  @override
  String get voiceTitleWake => 'Say “Hey Synkora”';

  @override
  String get voiceTitleTap => 'Tap to talk';

  @override
  String get micMuted => 'Mic is muted';

  @override
  String get listeningDots => 'Listening…';

  @override
  String get imListening => 'I’m listening';

  @override
  String get thinkingTitle => 'Thinking…';

  @override
  String get speakingTitle => 'Speaking';

  @override
  String get somethingWrong => 'Something went wrong';

  @override
  String get turnOnVoice => 'Turn on voice';

  @override
  String get usePhoneVoice => 'Use my phone’s voice';

  @override
  String get tryAgain => 'Try again';

  @override
  String get unmuteMic => 'Unmute microphone';

  @override
  String get muteMic => 'Mute microphone';

  @override
  String get endConversation => 'End conversation';

  @override
  String get typeMessage => 'Type a message';

  @override
  String get typeInstead => 'Type instead…';

  @override
  String get send => 'Send';

  @override
  String get talkTo => 'Talk to';

  @override
  String get noOtherAgents => 'No other agents yet.';

  @override
  String get transcriptEmpty =>
      'Nothing yet. Start talking and your conversation will appear here.';

  @override
  String get interrupted => 'Interrupted';

  @override
  String get wakeTitle => 'Wake with “Hey Synkora”';

  @override
  String get wakeSubtitle =>
      'Listens for the phrase while Synkora is open, so you can talk hands-free. Audio is checked on your phone and is only sent once you start speaking.';

  @override
  String get interruptTitle => 'Interrupt by speaking';

  @override
  String get interruptSubtitle => 'Talk over the assistant to cut it off.';

  @override
  String get soundsTitle => 'Sounds';

  @override
  String get soundsSubtitle => 'A soft chime when it wakes or finishes.';

  @override
  String get hapticsTitle => 'Haptics';

  @override
  String get hapticsSubtitle => 'Gentle taps at key moments.';

  @override
  String speakingSpeed(String speed) {
    return 'Speaking speed  ·  $speed×';
  }

  @override
  String get wakeLow => 'Fewer wakes';

  @override
  String get wakeBalanced => 'Balanced';

  @override
  String get wakeHigh => 'Catch more';

  @override
  String get wakeSensitivity => 'Wake sensitivity';

  @override
  String get wakeHelp =>
      'If it wakes when you did not say it, choose “Fewer wakes”. If it misses you, choose “Catch more”.';

  @override
  String wakeUnavailable(String message) {
    return '“Hey Synkora” is unavailable on this device right now. You can still tap the orb to talk.\n$message';
  }

  @override
  String get talkToAgents => 'Talk to your agents';

  @override
  String talkToAgent(String name) {
    return 'Talk to $name';
  }

  @override
  String get handsFreeOn => 'Hands-free is on. Just say “Hey Synkora”.';

  @override
  String get startVoice => 'Have a real voice conversation. Tap to start.';
}
