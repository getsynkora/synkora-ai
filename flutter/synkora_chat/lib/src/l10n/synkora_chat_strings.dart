import 'package:flutter/widgets.dart';

/// Every piece of fixed text the chat shows, for one language.
///
/// English and German are built in. Pick one with
/// `SynkoraChatWidget(locale: Locale('de'))`, or leave `locale` empty to follow
/// the host app's language. Text that comes from the widget configuration on the
/// server (title, welcome message, suggested prompts) is translated there instead.
///
/// To change a few words, or add a language, build your own table. Anything you
/// leave out falls back to English:
///
/// ```dart
/// SynkoraChatWidget(
///   locale: const Locale('fr'),
///   strings: SynkoraChatStrings.custom('fr', {
///     'cancel': 'Annuler',
///     'message_placeholder': 'Écrivez un message…',
///   }),
/// )
/// ```
class SynkoraChatStrings {
  const SynkoraChatStrings._(this.languageCode, this._table);

  /// A table for [languageCode] with your own text in [overrides]; keys you do not
  /// set come from [base] (English unless you pass another table).
  factory SynkoraChatStrings.custom(
    String languageCode,
    Map<String, String> overrides, {
    SynkoraChatStrings? base,
  }) {
    return SynkoraChatStrings._(languageCode, {
      ...(base ?? en)._table,
      ...overrides,
    });
  }

  /// ISO 639-1 code of this table, e.g. `de`.
  final String languageCode;
  final Map<String, String> _table;

  static const List<String> supportedLanguageCodes = ['en', 'de'];

  /// The built-in table for [locale]'s language, or English if there is none.
  static SynkoraChatStrings forLocale(Locale locale) =>
      _builtIn[locale.languageCode.toLowerCase()] ?? en;

  /// The strings of the nearest [SynkoraChatStringsScope] (English outside one).
  static SynkoraChatStrings of(BuildContext context) =>
      context
          .dependOnInheritedWidgetOfExactType<SynkoraChatStringsScope>()
          ?.strings ??
      en;

  /// Keys every built-in table defines (used by tests to keep languages in sync).
  Iterable<String> get keys => _table.keys;

  /// The raw text for [key] with its `{placeholders}` unfilled, or null if this
  /// table does not define it.
  String? template(String key) => _table[key];

  String _t(String key, [Map<String, String> args = const {}]) {
    var text = _table[key] ?? en._table[key] ?? key;
    args.forEach((name, value) => text = text.replaceAll('{$name}', value));
    return text;
  }

  // Header and navigation
  String get newChat => _t('new_chat');
  String get navHome => _t('nav_home');
  String get navChat => _t('nav_chat');
  String get headerBeforeWeStart => _t('before_we_start');
  String get headerConnectedToSupport => _t('connected_to_support');
  String get headerWaitingForApproval => _t('waiting_for_approval');
  String get headerOnline => _t('online');
  String get headerReadyToChat => _t('ready_to_chat');
  String get headerYourConversations => _t('your_conversations');
  String get headerWelcome => _t('welcome');
  String get defaultAgentName => _t('default_agent_name');

  // Home screen
  String get greetingFallback => _t('greeting_fallback');
  String get subGreetingFallback => _t('sub_greeting_fallback');
  String get startNewConversation => _t('start_new_conversation');
  String get replyTime => _t('reply_time');
  String get recentMessage => _t('recent_message');
  String get conversation => _t('conversation');
  String get faqs => _t('faqs');

  // Sessions
  String get noPreviousSessions => _t('no_previous_sessions');
  String get startNewChatToBegin => _t('start_new_chat_to_begin');
  String get sessionActive => _t('session_active');
  String get sessionClosed => _t('session_closed');
  String get endSession => _t('end_session');

  // Clear-chat dialog
  String get clearChatTitle => _t('clear_chat_title');
  String get clearChatBody => _t('clear_chat_body');
  String get cancel => _t('cancel');
  String get clear => _t('clear');

  // Pre-chat form
  String get preChatIntro => _t('pre_chat_intro');
  String get nameLabel => _t('name_label');
  String get nameHint => _t('name_hint');
  String get emailLabel => _t('email_label');
  String get emailHint => _t('email_hint');
  String get phoneLabel => _t('phone_label');
  String get startChatting => _t('start_chatting');
  String get skip => _t('skip');

  // Conversation
  String get messagePlaceholder => _t('message_placeholder');
  String get askMeAnything => _t('ask_me_anything');
  String get askMeAnythingBody => _t('ask_me_anything_body');
  String get browseSuggestions => _t('browse_suggestions');
  String get chatClosed => _t('chat_closed');
  String get conversationReadOnly => _t('conversation_read_only');
  String get handoffBanner => _t('handoff_banner');
  String get supportSessionEnded => _t('support_session_ended');
  String get you => _t('you');
  String get support => _t('support');
  String poweredBy(String name) => _t('powered_by', {'name': name});

  // Tool approval
  String get approvalRequired => _t('approval_required');
  String approvalBody(String tool) => _t('approval_body', {'tool': tool});
  String toolLabel(String tool) => _t('tool_label', {'tool': tool});
  String expiresLabel(String when) => _t('expires_label', {'when': when});
  String get approve => _t('approve');
  String get reject => _t('reject');

  // Connection errors
  String get connectionIssue => _t('connection_issue');
  String expectedUrl(String url) => _t('expected_url', {'url': url});
  String get retryConnection => _t('retry_connection');

  // Relative times
  String get now => _t('now');
  String minutesAgo(int minutes) => _t('minutes', {'n': '$minutes'});
  String hoursAgo(int hours) => _t('hours', {'n': '$hours'});
  String daysAgo(int days) => _t('days', {'n': '$days'});
  String weeksAgo(int weeks) => _t('weeks', {'n': '$weeks'});

  static final SynkoraChatStrings en = SynkoraChatStrings._('en', {
    'new_chat': 'New chat',
    'nav_home': 'Home',
    'nav_chat': 'Chat',
    'before_we_start': 'Before we start',
    'connected_to_support': 'Connected to support',
    'waiting_for_approval': 'Waiting for approval',
    'online': 'Online',
    'ready_to_chat': 'Ready to chat',
    'your_conversations': 'Your conversations',
    'welcome': 'Welcome',
    'default_agent_name': 'Assistant',
    'greeting_fallback': 'Hello there',
    'sub_greeting_fallback': 'How can we help?',
    'start_new_conversation': 'Start new conversation',
    'reply_time': 'Typically reply within few moments',
    'recent_message': 'Recent message',
    'conversation': 'Conversation',
    'faqs': 'FAQs',
    'no_previous_sessions': 'No previous sessions',
    'start_new_chat_to_begin': 'Start a new chat to begin',
    'session_active': 'Active',
    'session_closed': 'Closed',
    'end_session': 'End',
    'clear_chat_title': 'Clear current chat',
    'clear_chat_body':
        'This starts a fresh local chat. Server-side history is kept.',
    'cancel': 'Cancel',
    'clear': 'Clear',
    'pre_chat_intro':
        'Share a bit about yourself so we can help you better. All fields are optional.',
    'name_label': 'Name',
    'name_hint': 'Your name',
    'email_label': 'Email',
    'email_hint': 'you@example.com',
    'phone_label': 'Phone',
    'start_chatting': 'Start chatting',
    'skip': 'Skip',
    'message_placeholder': 'Type a message...',
    'ask_me_anything': 'Ask me anything',
    'ask_me_anything_body':
        'Type a message below or go back to browse suggested prompts.',
    'browse_suggestions': 'Browse suggestions',
    'chat_closed': 'Chat closed',
    'conversation_read_only': 'The conversation is read only',
    'handoff_banner': 'Connected to support — the agent is paused',
    'support_session_ended': 'Support session ended',
    'you': 'You',
    'support': 'Support',
    'powered_by': 'Powered by {name}',
    'approval_required': 'Approval required',
    'approval_body': 'The agent wants to run "{tool}" and needs your approval.',
    'tool_label': 'Tool: {tool}',
    'expires_label': 'Expires: {when}',
    'approve': 'Approve',
    'reject': 'Reject',
    'connection_issue': 'Connection issue',
    'expected_url': 'Expected: {url}',
    'retry_connection': 'Retry connection',
    'now': 'Now',
    'minutes': '{n} min',
    'hours': '{n}hr',
    'days': '{n}d',
    'weeks': '{n}w',
  });

  /// German, formal address ("Sie").
  static final SynkoraChatStrings de = SynkoraChatStrings._('de', {
    'new_chat': 'Neuer Chat',
    'nav_home': 'Start',
    'nav_chat': 'Chat',
    'before_we_start': 'Bevor wir starten',
    'connected_to_support': 'Mit dem Support verbunden',
    'waiting_for_approval': 'Warten auf Freigabe',
    'online': 'Online',
    'ready_to_chat': 'Bereit zum Chatten',
    'your_conversations': 'Ihre Unterhaltungen',
    'welcome': 'Willkommen',
    'default_agent_name': 'Assistent',
    'greeting_fallback': 'Hallo!',
    'sub_greeting_fallback': 'Wie können wir helfen?',
    'start_new_conversation': 'Neue Unterhaltung starten',
    'reply_time': 'Antwortet in der Regel innerhalb weniger Augenblicke',
    'recent_message': 'Letzte Nachricht',
    'conversation': 'Unterhaltung',
    'faqs': 'Häufige Fragen',
    'no_previous_sessions': 'Noch keine Unterhaltungen',
    'start_new_chat_to_begin': 'Starten Sie einen neuen Chat, um zu beginnen',
    'session_active': 'Aktiv',
    'session_closed': 'Geschlossen',
    'end_session': 'Beenden',
    'clear_chat_title': 'Aktuellen Chat leeren',
    'clear_chat_body':
        'Dadurch wird ein neuer lokaler Chat gestartet. Der Verlauf auf dem Server bleibt erhalten.',
    'cancel': 'Abbrechen',
    'clear': 'Leeren',
    'pre_chat_intro':
        'Erzählen Sie uns ein wenig über sich, damit wir Ihnen besser helfen können. Alle Angaben sind freiwillig.',
    'name_label': 'Name',
    'name_hint': 'Ihr Name',
    'email_label': 'E-Mail',
    'email_hint': 'sie@beispiel.de',
    'phone_label': 'Telefon',
    'start_chatting': 'Chat starten',
    'skip': 'Überspringen',
    'message_placeholder': 'Nachricht eingeben …',
    'ask_me_anything': 'Fragen Sie mich alles',
    'ask_me_anything_body':
        'Geben Sie unten eine Nachricht ein oder gehen Sie zurück, um Vorschläge anzusehen.',
    'browse_suggestions': 'Vorschläge ansehen',
    'chat_closed': 'Chat geschlossen',
    'conversation_read_only': 'Diese Unterhaltung ist schreibgeschützt',
    'handoff_banner': 'Mit dem Support verbunden – der Agent ist pausiert',
    'support_session_ended': 'Support-Sitzung beendet',
    'you': 'Sie',
    'support': 'Support',
    'powered_by': 'Bereitgestellt von {name}',
    'approval_required': 'Freigabe erforderlich',
    'approval_body':
        'Der Agent möchte „{tool}“ ausführen und benötigt Ihre Freigabe.',
    'tool_label': 'Tool: {tool}',
    'expires_label': 'Läuft ab: {when}',
    'approve': 'Freigeben',
    'reject': 'Ablehnen',
    'connection_issue': 'Verbindungsproblem',
    'expected_url': 'Erwartet: {url}',
    'retry_connection': 'Verbindung erneut versuchen',
    'now': 'Jetzt',
    'minutes': '{n} Min.',
    'hours': '{n} Std.',
    'days': '{n} T.',
    'weeks': '{n} Wo.',
  });

  static final Map<String, SynkoraChatStrings> _builtIn = {
    'en': en,
    'de': de,
  };
}

/// Makes [strings] the text of every chat widget below it.
class SynkoraChatStringsScope extends InheritedWidget {
  const SynkoraChatStringsScope({
    super.key,
    required this.strings,
    required super.child,
  });

  final SynkoraChatStrings strings;

  @override
  bool updateShouldNotify(SynkoraChatStringsScope oldWidget) =>
      oldWidget.strings != strings;
}
