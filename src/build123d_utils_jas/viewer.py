"""ocp_vscode viewer wrappers, gated behind an explicit ``init_viewer()`` call.

All functions are no-ops until ``init_viewer()`` has been called, so library
and batch code can call ``show_object`` freely without a viewer running.
``ocp_vscode`` is imported lazily — the ``preview`` extra is only needed when
the viewer is actually used.
"""

from build123d import BuildLine, BuildPart, BuildSketch

__all__ = [
  "init_viewer",
  "reset_show",
  "show_object",
  "push_object",
  "show_objects",
]

USE_VIEWER = False


def init_viewer():
  import ocp_vscode

  ocp_vscode.set_port(3939)
  ocp_vscode.set_viewer_config(port=3939)

  global USE_VIEWER
  USE_VIEWER = True


def reset_show():
  if not USE_VIEWER:
    return

  import ocp_vscode

  ocp_vscode.reset_show()


def show_object(obj, name=None, alpha=None, color=None, options=None, **kwargs):
  if not USE_VIEWER:
    return

  import ocp_vscode

  if isinstance(obj, BuildPart):
    obj = obj.part
  if isinstance(obj, BuildSketch):
    obj = obj.sketch
  if isinstance(obj, BuildLine):
    obj = obj.line

  if options is None:
    options = {}
  if alpha is not None:
    options["alpha"] = alpha
  if color is not None:
    options["color"] = color
  kwargs["update"] = kwargs.get("update", True)
  kwargs["name"] = name or (obj.label if "label" in dir(obj) else None)
  kwargs["deviation"] = kwargs.get("deviation", 0.5)
  kwargs["angular_tolerance"] = kwargs.get("angular_tolerance", 0.25)
  ocp_vscode.show_object(obj, options=options, **kwargs)


def push_object(obj, name=None, alpha=None, color=None, **kwargs):
  if not USE_VIEWER:
    return

  import ocp_vscode

  if isinstance(obj, BuildPart):
    obj = obj.part
  if isinstance(obj, BuildSketch):
    obj = obj.sketch
  if isinstance(obj, BuildLine):
    obj = obj.line
  ocp_vscode.push_object(obj, name=name, alpha=alpha, color=color, **kwargs)


def show_objects(**kwargs):
  """Show all pushed objects in the viewer, or show the given objects passed as kwargs."""
  if not USE_VIEWER:
    return

  import ocp_vscode

  if len(kwargs) > 0:
    reset_show()
    for name, obj in kwargs.items():
      push_object(obj, name=name)

  ocp_vscode.show_objects(deviation=0.5, angular_tolerance=0.25)
