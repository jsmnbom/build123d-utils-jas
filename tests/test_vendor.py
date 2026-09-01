import pytest
from build123d import Box, export_step

from build123d_utils_jas import MIN, import_vendor, set_vendor_dir
from build123d_utils_jas import vendor as vendor_mod


@pytest.fixture
def vendor_dir(tmp_path):
  d = tmp_path / "vendor"
  d.mkdir()
  export_step(Box(2, 3, 4), str(d / "widget.step"))
  return d


def test_import_labels_and_aligns(vendor_dir):
  shape = import_vendor("widget.step", vendor_dir=vendor_dir)
  assert shape.label == "widget"
  assert shape.bounding_box(optimal=True).center().length == pytest.approx(0, abs=1e-4)


def test_disk_cache_created_and_used(vendor_dir, capsys):
  import_vendor("widget.step", vendor_dir=vendor_dir)
  breps = list((vendor_dir / "cache" / "widget.step").glob("*.brep"))
  assert len(breps) == 1
  # different align -> memo miss, but disk cache hit
  import_vendor("widget.step", align=(MIN, MIN, MIN), vendor_dir=vendor_dir)
  assert "Loading cached" in capsys.readouterr().out


def test_memo_returns_same_object(vendor_dir):
  a = import_vendor("widget.step", vendor_dir=vendor_dir)
  b = import_vendor("widget.step", vendor_dir=vendor_dir)
  assert a is b


def test_cache_false_skips_everything(vendor_dir):
  shape = import_vendor("widget.step", cache=False, vendor_dir=vendor_dir)
  assert shape.label == "widget"
  assert not (vendor_dir / "cache").exists()


def test_set_vendor_dir(vendor_dir):
  old = vendor_mod._vendor_dir
  try:
    set_vendor_dir(vendor_dir)
    assert import_vendor("widget.step").label == "widget"
  finally:
    set_vendor_dir(old)
