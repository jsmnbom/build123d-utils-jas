"""Personal build123d utilities.

Everything except ``FastHeatSetNut`` is importable without the optional extras;
``FastHeatSetNut`` needs the ``fasteners`` extra (bd_warehouse) and is loaded
lazily so the base package works without it.
"""

from .assembly import find_part, make_compound
from .fast_patch import apply_fast_patch, no_fast_patch, remove_fast_patch
from .helpers import (
  CENTER,
  MAX,
  MIN,
  align,
  convex_face_from_points,
  extrude_to,
  flip,
  lift,
  make_solid,
  offset_to,
  raise_to,
  shell_loft,
)
from .printing import fix_horizontal_holes
from .vendor import import_part, import_vendor, set_vendor_dir
from .viewer import init_viewer, push_object, reset_show, show_object, show_objects

__all__ = [
  "CENTER",
  "MIN",
  "MAX",
  "align",
  "apply_fast_patch",
  "convex_face_from_points",
  "extrude_to",
  "find_part",
  "fix_horizontal_holes",
  "flip",
  "FastHeatSetNut",
  "import_part",
  "import_vendor",
  "init_viewer",
  "lift",
  "make_compound",
  "make_solid",
  "no_fast_patch",
  "offset_to",
  "push_object",
  "raise_to",
  "remove_fast_patch",
  "reset_show",
  "set_vendor_dir",
  "shell_loft",
  "show_object",
  "show_objects",
]


def __getattr__(name):
  if name == "FastHeatSetNut":
    from .fasteners import FastHeatSetNut

    return FastHeatSetNut
  raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
