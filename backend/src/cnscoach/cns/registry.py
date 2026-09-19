"""Model registry, so swapping the scoring algorithm is a string, not a refactor."""

from __future__ import annotations

from collections.abc import Iterable

from cnscoach.cns.base import CNSModel

_REGISTRY: dict[str, type] = {}


def register(cls: type) -> type:
    """Class decorator. Registers under the class's `name` attribute."""
    name = getattr(cls, "name", None)
    if not name:
        raise ValueError(f"{cls.__name__} needs a class-level `name` to be registered")
    if name in _REGISTRY and _REGISTRY[name] is not cls:
        raise ValueError(f"CNS model '{name}' is already registered by {_REGISTRY[name].__name__}")
    _REGISTRY[name] = cls
    return cls


def get_model(name: str) -> CNSModel:
    if name not in _REGISTRY:
        raise KeyError(f"Unknown CNS model '{name}'. Registered: {sorted(_REGISTRY)}")
    return _REGISTRY[name]()


def available() -> list[dict]:
    return [
        {
            "name": cls.name,
            "version": cls.version,
            "description": getattr(cls, "description", ""),
        }
        for cls in sorted(_REGISTRY.values(), key=lambda c: c.name)
    ]


def names() -> Iterable[str]:
    return sorted(_REGISTRY)


DEFAULT_MODEL = "v0_autonomic"
