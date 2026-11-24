"""Live MQTT over TLS: the transport against a real broker with TLS and a password.

Skipped unless ``URML_MQTT_TLS_DIR`` names a folder made by
``tools/scripts/mqtt_tls_fixture.sh`` and ``URML_MQTT_TLS_BROKER=host`` names a
broker serving that folder's configuration (port 8883: TLS and a password;
port 8884: TLS and a client certificate). CI runs it against Mosquitto
(``.github/workflows/vda5050-integration.yml``). The host must be a name the
server certificate carries ("localhost").
"""

from __future__ import annotations

import os
import time
import uuid
from pathlib import Path
from typing import Any

import pytest

TLS_DIR = os.environ.get("URML_MQTT_TLS_DIR")
HOST = os.environ.get("URML_MQTT_TLS_BROKER", "localhost")
pytestmark = pytest.mark.skipif(not TLS_DIR, reason="set URML_MQTT_TLS_DIR and URML_MQTT_TLS_BROKER to run")


def _dir() -> Path:
    assert TLS_DIR is not None
    return Path(TLS_DIR)


def _transport(**kwargs: Any) -> Any:
    pytest.importorskip("paho.mqtt.client")
    from urml_vda5050_runtime import PahoTransport

    return PahoTransport(HOST, kwargs.pop("port", 8883), client_id=f"tls-{uuid.uuid4()}", **kwargs)


def _tls(**kwargs: str) -> Any:
    from urml_vda5050_runtime import BrokerTls

    return BrokerTls(ca_file=str(_dir() / "ca.pem"), **kwargs).context()


def _password() -> str:
    return (_dir() / "password").read_text(encoding="utf-8")


def test_a_message_round_trips_over_tls_with_a_password() -> None:
    a = _transport(tls=_tls(), username="urml", password=_password())
    b = _transport(tls=_tls(), username="urml", password=_password())
    got: list[dict[str, Any]] = []
    topic = f"uagv/v3/acme/{uuid.uuid4().hex}/state"
    b.subscribe(topic, lambda _t, payload: got.append(payload))
    time.sleep(0.5)
    a.publish(topic, {"hello": "tls"})
    deadline = time.monotonic() + 5
    while not got and time.monotonic() < deadline:
        time.sleep(0.05)
    a.close()
    b.close()
    assert got == [{"hello": "tls"}]


def test_a_wrong_password_is_refused_at_connect() -> None:
    started = time.monotonic()
    with pytest.raises(ConnectionError, match="refused"):
        _transport(tls=_tls(), username="urml", password="wrong")
    assert time.monotonic() - started < 5, "a refusal must not wait for the timeout"


def test_a_broker_signed_by_another_ca_is_refused() -> None:
    from urml_vda5050_runtime import BrokerTls

    other = BrokerTls(ca_file=str(_dir() / "other-ca.pem")).context()
    with pytest.raises(ConnectionError, match="TLS"):
        _transport(tls=other, username="urml", password=_password())


def test_a_host_name_the_certificate_does_not_carry_is_refused() -> None:
    pytest.importorskip("paho.mqtt.client")
    from urml_vda5050_runtime import PahoTransport

    with pytest.raises(ConnectionError, match="TLS"):
        PahoTransport(
            "127.0.0.1", 8883, client_id=f"tls-{uuid.uuid4()}", tls=_tls(), username="urml", password=_password()
        )


def test_mutual_tls_with_a_client_certificate() -> None:
    tls = _tls(client_cert_file=str(_dir() / "client.pem"), client_key_file=str(_dir() / "client.key"))
    _transport(port=8884, tls=tls).close()


def test_mutual_tls_without_a_client_certificate_is_refused() -> None:
    with pytest.raises(ConnectionError):
        _transport(port=8884, tls=_tls())
