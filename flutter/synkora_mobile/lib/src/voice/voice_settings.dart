import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'wake/wake_keywords.dart';

/// User preferences for voice, persisted on the device.
class VoiceSettings extends ChangeNotifier {
  VoiceSettings._(this._prefs);

  final SharedPreferences _prefs;

  static const _wakeKey = 'voice.wakeEnabled';
  static const _speedKey = 'voice.speed';
  static const _sensitivityKey = 'voice.wakeSensitivity';
  static const _soundsKey = 'voice.cueSounds';
  static const _hapticsKey = 'voice.cueHaptics';
  static const _bargeInKey = 'voice.bargeIn';
  static const _lastAgentKey = 'voice.lastAgentId';

  static Future<VoiceSettings> load([SharedPreferences? prefs]) async =>
      VoiceSettings._(prefs ?? await SharedPreferences.getInstance());

  /// Listen for "Hey Synkora" while the app is open. Off by default because it
  /// keeps the microphone running.
  bool get wakeEnabled => _prefs.getBool(_wakeKey) ?? false;

  /// How eagerly "Hey Synkora" triggers.
  WakeSensitivity get wakeSensitivity {
    final index = _prefs.getInt(_sensitivityKey);
    if (index == null || index < 0 || index >= WakeSensitivity.values.length) {
      return WakeSensitivity.balanced;
    }
    return WakeSensitivity.values[index];
  }

  /// How fast the assistant speaks, 0.8 to 1.4 (1.0 is normal).
  double get speed => (_prefs.getDouble(_speedKey) ?? 1.0).clamp(0.8, 1.4);

  bool get cueSounds => _prefs.getBool(_soundsKey) ?? true;
  bool get cueHaptics => _prefs.getBool(_hapticsKey) ?? true;

  /// Let the user interrupt the assistant by speaking.
  bool get bargeIn => _prefs.getBool(_bargeInKey) ?? true;

  /// The agent used when the wake phrase is heard from the home screen.
  String? get lastAgentId => _prefs.getString(_lastAgentKey);

  Future<void> setWakeEnabled(bool value) => _set(_wakeKey, value);
  Future<void> setWakeSensitivity(WakeSensitivity value) =>
      _set(_sensitivityKey, value.index);
  Future<void> setSpeed(double value) => _set(_speedKey, value.clamp(0.8, 1.4));
  Future<void> setCueSounds(bool value) => _set(_soundsKey, value);
  Future<void> setCueHaptics(bool value) => _set(_hapticsKey, value);
  Future<void> setBargeIn(bool value) => _set(_bargeInKey, value);
  Future<void> setLastAgentId(String id) => _set(_lastAgentKey, id);

  Future<void> _set(String key, Object value) async {
    switch (value) {
      case bool v:
        await _prefs.setBool(key, v);
      case int v:
        await _prefs.setInt(key, v);
      case double v:
        await _prefs.setDouble(key, v);
      case String v:
        await _prefs.setString(key, v);
    }
    notifyListeners();
  }
}
