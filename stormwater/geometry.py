"""Compatibility import; implementation lives in drainage_core.geometry."""

from drainage_core import geometry as _implementation

globals().update(
    {
        name: getattr(_implementation, name)
        for name in dir(_implementation)
        if not name.startswith("__")
    }
)


def measure(case):
    """Preserve legacy Philadelphia source-lineage defaults for saved cases."""
    configured = dict(case)
    configured.setdefault("dependent_source_families", ["PWD", "City impervious", "City buildings"])
    return _implementation.measure(configured)
