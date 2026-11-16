// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for German (`de`).
class AppLocalizationsDe extends AppLocalizations {
  AppLocalizationsDe([String locale = 'de']) : super(locale);

  @override
  String get appTitle => 'Synkora AI';

  @override
  String get signInTitle => 'Synkora AI';

  @override
  String get signInSubtitle =>
      'Nutzen Sie jeden Agenten Ihres Arbeitsbereichs in einer eigenen nativen App.';

  @override
  String get email => 'E-Mail';

  @override
  String get password => 'Passwort';

  @override
  String get signIn => 'Anmelden';

  @override
  String get orContinueWith => 'oder weiter mit';

  @override
  String get continueWithGoogle => 'Weiter mit Google';

  @override
  String get signInFootnote =>
      'Diese App verwendet dasselbe Synkora-Konto und dasselbe Zugriffsmodell für Workspaces wie die Web-App.';

  @override
  String get chooseWorkspace => 'Workspace wählen';

  @override
  String get chooseWorkspaceBody =>
      'Ihr Konto hat Zugriff auf mehrere Synkora-Workspaces. Wählen Sie den, den Sie mobil nutzen möchten.';

  @override
  String get bootBranding => 'Powered by Synkora';

  @override
  String get bootLoading =>
      'Ihr Workspace, Ihre Agenten und Aktionen werden geladen.';

  @override
  String get signInCancelled =>
      'Die Anmeldung wurde abgebrochen oder konnte nicht abgeschlossen werden.';

  @override
  String get signInNotCompleted => 'Die Anmeldung wurde nicht abgeschlossen.';

  @override
  String get authRequestFailed => 'Die Anmeldeanfrage ist fehlgeschlagen.';

  @override
  String get workspaceNotFound =>
      'Der ausgewählte Workspace wurde nicht gefunden.';

  @override
  String get sessionIncomplete =>
      'Ihre Sitzung ist unvollständig. Bitte melden Sie sich erneut an.';

  @override
  String streamFailed(String error) {
    return 'Die Antwort des Agenten konnte nicht übertragen werden: $error';
  }

  @override
  String get authRequired => 'Anmeldung erforderlich.';

  @override
  String get networkError => 'Unerwarteter Netzwerkfehler';

  @override
  String get timeJustNow => 'Gerade eben';

  @override
  String timeMinutesAgo(int count) {
    return 'vor $count Min.';
  }

  @override
  String timeHoursAgo(int count) {
    return 'vor $count Std.';
  }

  @override
  String timeDaysAgo(int count) {
    return 'vor $count T.';
  }

  @override
  String get unknown => 'Unbekannt';

  @override
  String get navAgents => 'Agenten';

  @override
  String get navInbox => 'Posteingang';

  @override
  String get navActivity => 'Aktivität';

  @override
  String get navProfile => 'Profil';

  @override
  String get inboxSubtitle =>
      'Push-Antworten, Freigaben und Abschlüsse erscheinen hier.';

  @override
  String get activitySubtitle =>
      'Betriebsaktivität und Arbeitsprotokolle der Agenten erscheinen hier.';

  @override
  String welcomeBack(String name) {
    return 'Willkommen zurück, $name';
  }

  @override
  String get welcomeBackAnonymous => 'Willkommen zurück';

  @override
  String workspaceName(String name) {
    return 'Workspace: $name';
  }

  @override
  String get searchAgents => 'Agenten durchsuchen';

  @override
  String get filtersSoon => 'Filter folgen im nächsten Mobile-Update.';

  @override
  String get heroTitle => 'Alle Agenten Ihres Workspaces in einer App';

  @override
  String get heroBody =>
      'Springen Sie in jeden Agenten – mit vollständiger Kontoanmeldung und nativer Flutter-Performance.';

  @override
  String get retry => 'Erneut versuchen';

  @override
  String get spotlight => 'Im Fokus';

  @override
  String get allAgents => 'Alle Agenten';

  @override
  String runsCount(int count) {
    String _temp0 = intl.Intl.pluralLogic(
      count,
      locale: localeName,
      other: '$count Ausführungen',
      one: '$count Ausführung',
    );
    return '$_temp0';
  }

  @override
  String successPercent(int percent) {
    return '$percent% erfolgreich';
  }

  @override
  String get profileTitle => 'Profil';

  @override
  String get synkoraUser => 'Synkora-Nutzer';

  @override
  String get workspace => 'Workspace';

  @override
  String get role => 'Rolle';

  @override
  String get switchWorkspace => 'Workspace wechseln';

  @override
  String get switchWorkspaceHint =>
      'Einen anderen Workspace auf diesem Gerät verwenden';

  @override
  String get signOut => 'Abmelden';

  @override
  String get signOutHint =>
      'Geräte-Sitzung beenden und zur Anmeldung zurückkehren';

  @override
  String get language => 'Sprache';

  @override
  String get languageSystem => 'Systemstandard';

  @override
  String get agentTitle => 'Agent';

  @override
  String get actionMessage => 'Nachricht';

  @override
  String get actionTalk => 'Sprechen';

  @override
  String get actionScan => 'Scannen';

  @override
  String get capabilities => 'Fähigkeiten';

  @override
  String get recentSessions => 'Letzte mobile Unterhaltungen';

  @override
  String get noSessions => 'Noch keine mobilen Unterhaltungen';

  @override
  String get noSessionsHint =>
      'Starten Sie mit diesem Agenten eine neue Unterhaltung.';

  @override
  String imageSelectionFailed(String error) {
    return 'Bildauswahl fehlgeschlagen: $error';
  }

  @override
  String get scanAttachedHint =>
      'Scan angehängt. Fügen Sie Anweisungen hinzu und senden Sie ihn an den Agenten.';

  @override
  String get scanAttachedSnack =>
      'Scan angehängt. Anweisungen hinzufügen und senden.';

  @override
  String cameraScanFailed(String error) {
    return 'Kamerascan fehlgeschlagen: $error';
  }

  @override
  String get voiceStarting =>
      'Die Spracheingabe startet noch. Einen Moment bitte.';

  @override
  String speechRateLimitedHint(int seconds) {
    return 'Die Spracherkennung wird von Android vorübergehend gedrosselt. Versuchen Sie es in $seconds s erneut.';
  }

  @override
  String speechCoolingDown(int seconds) {
    return 'Die Spracherkennung pausiert kurz. Versuchen Sie es in $seconds s erneut.';
  }

  @override
  String get voiceListening =>
      'Ich höre zu … Sie können sprechen. Bleibt die Anzeige flach, empfängt der Emulator kein Mikrofonsignal.';

  @override
  String get voiceStartFailedHint =>
      'Die Spracheingabe konnte nicht gestartet werden. Warten Sie kurz und versuchen Sie es erneut.';

  @override
  String voiceStartFailedSnack(String error) {
    return 'Die Spracheingabe konnte nicht gestartet werden: $error';
  }

  @override
  String get speechUnavailable =>
      'Die Spracherkennung ist auf diesem Gerät nicht verfügbar.';

  @override
  String get voiceDraftReady =>
      'Spracheingabe als Entwurf bereit. Prüfen Sie ihn und senden Sie ihn ab.';

  @override
  String get audioDetected => 'Ton erkannt. Sprechen Sie weiter.';

  @override
  String get androidRateLimitedHint =>
      'Die Android-Spracherkennung wird gedrosselt. Warten Sie 15 s und tippen Sie dann erneut auf Sprechen.';

  @override
  String get androidRateLimitedSnack =>
      'Die Android-Spracherkennung wird gedrosselt. Warten Sie 15 Sekunden und versuchen Sie es erneut.';

  @override
  String get voiceUnavailable =>
      'Die Spracheingabe ist derzeit nicht verfügbar. Sie können weiter tippen.';

  @override
  String voiceFailed(String error) {
    return 'Spracheingabe fehlgeschlagen: $error';
  }

  @override
  String get noTranscript =>
      'Es wurde Ton erkannt, aber Android lieferte kein Transkript. Der Erkenner im Emulator ist unzuverlässig.';

  @override
  String get noSpeech =>
      'Keine Sprache erkannt. Tippen Sie auf Sprechen und fangen Sie sofort an zu sprechen.';

  @override
  String get tapTalkHint =>
      'Tippen Sie einmal auf Sprechen, um die Spracheingabe zu starten.';

  @override
  String get noSupportedFiles =>
      'Es wurden keine unterstützten Dateien ausgewählt.';

  @override
  String fileSelectionFailed(String error) {
    return 'Dateiauswahl fehlgeschlagen: $error';
  }

  @override
  String get addMessageFirst =>
      'Fügen Sie eine Nachricht hinzu, bevor Sie Anhänge senden.';

  @override
  String toolStatus(String tool, String status) {
    return '$tool • $status';
  }

  @override
  String get toolDefaultName => 'Agent';

  @override
  String get toolDefaultStatus => 'arbeitet';

  @override
  String get agentError => 'Der Agent hat einen Fehler gemeldet.';

  @override
  String uploading(int current, int total, String name) {
    return 'Hochladen $current/$total • $name';
  }

  @override
  String fileNotReadable(String name) {
    return 'Die ausgewählte Datei „$name“ ist nicht lesbar.';
  }

  @override
  String get freshConversation => 'Neue Unterhaltung';

  @override
  String get voiceConversation => 'Sprachunterhaltung';

  @override
  String get newChat => 'Neuer Chat';

  @override
  String get listening => 'Hört zu';

  @override
  String get stopVoiceInput => 'Spracheingabe beenden';

  @override
  String get attachImage => 'Bild anhängen';

  @override
  String get attachFile => 'Datei anhängen';

  @override
  String get messageHint => 'Nachricht an diesen Agenten';

  @override
  String get attachmentsNeedMessage =>
      'Fügen Sie eine Nachricht hinzu, damit der Agent weiß, was er mit Ihren Anhängen tun soll.';

  @override
  String get emptyPromptStrengths =>
      'Fasse zusammen, worin dieser Agent am besten ist.';

  @override
  String get emptyPromptPlan =>
      'Hilf mir, aus einer groben Aufgabe einen konkreten Plan zu machen.';

  @override
  String get emptyPromptReview =>
      'Prüfe den aktuellen Kontext und sag mir, was Aufmerksamkeit braucht.';

  @override
  String emptyTitle(String agentName) {
    return 'Starten Sie eine Premium-Unterhaltung mit $agentName';
  }

  @override
  String get emptyBody =>
      'Bitten Sie um strukturierte Analysen, senden Sie Dateien oder Screenshots und lassen Sie den Agenten mit echtem Kontext arbeiten.';

  @override
  String get streaming => 'Wird geschrieben';

  @override
  String get voiceSemanticSpeaking =>
      'Der Assistent spricht. Zum Unterbrechen doppelt tippen.';

  @override
  String get voiceSemanticThinking =>
      'Der Assistent denkt nach. Zum Abbrechen doppelt tippen.';

  @override
  String get voiceSemanticListening =>
      'Ich höre zu. Doppelt tippen, um das Gesagte jetzt zu senden.';

  @override
  String get voiceSemanticError =>
      'Es gab ein Problem. Zum Wiederholen doppelt tippen.';

  @override
  String get voiceSemanticIdle => 'Doppelt tippen, um zu sprechen.';

  @override
  String get close => 'Schließen';

  @override
  String get transcript => 'Transkript';

  @override
  String get voiceSettings => 'Spracheinstellungen';

  @override
  String get voiceTitleWake => 'Sagen Sie „Hey Synkora“';

  @override
  String get voiceTitleTap => 'Zum Sprechen tippen';

  @override
  String get micMuted => 'Mikrofon stummgeschaltet';

  @override
  String get listeningDots => 'Hört zu …';

  @override
  String get imListening => 'Ich höre zu';

  @override
  String get thinkingTitle => 'Denkt nach …';

  @override
  String get speakingTitle => 'Spricht';

  @override
  String get somethingWrong => 'Etwas ist schiefgelaufen';

  @override
  String get turnOnVoice => 'Sprache einschalten';

  @override
  String get usePhoneVoice => 'Stimme meines Telefons nutzen';

  @override
  String get tryAgain => 'Erneut versuchen';

  @override
  String get unmuteMic => 'Mikrofon einschalten';

  @override
  String get muteMic => 'Mikrofon stummschalten';

  @override
  String get endConversation => 'Unterhaltung beenden';

  @override
  String get typeMessage => 'Nachricht tippen';

  @override
  String get typeInstead => 'Stattdessen tippen …';

  @override
  String get send => 'Senden';

  @override
  String get talkTo => 'Sprechen mit';

  @override
  String get noOtherAgents => 'Noch keine weiteren Agenten.';

  @override
  String get transcriptEmpty =>
      'Noch nichts. Fangen Sie an zu sprechen, dann erscheint Ihre Unterhaltung hier.';

  @override
  String get interrupted => 'Unterbrochen';

  @override
  String get wakeTitle => 'Mit „Hey Synkora“ aufwecken';

  @override
  String get wakeSubtitle =>
      'Hört auf die Wortfolge, solange Synkora geöffnet ist, damit Sie freihändig sprechen können. Das Audio wird auf Ihrem Telefon geprüft und erst gesendet, wenn Sie zu sprechen beginnen.';

  @override
  String get interruptTitle => 'Durch Sprechen unterbrechen';

  @override
  String get interruptSubtitle =>
      'Sprechen Sie dazwischen, um den Assistenten zu unterbrechen.';

  @override
  String get soundsTitle => 'Töne';

  @override
  String get soundsSubtitle => 'Ein sanfter Ton beim Aufwachen und Beenden.';

  @override
  String get hapticsTitle => 'Haptik';

  @override
  String get hapticsSubtitle => 'Sanfte Vibrationen an wichtigen Stellen.';

  @override
  String speakingSpeed(String speed) {
    return 'Sprechtempo  ·  $speed×';
  }

  @override
  String get wakeLow => 'Weniger Aktivierungen';

  @override
  String get wakeBalanced => 'Ausgewogen';

  @override
  String get wakeHigh => 'Mehr erkennen';

  @override
  String get wakeSensitivity => 'Empfindlichkeit';

  @override
  String get wakeHelp =>
      'Wenn es ohne Ihr Zutun aufwacht, wählen Sie „Weniger Aktivierungen“. Wenn es Sie überhört, wählen Sie „Mehr erkennen“.';

  @override
  String wakeUnavailable(String message) {
    return '„Hey Synkora“ ist auf diesem Gerät derzeit nicht verfügbar. Sie können weiterhin auf die Kugel tippen, um zu sprechen.\n$message';
  }

  @override
  String get talkToAgents => 'Mit Ihren Agenten sprechen';

  @override
  String talkToAgent(String name) {
    return 'Mit $name sprechen';
  }

  @override
  String get handsFreeOn =>
      'Freihändig ist aktiv. Sagen Sie einfach „Hey Synkora“.';

  @override
  String get startVoice =>
      'Führen Sie ein echtes Sprachgespräch. Zum Starten tippen.';
}
