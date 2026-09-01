import pytest
from build123d import (
  Box,
  BuildPart,
  BuildSketch,
  Circle,
  Edge,
  Plane,
  Rectangle,
  Shell,
  Wire,
)

from build123d_utils_jas import (
  CENTER,
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
from build123d_utils_jas.helpers import _distance_along_normal


def test_align_min_puts_bb_corner_at_origin():
  box = align(Box(2, 4, 6), (MIN, MIN, MIN))
  bb = box.bounding_box(optimal=True)
  assert (bb.min.X, bb.min.Y, bb.min.Z) == pytest.approx((0, 0, 0), abs=1e-6)
  centered = align(box, (CENTER, CENTER, CENTER))
  assert centered.bounding_box(optimal=True).center().length == pytest.approx(0, abs=1e-6)


def test_align_with_rotation():
  box = align(Box(2, 4, 6), (MIN, MIN, MIN), rot=(0, 0, 90))
  bb = box.bounding_box(optimal=True)
  assert bb.size.X == pytest.approx(4, abs=1e-6)
  assert bb.size.Y == pytest.approx(2, abs=1e-6)


def test_lift_and_raise_to():
  edge = Edge.make_line((0, 0, 1), (1, 0, 1))
  assert (lift(edge, 5) @ 0).Z == pytest.approx(6)
  assert (raise_to(edge, 10) @ 0).Z == pytest.approx(10)


def test_flip_reverses_orientation():
  face = Plane.XY * Rectangle(1, 1)
  flipped = flip(face.face())
  n0 = face.face().normal_at()
  n1 = flipped.normal_at()
  assert (n0 + n1).length == pytest.approx(0, abs=1e-6)


def test_offset_to_scalar_and_point():
  plane = offset_to(Plane.XY, 5)
  assert plane.origin.Z == pytest.approx(5)
  plane = offset_to(Plane.XY.offset(2), (100, -3, 7))
  assert plane.origin.Z == pytest.approx(7)


def test_offset_to_scalar_requires_axis_aligned():
  tilted = Plane.XY.rotated((30, 0, 0))
  with pytest.raises(ValueError, match="axis-aligned"):
    _distance_along_normal(tilted, 5.0)


def test_extrude_to_in_context():
  with BuildPart() as bp:
    with BuildSketch(Plane.XY.offset(2)):
      Rectangle(1, 1)
    extrude_to(10)
  bb = bp.part.bounding_box(optimal=True)
  assert bb.min.Z == pytest.approx(2, abs=1e-6)
  assert bb.max.Z == pytest.approx(10, abs=1e-6)
  assert bp.part.volume == pytest.approx(8, abs=1e-6)


def test_extrude_to_outside_context():
  face = Plane.XY.offset(1) * Rectangle(2, 2)
  part = extrude_to(4, face.face())
  assert part.volume == pytest.approx(2 * 2 * 3, abs=1e-6)


def test_extrude_to_requires_faces():
  with pytest.raises(ValueError, match="face or sketch"):
    extrude_to(5)


def test_shell_loft_and_make_solid():
  w0 = Wire(Plane.XY * Circle(2).face().outer_wire())
  w1 = Wire(Plane.XY.offset(3) * Circle(1).face().outer_wire())
  shell = shell_loft(w0, w1)
  assert isinstance(shell, Shell)
  assert shell.area > 0

  closed = Box(2, 2, 2).shells()[0]
  solid = make_solid(closed)
  assert solid.volume == pytest.approx(8, abs=1e-6)


def test_convex_face_from_points():
  pts = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (0.5, 0.5, 0)]  # one interior
  face = convex_face_from_points(Plane.XY, pts)
  assert face.area == pytest.approx(1, abs=1e-6)
  with pytest.raises(ValueError, match="at least 3"):
    convex_face_from_points(Plane.XY, [(0, 0, 0), (1, 0, 0)])
