import 'package:flutter_test/flutter_test.dart';
import 'package:synkora_mobile/src/config/app_environment.dart';

void main() {
  group('AppEnvironment.resolveApiBaseUrl', () {
    test('uses Android emulator host by default on Android', () {
      expect(
        AppEnvironment.resolveApiBaseUrl(isAndroid: true),
        'http://10.0.2.2:5001',
      );
    });

    test('uses localhost by default off Android', () {
      expect(
        AppEnvironment.resolveApiBaseUrl(isAndroid: false),
        'http://localhost:5001',
      );
    });

    test('preserves explicit override and trims trailing slash', () {
      expect(
        AppEnvironment.resolveApiBaseUrl(
          configuredApiUrl: 'http://api.example.com/',
          isAndroid: true,
        ),
        'http://api.example.com',
      );
    });
  });
}
