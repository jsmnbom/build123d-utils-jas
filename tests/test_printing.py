import math

import pytest
from build123d import Axis, Box, Cylinder, Pos, Rot, Vector

from build123d_utils_jas import fix_horizontal_holes, printing

TOL = 1e-3


def bb(part):
  b = part.bounding_box()
  return b.min, b.max


def check(part, single=True):
  """A cutter must be a valid, non-empty, single solid."""
  assert part.is_valid
  assert part.volume > 0
  if single:
    assert len(part.solids()) == 1
  return part


def close(a, b, tol=TOL):
  assert abs(a - b) < tol, f"{a:.4f} != {b:.4f}"


# ---------------------------------------------------------------- fix_horizontal_holes


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


# ---------------------------------------------------------------- holes


def test_hole_horizontal_roof():
  # d=10, flat 0.4 above the circle -> top at z=5.4, X is the axis
  h = check(printing.hole_horizontal(10, 20))
  lo, hi = bb(h)
  close(hi.Z, 5.4)
  close(lo.Z, -5)
  close(hi.X - lo.X, 20)
  flat_w = 2 * (10 / 2 * math.sqrt(2) - 5.4)  # 90° teardrop: apex r·√2
  top_face = max(h.faces(), key=lambda fc: fc.center().Z)
  close(top_face.bounding_box().size.Y, flat_w, 1e-2)


def test_hole_horizontal_small_stays_pointed():
  # the apex is under the roof line, so no flat is cut
  h4 = check(printing.hole_horizontal(4, 10, roof=1.0))
  close(bb(h4)[1].Z, 2 * math.sqrt(2))


def test_hole_vertical_seam_tip():
  # 120° tip -> apex r/sin60, pointing +Y by default
  v = check(printing.hole_vertical(6, 5))
  lo, hi = bb(v)
  close(hi.Y, 3 / math.sin(math.radians(60)))
  close(lo.Y, -3)
  close(lo.Z, -5)
  close(hi.Z, 0)
  vx = printing.hole_vertical(6, 5, seam_dir=0)
  close(bb(vx)[1].X, 3 / math.sin(math.radians(60)))
  plain = check(printing.hole_vertical(6, 5, seam_dir=None))
  close(bb(plain)[1].Y, 3)


def test_clearance_hole():
  close(printing.clearance_d("M3"), 3.4)
  c = check(printing.clearance_hole("M3", 8, horizontal=True))
  lo, hi = bb(c)
  close(lo.X, -8)
  close(hi.X, 0)
  assert hi.Z > 1.7, "horizontal clearance hole tip points +Z"


# ---------------------------------------------------------------- fasteners


def test_heatset_pocket():
  # M3: Ø4.1 (round, 4.0 + 0.1), depth 6.7, + screw tip
  hs = check(printing.heatset_pocket("M3"))
  lo, hi = bb(hs)
  close(hi.X - lo.X, 4.1)
  close(lo.Z, -6.7)
  hs2 = check(printing.heatset_pocket("M3", screw_depth=3))
  close(bb(hs2)[0].Z, -9.7)
  check(printing.heatset_pocket("M3", horizontal=True, screw_depth=2))


def test_nut_trap():
  # M3 press: across flats 5.6 along Y, corners along X, depth 2.7
  n = check(printing.nut_trap("M3"))
  lo, hi = bb(n)
  close(hi.Y - lo.Y, 5.6)
  close(hi.X - lo.X, 5.6 / math.cos(math.radians(30)))
  close(lo.Z, -2.7)
  ns = check(printing.nut_trap("M3", fit="drop", slot=10))
  lo, hi = bb(ns)
  close(hi.Y - lo.Y, 5.8)
  close(hi.X, 10)


def test_counterbore_up_bridges():
  cb = check(printing.counterbore_up(3.4, 6.5, 3.4, 10))
  lo, hi = bb(cb)
  close(lo.Z, 0)
  close(hi.Z, 10)
  # at layer 1 the cut is (bore ∩ slot): width 3.4 in Y, spans the bore in X
  sl = (cb & Pos(0, 0, 3.4 + 0.1) * Box(20, 20, 0.01)).bounding_box().size
  close(sl.Y, 3.4)
  close(sl.X, 6.5, 1e-2)
  sq = (cb & Pos(0, 0, 3.4 + 0.3) * Box(20, 20, 0.01)).bounding_box().size
  close(sq.X, 3.4)
  close(sq.Y, 3.4)
  check(printing.counterbore_up(3.4, 5.6, 2.7, 10, shape="hex"))


# ---------------------------------------------------------------- fits


def test_crush_rib_bore():
  # 22 mm bearing: bore 22.4, rib tips on Ø21.8
  cr = check(printing.crush_rib_bore(22, 7))
  lo, hi = bb(cr)
  close(hi.X - lo.X, 22.4 + 2 * 0.5, 1e-2)  # incl. lead-in
  assert cr.is_inside(Vector(21.8 / 2 - 0.02, 0, -4)), "inside rib tip circle is cut"
  assert not cr.is_inside(Vector(21.8 / 2 + 0.02, 0, -4)), "rib material reaches Ø21.8"
  between = 22.4 / 2 - 0.02  # 30° is midway between ribs at 0° and 60°
  assert cr.is_inside(
    Vector(between * math.cos(math.pi / 6), between * math.sin(math.pi / 6), -4)
  ), "between ribs the bore reaches Ø22.4"
  assert not cr.is_inside(Vector(22.4 / 2 + 0.02, 0, -4)), "bore wall at Ø22.4"


def test_hex_press_hole():
  check(printing.hex_press_hole(3, 6))


# ---------------------------------------------------------------- misc


def test_zip_tie_channel():
  z = check(printing.zip_tie_channel())
  s = z.bounding_box().size
  close(s.X, 3.5)
  close(s.Y, 5.5)
  close(s.Z, 2.75)


def test_mouse_ear_and_foot_chamfer():
  me = check(printing.mouse_ear())
  close(me.bounding_box().size.Z, 0.2)
  blk = Pos(0, 0, 5) * Box(20, 20, 10) - Pos(0, 0, 10) * printing.hole_vertical(3.4, 10)
  fc = check(printing.foot_chamfer(blk))
  assert fc.volume < blk.volume, "chamfer removed material"
  bottom = fc.faces().sort_by(Axis.Z)[0]
  close(bottom.bounding_box().size.X, 20 - 0.8, 1e-2)  # shrinks by 2×0.4


def test_numbers():
  close(printing.screw_into_plastic_d("M3"), 2.7)
  close(printing.thread_forming_d(4), 3.4)
  close(printing.bore_d(10), 10.4)
  close(printing.bore_d(22, gap=0, p=printing.ABS), 22 * 1.007 + 0.2)
  y = printing.snap_cantilever(15, 1.5)
  close(y, 1.09 * 0.017 * 225 / 1.5)


def test_public_helpers_exist():
  # projects used to reach into dfam._teardrop / dfam._cut_into
  cut = check(printing.cut_into(5, True, lambda: printing.teardrop_sketch(6, 90, 0.4)))
  lo, hi = bb(cut)
  close(lo.X, -5)
  close(hi.Z, 3.4)
