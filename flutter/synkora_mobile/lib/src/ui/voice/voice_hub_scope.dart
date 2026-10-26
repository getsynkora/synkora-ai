import 'package:flutter/widgets.dart';

import '../../voice/voice_hub.dart';

/// Makes the app's [VoiceHub] available to any screen below it.
class VoiceHubScope extends InheritedWidget {
  const VoiceHubScope({super.key, required this.hub, required super.child});

  final VoiceHub hub;

  static VoiceHub? maybeOf(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<VoiceHubScope>()?.hub;

  @override
  bool updateShouldNotify(VoiceHubScope oldWidget) => hub != oldWidget.hub;
}
