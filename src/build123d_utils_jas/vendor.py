"""Vendor model import with two-level caching, and a loader for part modules.

``import_vendor`` resolves paths against a configurable vendor directory
(default: ``vendor/`` relative to the current working directory — call
``set_vendor_dir()`` or pass ``vendor_dir=`` to change it). Imported STEP
files are cached on disk as BREP (keyed by the file's SHA-256, so edits
invalidate automatically) and memoized in-memory for the current process.
"""

import hashlib
from pathlib import Path

from build123d import export_brep, import_brep, import_step
from build123d.topology.shape_core import Shape

from .helpers import CENTER, align as _align

__all__ = [
  "import_vendor",
  "import_part",
  "set_vendor_dir",
]

_vendor_dir = Path("vendor")

# In-memory memo so repeated import_vendor calls in one process (e.g. rebuilding
# an assembly in a live session) don't re-read the brep/step from disk each time.
_vendor_memo: dict = {}


def set_vendor_dir(path) -> None:
  """Set the directory ``import_vendor`` resolves relative paths against."""
  global _vendor_dir
  _vendor_dir = Path(path)


def import_vendor(
  path,
  *,
  rot=(0, 0, 0),
  align=(CENTER, CENTER, CENTER),
  cache=True,
  vendor_dir=None,
) -> Shape:
  """Import a STEP file, label it, then optionally rotate and align it.

  Args:
    path: Path to the .step/.stp file, relative to the vendor directory.
    rot: Intrinsic rotation as (rX, rY, rZ) degrees, applied before alignment.
      The default (0, 0, 0) skips the transform entirely.
    align: Per-axis bounding-box alignment (see `align`). Pass None to keep
      the part's imported position untouched.
    cache: Use the disk BREP cache and in-memory memo.
    vendor_dir: Override the module-level vendor directory for this call.

  Returns:
    The imported shape, with `.label` set to the file's stem.
  """
  base = Path(vendor_dir) if vendor_dir is not None else _vendor_dir
  path = base / path
  memo_key = (str(path), tuple(rot), align if align is None else tuple(align))
  if cache and memo_key in _vendor_memo:
    return _vendor_memo[memo_key]
  # Hash of the file is the cache key, so we don't re-import unchanged files.
  shape = None
  if cache:
    h = hashlib.sha256(path.read_bytes()).hexdigest()
    cache_path = base / "cache" / f"{path.name}/{h}.brep"
    if cache_path.exists():
      print(f"Loading cached {cache_path.name}...")
      shape = import_brep(str(cache_path))

  if not shape:
    print(f"Importing {path.name}...")
    shape = import_step(str(path))

  if cache and not cache_path.exists():
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    export_brep(shape, str(cache_path))

  shape.label = path.stem
  shape = _align(shape, align, rot)
  if cache:
    _vendor_memo[memo_key] = shape
  return shape


def import_part(name: str):
  """Import a sibling part module, e.g. ``import_part("60AIM40F")``.

  The part directories are named after the part itself, so their module names are
  not valid Python identifiers -- hence the explicit loader.

  Args:
    name: The directory (and file stem) of the part, without the ``.py``.

  Returns:
    The imported module, also registered in ``sys.modules`` under `name`.
  """
  import importlib.util
  import sys

  if name in sys.modules:
    return sys.modules[name]
  spec = importlib.util.spec_from_file_location(name, Path(name) / f"{name}.py")
  if spec is None or spec.loader is None:
    raise ImportError(f"No part module named {name!r}")
  module = importlib.util.module_from_spec(spec)
  sys.modules[name] = module
  spec.loader.exec_module(module)
  return module
