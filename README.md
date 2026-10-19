# build123d-utils-jas

Personal [build123d](https://github.com/gumyr/build123d) utilities, extracted
from a pile of CAD projects that each carried their own diverging copy.

```sh
uv add build123d-utils-jas            # core
uv add 'build123d-utils-jas[fasteners,preview]'  # + FastHeatSetNut, + ocp_vscode viewer
```

Requires build123d `>=0.13` (OCP 8). Developed and tested against both the latest
release and a pinned build123d `dev` revision (see `[tool.uv.sources]`). The 0.1.x
series supported build123d 0.11.

## Modules

### `fast_patch` — faster `Shape` operations

Monkey-patches `Shape.__copy__`/`moved`/`located`/`_apply_transform`/`fix`/
`bounding_box` to skip revalidation and share the underlying `TopoDS_Shape`.
`bounding_box` also defaults to the fast non-optimal OCC box with a coarse
tolerance. Nothing happens at import time — opt in explicitly:

```python
from build123d_utils_jas import apply_fast_patch, no_fast_patch

if __name__ == "__main__":
  apply_fast_patch()

with no_fast_patch():
  ...  # stock build123d behavior restored for this block
```

### `helpers` — geometry helpers

```python
from build123d_utils_jas import align, lift, raise_to, offset_to, extrude_to, CENTER, MIN, MAX

part = align(part, (CENTER, CENTER, MIN))       # bounding-box alignment to origin
plane = offset_to(Plane.XY.offset(3), bb.max.Z)  # offset a plane to an absolute coordinate
extrude_to(heatsink_bb.min.X)                    # extrude pending sketches to an absolute coordinate
```

Also `flip`, `shell_loft`, `make_solid` (solid from shells, holes supported),
and `convex_face_from_points` (planar face from a point cloud's hull).

### `assembly` — labeled compounds

```python
from build123d_utils_jas import make_compound, find_part

a = make_compound(label="lamp", base=base, wago=[w1, w2])
find_part(a, "wago")      # -> [wago_0, wago_1]
find_part(a, "cap.can")   # dotted paths descend into nested compounds
```

### `vendor` — cached STEP imports

```python
from build123d_utils_jas import import_vendor, set_vendor_dir

set_vendor_dir("vendor")  # the default; resolved against the cwd
cob = import_vendor("XLamp CMA1303.STEP", rot=(90, 0, 0))
```

STEP files are cached on disk as BREP keyed by content hash
(`vendor/cache/<file>/<sha256>.brep`) and memoized in-memory per process, so
re-running a script re-imports nothing that didn't change.

### `viewer` — ocp_vscode wrappers (opt-in)

`show_object`, `push_object`, `show_objects`, `reset_show` are no-ops until
`init_viewer()` is called, so batch runs and imports never need a viewer.
Requires the `preview` extra when actually used.

### `printing` — design-for-printing helpers

Cutters for holes, fastener pockets and fits, with numbers chosen so FDM parts
work without test prints (0.4 nozzle / 0.2 layer, +Z is the print direction).

```python
from build123d_utils_jas import printing

part -= Pos(x, y, top) * printing.heatset_pocket("M3", screw_depth=4)
part -= Pos(x, y, top) * printing.nut_trap("M4", slot=12)
with BuildPart() as bp:
  ...
  insert(Pos(x, y, top) * printing.hole_vertical(printing.bore_d(5), 10), mode=Mode.SUBTRACT)
```

Every helper returns a cutter to subtract, with its mouth at the origin cutting
toward −Z (or −X for `horizontal=True`, teardrop tip up). Exceptions: `mouse_ear`
is added, `foot_chamfer` and `fix_horizontal_holes` return the modified part, and
`counterbore_up` opens toward the bed and cuts +Z.

| Group | Helpers |
|---|---|
| numbers | `bore_d`, `clearance_d`, `screw_into_plastic_d`, `thread_forming_d`, `snap_cantilever`; tables `NUT`, `CLEARANCE`, `TAP_DRILL`, `HEATSET`, `SNAP_STRAIN` |
| holes | `hole_vertical` (seam tip), `hole_horizontal` (teardrop), `clearance_hole` |
| fasteners | `heatset_pocket`, `nut_trap`, `counterbore_up` (bridge trick, opens downward) |
| fits | `crush_rib_bore`, `hex_press_hole` |
| misc | `zip_tie_channel`, `mouse_ear`, `foot_chamfer` |
| finished geometry | `fix_horizontal_holes(shape)` turns existing horizontal-ish round bores into flat-roof teardrops |
| building blocks | `teardrop_sketch`, `cut_into`, `teardrop_wire`, `bore_geometry` |

All defaults live in `printing.Params`: `printing.P` is the default and
`printing.ABS` adds XY shrink compensation for bores that take bought parts
(`bore_d(22, gap=0, p=printing.ABS)`). Other processes get a preset via
`dataclasses.replace(printing.P, ...)`. The module docstring lists which helpers
are FDM-only (teardrops, seam tips, the bridge trick, mouse ears, foot chamfer).

### `fasteners` — `FastHeatSetNut`

A bd_warehouse `Nut` for heat-set inserts with knurling removed for fast
generation, plus a `fill_factor` property (insert volume vs. hole volume).
Requires the `fasteners` extra.

## AI use

AI (Claude) was used to manage the extraction of these utilities from their
original per-project copies, and assisted in writing parts of the code. Design
decisions and the original implementations are my own.

## License

MIT
