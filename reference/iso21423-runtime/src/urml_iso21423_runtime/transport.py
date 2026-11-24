"""MQTT transport for ISO 21423, with the retained messages and QoS it relies on.

ISO 21423 runs on MQTT 3.1.1 with JSON. Three broker features carry meaning
in it: retained messages (an entity's identity and status are its current
value; a request waits in its topic until cleared), QoS 2 for requests, and
the Last Will that the broker publishes when an entity drops off. The
adapter depends on the small ``Transport`` protocol below:

- ``InMemoryBroker`` delivers synchronously in one process and keeps
  retained messages, so a late subscriber gets the current value. The
  hermetic tests and the demo use it with
  :class:`~urml_iso21423_runtime.sim.SimulatedImr`.
- ``PahoTransport`` talks to a real broker through ``paho-mqtt``, imported
  lazily (the ``[mqtt]`` extra).

A payload of ``None`` is the zero-byte message that clears a retained topic.
"""

from __future__ import annotations

import json
import ssl
import threading
import warnings
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from urml_iso21423_runtime.broker import is_loopback

Handler = Callable[[str, dict[str, Any] | None], None]


@dataclass(frozen=True)
class Will:
    """A Last Will: what the broker publishes if this client drops without disconnecting."""

    topic: str
    payload: dict[str, Any]
    qos: int = 1
    retain: bool = True


@runtime_checkable
class Transport(Protocol):
    def publish(self, topic: str, payload: dict[str, Any] | None, *, qos: int = 0, retain: bool = False) -> None: ...

    def subscribe(self, topic: str, handler: Handler, *, qos: int = 0) -> None: ...

    def close(self) -> None: ...


def topic_matches(pattern: str, topic: str) -> bool:
    """MQTT wildcard match: ``+`` is one level, ``#`` is the rest."""
    p_parts, t_parts = pattern.split("/"), topic.split("/")
    for index, part in enumerate(p_parts):
        if part == "#":
            return True
        if index >= len(t_parts) or (part != "+" and part != t_parts[index]):
            return False
    return len(p_parts) == len(t_parts)


class InMemoryBroker:
    """A synchronous, in-process stand-in for an MQTT broker, with retained messages.

    Payloads round-trip through JSON. Every publish is kept in ``log`` as
    ``(topic, payload, qos, retain)``. ``drop(will)`` plays the broker's
    part when a client vanishes: it publishes the will.
    """

    def __init__(self) -> None:
        self._handlers: list[tuple[str, Handler]] = []
        self._retained: dict[str, dict[str, Any]] = {}
        self.log: list[tuple[str, dict[str, Any] | None, int, bool]] = []

    def publish(self, topic: str, payload: dict[str, Any] | None, *, qos: int = 0, retain: bool = False) -> None:
        wire = None if payload is None else json.loads(json.dumps(payload))
        self.log.append((topic, wire, qos, retain))
        if retain:
            if wire is None:
                self._retained.pop(topic, None)
            else:
                self._retained[topic] = wire
        for pattern, handler in list(self._handlers):
            if topic_matches(pattern, topic):
                handler(topic, None if wire is None else json.loads(json.dumps(wire)))

    def subscribe(self, topic: str, handler: Handler, *, qos: int = 0) -> None:
        self._handlers.append((topic, handler))
        for retained_topic, payload in list(self._retained.items()):
            if topic_matches(topic, retained_topic):
                handler(retained_topic, json.loads(json.dumps(payload)))

    def drop(self, will: Will) -> None:
        self.publish(will.topic, will.payload, qos=will.qos, retain=will.retain)

    def close(self) -> None:
        self._handlers.clear()

    def retained(self, topic: str) -> dict[str, Any] | None:
        return self._retained.get(topic)

    def published(self, suffix: str) -> list[tuple[str, dict[str, Any] | None]]:
        """``(topic, payload)`` of every publish whose topic ends with ``/<suffix>``."""
        return [(t, p) for t, p, _q, _r in self.log if t.endswith("/" + suffix)]


def _secure(client: Any, host: str, tls: ssl.SSLContext | None, username: str | None, password: str | None) -> None:
    if tls is not None:
        client.tls_set_context(tls)
    elif not is_loopback(host):
        warnings.warn(
            f"MQTT connection to {host} without TLS: commands and state cross the network in clear text. "
            "Set broker_tls in the adapter config, or protect the conduit with the network.",
            UserWarning,
            stacklevel=3,
        )
    if username is not None:
        client.username_pw_set(username, password)


def _connect(client: Any, host: str, port: int, keepalive: int, timeout: float) -> None:
    """Connect and wait for the broker's answer; ``ConnectionError`` when it does not accept."""
    answered = threading.Event()
    outcome: list[Any] = []

    def on_connect(_client: Any, _userdata: Any, _flags: Any, reason_code: Any, _properties: Any = None) -> None:
        outcome.append(reason_code)
        answered.set()

    def on_disconnect(_client: Any, _userdata: Any, _flags: Any, reason_code: Any, _properties: Any = None) -> None:
        # Some brokers drop a refused client without a CONNACK; count that as a refusal.
        if not answered.is_set():
            outcome.append(_Refused(f"closed before accepting it ({reason_code}); check the credentials"))
            answered.set()

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    try:
        client.connect(host, port, keepalive)
    except ssl.SSLError as exc:
        raise ConnectionError(f"TLS to the broker at {host}:{port} failed: {exc}") from exc
    except OSError as exc:
        raise ConnectionError(f"cannot reach the broker at {host}:{port}: {exc}") from exc
    client.loop_start()
    if not answered.wait(timeout):
        _stop(client)
        raise ConnectionError(f"the broker at {host}:{port} did not answer within {timeout:g} s")
    reason = outcome[0]
    if getattr(reason, "is_failure", False):
        _stop(client)
        raise ConnectionError(f"the broker at {host}:{port} refused the connection: {reason}")


class _Refused:
    is_failure = True

    def __init__(self, text: str) -> None:
        self._text = text

    def __str__(self) -> str:
        return self._text


def _stop(client: Any) -> None:
    with suppress(Exception):
        client.loop_stop()
    with suppress(Exception):
        client.disconnect()


def _require_paho() -> Any:
    try:
        import paho.mqtt.client as mqtt  # type: ignore[import-not-found,import-untyped,unused-ignore]
    except ImportError as exc:
        raise RuntimeError(
            "paho-mqtt is not installed. PahoTransport requires the [mqtt] extra.\n"
            "  Install with: pip install urml-iso21423-runtime[mqtt]"
        ) from exc
    return mqtt


class PahoTransport:
    """MQTT 3.1.1 over ``paho-mqtt`` 2.x: persistent session, 60 s keep-alive, optional will.

    Connects on construction and returns only once the broker has accepted the
    connection, so a refused login or a failed TLS check raises
    ``ConnectionError`` here instead of surfacing later as a silent timeout.
    ``tls`` is a client context (``BrokerTls.context()``); without one, a
    connection to a host other than this machine sends everything in clear
    text, and a warning says so.
    """

    def __init__(
        self,
        host: str,
        port: int = 1883,
        *,
        client_id: str,
        will: Will | None = None,
        keepalive: int = 60,
        tls: ssl.SSLContext | None = None,
        username: str | None = None,
        password: str | None = None,
        connect_timeout: float = 10.0,
    ) -> None:
        mqtt = _require_paho()
        self._handlers: list[tuple[str, Handler]] = []
        self._lock = threading.Lock()
        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
            clean_session=False,
            protocol=mqtt.MQTTv311,
        )
        if will is not None:
            self._client.will_set(will.topic, json.dumps(will.payload), qos=will.qos, retain=will.retain)
        self._client.on_message = self._on_message
        _secure(self._client, host, tls, username, password)
        _connect(self._client, host, port, keepalive, connect_timeout)

    def _on_message(self, _client: Any, _userdata: Any, message: Any) -> None:
        payload: dict[str, Any] | None
        if not message.payload:
            payload = None
        else:
            try:
                decoded = json.loads(message.payload)
            except ValueError:
                return
            if not isinstance(decoded, dict):
                return
            payload = decoded
        with self._lock:
            handlers = [h for pattern, h in self._handlers if topic_matches(pattern, message.topic)]
        for handler in handlers:
            handler(message.topic, payload)

    def publish(self, topic: str, payload: dict[str, Any] | None, *, qos: int = 0, retain: bool = False) -> None:
        body = b"" if payload is None else json.dumps(payload)
        self._client.publish(topic, body, qos=qos, retain=retain)

    def subscribe(self, topic: str, handler: Handler, *, qos: int = 0) -> None:
        with self._lock:
            self._handlers.append((topic, handler))
        self._client.subscribe(topic, qos=qos)

    def close(self) -> None:
        with suppress(Exception):
            self._client.disconnect()
        with suppress(Exception):
            self._client.loop_stop()
