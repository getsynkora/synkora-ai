import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_de.dart';
import 'app_localizations_en.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'l10n/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
    : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations)!;
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
        delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
      ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('de'),
    Locale('en'),
  ];

  /// No description provided for @appTitle.
  ///
  /// In en, this message translates to:
  /// **'Synkora AI'**
  String get appTitle;

  /// No description provided for @signInTitle.
  ///
  /// In en, this message translates to:
  /// **'Synkora AI'**
  String get signInTitle;

  /// No description provided for @signInSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Use every agent in your workspace from a dedicated native app.'**
  String get signInSubtitle;

  /// No description provided for @email.
  ///
  /// In en, this message translates to:
  /// **'Email'**
  String get email;

  /// No description provided for @password.
  ///
  /// In en, this message translates to:
  /// **'Password'**
  String get password;

  /// No description provided for @signIn.
  ///
  /// In en, this message translates to:
  /// **'Sign in'**
  String get signIn;

  /// No description provided for @orContinueWith.
  ///
  /// In en, this message translates to:
  /// **'or continue with'**
  String get orContinueWith;

  /// No description provided for @continueWithGoogle.
  ///
  /// In en, this message translates to:
  /// **'Continue with Google'**
  String get continueWithGoogle;

  /// No description provided for @signInFootnote.
  ///
  /// In en, this message translates to:
  /// **'This app uses the same Synkora account and tenant access model as the web app.'**
  String get signInFootnote;

  /// No description provided for @chooseWorkspace.
  ///
  /// In en, this message translates to:
  /// **'Choose workspace'**
  String get chooseWorkspace;

  /// No description provided for @chooseWorkspaceBody.
  ///
  /// In en, this message translates to:
  /// **'Your account has access to multiple Synkora tenants. Pick the workspace you want to use on mobile.'**
  String get chooseWorkspaceBody;

  /// No description provided for @bootBranding.
  ///
  /// In en, this message translates to:
  /// **'Branded by Synkora'**
  String get bootBranding;

  /// No description provided for @bootLoading.
  ///
  /// In en, this message translates to:
  /// **'Loading your workspace, agents, and premium actions.'**
  String get bootLoading;

  /// No description provided for @signInCancelled.
  ///
  /// In en, this message translates to:
  /// **'Sign-in was cancelled or could not be completed.'**
  String get signInCancelled;

  /// No description provided for @signInNotCompleted.
  ///
  /// In en, this message translates to:
  /// **'Sign-in was not completed.'**
  String get signInNotCompleted;

  /// No description provided for @authRequestFailed.
  ///
  /// In en, this message translates to:
  /// **'Authentication request failed.'**
  String get authRequestFailed;

  /// No description provided for @workspaceNotFound.
  ///
  /// In en, this message translates to:
  /// **'Selected workspace was not found.'**
  String get workspaceNotFound;

  /// No description provided for @sessionIncomplete.
  ///
  /// In en, this message translates to:
  /// **'Your session is incomplete. Please sign in again.'**
  String get sessionIncomplete;

  /// No description provided for @streamFailed.
  ///
  /// In en, this message translates to:
  /// **'Failed to stream agent response: {error}'**
  String streamFailed(String error);

  /// No description provided for @authRequired.
  ///
  /// In en, this message translates to:
  /// **'Authentication required.'**
  String get authRequired;

  /// No description provided for @networkError.
  ///
  /// In en, this message translates to:
  /// **'Unexpected network error'**
  String get networkError;

  /// No description provided for @timeJustNow.
  ///
  /// In en, this message translates to:
  /// **'Just now'**
  String get timeJustNow;

  /// No description provided for @timeMinutesAgo.
  ///
  /// In en, this message translates to:
  /// **'{count}m ago'**
  String timeMinutesAgo(int count);

  /// No description provided for @timeHoursAgo.
  ///
  /// In en, this message translates to:
  /// **'{count}h ago'**
  String timeHoursAgo(int count);

  /// No description provided for @timeDaysAgo.
  ///
  /// In en, this message translates to:
  /// **'{count}d ago'**
  String timeDaysAgo(int count);

  /// No description provided for @unknown.
  ///
  /// In en, this message translates to:
  /// **'Unknown'**
  String get unknown;

  /// No description provided for @navAgents.
  ///
  /// In en, this message translates to:
  /// **'Agents'**
  String get navAgents;

  /// No description provided for @navInbox.
  ///
  /// In en, this message translates to:
  /// **'Inbox'**
  String get navInbox;

  /// No description provided for @navActivity.
  ///
  /// In en, this message translates to:
  /// **'Activity'**
  String get navActivity;

  /// No description provided for @navProfile.
  ///
  /// In en, this message translates to:
  /// **'Profile'**
  String get navProfile;

  /// No description provided for @inboxSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Push replies, approvals, and completions will land here.'**
  String get inboxSubtitle;

  /// No description provided for @activitySubtitle.
  ///
  /// In en, this message translates to:
  /// **'Operational activity and agent work logs will appear here.'**
  String get activitySubtitle;

  /// No description provided for @welcomeBack.
  ///
  /// In en, this message translates to:
  /// **'Welcome back, {name}'**
  String welcomeBack(String name);

  /// No description provided for @welcomeBackAnonymous.
  ///
  /// In en, this message translates to:
  /// **'Welcome back'**
  String get welcomeBackAnonymous;

  /// No description provided for @workspaceName.
  ///
  /// In en, this message translates to:
  /// **'Workspace: {name}'**
  String workspaceName(String name);

  /// No description provided for @searchAgents.
  ///
  /// In en, this message translates to:
  /// **'Search your agents'**
  String get searchAgents;

  /// No description provided for @filtersSoon.
  ///
  /// In en, this message translates to:
  /// **'Filters land in the next mobile slice.'**
  String get filtersSoon;

  /// No description provided for @heroTitle.
  ///
  /// In en, this message translates to:
  /// **'All tenant agents, one app'**
  String get heroTitle;

  /// No description provided for @heroBody.
  ///
  /// In en, this message translates to:
  /// **'Jump into any agent with full account auth and Flutter-native performance.'**
  String get heroBody;

  /// No description provided for @retry.
  ///
  /// In en, this message translates to:
  /// **'Retry'**
  String get retry;

  /// No description provided for @spotlight.
  ///
  /// In en, this message translates to:
  /// **'Spotlight'**
  String get spotlight;

  /// No description provided for @allAgents.
  ///
  /// In en, this message translates to:
  /// **'All agents'**
  String get allAgents;

  /// No description provided for @runsCount.
  ///
  /// In en, this message translates to:
  /// **'{count, plural, one{{count} run} other{{count} runs}}'**
  String runsCount(int count);

  /// No description provided for @successPercent.
  ///
  /// In en, this message translates to:
  /// **'{percent}% success'**
  String successPercent(int percent);

  /// No description provided for @profileTitle.
  ///
  /// In en, this message translates to:
  /// **'Profile'**
  String get profileTitle;

  /// No description provided for @synkoraUser.
  ///
  /// In en, this message translates to:
  /// **'Synkora User'**
  String get synkoraUser;

  /// No description provided for @workspace.
  ///
  /// In en, this message translates to:
  /// **'Workspace'**
  String get workspace;

  /// No description provided for @role.
  ///
  /// In en, this message translates to:
  /// **'Role'**
  String get role;

  /// No description provided for @switchWorkspace.
  ///
  /// In en, this message translates to:
  /// **'Switch workspace'**
  String get switchWorkspace;

  /// No description provided for @switchWorkspaceHint.
  ///
  /// In en, this message translates to:
  /// **'Use a different tenant on this device'**
  String get switchWorkspaceHint;

  /// No description provided for @signOut.
  ///
  /// In en, this message translates to:
  /// **'Sign out'**
  String get signOut;

  /// No description provided for @signOutHint.
  ///
  /// In en, this message translates to:
  /// **'Clear the device session and return to login'**
  String get signOutHint;

  /// No description provided for @language.
  ///
  /// In en, this message translates to:
  /// **'Language'**
  String get language;

  /// No description provided for @languageSystem.
  ///
  /// In en, this message translates to:
  /// **'System default'**
  String get languageSystem;

  /// No description provided for @agentTitle.
  ///
  /// In en, this message translates to:
  /// **'Agent'**
  String get agentTitle;

  /// No description provided for @actionMessage.
  ///
  /// In en, this message translates to:
  /// **'Message'**
  String get actionMessage;

  /// No description provided for @actionTalk.
  ///
  /// In en, this message translates to:
  /// **'Talk'**
  String get actionTalk;

  /// No description provided for @actionScan.
  ///
  /// In en, this message translates to:
  /// **'Scan'**
  String get actionScan;

  /// No description provided for @capabilities.
  ///
  /// In en, this message translates to:
  /// **'Capabilities'**
  String get capabilities;

  /// No description provided for @recentSessions.
  ///
  /// In en, this message translates to:
  /// **'Recent mobile sessions'**
  String get recentSessions;

  /// No description provided for @noSessions.
  ///
  /// In en, this message translates to:
  /// **'No mobile sessions yet'**
  String get noSessions;

  /// No description provided for @noSessionsHint.
  ///
  /// In en, this message translates to:
  /// **'Start a fresh conversation from this agent.'**
  String get noSessionsHint;

  /// No description provided for @imageSelectionFailed.
  ///
  /// In en, this message translates to:
  /// **'Image selection failed: {error}'**
  String imageSelectionFailed(String error);

  /// No description provided for @scanAttachedHint.
  ///
  /// In en, this message translates to:
  /// **'Scan attached. Add instructions and send it to the agent.'**
  String get scanAttachedHint;

  /// No description provided for @scanAttachedSnack.
  ///
  /// In en, this message translates to:
  /// **'Scan attached. Add instructions and send.'**
  String get scanAttachedSnack;

  /// No description provided for @cameraScanFailed.
  ///
  /// In en, this message translates to:
  /// **'Camera scan failed: {error}'**
  String cameraScanFailed(String error);

  /// No description provided for @voiceStarting.
  ///
  /// In en, this message translates to:
  /// **'Voice input is still starting. Wait a moment.'**
  String get voiceStarting;

  /// No description provided for @speechRateLimitedHint.
  ///
  /// In en, this message translates to:
  /// **'Speech recognition is temporarily rate-limited by Android. Try again in {seconds}s.'**
  String speechRateLimitedHint(int seconds);

  /// No description provided for @speechCoolingDown.
  ///
  /// In en, this message translates to:
  /// **'Speech recognition is cooling down. Try again in {seconds}s.'**
  String speechCoolingDown(int seconds);

  /// No description provided for @voiceListening.
  ///
  /// In en, this message translates to:
  /// **'Listening... speak now. If the meter stays flat, the emulator is not receiving mic audio.'**
  String get voiceListening;

  /// No description provided for @voiceStartFailedHint.
  ///
  /// In en, this message translates to:
  /// **'Voice input failed to start. Wait a moment, then try again.'**
  String get voiceStartFailedHint;

  /// No description provided for @voiceStartFailedSnack.
  ///
  /// In en, this message translates to:
  /// **'Voice input failed to start: {error}'**
  String voiceStartFailedSnack(String error);

  /// No description provided for @speechUnavailable.
  ///
  /// In en, this message translates to:
  /// **'Speech recognition is not available on this device.'**
  String get speechUnavailable;

  /// No description provided for @voiceDraftReady.
  ///
  /// In en, this message translates to:
  /// **'Voice draft ready. Review it, then send.'**
  String get voiceDraftReady;

  /// No description provided for @audioDetected.
  ///
  /// In en, this message translates to:
  /// **'Audio detected. Keep speaking.'**
  String get audioDetected;

  /// No description provided for @androidRateLimitedHint.
  ///
  /// In en, this message translates to:
  /// **'Android speech recognition is rate-limited. Wait 15s, then try Talk again.'**
  String get androidRateLimitedHint;

  /// No description provided for @androidRateLimitedSnack.
  ///
  /// In en, this message translates to:
  /// **'Android speech recognition is rate-limited. Wait 15 seconds and try again.'**
  String get androidRateLimitedSnack;

  /// No description provided for @voiceUnavailable.
  ///
  /// In en, this message translates to:
  /// **'Voice input unavailable right now. You can keep typing.'**
  String get voiceUnavailable;

  /// No description provided for @voiceFailed.
  ///
  /// In en, this message translates to:
  /// **'Voice input failed: {error}'**
  String voiceFailed(String error);

  /// No description provided for @noTranscript.
  ///
  /// In en, this message translates to:
  /// **'Audio was detected, but Android returned no transcript. This emulator recognizer is unreliable.'**
  String get noTranscript;

  /// No description provided for @noSpeech.
  ///
  /// In en, this message translates to:
  /// **'No speech detected. Tap Talk and start speaking right away.'**
  String get noSpeech;

  /// No description provided for @tapTalkHint.
  ///
  /// In en, this message translates to:
  /// **'Tap Talk once to start voice input.'**
  String get tapTalkHint;

  /// No description provided for @noSupportedFiles.
  ///
  /// In en, this message translates to:
  /// **'No supported files were selected.'**
  String get noSupportedFiles;

  /// No description provided for @fileSelectionFailed.
  ///
  /// In en, this message translates to:
  /// **'File selection failed: {error}'**
  String fileSelectionFailed(String error);

  /// No description provided for @addMessageFirst.
  ///
  /// In en, this message translates to:
  /// **'Add a message before sending attachments.'**
  String get addMessageFirst;

  /// No description provided for @toolStatus.
  ///
  /// In en, this message translates to:
  /// **'{tool} • {status}'**
  String toolStatus(String tool, String status);

  /// No description provided for @toolDefaultName.
  ///
  /// In en, this message translates to:
  /// **'Agent'**
  String get toolDefaultName;

  /// No description provided for @toolDefaultStatus.
  ///
  /// In en, this message translates to:
  /// **'working'**
  String get toolDefaultStatus;

  /// No description provided for @agentError.
  ///
  /// In en, this message translates to:
  /// **'The agent returned an error.'**
  String get agentError;

  /// No description provided for @uploading.
  ///
  /// In en, this message translates to:
  /// **'Uploading {current}/{total} • {name}'**
  String uploading(int current, int total, String name);

  /// No description provided for @fileNotReadable.
  ///
  /// In en, this message translates to:
  /// **'Selected file \"{name}\" is not readable.'**
  String fileNotReadable(String name);

  /// No description provided for @freshConversation.
  ///
  /// In en, this message translates to:
  /// **'Fresh conversation'**
  String get freshConversation;

  /// No description provided for @voiceConversation.
  ///
  /// In en, this message translates to:
  /// **'Voice conversation'**
  String get voiceConversation;

  /// No description provided for @newChat.
  ///
  /// In en, this message translates to:
  /// **'New chat'**
  String get newChat;

  /// No description provided for @listening.
  ///
  /// In en, this message translates to:
  /// **'Listening'**
  String get listening;

  /// No description provided for @stopVoiceInput.
  ///
  /// In en, this message translates to:
  /// **'Stop voice input'**
  String get stopVoiceInput;

  /// No description provided for @attachImage.
  ///
  /// In en, this message translates to:
  /// **'Attach image'**
  String get attachImage;

  /// No description provided for @attachFile.
  ///
  /// In en, this message translates to:
  /// **'Attach file'**
  String get attachFile;

  /// No description provided for @messageHint.
  ///
  /// In en, this message translates to:
  /// **'Message this agent'**
  String get messageHint;

  /// No description provided for @attachmentsNeedMessage.
  ///
  /// In en, this message translates to:
  /// **'Add a message so the agent knows what to do with your attachments.'**
  String get attachmentsNeedMessage;

  /// No description provided for @emptyPromptStrengths.
  ///
  /// In en, this message translates to:
  /// **'Summarize what this agent is best at.'**
  String get emptyPromptStrengths;

  /// No description provided for @emptyPromptPlan.
  ///
  /// In en, this message translates to:
  /// **'Help me turn a rough task into a concrete plan.'**
  String get emptyPromptPlan;

  /// No description provided for @emptyPromptReview.
  ///
  /// In en, this message translates to:
  /// **'Review the latest context and tell me what needs attention.'**
  String get emptyPromptReview;

  /// No description provided for @emptyTitle.
  ///
  /// In en, this message translates to:
  /// **'Start a premium conversation with {agentName}'**
  String emptyTitle(String agentName);

  /// No description provided for @emptyBody.
  ///
  /// In en, this message translates to:
  /// **'Ask for structured analysis, send files, or drop in screenshots and let the agent work from real context.'**
  String get emptyBody;

  /// No description provided for @streaming.
  ///
  /// In en, this message translates to:
  /// **'Streaming'**
  String get streaming;

  /// No description provided for @voiceSemanticSpeaking.
  ///
  /// In en, this message translates to:
  /// **'Assistant is speaking. Double tap to interrupt.'**
  String get voiceSemanticSpeaking;

  /// No description provided for @voiceSemanticThinking.
  ///
  /// In en, this message translates to:
  /// **'Assistant is thinking. Double tap to cancel.'**
  String get voiceSemanticThinking;

  /// No description provided for @voiceSemanticListening.
  ///
  /// In en, this message translates to:
  /// **'Listening. Double tap to send what you said now.'**
  String get voiceSemanticListening;

  /// No description provided for @voiceSemanticError.
  ///
  /// In en, this message translates to:
  /// **'There was a problem. Double tap to retry.'**
  String get voiceSemanticError;

  /// No description provided for @voiceSemanticIdle.
  ///
  /// In en, this message translates to:
  /// **'Double tap to start talking.'**
  String get voiceSemanticIdle;

  /// No description provided for @close.
  ///
  /// In en, this message translates to:
  /// **'Close'**
  String get close;

  /// No description provided for @transcript.
  ///
  /// In en, this message translates to:
  /// **'Transcript'**
  String get transcript;

  /// No description provided for @voiceSettings.
  ///
  /// In en, this message translates to:
  /// **'Voice settings'**
  String get voiceSettings;

  /// No description provided for @voiceTitleWake.
  ///
  /// In en, this message translates to:
  /// **'Say “Hey Synkora”'**
  String get voiceTitleWake;

  /// No description provided for @voiceTitleTap.
  ///
  /// In en, this message translates to:
  /// **'Tap to talk'**
  String get voiceTitleTap;

  /// No description provided for @micMuted.
  ///
  /// In en, this message translates to:
  /// **'Mic is muted'**
  String get micMuted;

  /// No description provided for @listeningDots.
  ///
  /// In en, this message translates to:
  /// **'Listening…'**
  String get listeningDots;

  /// No description provided for @imListening.
  ///
  /// In en, this message translates to:
  /// **'I’m listening'**
  String get imListening;

  /// No description provided for @thinkingTitle.
  ///
  /// In en, this message translates to:
  /// **'Thinking…'**
  String get thinkingTitle;

  /// No description provided for @speakingTitle.
  ///
  /// In en, this message translates to:
  /// **'Speaking'**
  String get speakingTitle;

  /// No description provided for @somethingWrong.
  ///
  /// In en, this message translates to:
  /// **'Something went wrong'**
  String get somethingWrong;

  /// No description provided for @turnOnVoice.
  ///
  /// In en, this message translates to:
  /// **'Turn on voice'**
  String get turnOnVoice;

  /// No description provided for @usePhoneVoice.
  ///
  /// In en, this message translates to:
  /// **'Use my phone’s voice'**
  String get usePhoneVoice;

  /// No description provided for @tryAgain.
  ///
  /// In en, this message translates to:
  /// **'Try again'**
  String get tryAgain;

  /// No description provided for @unmuteMic.
  ///
  /// In en, this message translates to:
  /// **'Unmute microphone'**
  String get unmuteMic;

  /// No description provided for @muteMic.
  ///
  /// In en, this message translates to:
  /// **'Mute microphone'**
  String get muteMic;

  /// No description provided for @endConversation.
  ///
  /// In en, this message translates to:
  /// **'End conversation'**
  String get endConversation;

  /// No description provided for @typeMessage.
  ///
  /// In en, this message translates to:
  /// **'Type a message'**
  String get typeMessage;

  /// No description provided for @typeInstead.
  ///
  /// In en, this message translates to:
  /// **'Type instead…'**
  String get typeInstead;

  /// No description provided for @send.
  ///
  /// In en, this message translates to:
  /// **'Send'**
  String get send;

  /// No description provided for @talkTo.
  ///
  /// In en, this message translates to:
  /// **'Talk to'**
  String get talkTo;

  /// No description provided for @noOtherAgents.
  ///
  /// In en, this message translates to:
  /// **'No other agents yet.'**
  String get noOtherAgents;

  /// No description provided for @transcriptEmpty.
  ///
  /// In en, this message translates to:
  /// **'Nothing yet. Start talking and your conversation will appear here.'**
  String get transcriptEmpty;

  /// No description provided for @interrupted.
  ///
  /// In en, this message translates to:
  /// **'Interrupted'**
  String get interrupted;

  /// No description provided for @wakeTitle.
  ///
  /// In en, this message translates to:
  /// **'Wake with “Hey Synkora”'**
  String get wakeTitle;

  /// No description provided for @wakeSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Listens for the phrase while Synkora is open, so you can talk hands-free. Audio is checked on your phone and is only sent once you start speaking.'**
  String get wakeSubtitle;

  /// No description provided for @interruptTitle.
  ///
  /// In en, this message translates to:
  /// **'Interrupt by speaking'**
  String get interruptTitle;

  /// No description provided for @interruptSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Talk over the assistant to cut it off.'**
  String get interruptSubtitle;

  /// No description provided for @soundsTitle.
  ///
  /// In en, this message translates to:
  /// **'Sounds'**
  String get soundsTitle;

  /// No description provided for @soundsSubtitle.
  ///
  /// In en, this message translates to:
  /// **'A soft chime when it wakes or finishes.'**
  String get soundsSubtitle;

  /// No description provided for @hapticsTitle.
  ///
  /// In en, this message translates to:
  /// **'Haptics'**
  String get hapticsTitle;

  /// No description provided for @hapticsSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Gentle taps at key moments.'**
  String get hapticsSubtitle;

  /// No description provided for @speakingSpeed.
  ///
  /// In en, this message translates to:
  /// **'Speaking speed  ·  {speed}×'**
  String speakingSpeed(String speed);

  /// No description provided for @wakeLow.
  ///
  /// In en, this message translates to:
  /// **'Fewer wakes'**
  String get wakeLow;

  /// No description provided for @wakeBalanced.
  ///
  /// In en, this message translates to:
  /// **'Balanced'**
  String get wakeBalanced;

  /// No description provided for @wakeHigh.
  ///
  /// In en, this message translates to:
  /// **'Catch more'**
  String get wakeHigh;

  /// No description provided for @wakeSensitivity.
  ///
  /// In en, this message translates to:
  /// **'Wake sensitivity'**
  String get wakeSensitivity;

  /// No description provided for @wakeHelp.
  ///
  /// In en, this message translates to:
  /// **'If it wakes when you did not say it, choose “Fewer wakes”. If it misses you, choose “Catch more”.'**
  String get wakeHelp;

  /// No description provided for @wakeUnavailable.
  ///
  /// In en, this message translates to:
  /// **'“Hey Synkora” is unavailable on this device right now. You can still tap the orb to talk.\n{message}'**
  String wakeUnavailable(String message);

  /// No description provided for @talkToAgents.
  ///
  /// In en, this message translates to:
  /// **'Talk to your agents'**
  String get talkToAgents;

  /// No description provided for @talkToAgent.
  ///
  /// In en, this message translates to:
  /// **'Talk to {name}'**
  String talkToAgent(String name);

  /// No description provided for @handsFreeOn.
  ///
  /// In en, this message translates to:
  /// **'Hands-free is on. Just say “Hey Synkora”.'**
  String get handsFreeOn;

  /// No description provided for @startVoice.
  ///
  /// In en, this message translates to:
  /// **'Have a real voice conversation. Tap to start.'**
  String get startVoice;
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['de', 'en'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'de':
      return AppLocalizationsDe();
    case 'en':
      return AppLocalizationsEn();
  }

  throw FlutterError(
    'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
    'an issue with the localizations generation tool. Please file an issue '
    'on GitHub with a reproducible sample app and the gen-l10n configuration '
    'that was used.',
  );
}
