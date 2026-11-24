"""Broker security: TLS and credentials, checked without a broker.

The live checks against a real TLS broker are in
``tests/integration/test_tls_broker.py``.
"""

from __future__ import annotations

import ssl
import subprocess
import threading
import warnings
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from urml_vda5050_runtime import BrokerTls, Vda5050Config, load_vda5050_config
from urml_vda5050_runtime import transport as tr
from urml_vda5050_runtime.broker import is_loopback, password_from_env

REPO = Path(__file__).resolve().parents[3]
FIXTURE_SCRIPT = REPO / "tools" / "scripts" / "mqtt_tls_fixture.sh"
BASE = {"manufacturer": "acme", "serial_number": "amr1", "map_id": "site"}


@pytest.fixture(scope="module")
def certs(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("tls")
    try:
        subprocess.run(["bash", str(FIXTURE_SCRIPT), str(out)], check=True, capture_output=True)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        pytest.skip(f"openssl or bash unavailable: {exc}")
    return out


# ----- config -----


def test_a_plain_config_still_loads() -> None:
    config = Vda5050Config.model_validate(BASE)
    assert config.broker_tls is None and config.broker_username is None


def test_tls_and_credentials_load(tmp_path: Path) -> None:
    path = tmp_path / "adapter.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                **BASE,
                "broker_port": 8883,
                "broker_tls": {"ca_file": "certs/ca.pem"},
                "broker_username": "urml",
                "broker_password_env": "URML_BROKER_PASSWORD",
            }
        ),
        encoding="utf-8",
    )
    config = load_vda5050_config(path)
    assert config.broker_tls is not None
    assert config.broker_tls.ca_file == str(tmp_path / "certs" / "ca.pem")


@pytest.mark.parametrize(
    "extra",
    [
        {"broker_tls": {"client_cert_file": "c.pem"}},
        {"broker_tls": {"insecure": True}},
        {"broker_password_env": "URML_BROKER_PASSWORD"},
        {"broker_username": "urml", "broker_password_env": "not a name"},
        {"broker_password": "secret"},
    ],
    ids=["cert-without-key", "no-insecure-switch", "password-without-user", "bad-env-name", "no-inline-password"],
)
def test_bad_security_config_is_refused(extra: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        Vda5050Config.model_validate({**BASE, **extra})


def test_the_password_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("URML_TEST_BROKER_PASSWORD", "s3cret")
    assert password_from_env("URML_TEST_BROKER_PASSWORD") == "s3cret"
    assert password_from_env(None) is None
    monkeypatch.delenv("URML_TEST_BROKER_PASSWORD")
    with pytest.raises(ValueError, match="not set"):
        password_from_env("URML_TEST_BROKER_PASSWORD")


# ----- the TLS context -----


def test_the_context_verifies_and_refuses_old_tls(certs: Path) -> None:
    context = BrokerTls(ca_file=str(certs / "ca.pem")).context()
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname
    assert context.minimum_version >= ssl.TLSVersion.TLSv1_2


def test_the_context_loads_a_client_certificate(certs: Path) -> None:
    tls = BrokerTls(
        ca_file=str(certs / "ca.pem"),
        client_cert_file=str(certs / "client.pem"),
        client_key_file=str(certs / "client.key"),
    )
    assert tls.context().verify_mode == ssl.CERT_REQUIRED


def test_a_missing_certificate_file_is_reported(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="file not found"):
        BrokerTls(ca_file=str(tmp_path / "none.pem")).context()


# ----- the transport, with a stand-in for paho's client -----


class _Reason:
    def __init__(self, failure: bool, text: str) -> None:
        self.is_failure = failure
        self._text = text

    def __str__(self) -> str:
        return self._text


class _FakeClient:
    def __init__(self, answer: _Reason | None) -> None:
        self.answer = answer
        self.tls: ssl.SSLContext | None = None
        self.credentials: tuple[str, str | None] | None = None
        self.on_connect: Any = None
        self.on_disconnect: Any = None
        self.stopped = False

    def tls_set_context(self, context: ssl.SSLContext) -> None:
        self.tls = context

    def username_pw_set(self, username: str, password: str | None) -> None:
        self.credentials = (username, password)

    def connect(self, _host: str, _port: int, _keepalive: int) -> None:
        pass

    def loop_start(self) -> None:
        if self.answer is not None:
            threading.Timer(0.01, self.on_connect, (self, None, None, self.answer, None)).start()

    def loop_stop(self) -> None:
        self.stopped = True

    def disconnect(self) -> None:
        pass


def test_secure_sets_tls_and_credentials(certs: Path) -> None:
    client = _FakeClient(None)
    context = BrokerTls(ca_file=str(certs / "ca.pem")).context()
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        tr._secure(client, "broker.example", context, "urml", "s3cret")
    assert client.tls is context
    assert client.credentials == ("urml", "s3cret")


def test_plain_mqtt_off_this_machine_warns() -> None:
    with pytest.warns(UserWarning, match="without TLS"):
        tr._secure(_FakeClient(None), "10.0.0.5", None, None, None)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        tr._secure(_FakeClient(None), "127.0.0.1", None, None, None)
        tr._secure(_FakeClient(None), "localhost", None, None, None)


def test_connect_returns_once_the_broker_accepts() -> None:
    client = _FakeClient(_Reason(False, "Success"))
    tr._connect(client, "localhost", 8883, 30, timeout=2.0)
    assert not client.stopped


def test_a_refused_login_raises_at_connect() -> None:
    client = _FakeClient(_Reason(True, "Not authorized"))
    with pytest.raises(ConnectionError, match="refused the connection: Not authorized"):
        tr._connect(client, "localhost", 8883, 30, timeout=2.0)
    assert client.stopped


def test_a_broker_that_hangs_up_before_accepting_is_a_refusal() -> None:
    client = _FakeClient(None)
    original = client.loop_start

    def hang_up() -> None:
        original()
        threading.Timer(0.01, client.on_disconnect, (client, None, None, "Unspecified error", None)).start()

    client.loop_start = hang_up  # type: ignore[method-assign]
    with pytest.raises(ConnectionError, match="refused the connection: closed before accepting it"):
        tr._connect(client, "localhost", 8883, 30, timeout=2.0)


def test_a_silent_broker_times_out_at_connect() -> None:
    client = _FakeClient(None)
    with pytest.raises(ConnectionError, match="did not answer"):
        tr._connect(client, "localhost", 8883, 30, timeout=0.1)


def test_loopback_detection() -> None:
    assert is_loopback("127.0.0.1") and is_loopback("::1") and is_loopback("localhost")
    assert not is_loopback("10.0.0.5") and not is_loopback("broker.example")
