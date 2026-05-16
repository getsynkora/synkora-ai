import 'package:dio/dio.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';

/// Internal service — use [SynkoraPush] public API.
class SynkoraPushService {
  final String widgetKey;
  final String baseUrl;
  final String? Function()? conversationIdProvider;

  /// Returns the current user's ID at registration time.
  /// Should match the user_id used in your backend authentication.
  final String? Function()? userIdProvider;

  final Dio _dio;

  SynkoraPushService({
    required this.widgetKey,
    required String baseUrl,
    this.conversationIdProvider,
    this.userIdProvider,
  })  : baseUrl = baseUrl.endsWith('/') ? baseUrl.substring(0, baseUrl.length - 1) : baseUrl,
        _dio = Dio(
          BaseOptions(
            connectTimeout: const Duration(seconds: 10),
            headers: {
              'X-Widget-API-Key': widgetKey,
              'Content-Type': 'application/json',
            },
          ),
        );

  Future<void> initialize() async {
    // Request notification permission
    final settings = await FirebaseMessaging.instance.requestPermission(
      alert: true,
      badge: true,
      sound: true,
    );

    if (settings.authorizationStatus == AuthorizationStatus.denied) {
      debugPrint('SynkoraPush: notification permission denied');
      return;
    }

    // Get FCM token and register
    final token = await FirebaseMessaging.instance.getToken();
    if (token != null) {
      await _registerToken(token);
    }

    // Re-register on token refresh (tokens can rotate)
    FirebaseMessaging.instance.onTokenRefresh.listen((newToken) async {
      await _registerToken(newToken);
    });
  }

  Future<void> _registerToken(String fcmToken) async {
    try {
      final platform = defaultTargetPlatform == TargetPlatform.iOS ? 'ios' : 'android';
      final conversationId = conversationIdProvider?.call();
      final userId = userIdProvider?.call();

      await _dio.post(
        '$baseUrl/api/v1/widgets/push/register',
        data: {
          'fcm_token': fcmToken,
          'platform': platform,
          if (conversationId != null) 'conversation_id': conversationId,
          if (userId != null) 'user_id': userId,
        },
      );

      debugPrint('SynkoraPush: FCM token registered');
    } catch (e) {
      debugPrint('SynkoraPush: token registration failed (non-critical): $e');
    }
  }
}
