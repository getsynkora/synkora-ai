import 'package:audio_session/audio_session.dart';

/// Configures the OS audio session for a spoken conversation.
///
/// Voice-chat mode turns on the platform's echo cancellation and noise
/// suppression, which is what lets the user talk over the assistant without it
/// hearing itself. It also routes to the loudspeaker by default and allows
/// Bluetooth headsets.
///
/// Recording and playback must share this one session: the recorder is told not
/// to manage the session itself (see `RecordMic`), otherwise it resets the mode.
Future<void> configureVoiceAudioSession() async {
  final session = await AudioSession.instance;
  await session.configure(
    AudioSessionConfiguration(
      avAudioSessionCategory: AVAudioSessionCategory.playAndRecord,
      avAudioSessionCategoryOptions:
          AVAudioSessionCategoryOptions.allowBluetooth |
          AVAudioSessionCategoryOptions.allowBluetoothA2dp |
          AVAudioSessionCategoryOptions.defaultToSpeaker,
      avAudioSessionMode: AVAudioSessionMode.voiceChat,
      androidAudioAttributes: const AndroidAudioAttributes(
        contentType: AndroidAudioContentType.speech,
        usage: AndroidAudioUsage.voiceCommunication,
      ),
      androidAudioFocusGainType: AndroidAudioFocusGainType.gain,
      androidWillPauseWhenDucked: false,
    ),
  );
  await session.setActive(true);
}

Future<void> releaseVoiceAudioSession() async {
  final session = await AudioSession.instance;
  await session.setActive(false);
}
