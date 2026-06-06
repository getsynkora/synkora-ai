import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class StoredSession {
  const StoredSession({
    required this.accessToken,
    required this.refreshToken,
    required this.tenantId,
  });

  final String accessToken;
  final String refreshToken;
  final String? tenantId;
}

abstract class TokenStore {
  Future<StoredSession?> read();

  Future<void> write(StoredSession session);

  Future<void> clear();
}

class SecureTokenStore implements TokenStore {
  static const _accessTokenKey = 'synkora_mobile_access_token';
  static const _refreshTokenKey = 'synkora_mobile_refresh_token';
  static const _tenantIdKey = 'synkora_mobile_tenant_id';

  const SecureTokenStore();

  FlutterSecureStorage get _storage => const FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  );

  @override
  Future<void> clear() async {
    await _storage.delete(key: _accessTokenKey);
    await _storage.delete(key: _refreshTokenKey);
    await _storage.delete(key: _tenantIdKey);
  }

  @override
  Future<StoredSession?> read() async {
    final accessToken = await _storage.read(key: _accessTokenKey);
    final refreshToken = await _storage.read(key: _refreshTokenKey);
    final tenantId = await _storage.read(key: _tenantIdKey);
    if (accessToken == null || refreshToken == null) {
      return null;
    }
    return StoredSession(
      accessToken: accessToken,
      refreshToken: refreshToken,
      tenantId: tenantId,
    );
  }

  @override
  Future<void> write(StoredSession session) async {
    await _storage.write(key: _accessTokenKey, value: session.accessToken);
    await _storage.write(key: _refreshTokenKey, value: session.refreshToken);
    await _storage.write(key: _tenantIdKey, value: session.tenantId);
  }
}
