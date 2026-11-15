"""Compatibility import; implementation lives in drainage_core.raster."""
from drainage_core import raster as _implementation

globals().update({name:getattr(_implementation,name) for name in dir(_implementation)
                  if not name.startswith('__')})
