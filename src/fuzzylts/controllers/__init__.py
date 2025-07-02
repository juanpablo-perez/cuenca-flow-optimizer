# src/fuzzylts/controllers/__init__.py

"""
controllers package initializer
───────────────────────────────
Lazy factory for traffic-light controllers.  
Calling `get_controller("fuzzy")` returns the `get_phase_duration` function
from the `fuzzylts.controllers.fuzzy` module without importing other controllers.
"""

from __future__ import annotations
from importlib import import_module
from typing import Callable, Protocol, Dict

class Controller(Protocol):
    """Signature for a traffic-light controller function."""
    def __call__(self, tls_id: str) -> int: ...

# Map controller names to their module paths
_CONTROLLER_MODULES: Dict[str, str] = {
    "static":   "fuzzylts.controllers.static",
    "actuated": "fuzzylts.controllers.actuated",
    "fuzzy":    "fuzzylts.controllers.fuzzy",
    "gap_actuated": "fuzzylts.controllers.gap_actuated",
}

# Cache for imported controller functions
_controller_cache: Dict[str, Controller] = {}

def get_controller(name: str) -> Controller:
    """
    Retrieve the `get_phase_duration` function for the specified controller.
    
    Imports the controller module on first use and caches the function.
    
    Args:
        name: Identifier of the controller ("static", "actuated", or "fuzzy").
    
    Returns:
        A callable that takes a traffic-light ID and returns the green-phase duration.
    
    Raises:
        ValueError: If the controller name is not recognized.
    """
    if name in _controller_cache:
        return _controller_cache[name]

    try:
        module_path = _CONTROLLER_MODULES[name]
    except KeyError:
        raise ValueError(f"Unknown controller '{name}'. Valid options are: {list(_CONTROLLER_MODULES)}")

    module = import_module(module_path)
    controller_fn = getattr(module, "get_phase_duration")
    _controller_cache[name] = controller_fn
    return controller_fn
