import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:synkora_mobile/src/config/app_environment.dart';
import 'package:synkora_mobile/src/services/auth_service.dart';

class _FakeHttpAdapter implements HttpClientAdapter {
  _FakeHttpAdapter(this.handler);

  final ResponseBody Function(RequestOptions options) handler;

  @override
  void close({bool force = false}) {}

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    return handler(options);
  }
}

ResponseBody _jsonResponse(Map<String, dynamic> data, {int statusCode = 200}) {
  return ResponseBody.fromString(
    jsonEncode(data),
    statusCode,
    headers: {
      Headers.contentTypeHeader: [Headers.jsonContentType],
    },
  );
}

Dio _dioWithAdapter(ResponseBody Function(RequestOptions options) handler) {
  final dio = Dio(BaseOptions(baseUrl: 'http://10.0.2.2:5001'));
  dio.httpClientAdapter = _FakeHttpAdapter(handler);
  return dio;
}

void main() {
  group('SynkoraAuthService.signInWithProvider', () {
    test('exchanges the callback code for tokens on success', () async {
      final dio = _dioWithAdapter((options) {
        expect(options.path, '/api/v1/auth/token-exchange');
        expect(options.queryParameters['code'], 'abc123');
        return _jsonResponse({
          'access_token': 'access-1',
          'refresh_token': 'refresh-1',
          'expires_in': 3600,
        });
      });

      final service = SynkoraAuthService(
        dio: dio,
        webAuthenticate: ({required url, required callbackUrlScheme}) async {
          expect(callbackUrlScheme, AppEnvironment.mobileOAuthRedirectScheme);
          expect(url, contains('/api/v1/auth/google/login'));
          return 'synkora://auth-callback?login=success&provider=google&exchange_code=abc123';
        },
      );

      final tokens = await service.signInWithProvider('google');

      expect(tokens.accessToken, 'access-1');
      expect(tokens.refreshToken, 'refresh-1');
    });

    test('throws with the provider error message when login fails', () async {
      final dio = _dioWithAdapter((options) {
        fail('token-exchange should not be called when login failed');
      });
      final service = SynkoraAuthService(
        dio: dio,
        webAuthenticate: ({required url, required callbackUrlScheme}) async {
          return 'synkora://auth-callback?login=error&message=Sign-in%20failed';
        },
      );

      await expectLater(
        () => service.signInWithProvider('google'),
        throwsA(
          predicate((e) => e.toString().contains('Sign-in failed')),
        ),
      );
    });

    test(
      'wraps browser/authentication failures in a friendly exception',
      () async {
        final dio = _dioWithAdapter((options) {
          fail(
            'token-exchange should not be called when the browser flow throws',
          );
        });
        final service = SynkoraAuthService(
          dio: dio,
          webAuthenticate: ({required url, required callbackUrlScheme}) async {
            throw Exception('user cancelled');
          },
        );

        await expectLater(
          () => service.signInWithProvider('google'),
          throwsException,
        );
      },
    );
  });
}
