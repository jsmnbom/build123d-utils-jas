"""FDM-printability fixes applied to finished geometry."""

import math

from build123d import Axis, Compound, GeomType, Polyline, Solid, Vector, Wire
from build123d.topology.shape_core import Shape
from OCP.Geom import Geom_ConicalSurface, Geom_CylindricalSurface

from .viewer import show_object

__all__ = [
  "fix_horizontal_holes",
  "teardrop_wire",
  "bore_geometry",
]

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
