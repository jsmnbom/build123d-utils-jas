import copy
import math

import pytest
from build123d import Box, Location, Plane
from build123d.topology.shape_core import Shape

from build123d_utils_jas import apply_fast_patch, no_fast_patch, remove_fast_patch
from build123d_utils_jas import fast_patch as fp


def test_import_does_not_patch():
  assert Shape.__dict__.get("moved") is not fp._moved


def test_apply_and_remove_are_idempotent():
  stock = {name: Shape.__dict__.get(name) for name in fp._PATCHES}
  apply_fast_patch()
  apply_fast_patch()
  for name, func in fp._PATCHES.items():
    assert Shape.__dict__[name] is func
  remove_fast_patch()
  remove_fast_patch()
  for name, original in stock.items():
    assert Shape.__dict__.get(name) is original


def test_moved_accepts_location_and_plane():
  apply_fast_patch()
  box = Box(1, 2, 3)
  by_loc = box.moved(Location((5, 0, 0)))
  assert by_loc.bounding_box(optimal=True).center().X == pytest.approx(5)
  by_plane = box.moved(Plane.XY.offset(7))
  assert by_plane.bounding_box(optimal=True).center().Z == pytest.approx(7)


def test_copy_preserves_geometry_and_location():
  apply_fast_patch()
  box = Box(1, 2, 3).moved(Location((1, 2, 3)))
  dup = copy.copy(box)
  assert dup.volume == pytest.approx(box.volume)
  assert (dup.center() - box.center()).length == pytest.approx(0)
  # copies are independent: moving the copy leaves the original in place
  moved = dup.moved(Location((10, 0, 0)))
  assert (box.center() - moved.center()).length == pytest.approx(10)


def test_located_and_transform():
  apply_fast_patch()
  box = Box(1, 1, 1)
  there = box.located(Location((0, 0, 9)))
  assert there.center().Z == pytest.approx(9)
  rot = box.rotate(__import__("build123d").Axis.Z, 45)
  assert rot.volume == pytest.approx(box.volume)


def test_no_fast_patch_restores_stock():
  stock_moved = Shape.__dict__.get("moved")
  apply_fast_patch()
  assert Shape.__dict__["moved"] is fp._moved
  with no_fast_patch():
    assert Shape.__dict__.get("moved") is stock_moved
    # stock methods still work inside the block
    assert Box(1, 1, 1).moved(Location((1, 0, 0))).center().X == pytest.approx(1)
  assert Shape.__dict__["moved"] is fp._moved


def test_no_fast_patch_when_never_applied():
  stock_moved = Shape.__dict__.get("moved")
  with no_fast_patch():
    assert Shape.__dict__.get("moved") is stock_moved
  assert Shape.__dict__.get("moved") is stock_moved


def test_patched_results_match_stock():
  box = Box(2, 3, 4)
  stock_bb = box.moved(Location((1, 1, 1), (0, 0, 30))).bounding_box(optimal=True)
  apply_fast_patch()
  fast_bb = box.moved(Location((1, 1, 1), (0, 0, 30))).bounding_box(optimal=True)
  assert (stock_bb.center() - fast_bb.center()).length == pytest.approx(0, abs=1e-6)
  assert stock_bb.size.X == pytest.approx(fast_bb.size.X, abs=1e-6)
  assert math.isclose(stock_bb.size.Z, fast_bb.size.Z, abs_tol=1e-6)
