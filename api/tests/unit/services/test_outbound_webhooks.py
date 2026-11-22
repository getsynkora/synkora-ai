import hashlib
import hmac
import http.server
import socket
import ssl
import threading
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import requests

from src.services import outbound_webhooks as hooks
from src.services.billing.quota_service import QuotaService


class TestSigning:
    def test_signature_is_the_hmac_of_timestamp_dot_body(self):
        expected = hmac.new(b"whsec_x", b'123.{"a":1}', hashlib.sha256).hexdigest()
        assert hooks.sign_payload("whsec_x", 123, '{"a":1}') == expected

    def test_a_different_secret_or_body_gives_a_different_signature(self):
        base = hooks.sign_payload("s1", 1, "body")
        assert hooks.sign_payload("s2", 1, "body") != base
        assert hooks.sign_payload("s1", 1, "other") != base
        assert hooks.sign_payload("s1", 2, "body") != base

    def test_secrets_are_unique_and_prefixed(self):
        assert hooks.new_secret().startswith("whsec_")
        assert hooks.new_secret() != hooks.new_secret()


def _resolves_to(*addresses):
    """Make the resolver answer with these addresses, so no test touches the network."""
    infos = [(socket.AF_INET6 if ":" in a else socket.AF_INET, socket.SOCK_STREAM, 6, "", (a, 443)) for a in addresses]
    return patch.object(hooks.socket, "getaddrinfo", return_value=infos)


class TestPublicAddress:
    @pytest.mark.parametrize("address", ["93.184.216.34", "8.8.8.8", "2606:4700:4700::1111"])
    def test_public_addresses_are_allowed(self, address):
        assert hooks.is_public_address(address)

    @pytest.mark.parametrize(
        "address",
        [
            "127.0.0.1", "10.0.0.1", "172.16.0.1", "192.168.1.1", "169.254.169.254", "0.0.0.0", "100.64.0.1",
            "198.18.0.1", "224.0.0.1", "255.255.255.255", "::1", "::", "fe80::1", "fc00::1", "ff02::1",
            # IPv6 forms that carry an IPv4 address, or are not real destinations
            "::ffff:127.0.0.1", "::ffff:7f00:1", "::ffff:169.254.169.254", "::ffff:10.0.0.1",
            "64:ff9b::7f00:1", "64:ff9b::a00:1", "2002:7f00:1::", "2001:0:4136:e378:8000:63bf:3fff:fdd2",
            "not-an-ip", "",
        ],
    )  # fmt: skip
    def test_everything_else_is_refused(self, address):
        assert not hooks.is_public_address(address)

    def test_an_ipv4_mapped_public_address_is_judged_as_the_ipv4_address(self):
        assert hooks.is_public_address("::ffff:8.8.8.8")


class TestResolveDestination:
    def test_a_public_https_url_is_resolved_once_and_pinned(self):
        with _resolves_to("93.184.216.34") as lookup:
            destination, error = hooks.resolve_destination("https://hooks.example.com/in/x?a=1&b=2")
        assert error is None
        assert destination == hooks.Destination("hooks.example.com", 443, "93.184.216.34", "/in/x?a=1&b=2")
        lookup.assert_called_once()

    @pytest.mark.parametrize(
        "url",
        [
            # The reviewer's parser-differential bypass: urlparse sees example.com, requests connects to 127.0.0.1
            "https://127.0.0.1\\@example.com/x",
            "https://127.0.0.1:8443\\@example.com/",
            "https://example.com\\@127.0.0.1/",
            "https://user:pass@example.com/",
            "https://127.0.0.1@example.com/",
            "http://hooks.example.com/",
            "ftp://hooks.example.com/",
            "//hooks.example.com/",
            "hooks.example.com/in",
            "https://hooks.example.com:8443/",
            "https://hooks.example.com:80/",
            "https://hooks.exämple.com/",
            "https://hooks.example.com/with space",
            "https://hooks.example.com/\r\nHost: evil",
            "https://hooks.example.com/\x00",
            "https://",
            "",
        ],
    )
    def test_url_forms_that_could_be_parsed_two_ways_are_refused(self, url):
        with _resolves_to("93.184.216.34"):
            destination, error = hooks.resolve_destination(url)
        assert destination is None and error

    @pytest.mark.parametrize(
        "host",
        [
            "127.0.0.1", "10.1.2.3", "169.254.169.254", "[::1]", "[::]", "[::ffff:127.0.0.1]", "[::ffff:7f00:1]",
            "[::ffff:169.254.169.254]", "[64:ff9b::7f00:1]", "198.18.0.1", "100.64.0.1",
        ],
    )  # fmt: skip
    def test_literal_internal_addresses_are_refused(self, host):
        destination, error = hooks.resolve_destination(f"https://{host}/")
        assert destination is None and error == hooks.DESTINATION_REFUSED

    @pytest.mark.parametrize(
        "address", ["127.0.0.1", "10.0.0.5", "169.254.169.254", "::1", "::ffff:7f00:1", "198.18.0.1"]
    )
    def test_a_name_that_resolves_to_an_internal_address_is_refused(self, address):
        with _resolves_to(address):
            destination, error = hooks.resolve_destination("https://innocent.example.com/")
        assert destination is None and error == hooks.DESTINATION_REFUSED

    def test_every_address_must_be_public_not_just_the_first(self):
        with _resolves_to("93.184.216.34", "10.0.0.5"):
            destination, error = hooks.resolve_destination("https://mixed.example.com/")
        assert destination is None and error

    def test_an_unresolvable_name_is_refused(self):
        with patch.object(hooks.socket, "getaddrinfo", side_effect=socket.gaierror("no such host")):
            destination, error = hooks.resolve_destination("https://nope.example.com/")
        assert destination is None and error == hooks.DESTINATION_REFUSED

    def test_internal_and_unresolvable_names_get_the_same_answer(self):
        """Reproduces the check telling a caller which internal host names exist."""
        with _resolves_to("10.0.0.5"):
            internal = hooks.resolve_destination("https://redis.internal/")[1]
        with patch.object(hooks.socket, "getaddrinfo", side_effect=socket.gaierror("no such host")):
            missing = hooks.resolve_destination("https://nope.internal/")[1]
        assert internal == missing == hooks.DESTINATION_REFUSED

    @pytest.mark.parametrize(
        "address",
        ["::7f00:1", "::127.0.0.1", "::a9fe:a9fe", "::ffff:0:7f00:1", "::ffff:0:a9fe:a9fe", "2001:db8::1", "3fff::1"],
    )
    def test_ipv6_outside_global_unicast_is_refused(self, address):
        """IPv4-compatible and SIIT forms could be routed to an internal IPv4 address by a translator."""
        assert not hooks.is_public_address(address)
        with _resolves_to(address):
            assert hooks.resolve_destination("https://v6.example.com/")[0] is None

    def test_destination_error_is_the_reason_or_none(self):
        with _resolves_to("93.184.216.34"):
            assert hooks.destination_error("https://hooks.example.com/") is None
        assert hooks.destination_error("http://hooks.example.com/")


def _make_certificate(tmp_path, hostname):
    """A self-signed certificate for ``hostname``; returns (cert_file, key_file)."""
    cryptography = pytest.importorskip("cryptography")  # noqa: F841
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostname)])
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(hostname)]), critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    cert_file, key_file = tmp_path / f"{hostname}.pem", tmp_path / f"{hostname}.key"
    cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_file.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()
        )
    )
    return cert_file, key_file


class _Receiver:
    """A local HTTPS server that records what a webhook delivery looks like from the receiving side."""

    def __init__(self, cert_file, key_file, respond=204, location=None):
        self.seen = {}
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                outer.seen.update(
                    host=self.headers.get("Host"),
                    path=self.path,
                    body=self.rfile.read(int(self.headers.get("Content-Length", 0))).decode(),
                    signature=self.headers.get("X-Synkora-Signature"),
                )
                self.send_response(respond)
                if location:
                    self.send_header("Location", location)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *args):
                pass

        self.server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_file, key_file)
        context.sni_callback = lambda sock, name, ctx: self.seen.__setitem__("sni", name)
        self.server.socket = context.wrap_socket(self.server.socket, server_side=True)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def receiver_factory(tmp_path):
    started = []

    def start(hostname="hooks.example.com", **kwargs):
        cert_file, key_file = _make_certificate(tmp_path, hostname)
        receiver = _Receiver(cert_file, key_file, **kwargs)
        receiver.cert_file = cert_file
        started.append(receiver)
        return receiver

    yield start
    for receiver in started:
        receiver.stop()


class TestPinnedDelivery:
    """Real TLS connections to a local server: the connection goes to the pinned IP, the name is still verified."""

    def _destination(self, receiver, host="hooks.example.com", target="/in?x=1"):
        return hooks.Destination(host=host, port=receiver.port, ip="127.0.0.1", target=target)

    def test_connects_to_the_pinned_ip_with_the_original_host_name(self, receiver_factory):
        receiver = receiver_factory("hooks.example.com")
        headers = {"X-Synkora-Signature": "t=1,v1=abc"}
        status = hooks.post_pinned(self._destination(receiver), '{"a":1}', headers, 5, verify=str(receiver.cert_file))

        assert status == 204
        assert receiver.seen["sni"] == "hooks.example.com"  # TLS name is the host, not the IP
        assert receiver.seen["host"] == f"hooks.example.com:{receiver.port}"
        assert receiver.seen["path"] == "/in?x=1"
        assert receiver.seen["body"] == '{"a":1}'
        assert receiver.seen["signature"] == "t=1,v1=abc"

    def test_the_certificate_must_match_the_host_name_not_the_ip(self, receiver_factory):
        """A receiver whose certificate is for another name is refused, so the pinned IP cannot impersonate a host."""
        receiver = receiver_factory("someone-else.example.com")
        with pytest.raises(requests.exceptions.SSLError):
            hooks.post_pinned(self._destination(receiver), "{}", {}, 5, verify=str(receiver.cert_file))
        assert "path" not in receiver.seen  # nothing was sent

    def test_a_redirect_is_not_followed(self, receiver_factory):
        receiver = receiver_factory(respond=302, location="https://127.0.0.1/internal")
        status = hooks.post_pinned(self._destination(receiver), "{}", {}, 5, verify=str(receiver.cert_file))
        assert status == 302

    def test_proxy_environment_variables_are_ignored(self, receiver_factory, monkeypatch):
        monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")  # nothing listens there
        receiver = receiver_factory()
        assert hooks.post_pinned(self._destination(receiver), "{}", {}, 5, verify=str(receiver.cert_file)) == 204

    def test_an_ipv6_literal_host_is_bracketed_in_the_host_header(self):
        with patch.object(hooks.requests, "Session") as session:
            session.return_value.post.return_value = MagicMock(status_code=200)
            hooks.post_pinned(hooks.Destination("2606:4700::1", 443, "2606:4700::1", "/x"), "{}", {}, 5)
        assert session.return_value.post.call_args.kwargs["headers"]["Host"] == "[2606:4700::1]"

    def test_an_ipv6_address_is_bracketed_in_the_url(self):
        with patch.object(hooks.requests, "Session") as session:
            session.return_value.post.return_value = MagicMock(status_code=200)
            hooks.post_pinned(hooks.Destination("hooks.example.com", 443, "2606:4700::1", "/x"), "{}", {}, 5)
        assert session.return_value.post.call_args.args[0] == "https://[2606:4700::1]:443/x"
        assert session.return_value.post.call_args.kwargs["headers"]["Host"] == "hooks.example.com"
        assert session.return_value.trust_env is False


class TestEmitEvent:
    def _db(self, tenant, endpoints):
        db = AsyncMock()
        db.get = AsyncMock(return_value=tenant)
        result = MagicMock()
        result.scalars.return_value.all.return_value = endpoints
        db.execute = AsyncMock(return_value=result)
        return db

    async def test_event_goes_to_own_and_managers_endpoints_with_customer_identity(self):
        manager_id, customer_id = uuid4(), uuid4()
        customer = MagicMock(id=customer_id, external_ref="cust-7", managed_by_tenant_id=manager_id)
        manager = MagicMock(id=manager_id, can_manage_tenants=True)
        endpoints = [MagicMock(id=uuid4()), MagicMock(id=uuid4())]
        db = self._db(customer, endpoints)
        db.get = AsyncMock(side_effect=lambda model, key: customer if key == customer_id else manager)
        with patch.object(hooks, "deliver_to") as deliver:
            queued = await hooks.emit_event(db, customer_id, hooks.EVENT_USAGE_THRESHOLD, {"pool": "p"})

        assert queued == 2 and deliver.call_count == 2
        event = deliver.call_args.args[1]
        assert event["type"] == "usage.threshold"
        assert event["tenant_id"] == str(customer_id) and event["tenant_external_ref"] == "cust-7"
        assert event["data"] == {"pool": "p"}
        owners = next(v for v in db.execute.call_args[0][0].compile().params.values() if isinstance(v, list))
        assert set(owners) == {customer_id, manager_id}

    async def test_a_manager_whose_management_was_revoked_stops_receiving_customer_events(self):
        manager_id, customer_id = uuid4(), uuid4()
        customer = MagicMock(id=customer_id, external_ref="c", managed_by_tenant_id=manager_id)
        revoked = MagicMock(id=manager_id, can_manage_tenants=False)
        db = self._db(customer, [])
        db.get = AsyncMock(side_effect=lambda model, key: customer if key == customer_id else revoked)
        with patch.object(hooks, "deliver_to"):
            await hooks.emit_event(db, customer_id, hooks.EVENT_USAGE_THRESHOLD, {})
        owners = next(v for v in db.execute.call_args[0][0].compile().params.values() if isinstance(v, list))
        assert owners == [customer_id]

    async def test_no_endpoints_queues_nothing(self):
        db = self._db(MagicMock(id=uuid4(), external_ref=None, managed_by_tenant_id=None), [])
        with patch.object(hooks, "deliver_to") as deliver:
            assert await hooks.emit_event(db, uuid4(), hooks.EVENT_USAGE_THRESHOLD, {}) == 0
        deliver.assert_not_called()

    async def test_a_failure_never_breaks_the_caller(self):
        db = AsyncMock()
        db.get = AsyncMock(side_effect=RuntimeError("db down"))
        assert await hooks.emit_event(db, uuid4(), hooks.EVENT_USAGE_THRESHOLD, {}) == 0


class TestSubscriptionEventData:
    def test_describes_the_subscription(self):
        sub = MagicMock(
            status=MagicMock(value="ACTIVE"),
            current_period_start=datetime(2026, 11, 1, tzinfo=UTC),
            current_period_end=None,
            cancel_at_period_end=True,
        )
        data = hooks.subscription_event_data(sub, "Growth")
        assert data == {
            "plan": "Growth",
            "status": "ACTIVE",
            "current_period_start": "2026-11-01T00:00:00+00:00",
            "current_period_end": None,
            "cancel_at_period_end": True,
        }


class _Counter:
    """Stands in for the counter row: remembers the highest threshold already announced."""

    def __init__(self, notified=0):
        self.notified = notified

    async def execute(self, statement):
        percent = statement.compile().params["notified_percent"]
        result = MagicMock()
        if self.notified < percent:
            self.notified = percent
            result.first.return_value = (uuid4(),)
        else:
            result.first.return_value = None
        return result


class TestThresholds:
    START = datetime(2026, 11, 1, tzinfo=UTC)

    def _service(self, counter=None):
        db = AsyncMock()
        db.execute = (counter or _Counter()).execute
        return QuotaService(db)

    async def _announced(self, service, used, limit):
        with patch("src.services.billing.quota_service.emit_event", new=AsyncMock()) as emit:
            await service._notify_thresholds(uuid4(), {"key": "p", "label": "P", "limit": limit}, self.START, used)
        return [call.args[3]["threshold_percent"] for call in emit.await_args_list]

    @pytest.mark.parametrize(
        ("used", "limit", "expected"),
        [
            (3, 5, []),
            (4, 5, [80]),
            (5, 5, [80, 100]),
            (7, 10, []),
            (8, 10, [80]),
            (10, 10, [80, 100]),
            (1, 1, [80, 100]),
        ],
    )
    async def test_each_level_is_announced_once_it_is_reached(self, used, limit, expected):
        assert await self._announced(self._service(), used, limit) == expected

    async def test_a_level_is_never_announced_twice_in_a_period(self):
        """Reproduces duplicate 80% alerts when a unit is released and the pool crosses 80% again."""
        service = self._service()
        sequence = [(4, [80]), (3, []), (4, []), (4, []), (5, [100]), (4, []), (5, []), (6, [])]
        for used, expected in sequence:
            assert await self._announced(service, used, 5) == expected, used

    async def test_already_announced_levels_are_remembered_across_calls(self):
        service = self._service(_Counter(notified=80))
        assert await self._announced(service, 4, 5) == []
        assert await self._announced(service, 5, 5) == [100]

    async def test_nothing_is_queried_below_the_first_level(self):
        service = self._service()
        service.db.execute = AsyncMock()
        await self._announced(service, 1, 10)
        service.db.execute.assert_not_called()
        service.db.commit.assert_not_called()

    async def test_the_new_level_is_saved_before_the_event_is_queued(self):
        service = self._service()
        order = []
        service.db.commit = AsyncMock(side_effect=lambda: order.append("commit"))
        with patch(
            "src.services.billing.quota_service.emit_event", new=AsyncMock(side_effect=lambda *a: order.append("emit"))
        ):
            await service._notify_thresholds(uuid4(), {"key": "p", "limit": 5}, self.START, 4)
        assert order == ["commit", "emit"]

    async def test_a_pool_with_no_allowance_never_alerts(self):
        assert await self._announced(self._service(), 1, 0) == []
