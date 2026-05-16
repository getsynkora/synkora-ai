/// Synkora Push — FCM push notification add-on for synkora_chat.
///
/// Usage:
/// ```dart
/// // In main(), after Firebase.initializeApp():
/// await SynkoraPush.init(
///   widgetKey: 'wk_xxx',
///   baseUrl: 'https://your-synkora.com',
///   conversationIdProvider: () => chatController.conversationId,
///   userIdProvider: () => currentUser.id,   // optional — enables per-user targeting
/// );
///
/// // Optional: handle foreground messages
/// SynkoraPush.onMessage = (message) {
///   // show in-app banner, navigate to chat, etc.
/// };
/// ```
library synkora_push;

import 'package:firebase_messaging/firebase_messaging.dart';

import 'src/synkora_push_service.dart';

export 'src/synkora_push_service.dart';

class SynkoraPush {
  SynkoraPush._();

  static SynkoraPushService? _service;

  /// Optional handler for foreground FCM messages.
  static void Function(RemoteMessage message)? onMessage;

  /// Call once in main() after Firebase.initializeApp().
  ///
  /// [userIdProvider] — returns the current user's ID at registration time.
  /// When provided, the device is subscribed to both the widget-wide topic
  /// (for broadcast sends) and a per-user topic so agents can target this
  /// specific user with `internal_send_push_notification(user_id: '...')`.
  static Future<void> init({
    required String widgetKey,
    required String baseUrl,
    /// Returns the current conversationId at registration time.
    String? Function()? conversationIdProvider,
    /// Returns the current user's ID at registration time.
    /// Must match the user identifier used in the agent tool call.
    String? Function()? userIdProvider,
  }) async {
    _service = SynkoraPushService(
      widgetKey: widgetKey,
      baseUrl: baseUrl,
      conversationIdProvider: conversationIdProvider,
      userIdProvider: userIdProvider,
    );

    await _service!.initialize();

    // Handle foreground messages
    FirebaseMessaging.onMessage.listen((message) {
      onMessage?.call(message);
    });
  }
}
