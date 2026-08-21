import 'package:flutter/foundation.dart';

import '../models/synkora_models.dart';
import '../services/auth_service.dart';
import '../services/secure_token_store.dart';

enum SessionStage { booting, signedOut, selectingTenant, ready }

class SessionController extends ChangeNotifier {
  SessionController({
    required AuthService authService,
    required TokenStore tokenStore,
  }) : _authService = authService,
       _tokenStore = tokenStore;

  final AuthService _authService;
  final TokenStore _tokenStore;

  SessionStage _stage = SessionStage.booting;
  SynkoraAccount? _account;
  List<TenantMembership> _tenants = const [];
  TenantMembership? _activeTenant;
  bool _isBusy = false;
  String? _error;
  String? _accessToken;
  String? _refreshToken;
  String? _tokenTenantId;

  SessionStage get stage => _stage;
  SynkoraAccount? get account => _account;
  List<TenantMembership> get tenants => List.unmodifiable(_tenants);
  TenantMembership? get activeTenant => _activeTenant;
  bool get isBusy => _isBusy;
  String? get error => _error;
  String? get accessToken => _accessToken;

  Future<void> bootstrap() async {
    _isBusy = true;
    _error = null;
    _stage = SessionStage.booting;
    notifyListeners();

    final stored = await _tokenStore.read();
    if (stored == null) {
      _resetToSignedOut();
      return;
    }

    _accessToken = stored.accessToken;
    _refreshToken = stored.refreshToken;
    _tokenTenantId = stored.tenantId;

    try {
      final refreshed = await _authService.refresh(
        refreshToken: stored.refreshToken,
        tenantId: stored.tenantId,
      );
      _applyTokens(refreshed);
      final identity = await _authService.getCurrentIdentity(
        refreshed.accessToken,
      );
      await _hydrateIdentity(
        identity,
        preferredTenantId: refreshed.tenantId ?? stored.tenantId,
        forceTenantSelection: false,
      );
    } catch (error) {
      _error = error.toString().replaceFirst('Exception: ', '');
      await _tokenStore.clear();
      _resetToSignedOut(notify: false);
      notifyListeners();
    }
  }

  Future<void> signIn({required String email, required String password}) async {
    _isBusy = true;
    _error = null;
    notifyListeners();

    try {
      final session = await _authService.signIn(
        email: email,
        password: password,
      );
      _applyTokens(session.tokens);
      await _tokenStore.write(
        StoredSession(
          accessToken: _accessToken!,
          refreshToken: _refreshToken!,
          tenantId: session.tokens.tenantId,
        ),
      );
      await _hydrateIdentity(
        SessionIdentity(account: session.account, tenants: session.tenants),
        preferredTenantId: session.tokens.tenantId,
        forceTenantSelection: session.tenants.length > 1,
      );
    } catch (error) {
      _error = error.toString().replaceFirst('Exception: ', '');
      _isBusy = false;
      notifyListeners();
    }
  }

  Future<void> signInWithProvider(String provider) async {
    _isBusy = true;
    _error = null;
    notifyListeners();

    try {
      final tokens = await _authService.signInWithProvider(provider);
      _applyTokens(tokens);
      final identity = await _authService.getCurrentIdentity(
        tokens.accessToken,
      );
      await _hydrateIdentity(
        identity,
        preferredTenantId: tokens.tenantId,
        forceTenantSelection: identity.tenants.length > 1,
      );
    } catch (error) {
      _error = error.toString().replaceFirst('Exception: ', '');
      _isBusy = false;
      notifyListeners();
    }
  }

  Future<void> selectTenant(String tenantId) async {
    final target = _tenants.cast<TenantMembership?>().firstWhere(
      (tenant) => tenant?.tenantId == tenantId,
      orElse: () => null,
    );
    if (target == null) {
      _error = 'Selected workspace was not found.';
      notifyListeners();
      return;
    }

    if (_accessToken == null || _refreshToken == null) {
      _error = 'Your session is incomplete. Please sign in again.';
      _resetToSignedOut(notify: true);
      return;
    }

    _isBusy = true;
    _error = null;
    notifyListeners();

    try {
      if (_tokenTenantId != tenantId) {
        final switched = await _authService.switchTenant(
          accessToken: _accessToken!,
          tenantId: tenantId,
        );
        _applyTokens(switched);
      }
      _activeTenant = target;
      _stage = SessionStage.ready;
      await _tokenStore.write(
        StoredSession(
          accessToken: _accessToken!,
          refreshToken: _refreshToken!,
          tenantId: tenantId,
        ),
      );
    } catch (error) {
      _error = error.toString().replaceFirst('Exception: ', '');
    } finally {
      _isBusy = false;
      notifyListeners();
    }
  }

  Future<void> signOut() async {
    final currentToken = _accessToken;
    _resetToSignedOut(notify: false);
    await _tokenStore.clear();
    if (currentToken != null) {
      await _authService.signOut(currentToken);
    }
    notifyListeners();
  }

  void clearError() {
    if (_error == null) return;
    _error = null;
    notifyListeners();
  }

  Future<void> _hydrateIdentity(
    SessionIdentity identity, {
    String? preferredTenantId,
    required bool forceTenantSelection,
  }) async {
    _account = identity.account;
    _tenants = identity.tenants;

    final resolvedTenantId =
        preferredTenantId ??
        (_tenants.length == 1 ? _tenants.first.tenantId : null);
    _activeTenant = resolvedTenantId == null
        ? (_tenants.isNotEmpty ? _tenants.first : null)
        : _tenants.firstWhere(
            (tenant) => tenant.tenantId == resolvedTenantId,
            orElse: () => _tenants.first,
          );

    _stage = forceTenantSelection && _tenants.length > 1
        ? SessionStage.selectingTenant
        : SessionStage.ready;
    _isBusy = false;
    _error = null;

    await _tokenStore.write(
      StoredSession(
        accessToken: _accessToken!,
        refreshToken: _refreshToken!,
        tenantId: _activeTenant?.tenantId,
      ),
    );
    notifyListeners();
  }

  void _applyTokens(TokenEnvelope envelope) {
    _accessToken = envelope.accessToken;
    _refreshToken = envelope.refreshToken ?? _refreshToken;
    _tokenTenantId = envelope.tenantId ?? _tokenTenantId;
  }

  void _resetToSignedOut({bool notify = true}) {
    _stage = SessionStage.signedOut;
    _account = null;
    _tenants = const [];
    _activeTenant = null;
    _isBusy = false;
    _accessToken = null;
    _refreshToken = null;
    _tokenTenantId = null;
    if (notify) {
      notifyListeners();
    }
  }
}
