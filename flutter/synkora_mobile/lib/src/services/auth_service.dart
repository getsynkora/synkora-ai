import 'package:dio/dio.dart';
import 'package:flutter_web_auth_2/flutter_web_auth_2.dart';

import '../config/app_environment.dart';
import '../models/synkora_models.dart';

/// Opens [url] in a system browser/webview and resolves with the final redirect
/// URL once the browser navigates to [callbackUrlScheme]. Abstracted as a typedef
/// so tests can substitute a fake instead of driving a real browser.
typedef WebAuthenticator =
    Future<String> Function({
      required String url,
      required String callbackUrlScheme,
    });

abstract class AuthService {
  Future<AuthSession> signIn({required String email, required String password});

  /// Signs in via a social provider (google, microsoft, apple) using the
  /// backend's browser-redirect OAuth flow, capturing the callback through the
  /// app's registered custom URL scheme.
  Future<TokenEnvelope> signInWithProvider(String provider);

  Future<TokenEnvelope> refresh({
    required String refreshToken,
    String? tenantId,
  });

  Future<SessionIdentity> getCurrentIdentity(String accessToken);

  Future<TokenEnvelope> switchTenant({
    required String accessToken,
    required String tenantId,
  });

  Future<void> signOut(String accessToken);
}

class SynkoraAuthService implements AuthService {
  SynkoraAuthService({String? baseUrl, Dio? dio, WebAuthenticator? webAuthenticate})
    : _dio =
          dio ??
          Dio(
            BaseOptions(
              baseUrl: baseUrl ?? AppEnvironment.apiBaseUrl,
              connectTimeout: const Duration(seconds: 15),
              receiveTimeout: const Duration(seconds: 30),
              headers: const {'Content-Type': 'application/json'},
            ),
          ),
      _webAuthenticate = webAuthenticate ?? FlutterWebAuth2.authenticate;

  final Dio _dio;
  final WebAuthenticator _webAuthenticate;

  @override
  Future<SessionIdentity> getCurrentIdentity(String accessToken) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/console/api/auth/me',
        options: Options(headers: {'Authorization': 'Bearer $accessToken'}),
      );
      final data =
          (response.data?['data'] as Map<String, dynamic>?) ?? const {};
      final tenants = (data['tenants'] as List<dynamic>? ?? [])
          .map(
            (tenant) =>
                TenantMembership.fromJson(tenant as Map<String, dynamic>),
          )
          .toList();
      return SessionIdentity(
        account: SynkoraAccount.fromJson(
          (data['account'] as Map<String, dynamic>?) ?? const {},
        ),
        tenants: tenants,
      );
    } on DioException catch (error) {
      throw _wrap(error);
    }
  }

  @override
  Future<TokenEnvelope> refresh({
    required String refreshToken,
    String? tenantId,
  }) async {
    final data = <String, dynamic>{'refresh_token': refreshToken};
    if (tenantId != null) {
      data['tenant_id'] = tenantId;
    }

    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/console/api/auth/refresh',
        data: data,
      );
      return TokenEnvelope.fromJson(
        (response.data?['data'] as Map<String, dynamic>?) ?? const {},
      );
    } on DioException catch (error) {
      throw _wrap(error);
    }
  }

  @override
  Future<void> signOut(String accessToken) async {
    try {
      await _dio.post<Map<String, dynamic>>(
        '/console/api/auth/logout',
        options: Options(headers: {'Authorization': 'Bearer $accessToken'}),
      );
    } on DioException catch (_) {
      return;
    }
  }

  @override
  Future<AuthSession> signIn({
    required String email,
    required String password,
  }) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/console/api/auth/signin',
        data: {'email': email, 'password': password},
      );
      return AuthSession.fromJson(response.data ?? const {});
    } on DioException catch (error) {
      throw _wrap(error);
    }
  }

  @override
  Future<TokenEnvelope> signInWithProvider(String provider) async {
    final loginUrl = Uri.parse('${_dio.options.baseUrl}/api/v1/auth/$provider/login')
        .replace(
          queryParameters: {
            'redirect_url': '${AppEnvironment.mobileOAuthRedirectScheme}://auth-callback',
          },
        )
        .toString();

    String callbackUrl;
    try {
      callbackUrl = await _webAuthenticate(
        url: loginUrl,
        callbackUrlScheme: AppEnvironment.mobileOAuthRedirectScheme,
      );
    } catch (_) {
      throw Exception('Sign-in was cancelled or could not be completed.');
    }

    final callback = SocialAuthCallback.fromUri(Uri.parse(callbackUrl));
    if (!callback.isSuccess) {
      throw Exception(callback.errorMessage ?? 'Sign-in was not completed.');
    }

    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/api/v1/auth/token-exchange',
        queryParameters: {'code': callback.exchangeCode},
      );
      return TokenEnvelope.fromJson(response.data ?? const {});
    } on DioException catch (error) {
      throw _wrap(error);
    }
  }

  @override
  Future<TokenEnvelope> switchTenant({
    required String accessToken,
    required String tenantId,
  }) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/console/api/auth/switch-tenant',
        data: {'tenant_id': tenantId},
        options: Options(headers: {'Authorization': 'Bearer $accessToken'}),
      );
      return TokenEnvelope.fromJson(
        (response.data?['data'] as Map<String, dynamic>?) ?? const {},
      );
    } on DioException catch (error) {
      throw _wrap(error);
    }
  }

  Exception _wrap(DioException error) {
    final responseData = error.response?.data;
    if (responseData is Map<String, dynamic>) {
      final detail = responseData['detail'];
      if (detail is Map<String, dynamic>) {
        final message = detail['message']?.toString();
        if (message != null && message.isNotEmpty) {
          return Exception(message);
        }
      }
      final message =
          responseData['message']?.toString() ??
          responseData['detail']?.toString();
      if (message != null && message.isNotEmpty) {
        return Exception(message);
      }
    }
    return Exception(error.message ?? 'Authentication request failed.');
  }
}
