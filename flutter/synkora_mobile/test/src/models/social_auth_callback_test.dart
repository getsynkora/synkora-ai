import 'package:flutter_test/flutter_test.dart';
import 'package:synkora_mobile/src/models/synkora_models.dart';

void main() {
  group('SocialAuthCallback.fromUri', () {
    test('parses a successful callback with exchange code', () {
      final callback = SocialAuthCallback.fromUri(
        Uri.parse(
          'synkora://auth-callback?login=success&provider=google&exchange_code=abc123',
        ),
      );

      expect(callback.isSuccess, isTrue);
      expect(callback.provider, 'google');
      expect(callback.exchangeCode, 'abc123');
      expect(callback.errorMessage, isNull);
    });

    test('parses an error callback', () {
      final callback = SocialAuthCallback.fromUri(
        Uri.parse(
          'synkora://auth-callback?login=error&message=Sign-in%20failed',
        ),
      );

      expect(callback.isSuccess, isFalse);
      expect(callback.errorMessage, 'Sign-in failed');
    });

    test('treats a success status without an exchange code as not successful', () {
      final callback = SocialAuthCallback.fromUri(
        Uri.parse('synkora://auth-callback?login=success&provider=google'),
      );

      expect(callback.isSuccess, isFalse);
    });

    test('treats a missing login param as not successful', () {
      final callback = SocialAuthCallback.fromUri(
        Uri.parse('synkora://auth-callback'),
      );

      expect(callback.isSuccess, isFalse);
      expect(callback.status, 'error');
    });
  });
}
