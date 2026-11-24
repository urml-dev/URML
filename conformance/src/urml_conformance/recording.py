"""Record every call a runtime makes on an adapter (RFC-0706).

The conformance harness judges a runtime by what it asked the substrate to
do. Rather than trusting an adapter to keep its own log, the harness wraps
every adapter in ``RecordingAdapter`` and reads the record the proxy kept.
The main lane compares it with a fixture's ``audit_methods`` and
``per_member_audit``; the goal-line lane requires it to be empty.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RecordedCall:
    """One method call a runtime made on an adapter."""

    method: str
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = field(default_factory=dict)


class RecordingAdapter:
    """Wrap any adapter object and record every method call before forwarding it.

    Works for any adapter shape. Reading a plain attribute (``call_log``, a
    config value) is passed through and not recorded; calling anything is
    recorded, then forwarded to the wrapped adapter.

    The wrapped adapter's public methods are bound on the proxy up front.
    The runtime checks optional capabilities with ``isinstance`` against
    runtime-checkable Protocols, and Python 3.12+ looks those attributes up
    with ``inspect.getattr_static``, which skips ``__getattr__``. Binding
    them up front makes the proxy answer the checks the way the wrapped
    adapter does on every Python version.
    """

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.calls: list[RecordedCall] = []
        for name in dir(type(inner)):
            if name.startswith("_"):
                continue
            # Static lookup: no property or descriptor on the adapter runs here.
            static = inspect.getattr_static(inner, name, None)
            if inspect.isfunction(static) or isinstance(static, (staticmethod, classmethod)):
                setattr(self, name, self._recording(name, getattr(inner, name)))

    def _recording(self, name: str, method: Callable[..., Any]) -> Callable[..., Any]:
        def recorded(*args: Any, **kwargs: Any) -> Any:
            self.calls.append(RecordedCall(name, args, dict(kwargs)))
            return method(*args, **kwargs)

        return recorded

    def __getattr__(self, name: str) -> Any:
        # Only reached for names not bound above: plain attributes, and
        # callables the adapter sets on its instance.
        if name in {"_inner", "calls"}:  # not set yet (copy, pickle): no recursion
            raise AttributeError(name)
        attr = getattr(self._inner, name)
        return self._recording(name, attr) if callable(attr) else attr


__all__ = ["RecordedCall", "RecordingAdapter"]
