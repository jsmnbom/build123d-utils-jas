import pytest

bd_warehouse = pytest.importorskip("bd_warehouse")

from build123d_utils_jas import FastHeatSetNut  # noqa: E402


def test_heatset_nut_builds():
  nut = FastHeatSetNut("M3-0.5-Standard")
  assert nut.volume > 0
  assert nut.nut_diameter > 3


def test_fill_factor_reasonable():
  nut = FastHeatSetNut("M3-0.5-Standard")
  assert 0.3 < nut.fill_factor < 1.5
