import 'package:dio/dio.dart';

import '../config/app_environment.dart';
import '../models/synkora_models.dart';

abstract class AuthService {
  Future<AuthSession> signIn({required String email, required String password});

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
  SynkoraAuthService({String? baseUrl})
    : _dio = Dio(
        BaseOptions(
          baseUrl: baseUrl ?? AppEnvironment.apiBaseUrl,
          connectTimeout: const Duration(seconds: 15),
          receiveTimeout: const Duration(seconds: 30),
          headers: const {'Content-Type': 'application/json'},
        ),
      );

  final Dio _dio;

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
