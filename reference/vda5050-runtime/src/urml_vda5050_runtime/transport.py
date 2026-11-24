"""Message transport between the adapter (fleet control) and the vehicle.

VDA 5050 rides MQTT with JSON payloads (section 4). The adapter only
needs publish and subscribe, so it depends on the small ``Transport``
protocol below, not on an MQTT library:

- ``InMemoryBroker`` delivers messages synchronously inside one process.
  It is what the hermetic tests and the offline demo use, together with
  :class:`~urml_vda5050_runtime.sim.SimulatedVehicle`.
- ``PahoTransport`` talks to a real broker through ``paho-mqtt``, imported
  lazily (the ``[mqtt]`` extra), so this package imports on hosts without it.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from contextlib import suppress
from typing import Any, Protocol, runtime_checkable

Handler = Callable[[str, dict[str, Any]], None]

#: Section 4.1: QoS 1 for ``connection``, QoS 0 for every other topic.
_QOS_ONE_TOPICS = frozenset({"connection"})


def _qos(topic: str) -> int:
    return 1 if topic.rsplit("/", 1)[-1] in _QOS_ONE_TOPICS else 0


@runtime_checkable
class Transport(Protocol):
    def publish(self, topic: str, payload: dict[str, Any]) -> None: ...

    def subscribe(self, topic: str, handler: Handler) -> None: ...

    def close(self) -> None: ...


class InMemoryBroker:
    """A synchronous, in-process stand-in for an MQTT broker.

    Exact topic match only (no wildcards). Payloads are round-tripped
    through JSON so a message that would not survive the wire fails here
    too. Every published message is kept in ``log`` for inspection.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = {}
        self.log: list[tuple[str, dict[str, Any]]] = []

    def publish(self, topic: str, payload: dict[str, Any]) -> None:
        wire = json.loads(json.dumps(payload))
        self.log.append((topic, wire))
        for handler in list(self._handlers.get(topic, [])):
            handler(topic, json.loads(json.dumps(wire)))

    def subscribe(self, topic: str, handler: Handler) -> None:
        self._handlers.setdefault(topic, []).append(handler)

    def close(self) -> None:
        self._handlers.clear()

    def published(self, suffix: str) -> list[dict[str, Any]]:
        """Payloads published on topics ending in ``/<suffix>``, oldest first."""
        return [p for t, p in self.log if t.endswith("/" + suffix)]


def _require_paho() -> Any:
    try:
        import paho.mqtt.client as mqtt  # type: ignore[import-not-found,import-untyped,unused-ignore]
    except ImportError as exc:
        raise RuntimeError(
            "paho-mqtt is not installed. PahoTransport requires the [mqtt] extra.\n"
            "  Install with: pip install urml-vda5050-runtime[mqtt]"
        ) from exc
    return mqtt


class PahoTransport:
    """MQTT transport over ``paho-mqtt`` 2.x. Connects on construction."""

    def __init__(self, host: str, port: int = 1883, *, client_id: str = "", keepalive: int = 30) -> None:
        mqtt = _require_paho()
        self._handlers: dict[str, list[Handler]] = {}
        self._lock = threading.Lock()
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
        self._client.on_message = self._on_message
        self._client.connect(host, port, keepalive)
        self._client.loop_start()

    def _on_message(self, _client: Any, _userdata: Any, message: Any) -> None:
        try:
            payload = json.loads(message.payload)
        except ValueError:
            return  # not JSON, so not a VDA 5050 message
        if not isinstance(payload, dict):
            return
        with self._lock:
            handlers = list(self._handlers.get(message.topic, []))
        for handler in handlers:
            handler(message.topic, payload)

    def publish(self, topic: str, payload: dict[str, Any]) -> None:
        self._client.publish(topic, json.dumps(payload), qos=_qos(topic))

    def subscribe(self, topic: str, handler: Handler) -> None:
        with self._lock:
            self._handlers.setdefault(topic, []).append(handler)
        self._client.subscribe(topic, qos=_qos(topic))

    def close(self) -> None:
        with suppress(Exception):
            self._client.loop_stop()
        with suppress(Exception):
            self._client.disconnect()
