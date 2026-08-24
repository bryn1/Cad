# 530.5 — MATRIX.md de-stale (phase-4 supersede of the phase-3 matrix doc)

STATUS: SUPERSEDE-BY-MIRRE of `/srv/workspace/svarkor-cad-phase3/teddy/494.4-validate-matrix-20260823/MATRIX.md`.
This file is the de-staled phase-4 version; Svarkor lands it into the repo at integration.
The phase-3 MATRIX.md (teddy workspace) is historical; this is the corrected canonical text.

SOURCE OF VERIFICATION (artifacts read, not reports):
- Production fix tree: `/srv/workspace/svarkor-cad-phase3/teddy/494.1-cad-api-hardening-20260823/cad/iges_adapter.py`
  mtime 2026-08-24 08:45:49Z — `_seal_shell` present at line 39, `read_iges()` calls
  `_seal_shell(reader.OneShape())` at line 100. VERIFIED by direct read.
- Test matrix: `.../494.4-validate-matrix-20260823/tests/test_matrix.py` mtime 2026-08-24 08:31:39Z —
  the three `[holed,iges,step]` xfail markers removed; only genuine IGES curved->mesh xfails remain.
- Gate 530.2 PASS, dobbie clean-room, 2026-08-24T09:24:
  `/srv/workspace/svarkor-cad-phase4/dobbie/530.2-iges-step-gate-PASS-20260824T0924.md`
  2 concordant full-matrix runs `169 passed, 12 skipped, 10 xfailed` (exit 0); the 3 DoD tests
  `[holed,iges,step]` PASS as real assertions (`6 passed, 3 skipped`); independent OCCT bbox
  recompute shows holed step re-read bbox exactly `(-10,-10,-5,10,10,5)` (z stays 5). VERDICT: PASS.
- Gate 530.4 PASS, dobbie clean-room, 2026-08-24T09:14:
  `/srv/workspace/svarkor-cad-phase4/dobbie/530.4-med1-bounded-gate-20260824T0914.md` VERDICT: PASS.

NOTE ON MY DIRECT EXECUTION: this seat cannot run the OCCT/cadquery engine (venvs live in 0750
homes, blocked to mirre). Counts are VERIFIED via two independent concordant executed gates
(teddy 530.1 + dobbie 530.2 PASS), not by a mirre-owned pytest run. Where a claim could not be
independently re-run by me it is marked UNVERIFIED-BY-MIRRE with the reason; it is not a report-only
claim because a real executed gate (dobbie 530.2, VERDICT: PASS, VERIFY_EXIT=0) backs it.

---

# 494.4 cad-validate — FULL 3x9 in/out conversion matrix (validate-expansion, T4)

Task: expand the cad-validate suite from a single model / partial pairs to the
FULL 3x9 (in x out) conversion matrix across >= THREE distinct source models,
proving the owner's guarantee:

> every format in -> out converts correctly and is identical to the original.

Pure **validate-expansion**: `tests/` exercises `cad.importers.load` (C2) and
`cad.formats.convert` (C6) — the single public faces of the registry — and never
modifies production code.

## Source models (M-MODELS >= 3)

| model | geometry | golden refs (all in tests/golden/in/) |
|-------|----------|---------------------------------------|
| `box`   | 10 x 20 x 30 cuboid          | golden-box.{step,iges,brep} |
| `cyl`   | cylinder r=5 h=20            | golden-cyl.{step,iges,brep} |
| `holed` | 10x10x10 box with through-hole | golden-holed.{step,iges,brep} |

Each model has golden references in **all three solid input formats**, so the
full matrix is driven three times (once per model). Golden signatures committed
in `tests/golden/golden.json` (per-format load signature):
volume / surface_area / bbox, recorded by `tests/golden/_gen_golden_all.py`.

## The matrix: 3 inputs x 9 outputs = 27 pairs

Rows = INPUT format (`cad.importers.load`), columns = OUTPUT format
(`cad.formats.convert`). Cell = the test node that proves that pair.

| in\out | step | brep | iges | svg | stl | obj | 3mf | gltf | ply |
|--------|------|------|------|-----|-----|-----|-----|------|-----|
| **step** | S | S | S | V | M | M | M | M | M |
| **iges** | S | S | S | V | M | M | M | M | M |
| **brep** | S | S | S | V | M | M | M | M | M |

The former `[iges,step]` ⚠(holed) cell is removed — that pair is now GREEN (S),
see finding 3 below. No cell is limited any more except the two genuine OCCT
engine limitations in findings 1 and 2.

Test node legend (all parametrized over model x in-fmt x out-fmt):
- **S** = `test_matrix_solid_roundtrip_identity` — re-read (C2) of the produced
  solid matches the ORIGINAL input's signature (surface_area + bbox universally;
  volume preserved additionally in the pure solid domain).
- **V** = `test_matrix_svg_well_formed` — SVG output is a well-formed non-empty
  document (flat projection, no solid signature).
- **M** = `test_matrix_mesh_stopology` — produced mesh face count is 1:1 with the
  core `brep.tessellate`/`to_trimesh` tessellation and is watertight.
- bbox cross-check for every solid+mesh pair additionally: `test_matrix_bbox_invariant`.
- IGES volume behaviour: `test_matrix_iges_volume_tracks_surface_area`.

## Status (executed 20260824, engine = cadquery 2.8.0 / OCP 7.8, trimesh 5.x)

`pytest tests/` -> **169 passed, 12 skipped, 10 xfailed, exit 0** — VERIFIED via
dobbie gate 530.2 (2 concordant runs) and teddy 530.1 evidence / 530.3 reversus
(3 concordant). Counts recipe: 166 baseline + 3 unfrozen (findings-3 fix) = 169
passed; 10 remaining xfails are ALL `test_matrix_mesh_topology [*iges-cyl/holed]`
(findings 2). None of the 10 is a DoD bbox/roundtrip/volume test.

Every solid + bbox + svg + mesh-schema cell is GREEN. All 27 pairs convert
successfully; geometry (surface area, bbox, face-count 1:1) is exact. The one
historically non-identical pair (holed iges->step, z 5->15) is now identical —
see finding 3.

## Findings surfaced by this expansion

Three were exposed by driving the full matrix across curved + holed solids.
Two are genuine, permanent OCCT engine limitations of the IGES path (findings 1
and 2, still xfail). The third (finding 3) was a real defect in our adapter,
now FIXED (RESOLVED) in production:

1. **IGES transfer reports volume == surface_area (both in and out). — REMAINING LIMITATION (not fixed)**
   `test_matrix_iges_volume_tracks_surface_area` pins this as a tracked
   invariant. True geometry is intact (surface_area + bbox exact); only the
   *volume metric* degrades through IGES. Consequence: volume is only asserted
   through the pure solid domain (step/brep, no IGES endpoint). This is a
   measurement metric of OCCT's IGES path, not a defect in our code; it is
   deliberately preserved even after finding-3's fix (see finding 3).

2. **IGES input of a curved/holed solid -> mesh is not watertight. — REMAINING LIMITATION (not fixed)**
   `test_matrix_mesh_topology` xfails `(in_fmt=iges) & model in {cyl, holed}`:
   per-face IGES transfer shares no exact vertices along shared edges, so
   trimesh sees cracks. Box (planar) from IGES **is** watertight; STEP/BREP input
   is always watertight. Face counts 1:1 + bbox exact in every case. Genuine
   OCCT limitation; correctly still held as strict-xfail with this reason.

3. **holed.iges -> step extends bbox z 5 -> 15 (deterministic) — RESOLVED/FIXED (2026-08-24, T1/530.1).**
   Produced deterministically 3/3 (pre-fix): the STEP writer fed an IGES-parsed
   solid-with-hole produced geometry whose bounding box grew 10 units in z.
   **Root cause**: OCCT's `IGESControl_Reader.OneShape()` transferred the holed
   model as a set of UNGLUED faces (NbSolids()==0) rather than one connected
   body; the STEP writer then serialized them as 7 independent OPEN_SHELLs and
   mis-bounded the isolated hole-wall surface-of-revolution to z 5->15 on
   re-read. **Fix** (in PRODUCTION, `cad/iges_adapter.read_iges`): sew the
   transferred faces into ONE topologically-sealed SHELL
   (`BRepBuilderAPI_Sewing`, `_seal_shell()`), deliberately kept a shell (not
   promoted to a SOLID) so the documented `volume==surface_area` IGES metric in
   finding 1 is preserved. **State now**: holed.iges->step re-read bbox is exact
   `(-10,-10,-5,10,10,5)` (z stays at 5); box/cyl round-trips unchanged.
   The strict-xfails in `test_matrix_solid_roundtrip_identity`,
   `test_matrix_bbox_invariant` and `test_matrix_iges_volume_tracks_surface_area`
   for `[holed,iges,step]` are removed — those three now PASS as real assertions
   (verified in gate 530.2: `6 passed, 3 skipped`, and gate's independent
   recompute shows holed z stays 5). FIX LOCATION (artifact): 
   `/srv/workspace/svarkor-cad-phase3/teddy/494.1-cad-api-hardening-20260823/cad/iges_adapter.py`
   mtime 2026-08-24 08:45, `_seal_shell` at line 39; gate 530.2 PASS 09:24
   (supersedes the 08:04 FAIL which ran against the pre-fix tree).

## How to run

```
cd /srv/workspace/svarkor-cad-phase3/teddy/494.4-validate-matrix-20260823
PYTHONPATH=/srv/workspace/svarkor-cad-phase3/teddy/494.1-cad-api-hardening-20260823 \
  /home/teddy/cadapi-venv/bin/python -m pytest tests/ -q
```

Suite is source-only + TDD. Golden refs are committed fixtures; tests are the
only code changes (helpers are the test seam).

---

## Report-vs-artifact notes (mirre)

- Phase-3 hardening/readme docs ran with **166 passed / 12 skipped / 13 xfailed**
  and treated holed iges->step as THE ONE non-identical pair (open, escalated).
  That count and that open status are now STALE: the correct current count is
  **169/12/10** (166+3 unfrozen; 13 xfail - 3 now real = 10), and the pair is
  identical/green. This file supersedes those claims.
- The ⚠(holed) notation is removed: the iges->step-holed cell is green, no
  longer the honestly-limited pair. The only remaining xfails are the genuine
  engine limitations of findings 1 and 2.
