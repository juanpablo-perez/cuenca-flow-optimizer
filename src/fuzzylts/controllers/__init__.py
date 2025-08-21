# src/fuzzylts/controllers/__init__.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
controllers package initializer
───────────────────────────────
Lazy factory for traffic-light controllers.

`get_controller("<name>")` lazily imports and returns the **controller module**
(e.g., `fuzzylts.controllers.fuzzy`). That module is expected to expose
a callable named **`get_phase_duration(tls_id: str) -> int`** which the
simulation runner will invoke to obtain the green-phase duration.

Design
------
- Avoid importing all controllers up-front; only the requested one is imported.
- Cache imported modules for subsequent calls.
"""

from __future__ import annotations

from importlib import import_module
from typing import Callable, Dict, Protocol


class ControllerModule(Protocol):
    """Protocol for a controller module.

    Every controller module must expose:

        get_phase_duration(tls_id: str) -> int

    Where:
        tls_id: Traffic light system identifier from the SUMO network.
        returns: Duration (seconds) for the next green phase at `tls_id`.
    """

    def get_phase_duration(self, tls_id: str) -> int:  # pragma: no cover - protocol signature
        ...


# Map controller names to their module paths
_CONTROLLER_MODULES: Dict[str, str] = {
    "static": "fuzzylts.controllers.static",
    "actuated": "fuzzylts.controllers.actuated",
    "fuzzy": "fuzzylts.controllers.fuzzy",
    "gap_fuzzy": "fuzzylts.controllers.gap_fuzzy",
}

# Cache for imported controller modules
_controller_cache: Dict[str, ControllerModule] = {}


def get_controller(name: str) -> ControllerModule:
    """Retrieve the controller module for the specified `name`.

    This function imports the module on first use and caches it for subsequent calls.

    Args:
        name: Controller identifier (e.g., "static", "actuated", "fuzzy", "gap_fuzzy").

    Returns:
        The controller **module** implementing `get_phase_duration(tls_id: str) -> int`.

    Raises:
        ValueError: If `name` is not a recognized controller.
    """
    if name in _controller_cache:
        return _controller_cache[name]

    try:
        module_path = _CONTROLLER_MODULES[name]
    except KeyError as exc:
        valid = ", ".join(sorted(_CONTROLLER_MODULES.keys()))
        raise ValueError(f"Unknown controller '{name}'. Valid options are: {valid}") from exc

    module = import_module(module_path)  # type: ignore[assignment]
    _controller_cache[name] = module  # type: ignore[assignment]
    return module


__all__ = ["get_controller", "ControllerModule"]
