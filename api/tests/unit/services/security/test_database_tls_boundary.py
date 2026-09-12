import ssl

import pytest

from src.config.database import DatabaseConfig


@pytest.mark.parametrize("mode,hostname", [("require", True), ("verify-full", True), ("verify-ca", False)])
def test_database_ssl_modes_verify_certificates(mode, hostname):
    config = DatabaseConfig(db_extras=f"sslmode={mode}")
    context = config.sqlalchemy_async_engine_options["connect_args"]["ssl"]
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is hostname
    assert "sslmode" not in config.sqlalchemy_async_database_uri


def test_production_defaults_to_verified_tls(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    config = DatabaseConfig(db_extras="")
    assert "sslmode=verify-full" in config.sqlalchemy_database_uri
    context = config.sqlalchemy_async_engine_options["connect_args"]["ssl"]
    assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname


def test_database_ca_path_is_used_and_removed_from_async_url(tmp_path):
    missing = str(tmp_path / "missing.pem")
    config = DatabaseConfig(db_extras=f"sslmode=verify-full&sslrootcert={missing}")
    assert "sslrootcert" not in config.sqlalchemy_async_database_uri
    with pytest.raises(FileNotFoundError):
        _ = config.sqlalchemy_async_engine_options


@pytest.mark.parametrize("mode", ["prefer", "allow", "verify", "invalid"])
def test_database_rejects_unrecognized_or_downgradable_modes(mode):
    with pytest.raises(ValueError):
        _ = DatabaseConfig(db_extras=f"sslmode={mode}").sqlalchemy_async_engine_options


def test_tls_handshake_rejects_untrusted_certificate_and_wrong_hostname(tmp_path):
    """Exercise real TLS entirely in memory; no network or database is needed."""
    from datetime import UTC, datetime, timedelta

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "db.example")])
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("db.example")]), critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    cert_path, key_path = tmp_path / "cert.pem", tmp_path / "key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )
    server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_context.load_cert_chain(cert_path, key_path)

    def handshake(context, hostname):
        client_in, client_out, server_in, server_out = (ssl.MemoryBIO() for _ in range(4))
        client = context.wrap_bio(client_in, client_out, server_hostname=hostname)
        server = server_context.wrap_bio(server_in, server_out, server_side=True)
        for _ in range(20):
            try:
                client.do_handshake()
                return
            except ssl.SSLWantReadError:
                pass
            server_in.write(client_out.read())
            try:
                server.do_handshake()
            except ssl.SSLWantReadError:
                pass
            client_in.write(server_out.read())
        raise AssertionError("TLS handshake did not finish")

    untrusted = DatabaseConfig(db_extras="sslmode=verify-full").sqlalchemy_async_engine_options["connect_args"]["ssl"]
    with pytest.raises(ssl.SSLCertVerificationError):
        handshake(untrusted, "db.example")
    trusted = DatabaseConfig(db_extras=f"sslmode=verify-full&sslrootcert={cert_path}").sqlalchemy_async_engine_options[
        "connect_args"
    ]["ssl"]
    handshake(trusted, "db.example")
    with pytest.raises(ssl.SSLCertVerificationError):
        handshake(trusted, "impostor.example")
