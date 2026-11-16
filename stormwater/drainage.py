"""Compatibility import; implementation lives in drainage_core.drainage."""

from drainage_core import drainage as _implementation

globals().update(
    {
        name: getattr(_implementation, name)
        for name in dir(_implementation)
        if not name.startswith("__")
    }
)
