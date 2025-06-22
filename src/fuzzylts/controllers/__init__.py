"""
controllers.__init__
────────────────────
Factoría perezosa (lazy) de controladores:
   get_controller("fuzzy")  → devuelve función get_phase_duration
Solo importa el módulo necesario, evitando side-effects de los demás.
"""
from __future__ import annotations
from importlib import import_module
from typing import Callable, Protocol, Dict

class Controller(Protocol):
    def __call__(self, tls_id: str) -> int: ...

# Mapeo nombre → ruta de módulo
_MODULES: Dict[str, str] = {
    "static":   "fuzzylts.controllers.static",
    "actuated": "fuzzylts.controllers.actuated",
    "fuzzy":    "fuzzylts.controllers.fuzzy",
}

_CACHE: Dict[str, Controller] = {}

def get_controller(name: str) -> Controller:
    """Importa (una vez) y devuelve la función get_phase_duration."""
    if name in _CACHE:
        return _CACHE[name]
    try:
        mod = import_module(_MODULES[name])
    except KeyError as exc:
        raise ValueError(f"Controller '{name}' not found") from exc
    ctl = getattr(mod, "get_phase_duration")
    _CACHE[name] = ctl
    return ctl
