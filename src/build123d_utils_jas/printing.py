"""Design-for-printing helpers: cutters for holes, fastener pockets and fits, plus
fixes applied to finished geometry.

Conventions
- Print direction is +Z (bed at the bottom).
- Every helper returns a *cutter* Part to subtract
  (``part -= Pos(x, y, top) * nut_trap("M3")``; inside a ``BuildPart``:
  ``insert(Pos(...) * cutter, mode=Mode.SUBTRACT)``), except ``mouse_ear`` (add) and
  ``foot_chamfer`` / ``fix_horizontal_holes`` (return the modified part).
- Vertical cutters: mouth at z=0, cutting toward -Z (like drilling into a top face).
  ``counterbore_up`` is the exception: mouth on the bed side at z=0, cutting toward +Z.
- Horizontal cutters (``horizontal=True``): mouth at x=0, cutting toward -X, with any
  teardrop tip pointing +Z. Rotate them about Z only, or the tip stops pointing up.

Process scope
- All defaults are conservative portable numbers for FDM at 0.4 nozzle / 0.2 layer,
  chosen so parts work without test prints. They live in ``Params``: ``P`` is the
  default and ``ABS`` adds XY shrink compensation. For another process build a preset
  with ``dataclasses.replace(P, ...)`` and pass it as ``p=``.
- FDM-only (pointless or wrong for resin/SLS): the teardrops (``hole_horizontal``,
  ``clearance_hole(horizontal=True)``, ``heatset_pocket(horizontal=True)``,
  ``fix_horizontal_holes``), the seam tip in ``hole_vertical``, the bridge trick in
  ``counterbore_up``, ``mouse_ear``, ``foot_chamfer`` and the in-layer-plane
  ``SNAP_STRAIN`` values.
- Process-independent geometry with FDM-tuned offsets: ``nut_trap``, ``heatset_pocket``,
  ``clearance_hole``, ``bore_d``, ``crush_rib_bore``, ``hex_press_hole``,
  ``snap_cantilever``.
- Process-independent data: ``NUT``, ``CLEARANCE``, ``TAP_DRILL``, ``HEATSET``,
  ``zip_tie_channel``.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, replace

from build123d import (
  Align,
  Axis,
  BuildPart,
  BuildSketch,
  Circle,
  Compound,
  Cone,
  Cylinder,
  GeomType,
  Locations,
  Mode,
  Part,
  Plane,
  Polygon,
  Polyline,
  Pos,
  Rectangle,
  RegularPolygon,
  Rot,
  Solid,
  Vector,
  Wire,
  chamfer,
  extrude,
)
from build123d.topology.shape_core import Shape
from OCP.Geom import Geom_ConicalSurface, Geom_CylindricalSurface

from .viewer import show_object

__all__ = [
  "ABS",
  "CLEARANCE",
  "HEATSET",
  "HEATSET_CAD_EXTRA",
  "NUT",
  "SNAP_STRAIN",
  "TAP_DRILL",
  "P",
  "Params",
  "bore_d",
  "bore_geometry",
  "clearance_d",
  "clearance_hole",
  "counterbore_up",
  "crush_rib_bore",
  "cut_into",
  "fix_horizontal_holes",
  "foot_chamfer",
  "heatset_pocket",
  "hex_press_hole",
  "hole_horizontal",
  "hole_vertical",
  "mouse_ear",
  "nominal_d",
  "nut_trap",
  "screw_into_plastic_d",
  "snap_cantilever",
  "teardrop_sketch",
  "teardrop_wire",
  "thread_forming_d",
  "zip_tie_channel",
]


@dataclass(frozen=True)
class Params:
  """Process numbers. Defaults are FDM, 0.4 nozzle / 0.2 layer."""

  layer: float = 0.2  # layer height
  line: float = 0.45  # extrusion line width
  overhang: float = 45.0  # max overhang, degrees from vertical
  bridge_max: float = 10.0  # longest bridge to rely on
  slide: float = 0.2  # gap per face, printed<->printed clearance/sliding fit
  pip: float = 0.3  # gap per face, print-in-place parts
  hole_undersize: float = 0.2  # small printed holes come out this much small (on Ø)
  # XY shrink fraction for bores that take NON-printed parts only (ABS ≈ 0.007).
  # Printed<->printed fits shrink together and never use this.
  shrink_xy: float = 0.0


P = Params()
ABS = replace(P, shrink_xy=0.007)

# ---------------------------------------------------------------- tables (mm)

# ISO 4032 hex nut: (across flats s, thickness m)
NUT = {
  "M2": (4.0, 1.6),
  "M2.5": (5.0, 2.0),
  "M3": (5.5, 2.4),
  "M4": (7.0, 3.2),
  "M5": (8.0, 4.7),
  "M6": (10.0, 5.2),
  "M8": (13.0, 6.8),
}

# ISO 273 clearance hole: (fine, medium, coarse)
CLEARANCE = {
  "M2": (2.2, 2.4, 2.6),
  "M2.5": (2.7, 2.9, 3.1),
  "M3": (3.2, 3.4, 3.6),
  "M4": (4.3, 4.5, 4.8),
  "M5": (5.3, 5.5, 5.8),
  "M6": (6.4, 6.6, 7.0),
  "M8": (8.4, 9.0, 10.0),
}

# ISO tap drill, for cutting threads with a tap after printing
TAP_DRILL = {
  "M2": 1.6,
  "M2.5": 2.05,
  "M3": 2.5,
  "M4": 3.3,
  "M5": 4.2,
  "M6": 5.0,
  "M8": 6.8,
}

# CNC Kitchen standard knurled heat-set inserts: (datasheet hole Ø, length, OD, min wall)
HEATSET = {
  "M2": (3.2, 4.0, 3.6, 1.3),
  "M2.5": (4.0, 4.0, 4.6, 1.6),
  "M3": (4.0, 5.7, 4.6, 1.6),
  "M4": (5.7, 8.1, 6.3, 2.1),
  "M5": (6.5, 9.5, 7.1, 2.6),
  "M6": (8.1, 12.7, 8.7, 3.3),
}
HEATSET_CAD_EXTRA = 0.1  # printed holes come out small; added to the datasheet Ø

# Allowable bending strain for printed cantilever snaps that flex IN the layer plane:
# (one-time assembly, repeated assembly). ABS is derived from a printed-specimen
# datasheet; PETG/PLA are weaker estimates. Never flex a snap across layers.
SNAP_STRAIN = {"ABS": (0.029, 0.017), "PETG": (0.018, 0.011), "PLA": (0.007, 0.004)}


def nominal_d(size: str) -> float:
  """'M3' -> 3.0"""
  return float(size.upper().lstrip("M"))


def clearance_d(size: str, fit: str = "medium") -> float:
  """ISO 273 clearance hole Ø. fit: 'fine' (locating), 'medium', 'coarse'."""
  return CLEARANCE[size][("fine", "medium", "coarse").index(fit)]


def screw_into_plastic_d(size: str) -> float:
  """Hole Ø for a metric machine screw driven straight into plastic (0.9·d, M3 -> 2.7).
  Holds only ~1 Nm on M3, so use it for low-reuse joints."""
  return round(0.9 * nominal_d(size), 2)


def thread_forming_d(d: float, p: Params = P) -> float:
  """Hole Ø for a thread-forming plastics screw (EJOT PT/Delta PT style) of major Ø d:
  0.8·d from molding guides, plus the printed-hole undersize. Boss OD >= 2·d,
  engagement >= 2·d."""
  return round(0.8 * d + p.hole_undersize, 2)


def bore_d(d: float, gap: float = 0.1, p: Params = P) -> float:
  """Hole Ø for a NON-printed round part (shaft, magnet, dowel) of nominal Ø d.
  gap is the per-face clearance after compensation (0 gives a light press fit)."""
  return round(d * (1 + p.shrink_xy) + p.hole_undersize + 2 * gap, 3)


# ---------------------------------------------------------------- profiles


def teardrop_sketch(d: float, apex_deg: float, roof: float | None) -> None:
  """Draw a teardrop into the active BuildSketch, tip toward local +Y.

  apex_deg: included tip angle (90 for overhang teardrops, 120 for seam tips).
  roof: flat cut this far above the circle top (None = pointed).
  Use this when building a cutter up front; `teardrop_wire` is the 3D counterpart that
  `fix_horizontal_holes` applies to bores that already exist in finished geometry."""
  r = d / 2
  half = math.radians(apex_deg / 2)
  phi = math.pi / 2 - half  # tangent point, measured from +Y
  apex = r / math.sin(half)
  tx, ty = r * math.sin(phi), r * math.cos(phi)
  Circle(r)
  Polygon((tx, ty), (0, apex), (-tx, ty))
  if roof is not None and r + roof < apex:
    with Locations((0, r + roof)):
      Rectangle(4 * apex, 2 * apex, align=(Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)


def cut_into(depth: float, horizontal: bool, draw: Callable[[], None]) -> Part:
  """Extrude whatever `draw()` sketches, from the mouth at the origin into the part.

  Vertical: sketch on XY, cut toward -Z. Horizontal: sketch on YZ (local +Y is world
  +Z, so a teardrop tip points up), cut toward -X."""
  plane = Plane.YZ if horizontal else Plane.XY
  direction = (-1, 0, 0) if horizontal else (0, 0, -1)
  with BuildPart() as bp:
    with BuildSketch(plane):
      draw()
    extrude(amount=depth, dir=direction)
  return bp.part


# ---------------------------------------------------------------- holes


def hole_horizontal(
  d: float, length: float, roof: float | None = 0.4, apex_deg: float = 90
) -> Part:
  """Through-hole along X, centred on the origin, with a teardrop pointing +Z.
  Default: a 90° teardrop cut flat 0.4 mm above the circle, so bridge droop doesn't
  touch the fit. Small holes stay nearly pointed."""
  with BuildPart() as bp:
    with BuildSketch(Plane.YZ):
      teardrop_sketch(d, apex_deg, roof)
    extrude(amount=length / 2, both=True)
  return bp.part


def hole_vertical(d: float, depth: float, seam_dir: float | None = 90) -> Part:
  """Vertical hole with a tiny 120° tip where the perimeter seam can hide.
  seam_dir: direction of the tip in degrees from +X (point it away from the
  critical side). None gives a plain circle."""

  def draw():
    if seam_dir is None:
      Circle(d / 2)
    else:
      teardrop_sketch(d, 120, None)

  part = cut_into(depth, False, draw)
  return part if seam_dir is None else Rot(0, 0, seam_dir - 90) * part


def clearance_hole(
  size: str, depth: float, fit: str = "medium", horizontal: bool = False
) -> Part:
  """Screw clearance hole (ISO 273). Horizontal holes get the teardrop."""
  d = clearance_d(size, fit)
  return _horizontal_blind(d, depth) if horizontal else hole_vertical(d, depth)


def _horizontal_blind(d: float, depth: float, roof: float | None = 0.4) -> Part:
  """Teardrop hole from the mouth at x=0 toward -X."""
  return cut_into(depth, True, lambda: teardrop_sketch(d, 90, roof))


# ---------------------------------------------------------------- fasteners


def heatset_pocket(
  size: str,
  through: bool = False,
  screw_depth: float = 0.0,
  horizontal: bool = False,
  p: Params = P,
) -> Part:
  """Pocket for a CNC Kitchen-style knurled heat-set insert.
  Ø = datasheet + 0.1 mm. Depth = insert length + 1 mm (blind) or length (through).
  screw_depth adds a clearance hole beyond the pocket for the screw tip.
  Keep at least HEATSET[size][3] of wall around the pocket. Set the iron to roughly
  print temperature + 10–20 °C (ABS about 265 °C).
  Horizontal pockets get a teardrop flat at one layer above the circle (unverified)."""
  hole, length, _, _ = HEATSET[size]
  d = hole + HEATSET_CAD_EXTRA
  depth = length if through else length + 1.0
  if horizontal:
    pocket = _horizontal_blind(d, depth, roof=p.layer)
  else:
    pocket = cut_into(depth, False, lambda: Circle(d / 2))
  if screw_depth > 0:
    tip = clearance_hole(size, screw_depth, horizontal=horizontal)
    pocket += Pos(-depth, 0, 0) * tip if horizontal else Pos(0, 0, -depth) * tip
  return pocket


def _hex(af: float) -> None:
  """Hexagon with flats parallel to X (across flats = af) in the active sketch."""
  RegularPolygon(af / 2, 6, major_radius=False, rotation=0)


def nut_trap(
  size: str, fit: str = "press", depth: float | None = None, slot: float = 0.0
) -> Part:
  """Hex nut pocket, mouth at z=0, cutting toward -Z. The hex has flats parallel to X.
  fit: 'press' (across flats = s + 0.1, pressed in, stays put) or
       'drop' (s + 0.3, falls in freely).
  depth defaults to nut thickness + 0.3.
  slot > 0 adds a side-entry slot of width = across flats, running from the nut
  centre toward +X by `slot` mm (make it reach an outside face).
  For a buried trap with the screw hole above it, start that hole one layer above
  the trap ceiling (sacrificial layer, drill it out) or use `counterbore_up`.
  Do not use bd_warehouse captive_nut pockets: they are rounded rectangles."""
  s, m = NUT[size]
  af = s + (0.1 if fit == "press" else 0.3)
  depth = m + 0.3 if depth is None else depth

  def draw():
    _hex(af)
    if slot > 0:
      Rectangle(slot, af, align=(Align.MIN, Align.CENTER))

  return cut_into(depth, False, draw)


def counterbore_up(
  hole_d: float,
  bore: float,
  bore_depth: float,
  hole_len: float,
  shape: str = "circle",
  p: Params = P,
) -> Part:
  """Counterbore or nut pocket that opens DOWNWARD (bed side, mouth at z=0, cutting +Z),
  using the overhanging-counterbore trick so it prints without supports:
    layer 1 above the bore: slot hole_d wide spanning the bore (bridges left/right)
    layer 2: hole_d square (perpendicular bridges)
    then the round hole continues up to hole_len (measured from z=0).
  shape: 'circle' (bore = Ø) or 'hex' (bore = across flats, flats parallel to X)."""

  def pocket():
    if shape == "hex":
      _hex(bore)
    else:
      Circle(bore / 2)

  with BuildPart() as bp:
    with BuildSketch():
      pocket()
    extrude(amount=bore_depth)
    with BuildSketch(Plane.XY.offset(bore_depth)):
      pocket()
      Rectangle(4 * bore, hole_d, mode=Mode.INTERSECT)
    extrude(amount=p.layer)
    with BuildSketch(Plane.XY.offset(bore_depth + p.layer)):
      Rectangle(hole_d, hole_d)
    extrude(amount=p.layer)
    with BuildSketch(Plane.XY.offset(bore_depth)):
      Circle(hole_d / 2)
    extrude(amount=hole_len - bore_depth)
  return bp.part


# ---------------------------------------------------------------- fits


def crush_rib_bore(
  d: float, depth: float, ribs: int = 6, lead_in: float = 0.5, p: Params = P
) -> Part:
  """Press-fit bore for a NON-printed round part of Ø d (bearing, shaft, dowel).
  Bore Ø d+0.4, with `ribs` half-round ribs whose tips sit on Ø d-0.2 (Rahix's
  numbers, read as diameters). One assembly only: ribs deform plastically.
  Mouth at z=0, cutting toward -Z, with a lead-in cone that also tapers the rib tops."""
  D = d * (1 + p.shrink_xy) + 0.4
  tip = d * (1 + p.shrink_xy) - 0.2
  rib_r = (D - tip) / 2  # rib protrudes by its own radius
  with BuildPart() as bp:
    with BuildSketch():
      Circle(D / 2)
      for i in range(ribs):
        a = 2 * math.pi * i / ribs
        with Locations((D / 2 * math.cos(a), D / 2 * math.sin(a))):
          Circle(rib_r, mode=Mode.SUBTRACT)
    extrude(amount=depth, dir=(0, 0, -1))
    if lead_in > 0:
      with Locations((0, 0, -lead_in)):
        Cone(
          D / 2, D / 2 + lead_in, lead_in, align=(Align.CENTER, Align.CENTER, Align.MIN)
        )
  return bp.part


def hex_press_hole(
  d: float, depth: float, af: float | None = None, lead_in: float = 0.4
) -> Part:
  """Hex hole for a light press fit on a round pin of Ø d (R2.8). The flats bend
  instead of the wall stretching. Across flats defaults to d: the printed undersize
  provides the interference. Best for small Ø; use crush ribs for larger ones."""
  af = d if af is None else af
  with BuildPart() as bp:
    with BuildSketch():
      _hex(af)
    extrude(amount=depth, dir=(0, 0, -1))
    if lead_in > 0:
      r = af / 2 / math.cos(math.radians(30))
      with Locations((0, 0, -lead_in)):
        Cone(
          af / 2, r + lead_in, lead_in, align=(Align.CENTER, Align.CENTER, Align.MIN)
        )
  return bp.part


# ---------------------------------------------------------------- misc features


def zip_tie_channel() -> Part:
  """Channel for 100 mm zip ties. Surface at z=0, material below. The tie dives into
  one slot, wraps under a Ø2.5 core and comes out of the other slot. Channel width
  is 3.5 along X; the core runs along X.
  Orient the part so the core axis is parallel to the bed (never vertical)."""
  with BuildPart() as bp:
    with BuildSketch(Plane.YZ):
      Circle(2.75)
      Circle(1.25, mode=Mode.SUBTRACT)
      Rectangle(6, 3, align=(Align.CENTER, Align.MIN), mode=Mode.SUBTRACT)
    extrude(amount=1.75, both=True)
  return bp.part


def mouse_ear(d: float = 8.0, p: Params = P) -> Part:
  """One-layer disc to ADD at a corner that tends to lift (z = 0..layer).
  Centre it on the corner and cut it off after printing."""
  return Cylinder(d / 2, p.layer, align=(Align.CENTER, Align.CENTER, Align.MIN))


def foot_chamfer(part: Part, size: float = 0.4) -> Part:
  """45° chamfer on every bed-side edge, to absorb elephant foot. Hole rims on the
  bottom face get it too. Do this before other bottom-edge features."""
  return chamfer(part.edges().group_by(Axis.Z)[0], size)


def snap_cantilever(
  length: float,
  thickness: float,
  material: str = "ABS",
  repeated: bool = True,
  tapered: bool = True,
) -> float:
  """Max deflection (mm) at the tip of a cantilever snap arm that flexes in the
  layer plane. Bayer/Covestro: y = k·ε·L²/t, k = 0.67 for a constant section,
  1.09 when t tapers to t/2 at the tip. Make the undercut about 0.7·y
  (at least 0.3 mm); root fillet >= 0.5·t; t >= 1, width >= 5."""
  eps = SNAP_STRAIN[material][1 if repeated else 0]
  k = 1.09 if tapered else 0.67
  return k * eps * length**2 / thickness


# ---------------------------------------------------------------- fixes on finished geometry

# Self-supporting "flat-roof teardrop" for horizontal-ish round holes.
#
# A horizontal bore sags when FDM-printed because the top ~90deg arc overhangs
# steeper than 45deg. We fix that by cutting the top of the hole into a teardrop:
# two 45deg walls rise from the bore and are capped by a short flat ceiling
# (a single easy bridge layer) instead of a sharp peak. The bore stays round in
# the load-bearing region, so press-fit tolerances are unaffected.
#
# Works for both cylindrical and conical bores. For a cone the section scales
# linearly along the axis (radius is affine in the surface's v-parameter), so a
# straight loft between the two end sections reproduces the exact radius
# everywhere in between.

# overhang angle of the teardrop walls (self-supporting)
WALL_ANGLE_DEG = 45.0
# flat ceiling height above the bore top, as a fraction of radius
ROOF_RISE_FACTOR = 0.1
# |axis . Z| below this counts as horizontal-ish (~20deg)
HORIZONTAL_TOL = 0.34

Z = Vector(0, 0, 1)


def teardrop_wire(center: Vector, radius: float, up: Vector, side: Vector) -> Wire:
  """Cross-section of the material to remove to open a bore into a flat-roof teardrop.

  `up` points toward the build direction (world +Z projected into the bore's
  cross-section plane) and `side` is the in-plane perpendicular. The returned
  quad spans from the two 45deg tangent points on the bore up to a short flat
  ceiling; cutting it (the bore below is already void) leaves a teardrop hole.
  The roof sits at 10 % of the radius above the bore; `teardrop_sketch` is the 2D
  version for cutters built up front, with a fixed-height roof.
  """
  a = math.radians(WALL_ANGLE_DEG)
  sin_a, cos_a = math.sin(a), math.cos(a)

  tx, ty = (
    radius * sin_a,
    radius * cos_a,
  )  # tangent points where the walls meet the bore
  apex_h = radius / cos_a  # height a pointed teardrop's apex would reach
  roof_h = min(
    radius * (1.0 + ROOF_RISE_FACTOR), apex_h * 0.95
  )  # keep the roof below the apex
  roof_half = (radius - roof_h * cos_a) / sin_a  # half-width of the flat ceiling

  pts2d = [(-tx, ty), (tx, ty), (roof_half, roof_h), (-roof_half, roof_h)]
  pts3d = [center + side * s + up * u for s, u in pts2d]
  return Wire(Polyline(*pts3d, close=True))


def bore_geometry(surface):
  """For a cylindrical/conical surface return (axis, radius(v), center(v)) or None.

  radius(v) and center(v) give the bore radius and on-axis center at the
  surface's v-parameter; both are affine in v for these surfaces.
  """
  if isinstance(surface, Geom_CylindricalSurface):
    axis = Axis(surface.Axis())
    pos, d = axis.position, axis.direction
    r = surface.Radius()
    return axis, (lambda v: r), (lambda v: pos + d * v)
  if isinstance(surface, Geom_ConicalSurface):
    axis = Axis(surface.Axis())
    pos, d = axis.position, axis.direction
    r0, ang = surface.RefRadius(), surface.SemiAngle()
    sin_ang, cos_ang = math.sin(ang), math.cos(ang)
    return axis, (lambda v: r0 + v * sin_ang), (lambda v: pos + d * (v * cos_ang))
  return None


def fix_horizontal_holes(shape: Shape, debug: bool = False) -> Shape:
  """Cut every horizontal-ish round bore of a finished shape into a flat-roof teardrop.

  Use this on geometry whose holes were not made with the cutters above (imported
  parts, holes from `Hole`/`Cylinder`). FDM-only."""
  cutters = []
  faces = shape.faces().filter_by(
    lambda f: f.geom_type in (GeomType.CYLINDER, GeomType.CONE)
  )
  for face in faces:
    geom = bore_geometry(face.geom_adaptor())
    if geom is None:
      continue
    axis, radius_at, center_at = geom

    # Only horizontal-ish bores need the teardrop; near-vertical ones print fine.
    if abs(axis.direction.dot(Z)) >= HORIZONTAL_TOL:
      continue

    # Only complete (360deg) round faces.
    u_min, u_max, v_min, v_max = face._uv_bounds()
    if not math.isclose(u_max - u_min, math.tau):
      continue

    # Only concave faces (actual holes); skip external cylinders/cones whose
    # outward normal points away from the axis.
    p = face.position_at(0.5, 0.5)
    on_axis = axis.position + axis.direction * (p - axis.position).dot(axis.direction)
    if face.normal_at(p).dot(p - on_axis) > 0:
      continue

    # Teardrop "up" = build direction projected into the bore's cross-section plane.
    up = Z - axis.direction * Z.dot(axis.direction)
    if up.length < 1e-6:
      continue
    up = up.normalized()
    side = axis.direction.cross(up).normalized()

    # Build the teardrop section at each end (extended past the mouths) and loft.
    v0, v1 = v_min, v_max
    w0 = teardrop_wire(center_at(v0), max(radius_at(v0), 0.1), up, side)
    w1 = teardrop_wire(center_at(v1), max(radius_at(v1), 0.1), up, side)
    cutters.append(Solid.make_loft([w0, w1]))

  if debug:
    show_object(
      Compound(
        None,
        children=[
          Compound(None, label=f"{i}", children=[f, c])
          for i, (f, c) in enumerate(zip(faces, cutters))
        ],
      ),
      name="fix_horizontal_holes debug",
      alpha=0.4,
      color="RED",
    )

  for cutter in cutters:
    shape = shape.cut(cutter)
  return shape
