"""Performance monkey-patches for build123d's ``Shape``.

Stock build123d re-validates and deep-copies more than needed for interactive
modelling. ``apply_fast_patch()`` swaps a handful of ``Shape`` methods for
faster equivalents:

- ``__copy__`` shares the underlying ``TopoDS_Shape`` (re-located, not rebuilt)
- ``moved``/``located``/``_apply_transform`` skip revalidation
- ``bounding_box`` defaults to the non-optimal OCC bounding box with a coarse
  tolerance (0.001), which is much faster than the stock ``optimal=True``

Nothing is patched at import time — call ``apply_fast_patch()`` explicitly,
typically at the top of a script or under ``if __name__ == "__main__":``.
Use ``no_fast_patch()`` to temporarily restore the stock methods, or
``remove_fast_patch()`` to undo entirely.
"""

import contextlib
import copy

from build123d import BoundBox, Location, Plane
from build123d.topology.shape_core import Shape, downcast, fix
from OCP.Bnd import Bnd_Box
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.gp import gp_Trsf

__all__ = [
  "apply_fast_patch",
  "remove_fast_patch",
  "no_fast_patch",
]


def _copy(self):
  cls = self.__class__
  result = cls.__new__(cls)
  for key, value in self.__dict__.items():
    if key == "_wrapped":
      result.wrapped = downcast(self.wrapped.Located(self.wrapped.Location()))
    else:
      setattr(result, key, copy.copy(value))
  return result


def _moved(self, loc: Location | Plane):
  if isinstance(loc, Plane):
    loc = loc.location
  if self._wrapped is None:
    raise ValueError("Cannot move an empty shape")
  if loc.wrapped is None:
    raise ValueError("Cannot move a shape at an empty location")
  shape_copy: Shape = copy.copy(self)
  shape_copy.wrapped = downcast(self.wrapped.Moved(loc.wrapped))
  return shape_copy


def _apply_transform(self, transformation: gp_Trsf):
  if self._wrapped is None:
    return self
  shape_copy: Shape = copy.copy(self)
  transformed_shape = BRepBuilderAPI_Transform(
    self.wrapped,
    transformation,
    True,
  ).Shape()
  shape_copy.wrapped = downcast(transformed_shape)
  return shape_copy


def _fix(self):
  if self._wrapped is None:
    return self
  if not self.is_valid:
    shape_copy: Shape = copy.copy(self)
    shape_copy.wrapped = fix(self.wrapped)

    return shape_copy

  return self


def _located(self, loc: Location):
  if self._wrapped is None:
    raise ValueError("Cannot locate an empty shape")
  if loc.wrapped is None:
    raise ValueError("Cannot locate a shape at an empty location")
  shape_copy: Shape = copy.copy(self)
  shape_copy.wrapped.Location(loc.wrapped)  # type: ignore
  return shape_copy


def _bounding_box(
  self, tolerance: float | None = None, optimal: bool = False
) -> BoundBox:
  if self._wrapped is None:
    return BoundBox(Bnd_Box())
  tolerance = 0.001 if tolerance is None else tolerance
  return BoundBox.from_topo_ds(self.wrapped, tolerance=tolerance, optimal=optimal)


_PATCHES = {
  "__copy__": _copy,
  "moved": _moved,
  "_apply_transform": _apply_transform,
  "fix": _fix,
  "located": _located,
  "bounding_box": _bounding_box,
}

_MISSING = object()  # attribute did not exist on Shape before patching
_originals: dict | None = None


def apply_fast_patch() -> None:
  """Install the fast ``Shape`` methods. Idempotent."""
  global _originals
  if _originals is not None:
    return
  _originals = {name: Shape.__dict__.get(name, _MISSING) for name in _PATCHES}
  for name, func in _PATCHES.items():
    setattr(Shape, name, func)


def remove_fast_patch() -> None:
  """Restore the stock ``Shape`` methods. Idempotent."""
  global _originals
  if _originals is None:
    return
  for name, original in _originals.items():
    if original is _MISSING:
      delattr(Shape, name)
    else:
      setattr(Shape, name, original)
  _originals = None


@contextlib.contextmanager
def no_fast_patch():
  """Temporarily restore stock ``Shape`` behavior for the enclosed block."""
  was_patched = _originals is not None
  remove_fast_patch()
  try:
    yield
  finally:
    if was_patched:
      apply_fast_patch()
