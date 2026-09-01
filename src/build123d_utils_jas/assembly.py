"""Assembly helpers: building labeled compounds and querying them by label."""

import re
from typing import Sequence

from build123d import Compound
from build123d.topology.shape_core import Shape

__all__ = [
  "make_compound",
  "find_part",
]


def make_compound(label=None, children=None, type=Compound, **named_children):
  children = list(children or [])
  for l, c in named_children.items():
    if isinstance(c, Sequence):
      for i, part in enumerate(c):
        part.label = f"{l}_{i}"
        children.append(part)
    else:
      c.label = l
      children.append(c)
  compound = type(None, label=label, children=children)
  return compound


def find_part(shape: Shape, name: str):
  """Get a descendant of a compound by its label.

  ``find_part(assembly(), "heatsink")`` returns the single shape labeled
  ``heatsink``. A name whose members were labeled ``name_0``, ``name_1``, ...
  by `make_compound` (a list child) returns them all: ``find_part(a, "wago")``
  -> ``[wago_0, wago_1]``. Dotted paths descend into nested compounds:
  ``find_part(a, "cap.can")``. When the same label appears at several depths
  (e.g. a ``pcb`` compound containing a ``pcb`` board), the shallowest match
  wins; it's only ambiguous if multiple shapes share the label at that depth.

  Raises KeyError (listing the labels that do exist) when nothing matches.
  """
  head, _, rest = name.partition(".")

  def descendants(s, depth=1):
    for c in s.children:
      yield depth, c
      yield from descendants(c, depth + 1)

  exact = [(d, c) for d, c in descendants(shape) if c.label == head]
  if exact:
    min_depth = min(d for d, _ in exact)
    shallowest = [c for d, c in exact if d == min_depth]
    if len(shallowest) > 1:
      raise KeyError(f"{head!r} is ambiguous: {len(shallowest)} shapes carry that label")
    return find_part(shallowest[0], rest) if rest else shallowest[0]

  pattern = re.compile(re.escape(head) + r"_(\d+)$")
  group = [(int(m[1]), c) for _, c in descendants(shape) if (m := pattern.fullmatch(c.label or ""))]
  if group:
    if rest:
      raise KeyError(f"{head!r} is a group; index it before descending, e.g. {head}_0.{rest}")
    return [c for _, c in sorted(group)]

  labels = sorted({c.label for _, c in descendants(shape) if c.label})
  raise KeyError(f"no part {name!r} in {shape.label or shape!r}; labels here: {', '.join(labels)}")
