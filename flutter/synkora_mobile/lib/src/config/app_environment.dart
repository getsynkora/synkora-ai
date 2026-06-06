import 'dart:io' show Platform;

import 'package:flutter/foundation.dart';

class AppEnvironment {
  static const String _configuredApiUrl = String.fromEnvironment(
    'SYNKORA_API_URL',
    defaultValue: '',
  );

  static String get apiBaseUrl => resolveApiBaseUrl(
    configuredApiUrl: _configuredApiUrl,
    isAndroid: !kIsWeb && Platform.isAndroid,
  );

  static Uri get apiBaseUri => Uri.parse(apiBaseUrl);

  static String resolveApiBaseUrl({
    String configuredApiUrl = '',
    required bool isAndroid,
  }) {
    final baseUrl = configuredApiUrl.isNotEmpty
        ? configuredApiUrl
        : _defaultApiUrl(isAndroid: isAndroid);

    return _normalize(baseUrl);
  }

  static String _defaultApiUrl({required bool isAndroid}) {
    if (isAndroid) {
      // Android emulators reach services on the host machine through 10.0.2.2.
      return 'http://10.0.2.2:5001';
    }

    return 'http://localhost:5001';
  }

  static String? normalizeRemoteUrl(String? rawUrl) {
    if (rawUrl == null) return null;
    final trimmed = rawUrl.trim();
    if (trimmed.isEmpty) return null;
    if (trimmed.startsWith('s3://')) return null;

    final uri = Uri.tryParse(trimmed);
    if (uri == null) return trimmed;

    if (!uri.hasScheme) {
      final normalizedPath = trimmed.startsWith('/') ? trimmed : '/$trimmed';
      return apiBaseUri.replace(path: normalizedPath).toString();
    }

    if (uri.scheme != 'http' && uri.scheme != 'https') {
      return trimmed;
    }

    if (_isLocalHost(uri.host)) {
      return uri.replace(host: apiBaseUri.host).toString();
    }

    return trimmed;
  }

  static bool _isLocalHost(String host) =>
      host == 'localhost' || host == '127.0.0.1' || host == '0.0.0.0';

  static String _normalize(String url) =>
      url.endsWith('/') ? url.substring(0, url.length - 1) : url;
}
