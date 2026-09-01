"""Fastener models for 3D printing. Requires the ``fasteners`` extra (bd_warehouse)."""

from math import pi
from typing import Literal, Union

from bd_warehouse.fastener import (
  Nut,
  read_drill_sizes,
  read_fastener_parameters_from_csv,
)
from build123d import (
  Align,
  BuildSketch,
  Cylinder,
  Face,
  Mode,
  Plane,
  Rectangle,
  RotationLike,
  Solid,
  Vector,
)

__all__ = [
  "FastHeatSetNut",
]


class FastHeatSetNut(Nut):
  fastener_data = read_fastener_parameters_from_csv("heatset_nut_parameters.csv")

  @property
  def nut_diameter(self):
    """Calculate the maximum diameter of the nut"""
    return float(self.fastener_data[self.nut_size][self.fastener_type + ":s"])

  def __init__(
    self,
    size: str,
    fastener_type: Literal["McMaster-Carr", "Hilitchi"] = "McMaster-Carr",
    hand: Literal["right", "left"] = "right",
    simple: bool = True,
    rotation: RotationLike = (0, 0, 0),
    align: Union[None, Align, tuple[Align, Align, Align]] = None,
    mode: Mode = Mode.ADD,
  ):
    super().__init__(size, fastener_type, hand, simple, rotation, align, mode)

  @property
  def fill_factor(self) -> float:
    """Relative size of nut vs hole

    Returns:
        float: Fraction of insert hole filled with heatset nut
    """
    drill_sizes = read_drill_sizes()
    hole_radius = drill_sizes[self.nut_data["drill"].strip()] / 2
    heatset_volume = (
      self.volume + self.nut_data["m"] * pi * (self.thread_diameter / 2) ** 2
    )
    hole_volume = self.nut_data["m"] * pi * hole_radius**2
    return heatset_volume / hole_volume

  def make_nut(self) -> Solid:
    """Build heatset nut object

    Create the heatset nut with a flanged bottom and two plain cylindrical
    sections (knurling removed for fast generation).

    Returns:
        Solid: the heatset nut
    """
    nut = (
      Cylinder(
        self.nut_data["dc"] / 2,
        0.11 * self.nut_data["m"],
        align=(Align.CENTER, Align.CENTER, Align.MIN),
      )
      + Cylinder(
        0.425 * self.nut_data["dc"],
        0.24 * self.nut_data["m"],
        align=(Align.CENTER, Align.CENTER, Align.MIN),
      )
      + Cylinder(
        self.nut_data["s"] / 2,
        0.33 * self.nut_data["m"],
        align=(Align.CENTER, Align.CENTER, Align.MIN),
      ).translate(Vector(0, 0, 0.24 * self.nut_data["m"]))
      + Cylinder(
        0.425 * self.nut_data["dc"],
        0.1 * self.nut_data["m"],
        align=(Align.CENTER, Align.CENTER, Align.MIN),
      ).translate(Vector(0, 0, 0.57 * self.nut_data["m"]))
      + Cylinder(
        self.nut_data["s"] / 2,
        0.33 * self.nut_data["m"],
        align=(Align.CENTER, Align.CENTER, Align.MIN),
      ).translate(Vector(0, 0, 0.67 * self.nut_data["m"]))
    )

    # Bore out the central thread hole
    nut -= Cylinder(
      self.thread_diameter / 2,
      self.nut_data["m"],
      align=(Align.CENTER, Align.CENTER, Align.MIN),
    )

    nut = nut.solid()
    nut.label = "body"

    return nut

  def nut_profile(self) -> Face:  # pragma: no cover
    """Not used but required by the abstract base class"""
    pass

  def nut_plan(self) -> Face:  # pragma: no cover
    """Not used but required by the abstract base class"""
    pass

  def countersink_profile(self, manufacturing_compensation: float = 0.0) -> Face:
    """countersink_profile

    Create the profile for a cavity allowing the heatset nut to be countersunk into the plastic.

    Args:
        manufacturing_compensation (float, optional): used to compensate for over-extrusion
            of 3D printers. A value of 0.2mm will reduce the radius of an external thread
            by 0.2mm (and increase the radius of an internal thread) such that the resulting
            3D printed part matches the target dimensions. Defaults to 0.0.

    Returns:
        Face: The countersink hole profile
    """
    drill_sizes = read_drill_sizes()
    hole_radius = (
      drill_sizes[self.nut_data["drill"].strip()] / 2 + manufacturing_compensation
    )
    with BuildSketch(Plane.XZ) as profile:
      Rectangle(hole_radius, self.nut_data["m"], align=Align.MIN).face()
    return profile.sketch
