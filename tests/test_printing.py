import pytest
from build123d import Axis, Box, Cylinder, Rot

from build123d_utils_jas import fix_horizontal_holes


def box_with_hole(axis: Axis):
  hole = Cylinder(2, 20)
  if axis == Axis.X:
    hole = Rot(0, 90, 0) * hole
  return Box(10, 10, 10) - hole


def test_horizontal_hole_gets_teardrop():
  part = box_with_hole(Axis.X)
  fixed = fix_horizontal_holes(part)
  # the teardrop cut removes extra material above the bore
  assert fixed.volume < part.volume - 1e-3
  assert fixed.is_valid


def test_vertical_hole_untouched():
  part = box_with_hole(Axis.Z)
  fixed = fix_horizontal_holes(part)
  assert fixed.volume == pytest.approx(part.volume, abs=1e-6)


def test_external_cylinder_untouched():
  part = Rot(0, 90, 0) * Cylinder(3, 10)
  fixed = fix_horizontal_holes(part)
  assert fixed.volume == pytest.approx(part.volume, abs=1e-6)
