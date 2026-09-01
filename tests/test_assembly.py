import pytest
from build123d import Box, Compound

from build123d_utils_jas import find_part, make_compound


def lamp():
  base = Box(4, 4, 1)
  wagos = [Box(1, 1, 1), Box(1, 2, 1)]
  can = Box(1, 1, 2)
  cap = make_compound(label="cap", can=can)
  return make_compound(label="lamp", base=base, wago=wagos, cap=cap)


def test_make_compound_labels():
  a = lamp()
  assert isinstance(a, Compound)
  assert a.label == "lamp"
  assert sorted(c.label for c in a.children) == ["base", "cap", "wago_0", "wago_1"]


def test_find_single():
  a = lamp()
  assert find_part(a, "base").label == "base"


def test_find_group_returns_sorted_list():
  a = lamp()
  wagos = find_part(a, "wago")
  assert [w.label for w in wagos] == ["wago_0", "wago_1"]


def test_find_dotted_path():
  a = lamp()
  assert find_part(a, "cap.can").label == "can"


def test_shallowest_match_wins():
  inner = make_compound(label="pcb", pcb=Box(1, 1, 1))
  a = make_compound(label="a", children=[inner])
  assert find_part(a, "pcb") is not None
  assert find_part(a, "pcb").children  # got the compound, not the board


def test_ambiguous_same_depth_raises():
  a = make_compound(label="a", children=[Box(1, 1, 1), Box(2, 2, 2)])
  for c in a.children:
    c.label = "dup"
  with pytest.raises(KeyError, match="ambiguous"):
    find_part(a, "dup")


def test_group_cannot_be_descended():
  a = lamp()
  with pytest.raises(KeyError, match="group"):
    find_part(a, "wago.anything")


def test_missing_lists_labels():
  a = lamp()
  with pytest.raises(KeyError, match="base"):
    find_part(a, "nope")
