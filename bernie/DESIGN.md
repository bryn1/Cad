# MC 398.2 (T2, seat bernie) — DESIGN.md: CAD-filkonverterare (file-level design + MODULE TASK BREAKDOWN)

UTC: 20260822T1756  |  REV r1 (20260822T1810): design-gate cycle 1/3 FIX — folded in Neo
398.3's two refutations (cad-validate now depends on cad-cli+cad-api; cad-iges now
depends on cad-core, option a). No architectural change — decomposition, invariants I1-I6,
contracts C1-C9 all stand. See §7 rows + C5 note.
Project: svarkor-cad-phase1   |   Parent 398 "[relayed] CAD-filkonverterare — plan+arkitektur+review"
Chain: sickan(T1 plan, DONE) -> bernie(T2 arkitektur, DETTA) -> neo(T3 DA-review)
Inputs read (VERIFIED this session): LEDGER.md, /srv/workspace/Cad/sickan/PLAN.md (398.1), dispatch brief /tmp/svarkor-cad-p1-t2.txt, spike venv /tmp/cadspike (python 3.11.15, cadquery 2.8.0, numpy 2.4.6, NO trimesh).

This is DESIGN-ONLY. No repo code, no build/run, no deploy. It pins interfaces (C ids) a
build brief can cite, and ends with the MODULE TASK BREAKDOWN table svarkor transcribes to
file phase-2 build cards.

================================================================================
## 1. FRAMING

DESIGNING : file-level structure + interface contracts + module task breakdown for a
            greenfield CAD-filkonverterare built on the spike-verified CadQuery/OCCT
            engine, plus a trimesh mesh sidecar and a low-level OCCT IGES adapter.

MUST HOLD (invariants that must never break — every module obeys these):
- I1. ONE core B-rep representation in the system: `cad/brep.py::BRep` wrapping an OCCT
      Shape. Every other module reads/writes the CAD model ONLY through BRep. No module
      touches OCP/Shape directly except cad/brep.py, cad/iges_adapter.py and the
      CadQuery importers/exporters they call.
- I2. ONE dispatch mechanism for ALL outputs: `cad/formats.py` is the single registry
      mapping format-name -> handler. No format has its own bespoke conversion path.
      Mesh outputs (STL/OBJ/3MF/GLTF/PLY) share EXACTLY one mesh path (core->trimesh).
- I3. All 3 inputs (STEP/IGES/BREP) converge to ONE BRep in core via the input register;
      no input format keeps a private representation.
- I4. No monolith: one concern per module, one implementation per concern. Flag any file
      that would exceed ~500 loc as a split candidate during build.
- I5. Web and CLI are THIN shells over the same registry — identical conversion pipeline,
      no duplicated conversion logic in either.
- I6. Python 3.11 target (verified spike venv); deps via venv; CadQuery/OCCT/numpy are
      REUSED as-is (verified working), trimesh and all app modules are NEW.

CONSTRAINTS (fixed points — do not violate in phase 2):
- C-1. Repo: github.com/bryn1/Cad ; local code root /srv/workspace/Cad (greenfield,
       VERIFIED empty except LEDGER + sickan/).
- C-2. Engine (VERIFIED in /tmp/cadspike this session + 398.1): CadQuery 2.8.0 / OCP
       OCCT 7.9.3.1.1, numpy 2.4.6. Exports verified working: STEP, STL, BREP, 3MF, SVG.
       STEP import verified. OCR tessellate verified (24v/12f) feeds mesh path.
- C-3. trimesh NOT installed (VERIFIED) — NEW dependency, mesh sidecar, output-only
       (trimesh cannot ingest IGES/B-rep).
- C-4. IGES is NOT supported by CadQuery importers/exporters (VERIFIED: import
       "Unsupported import type", export ValueError) — requires the low-level OCCT
       IGESControl_Reader/Writer adapter. Highest-risk NEW module (PLAN R1, SO-1).
- C-5. Formats (from A1/LEDGER): IN {STEP, IGES, BREP}; OUT {STEP, IGES, BREP, STL, OBJ,
       3MF, GLTF, PLY, SVG}.
- C-6. Deliverable paths (chain): PRIMARY /srv/workspace/Cad/bernie/{DESIGN.md,RESULT.md}
       (what phase-2 + neo read), copy in runner-computed workspace
       /srv/workspace/svarkor-cad-phase1/bernie/. Group-readable, no secrets.

================================================================================
## 2. FILE STRUCTURE (each file owns ONE concern; paths under /srv/workspace/Cad)

```
Cad/
  pyproject.toml / requirements.txt     # python 3.11, pin trimesh (R2), cadquery, numpy
  cad/
    __init__.py                         # exports BRep, convert() facade (C9)
    brep.py                             # C1  — BRep, the ONE core representation
    importers.py                        # C2  — input register: STEP/BREP/IGES -> BRep
    exporters.py                        # C3  — output B-rep/vector path: STEP/BREP/SVG -> file
    mesh.py                             # C4  — mesh path: BRep.tessellate -> trimesh -> STL/OBJ/3MF/GLTF/PLY
    iges_adapter.py                     # C5  — IGES in+out via low-level OCCT IGESControl (bypasses CadQuery)
    formats.py                          # C6  — central export/convert registry + dispatch
    errors.py                           # C7  — typed errors (unsupported format, parse failure, conversion failure)
  server/
    __init__.py
    api.py                              # C8  — FastAPI app: POST /convert, GET /formats (thin over C6)
    web.py                              # C8b — static drag-drop index.html served by api
  cli.py                                # C9  — `cadconv in.step --to obj` (thin over C6)
  tests/
    test_importers.py  test_exporters.py  test_mesh.py  test_iges.py
    test_registry.py   test_cli.py        test_api.py
    golden/                             # reference in/out files for dobbie-gate A4
```

Dependency graph (module -> what it imports / depends on):
```
cad/brep.py (.shape, .tessellate)                     [CADQuery/OCCT]
   ^
cad/importers.py  -> uses BRep + CadQuery importers + iges_adapter   [core -> BRep]
cad/exporters.py  -> uses BRep + CadQuery exporters + iges_adapter
cad/iges_adapter.py -> uses cad-core BRep + OCCT IGESControl   [sealed, high risk; sole edge = cad-core]
cad/mesh.py       -> uses BRep.tessellate + trimesh            [NEW dep]
cad/formats.py    -> uses exporters + mesh + iges_adapter      [registry central]
   ^                 (single dispatch for all outputs)
cli.py            -> uses formats.convert                       [shell over registry]
server/api.py     -> uses formats.convert                       [shell over registry; FastAPI REUSE]
server/web.py     -> served by api                              [static UI]
tests/*           -> exercise every module above               [dobby verify A4]
```

================================================================================
## 3. INTERFACE CONTRACTS (stable ids — phase-2 briefs CITE these)

C1 — cad/brep.py — the ONE core B-rep representation
  class BRep:
      @classmethod
      def from_shape(cls, shape: "OCP.TopoDS.TopoDS_Shape") -> BRep   # wrap OCCT shape
      @property
      def shape(self) -> "OCP.TopoDS.TopoDS_Shape"                     # the wrapped OCCT shape
      def tessellate(self, tolerance: float = 0.1)
             -> tuple[list[tuple[float,float,float]], list[tuple[int,int,int]]]
             # returns (vertices, triangle_faces) — THE seam into the mesh path (C4)
  Data crossing: only OCCT Shape inside; only plain verts/faces tuples leave it.
  Invariant: no other module holds an OCP Shape not obtained from a BRep.

C2 — cad/importers.py — all 3 inputs -> one BRep
  def load(path: str, fmt: str | None = None) -> BRep
      # fmt resolved from extension if None; dispatch to reader from internal register
  def supported_inputs() -> list[str]          # ['step','iges','brep']
  Internal register: dict[str, Callable[[str], BRep]]  # <fmt> -> reader
  Readers: STEP/BREP => CadQuery importers.importShape; IGES => iges_adapter.read_iges.
  Data crossing: file bytes -> BRep. Errors: raise UnsupportedFormatError / ParseError (C7).

C3 — cad/exporters.py — B-rep/vector output path (NO mesh here)
  def export_brep(brep: BRep, out_path: str, fmt: str) -> None
      # STEP/BREP => CadQuery exporters.export ; SVG => CadQuery exporters.export(svg)
      # IGES => iges_adapter.write_iges (see C5)
  def supported_brep_formats() -> list[str]    # ['step','brep','svg','iges']
  Data crossing: BRep -> file. Errors: UnsupportedFormatError / ConversionError (C7).

C4 — cad/mesh.py — mesh path: core triangles -> trimesh -> any mesh file
  def to_trimesh(brep: BRep, tolerance: float = 0.1) -> "trimesh.Trimesh"
      # calls brep.tessellate(tolerance) -> trimesh.Trimesh(vertices=..., faces=...)
  def export_mesh(brep: BRep, out_path: str, fmt: str, tolerance: float = 0.1) -> None
      # fmt in {stl,obj,3mf,gltf,ply}; delegates to trimesh.export(mesh, file_obj, file_type=fmt)
  def supported_mesh_formats() -> list[str]    # ['stl','obj','3mf','gltf','ply']
  Invariant: THE ONLY place trimesh is used. All 5 mesh formats share this one path.
  Data crossing: BRep.tessellate tuples -> trimesh.Trimesh -> file.

C5 — cad/iges_adapter.py — the highest-risk NEW module (bypasses CadQuery for IGES)
  def read_iges(path: str) -> BRep                       # OCCT IGESControl_Reader -> BRep
  def write_iges(brep: BRep, out_path: str) -> None      # OCCT IGESControl_Writer -> file
  Contract: imports cad-core's CONCRETE BRep (design-gate fix, option a). It is not a
  standalone protocol — it holds and returns the ONE BRep (I1). Its only module edge is
  cad-core; it does NOT wedge network/registry deps, so it remains dispatchable early.
  Invariant: ONLY module allowed to touch OCP IGESControl classes. All other modules go
             through importers.load / exporters.export_brep for IGES.
  Data crossing: file bytes <-> OCCT shape (via BRep). Errors: ParseError / ConversionError (C7).

C6 — cad/formats.py — the ONE central registry + dispatch for ALL conversions
  SUPPORTED_FORMATS: dict[str, Handler] where
      Handler = Callable[[BRep, str, dict], None]   # (brep, out_path, opts) -> writes file
  def get_handler(fmt: str) -> Handler               # raise UnsupportedFormatError if absent
  def convert(brep: BRep, fmt: str, out_path: str, **opts) -> None
      # dispatches by fmt to: export_brep (step/brep/svg), export_mesh (stl/obj/3mf/gltf/ply),
      #   iges_adapter.write_iges (iges)
  def available_formats() -> list[str]               # all output handlers' names
  Invariant: I2 — this is the ONLY dispatch point; CLI and web both call convert().
  Data crossing: BRep + fmt + opts -> out file. Errors: UnsupportedFormatError etc (C7).

C7 — cad/errors.py — typed errors, shared by every module
  class CadError(Exception)                          # base
  class UnsupportedFormatError(CadError)             # unknown in/out format
  class ParseError(CadError)                         # input could not be parsed
  class ConversionError(CadError)                    # conversion/write failed
  Invariant: every module raises these, never raw exceptions for expected failure modes.
  (CLI maps them to exit codes; API maps them to HTTP 4xx/5xx.)

C8 — server/api.py + server/web.py — web shell (REUSE FastAPI, present in fleet Hotell)
  app: FastAPI
  POST /convert        (multipart: file, format, tolerance?) -> returns converted file bytes
  GET  /formats        -> JSON {inputs:[...], outputs:[...]}
  GET  /               -> serves server/web.py index.html (static drag-drop UI)
  Render/style: static index.html + inline JS posts file to POST /convert, downloads result.
  Invariant: api has NO conversion logic — it calls formats.convert(C6) only.
  Errors: map CadError -> HTTP status (400/415/500), Jsonable.
  (CLI-first recommendation SO-2: CLI can ship before this module; not a blocker.)

C9 — cli.py — CLI shell over the same registry
  usage: cadconv [-v] <input> --to <fmt> [-o <out>] [--tolerance <t>] [--list-formats]
  exit codes: 0 success; 2 usage/unsupported format; 3 parse error; 4 conversion error.
  Invariant: cli calls formats.convert(C6) only — identical pipeline to web, no HTTP.
  No conversion logic here beyond argparse + status-mapping from C7.

================================================================================
## 4. REJECTED ALTERNATIVES (and why)

- A monolithic `converter.py` — REJECTED: violates I4/sizing; 3 inputs x 9 outputs x
  CLI+web in one file = unreadable for a 35B executor and a gigantic test surface.
  Splitting happens up-front here, not a retrofit.
- One isolated module PER output format — REJECTED: duplicates the mesh path 5x and the
  B-rep path 3x. One registry + shared path (I2) is one mechanism per concern.
- Trusting trimesh to ingest IGES — REJECTED (VERIFIED): trimesh is mesh-only, cannot
  read B-rep; CadQuery can't do IGES either (C-4). OCCT IGESControl adapter is required.
- Direct OCP/Shape use everywhere (no BRep wrapper) — REJECTED: tears down I1, scatters
  the one representation across modules; the BRep seam is what makes the build testable
  and lets the IGES adapter slot in cleanly.
- A web server that shells out to the CLI — REJECTED: duplicated pipeline (I5), couples
  response timing to subprocess lifecycle, and re-parses args. A shared convert() call is
  the single pipeline both surfaces use.

REUSE summary (nothing new invented where an engine/mechanism already covers it):
- REUSE CadQuery 2.8.0 / OCCT 7.9.3.1.1 / numpy (C-2, verified) for B-rep core + STEP/BREP/SVG.
- REUSE OCCT tessellate as the in-seam to mesh path (C1.tessellate).
- REUSE low-level OCCT IGESControl_Reader/Writer for the IGES adapter (C5).
- REUSE FastAPI (fleet/library, e.g. Hotell) for the web API (C8).
- NEW: trimesh (verified absent, C-3), the eight app modules, the test suite.

================================================================================
## 5. RISKS / ROLLBACK / SIGN-OFF

R1 (HIGH, isolated): IGES — CadQuery can't, needs OCCT adapter (C5). MITIGATION: its own
   module + own DoD; sealed with a single edge to cad-core, dispatchable right after
   it (not a fan-out root); if it slips, IGES-IN/OUT removed
   from A1 without touching other modules (PLAN SO-1). neo (T3) reviews hardest here.
R2 (MED): trimesh is a new dep; a version change can alter mesh defaults. MITIGATION:
   pin trimesh in requirements (C-6/PLAN R2) + golden-file tests per mesh format (C4/tests).
R3 (MED): per-format options (GLTF draco, 3MF variants). MITIGATION: v1 = simple,
   uncompressed variants; options are later-phase; explicit in mesh/registry DoD (PLAN R3).
R4 (LOW): SVG is a vector path, not mesh — must be a separate registry handler. MITIGATION:
   C3 handles SVG in exporters, registry tags handler-type (PLAN R4) — neo verifies.
ROLLBACK: greenfield — nothing to break. Each module = separate commit/branch on
   bryn1/Cad (A5 pushes per milestone); a module missing DoD is dropped without
   hurting the rest. No live state, no secrets, no production.
SIGN-OFF (owner/orchestrator, surfaced by T1 as SO-1..SO-3, carry forward):
   SO-1 IGES in phase-1 scope (recommend YES, IGES-UT stretch acceptable) — the design is
         unaffected either way because IGES is a sealed module (C5).
   SO-2 CLI-first vs web-first — recommended CLI first; web is a sibling shell, so the
         order does not change the module graph. Not blocking.
   SO-3 Python 3.11 target confirmed (verified spike) — adopted (I6).

================================================================================
## 6. OUT OF SCOPE (explicitly NOT this build / phase 1)

- No GLTF advanced options (draco), no 2D XF/DXF input, no CAM/CNC input, no material/
  tolerance persistence, no large-assembly (>RAM) handling, no cloud/queue, no auth/multiuser.
- No parallel/cluster conversion in v1 (single-shot).
- No deployment/hosting pipeline (a later phase via the fleet hosting chain).
- Web UI is "simple drag-and-drop" (A3) — no full editor/preview in v1.
- This card writes NO production code — DESIGN only. Phase 2 builds from this breakdown.

================================================================================
## 7. MODULE TASK BREAKDOWN

Independent modules (fan-out for phase-2 dispatch): cad-core is the SINGLE root — the
smallest module (brep.py + __init__). cad-iges is sealed with a single edge to cad-core
(dispatch early, right after cad-core); cad-import/cad-export-brep/cad-mesh hang off
cad-core; the CLI/API/web shells each depend only on the registry/core chain. cad-mesh
needs trimesh. cad-api depends on cad-registry; cad-cli and cad-web are independent
siblings off cad-registry (cad-cli needs no api; cad-web needs cad-api only for serving).
cad-validate depends on the entire graph including cad-cli and cad-api, so it is always
dispatched last (no test import can race its module under test).

MODULE TASK BREAKDOWN:
- module: cad-core
  path: cad/brep.py, cad/__init__.py, pyproject.toml, requirements.txt
  depends_on: []
  buildable: true
  capabilities: [coder, tester]
  notes: BRep wrapper over OCP Shape + tessellate seam; CadQuery/OCCT/numpy REUSE; the seed

- module: cad-import
  path: cad/importers.py
  depends_on: [cad-core]
  buildable: true
  capabilities: [coder, tester]
  notes: STEP/BREP via CadQuery importers; IGES delegates to cad-iges

- module: cad-export-brep
  path: cad/exporters.py
  depends_on: [cad-core]
  buildable: true
  capabilities: [coder, tester]
  notes: STEP/BREP/SVG via CadQuery exporters; IGES delegates to cad-iges

- module: cad-iges
  path: cad/iges_adapter.py
  depends_on: [cad-core]
  buildable: true
  capabilities: [coder, tester, security]
  notes: highest-risk module; low-level OCCT IGESControl_Reader/Writer; file parse of
         untrusted input — security review warranted. Imports cad-core's concrete BRep
         (option a from design-gate fix) so the C5 IGES contract stays on the ONE
         representation (I1); its only edge is cad-core, the smallest module, so it can
         still be dispatched early once cad-core lands. R1 stays sealed in this module.

- module: cad-mesh
  path: cad/mesh.py
  depends_on: [cad-core]
  buildable: true
  capabilities: [coder, tester, researcher]
  notes: NEW trimesh dependency; ONLY trimesh user; golden-file each of 5 mesh formats;
         researcher to pin/compat-check trimesh

- module: cad-registry
  path: cad/formats.py, cad/errors.py
  depends_on: [cad-core, cad-export-brep, cad-mesh, cad-iges]
  buildable: true
  capabilities: [coder, tester]
  notes: single dispatch convert()/available_formats(); typed errors

- module: cad-cli
  path: cli.py
  depends_on: [cad-registry]
  buildable: true
  capabilities: [coder, tester]
  notes: argparse shell over registry; exit-code mapping

- module: cad-api
  path: server/api.py
  depends_on: [cad-registry]
  buildable: true
  capabilities: [coder, tester, security]
  notes: FastAPI REUSE; POST /convert + GET /formats; maps typed errors -> HTTP;
         file-upload boundary -> security review

- module: cad-web
  path: server/web.py
  depends_on: [cad-api]
  buildable: true
  capabilities: [frontend, tester, security]
  notes: static drag-drop index.html; served by api; browser boundary -> security

- module: cad-validate
  path: tests/
  depends_on: [cad-core, cad-import, cad-export-brep, cad-mesh, cad-iges, cad-registry, cad-cli, cad-api]
  buildable: false
  capabilities: [tester, technical_writer]
  notes: golden-files + roundtrip tests (STEP->BREP->STEP, +mesh/IGES); makes dobbie A4
         measurable; written as modules land, completes at the end; test-report doc

PROJECT-level phase-2 delivery (transcribed by svarkor, not a build module above):
- verify.sh authored per module from that module's DoD (deterministic-verdict shape).
- push to github.com/bryn1/Cad per milestone (A5).

================================================================================
## 8. CONFIDENCE

HIGH on every engine fact (I re-ran the spike venv this session: python 3.11.15,
cadquery 2.8.0, numpy 2.4.6, trimesh ABSENT; CadQuery export/import/tessellate verified by
T1 398.1 §3). HIGH on greenfield (VERIFIED /srv/workspace/Cad has only LEDGER + sickan/).
HIGH on the chain handoff (PLAN.md read, brief read). MEDIUM on owner's exact phase-1
IGES scope and web/CLI order — carried forward as SO-1/SO-2, non-blocking to this design.

DESIGN-GATE (Neo 398.3) cycle 1/3: VERDICT FAIL -> FIX, both refutations folded in
(revision r1 above): (1) cad-validate now depends on cad-cli+cad-api — its tests/
imports cli.py and server/api.py so it must dispatch after them (no import race);
(2) cad-iges now depends on cad-core (option a, concrete BRep) — its C5 contract reads/
writes the ONE BRep, so it cannot be a []-edge root; it stays sealed + early-dispatch
right behind cad-core. Six mechanical checks otherwise passed; no shape RECONSIDER.

