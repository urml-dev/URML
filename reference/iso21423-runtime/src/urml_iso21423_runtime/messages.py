"""ISO 21423 messages: build requests and identity, read status and telemetry.

Every ISO 21423 field name the adapter uses lives in this module. It is
URML's own code, written from the public description of the message model
(see the package README for sources and status), not copied from the
standard.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any

from urml_iso21423_runtime.config import Iso21423Config, Place

STANDARD_FORMAT = "ISO-21423"
ACTION_VERSION = "1.0"
TERMINAL = frozenset({"SUCCEEDED", "CANCELED", "ABORTED"})
#: Operating modes that take requests to move.
AUTO_MODES = frozenset({"MODE_AUTO", "MODE_SEMIAUTO"})
#: Operating states in which the adapter does not send motion requests.
BLOCKING_STATES = frozenset(
    {"STOP_CATEGORY_0", "STOP_CATEGORY_1", "STOP_CATEGORY_2", "LOST", "OFFLINE", "WAIT_FOR_RESET"}
)


def timestamp() -> str:
    now = datetime.now(UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def location_point(config: Iso21423Config, place: Place) -> dict[str, Any]:
    return {"ccsId": config.ccs_id, "x": place.x, "y": place.y, "z": place.z}


def detail(
    action_type: str,
    properties: Mapping[str, Any] | None = None,
    *,
    fmt: str = STANDARD_FORMAT,
    version: str = ACTION_VERSION,
) -> dict[str, Any]:
    """One request detail (an action), blocking and interruptible."""
    return {
        "type": action_type,
        "version": version,
        "format": fmt,
        "blocking": True,
        "atomic": False,
        "properties": dict(properties or {}),
    }


def move(config: Iso21423Config, place: Place) -> dict[str, Any]:
    props: dict[str, Any] = {"location": location_point(config, place), "toleranceRadius": config.tolerance_radius}
    return detail("move", props)


def dock(config: Iso21423Config, place: Place, dock_id: str | None, actions: Iterable[str]) -> dict[str, Any]:
    props: dict[str, Any] = {"dockLocation": location_point(config, place), "toleranceRadius": config.tolerance_radius}
    if dock_id is not None:
        props["dockId"] = dock_id
    acts = list(actions)
    if acts:
        props["dockActions"] = acts
    return detail("dock", props)


def cancel(requester_id: str, request_sequence_id: int) -> dict[str, Any]:
    return detail("cancel", {"source": requester_id, "requestId": request_sequence_id})


class RequestFactory:
    """Stamps request envelopes; ``sequenceId`` counts up per sender."""

    def __init__(self, config: Iso21423Config) -> None:
        self._config = config
        self._sequence = itertools.count(1)

    def request(self, details: list[dict[str, Any]], *, priority: int = 100) -> dict[str, Any]:
        return {
            "source": self._config.requester_id,
            "destination": self._config.executor_id,
            "sequenceId": next(self._sequence),
            "timestamp": timestamp(),
            "priority": priority,
            "atomic": False,
            "details": details,
        }


def requester_identity(config: Iso21423Config) -> dict[str, Any]:
    """The adapter's own identity: it sends requests and accepts none."""
    return {
        "id": config.requester_id,
        "timestamp": timestamp(),
        "entityType": config.requester_type,
        "manufacturerName": config.manufacturer_name,
        "iso21423Version": f"{config.major_version}.0",
        "capabilities": {"provides": ["identity"], "accepts": {"requests": []}},
    }


# ---------------------------------------------------------------------------
# Reading what the robot publishes
# ---------------------------------------------------------------------------


def accepted_requests(identity: Mapping[str, Any] | None) -> set[str]:
    if not identity:
        return set()
    return set(((identity.get("capabilities") or {}).get("accepts") or {}).get("requests") or [])


def mode(status: Mapping[str, Any] | None) -> str | None:
    for state in (status or {}).get("states") or []:
        if isinstance(state, str) and state.startswith("MODE_"):
            return state
    return None


def blocking_states(status: Mapping[str, Any] | None) -> list[str]:
    return [s for s in (status or {}).get("states") or [] if s in BLOCKING_STATES]


def failed_details(request_status: Mapping[str, Any]) -> list[str]:
    """Human-readable reasons for every detail that did not succeed."""
    out = []
    for entry in request_status.get("detailStatuses") or []:
        status = entry.get("status") or {}
        if status.get("code") != "SUCCEEDED":
            text = f"{entry.get('type', '?')} {status.get('code', '?')}"
            if status.get("reason"):
                text += f" ({status['reason']})"
            if status.get("message"):
                text += f": {status['message']}"
            out.append(text)
    return out
