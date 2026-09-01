from build123d import Box

from build123d_utils_jas import push_object, reset_show, show_object, show_objects


def test_viewer_functions_are_noops_without_init():
  # No viewer running, ocp_vscode possibly not installed: all must be silent no-ops.
  box = Box(1, 1, 1)
  assert show_object(box) is None
  assert push_object(box) is None
  assert show_objects(thing=box) is None
  assert reset_show() is None
