"""Geometry helpers: alignment, absolute-coordinate operations, shell/solid building."""

from typing import Sequence, TypeVar

import numpy as np
from build123d import (
  Align,
  BuildPart,
  Face,
  Location,
  Mode,
  Part,
  Plane,
  Polyline,
  ShapeList,
  Shell,
  Sketch,
  Solid,
  Vector,
  VectorLike,
  Vertex,
  Wire,
)
from build123d.topology.shape_core import Shape
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeSolid
from scipy.spatial import ConvexHull

__all__ = [
  "CENTER",
  "MIN",
  "MAX",
  "align",
  "flip",
  "lift",
  "raise_to",
  "offset_to",
  "extrude_to",
  "shell_loft",
  "make_solid",
  "convex_face_from_points",
]

CENTER = Align.CENTER
MIN = Align.MIN
MAX = Align.MAX

T = TypeVar("T", bound=Shape)


def flip(shape: T) -> T:
  return shape.__class__(shape.wrapped.Reversed())


_flip = flip


def shell_loft(
  *objs: Sequence[Wire | Vertex], ruled: bool = True, flip: bool = False
) -> Shell:
  shell = Shell.make_loft(objs, ruled=ruled)
  return _flip(shell) if flip else shell


def lift(shape: T, dz: float) -> T:
  """Translate along +Z."""
  return shape.moved(Location((0, 0, dz)))


def raise_to(shape: T, z: float) -> T:
  """Translate so its start point sits at absolute height ``z``."""
  return lift(shape, z - (shape @ 0).Z)


def align(
  obj: T,
  align: tuple[Align, Align, Align] = (CENTER, CENTER, CENTER),
  rot=(0, 0, 0),
) -> T:
  """Move a shape so its bounding box aligns to the given anchors.

  Args:
    obj: The shape to reposition (not mutated; a moved copy is returned).
    align: Per-axis anchor (X, Y, Z), each MIN, CENTER, or MAX. CENTER
      centres the bounding box on the origin along that axis; MIN/MAX put the
      box's low/high face on the origin.

  Returns:
    A copy of `obj` translated to the requested alignment.
  """
  if rot != (0, 0, 0):
    obj = obj.moved(Location((0, 0, 0), rot))
  bb = obj.bounding_box()
  return obj.moved(Location(bb.to_align_offset(align)))


def convex_face_from_points(plane: Plane, points) -> Face:
  """Build a planar Face from the convex hull of (near-)coplanar points.

  The points are projected into the plane's local 2D frame, hulled there (which
  drops interior points and yields a clean CCW ordering), then the ordered
  boundary is lifted back to global 3D to form the face.

  Args:
    plane: The plane the points lie in (or near); defines the projection frame.
    points: Iterable of at least 3 points (anything VectorLike).

  Returns:
    A planar Face bounded by the hull of the input points.

  Raises:
    ValueError: If fewer than 3 points are given.
  """
  pts3d = [Vector(p) for p in points]
  if len(pts3d) < 3:
    raise ValueError("Need at least 3 points to form a face.")
  local = [plane.to_local_coords(p) for p in pts3d]
  pts2d = np.array([(v.X, v.Y) for v in local])
  ordered = [pts3d[i] for i in ConvexHull(pts2d).vertices]  # hull is CCW
  return Face(Wire(Polyline(*ordered, close=True)))


def _distance_along_normal(plane: Plane, target: float | VectorLike) -> float:
  """Signed distance from ``plane`` to ``target`` along the plane's normal.

  A point target is projected onto the normal; a bare float is the coordinate
  along the normal's axis (requires an axis-aligned normal).
  """
  if isinstance(target, (int, float)):
    z_dir, origin = tuple(plane.z_dir), tuple(plane.origin)
    axis = max(range(3), key=lambda i: abs(z_dir[i]))
    if abs(abs(z_dir[axis]) - 1) > 1e-6:
      raise ValueError(
        f"scalar target needs an axis-aligned plane (z_dir={plane.z_dir}); "
        "pass a point instead"
      )
    return (target - origin[axis]) * z_dir[axis]
  return (Vector(target) - plane.origin).dot(plane.z_dir)


def offset_to(plane: Plane, target: float | VectorLike) -> Plane:
  """Like ``Plane.offset``, but to an absolute coordinate instead of a distance.

  Returns a copy of ``plane`` translated along its own normal until it passes
  through ``target`` — a coordinate along the normal's axis, or a point (whose
  off-normal components are ignored). ``offset_to(bottom_plane, bb.min.X)``
  replaces ``bottom_plane.offset(bb.min.X - <wherever bottom_plane sits>)``.
  """
  return plane.offset(_distance_along_normal(plane, target))


def extrude_to(
  target: float | VectorLike,
  to_extrude: Face | Sketch | None = None,
  *,
  taper: float = 0.0,
  clean: bool = True,
  mode: Mode = Mode.ADD,
) -> Part:
  """Part Operation: extrude the pending sketches to an absolute coordinate.

  Unlike ``extrude(amount=...)``, the distance is not relative to the sketch
  plane: each face is extruded until it reaches ``target``, however far away
  its own workplane happens to be. Faces on different workplanes each get
  their own distance.

  Args:
    target: Where to extrude to. A point (VectorLike) is projected onto each
      face's normal, so e.g. ``some_bb.center()`` works even when only one of
      its components matters. A bare float is the coordinate along the plane
      normal's axis (requires axis-aligned workplanes), e.g.
      ``extrude_to(heatsink_bb.min.X)`` from a sketch with ``z_dir=(1, 0, 0)``.
    to_extrude: Face or Sketch to extrude; pending faces if None.
    taper: taper angle in degrees.
    clean: Remove extraneous internal structure.
    mode: combination mode.
  """
  context: BuildPart | None = BuildPart._get_context("extrude_to")

  if to_extrude is None:
    if context is None or not context.pending_faces:
      raise ValueError("A face or sketch must be provided")
    faces, planes = context.pending_faces, context.pending_face_planes
    context.pending_faces = []
    context.pending_face_planes = []
  else:
    faces = (
      list(to_extrude)
      if isinstance(to_extrude, (tuple, list, filter))
      else to_extrude.faces()
    )
    planes = [Plane(f) for f in faces]

  new_solids = []
  for face, plane in zip(faces, planes):
    direction = plane.z_dir * _distance_along_normal(plane, target)
    if taper == 0:
      new_solids.append(Solid.extrude(face, direction=direction))
    else:
      new_solids.append(Solid.extrude_taper(face, direction=direction, taper=taper))

  if clean:
    new_solids = [s.clean() for s in new_solids]
  if context is not None:
    context._add_to_context(*new_solids, clean=clean, mode=mode)
  return Part(ShapeList(new_solids).solids())


def make_solid(*shells: Sequence[Shell]) -> Solid:
  """
  Make a solid from one or more shells.
  If multiple shells are given, the first is treated as the outer shell and the rest as inner shells (holes).
  """
  mk = BRepBuilderAPI_MakeSolid()
  for shell in shells:
    mk.Add(shell.wrapped)
  if not mk:
    raise ValueError("Failed to create solid from shells.")
  return Solid(mk.Solid())
