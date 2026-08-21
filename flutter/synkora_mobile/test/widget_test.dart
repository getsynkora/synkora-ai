import 'package:flutter_test/flutter_test.dart';
import 'package:synkora_mobile/src/models/synkora_models.dart';
import 'package:synkora_mobile/src/services/auth_service.dart';
import 'package:synkora_mobile/src/services/secure_token_store.dart';
import 'package:synkora_mobile/src/state/session_controller.dart';

void main() {
  group('SessionController', () {
    test(
      'bootstraps into ready state when stored session can refresh',
      () async {
        final controller = SessionController(
          authService: _FakeAuthService.singleTenant(),
          tokenStore: _FakeTokenStore(
            const StoredSession(
              accessToken: 'expired-access',
              refreshToken: 'refresh-token',
              tenantId: 'tenant-1',
            ),
          ),
        );

        await controller.bootstrap();

        expect(controller.stage, SessionStage.ready);
        expect(controller.account?.email, 'raju@synkora.ai');
        expect(controller.activeTenant?.tenantId, 'tenant-1');
      },
    );

    test(
      'requires tenant selection when login returns multiple tenants',
      () async {
        final authService = _FakeAuthService.multiTenant();
        final tokenStore = _FakeTokenStore();
        final controller = SessionController(
          authService: authService,
          tokenStore: tokenStore,
        );

        await controller.signIn(
          email: 'raju@synkora.ai',
          password: 'super-secret',
        );

        expect(controller.stage, SessionStage.selectingTenant);

        await controller.selectTenant('tenant-2');

        expect(controller.stage, SessionStage.ready);
        expect(controller.activeTenant?.tenantId, 'tenant-2');
        expect(tokenStore.saved?.tenantId, 'tenant-2');
      },
    );

    test('signs in via a social provider and hydrates identity', () async {
      final authService = _FakeAuthService.singleTenant();
      final tokenStore = _FakeTokenStore();
      final controller = SessionController(
        authService: authService,
        tokenStore: tokenStore,
      );

      await controller.signInWithProvider('google');

      expect(controller.stage, SessionStage.ready);
      expect(controller.account?.email, 'raju@synkora.ai');
      expect(tokenStore.saved?.accessToken, 'access-1');
      expect(controller.isBusy, isFalse);
    });

    test('surfaces an error when social sign-in fails', () async {
      final authService = _FakeAuthService.singleTenant()
        ..socialLoginError = Exception('Sign-in failed');
      final controller = SessionController(
        authService: authService,
        tokenStore: _FakeTokenStore(),
      );

      await controller.signInWithProvider('google');

      expect(controller.error, 'Sign-in failed');
      expect(controller.isBusy, isFalse);
      expect(controller.stage, isNot(SessionStage.ready));
    });
  });
}

class _FakeTokenStore implements TokenStore {
  _FakeTokenStore([this.saved]);

  StoredSession? saved;

  @override
  Future<void> clear() async {
    saved = null;
  }

  @override
  Future<StoredSession?> read() async => saved;

  @override
  Future<void> write(StoredSession session) async {
    saved = session;
  }
}

class _FakeAuthService implements AuthService {
  _FakeAuthService({
    required this.identity,
    required this.loginSession,
    required this.refreshedSession,
  });

  factory _FakeAuthService.singleTenant() {
    const account = SynkoraAccount(
      id: 'account-1',
      email: 'raju@synkora.ai',
      name: 'Raju',
      status: 'ACTIVE',
    );
    const tenant = TenantMembership(
      tenantId: 'tenant-1',
      tenantName: 'Synkora',
      role: 'owner',
      isOwner: true,
      isAdmin: true,
      canEdit: true,
    );
    return _FakeAuthService(
      identity: const SessionIdentity(account: account, tenants: [tenant]),
      loginSession: _session(account, [tenant], 'tenant-1'),
      refreshedSession: const TokenEnvelope(
        accessToken: 'access-1',
        refreshToken: 'refresh-1',
        expiresIn: 3600,
        tenantId: 'tenant-1',
      ),
    );
  }

  factory _FakeAuthService.multiTenant() {
    const account = SynkoraAccount(
      id: 'account-1',
      email: 'raju@synkora.ai',
      name: 'Raju',
      status: 'ACTIVE',
    );
    const tenantOne = TenantMembership(
      tenantId: 'tenant-1',
      tenantName: 'Synkora',
      role: 'owner',
      isOwner: true,
      isAdmin: true,
      canEdit: true,
    );
    const tenantTwo = TenantMembership(
      tenantId: 'tenant-2',
      tenantName: 'Labs',
      role: 'admin',
      isOwner: false,
      isAdmin: true,
      canEdit: true,
    );
    return _FakeAuthService(
      identity: const SessionIdentity(
        account: account,
        tenants: [tenantOne, tenantTwo],
      ),
      loginSession: _session(account, [tenantOne, tenantTwo], 'tenant-1'),
      refreshedSession: const TokenEnvelope(
        accessToken: 'access-1',
        refreshToken: 'refresh-1',
        expiresIn: 3600,
        tenantId: 'tenant-1',
      ),
    );
  }

  final SessionIdentity identity;
  final AuthSession loginSession;
  final TokenEnvelope refreshedSession;
  Object? socialLoginError;

  @override
  Future<SessionIdentity> getCurrentIdentity(String accessToken) async =>
      identity;

  @override
  Future<TokenEnvelope> signInWithProvider(String provider) async {
    if (socialLoginError != null) {
      throw socialLoginError!;
    }
    return refreshedSession;
  }

  @override
  Future<AuthSession> signIn({
    required String email,
    required String password,
  }) async {
    return loginSession;
  }

  @override
  Future<TokenEnvelope> refresh({
    required String refreshToken,
    String? tenantId,
  }) async {
    return refreshedSession;
  }

  @override
  Future<void> signOut(String accessToken) async {}

  @override
  Future<TokenEnvelope> switchTenant({
    required String accessToken,
    required String tenantId,
  }) async {
    return TokenEnvelope(
      accessToken: 'access-$tenantId',
      refreshToken: 'refresh-$tenantId',
      expiresIn: 3600,
      tenantId: tenantId,
    );
  }

  static AuthSession _session(
    SynkoraAccount account,
    List<TenantMembership> tenants,
    String tenantId,
  ) {
    return AuthSession(
      account: account,
      tenants: tenants,
      tokens: TokenEnvelope(
        accessToken: 'access-$tenantId',
        refreshToken: 'refresh-$tenantId',
        expiresIn: 3600,
        tenantId: tenantId,
      ),
    );
  }
}
