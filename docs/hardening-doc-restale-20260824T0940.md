# CAD phase-3 → phase-4 — /convert hardening + full 3x9 conversion-matrix guarantee
# (phase-4 de-stale supersede, MC 530.5)

Writer: Mirre (doc) — MC 530.5, 2026-08-24T0940 UTC — **written from the landed
phase-4 artifacts**, not from author reports. This is the de-staled supersede of
the phase-3 hardening doc
`/srv/workspace/svarkor-cad-phase3/mirre/494.6-hardening-and-full-matrix-doc-20260823T2225.md`.
The phase-3 file is historical; this file is the corrected canonical text for the
repo. Phase-4 changed two things the phase-3 doc got stale on:
**(1)** the holed iges->step bbox defect is FIXED (not the open escalated pair it
described); **(2)** the MED-1 rate-limiter map growth is CLOSED (not an open
residual). Both genuine OCCT engine limitations (findings 1 & 2) are RETAINED.

Every number below carries its recipe in "Sources & recipes" at the bottom;
anything not re-derived this turn is labelled with the reason.

Scope per brief: (a) the hardened `/convert` endpoint — 413 size cap, 429
per-client rate limit, the bumped secure web deps with the C7->HTTP mapping
intact; and (b) the full 3x9 in/out conversion-matrix correctness guarantee —
which pairs are proven at host level, which are honestly limited, how to add a
new source model, how to run the expanded suite.

---

## (a) /convert hardening (cad-api, MC 494.1 / sigrid 422.22)

The production tree under test is
`/srv/workspace/svarkor-cad-phase3/teddy/494.1-cad-api-hardening-20260823/`
(`server/api.py`, `requirements.txt`, `cad/`).

### 413 — upload/request size cap
- Constant (api.py:53): `MAX_UPLOAD_BYTES = 15 * 1024 * 1024` = **15 MiB
  (15,728,640 bytes)**.
- Enforced twice, both **before the body reaches the conversion flow**:
  1. **Header gate** (api.py:104-112): an over-cap `Content-Length` returns
     HTTP 413 up front, before starlette's multipart parser consumes the
     body — this is what closes the 422.22 multipart-parse DoS surface.
  2. **Streaming cap** (api.py:240-247): even a chunked transfer with *no*
     `Content-Length` is streamed 1 MiB at a time and hard-stops at the cap
     with a 413. This closes the chunked cap-BYPASS path (sigrid verified:
     `upload exceeds 15728640 byte cap` -> 413).
- 413 is distinct from FastAPI's own 422 (request-shape validation): the 413 is
  raised at the boundary, before parsing, so the two control statuses never
  collide (422.22 addendum, documented in the api.py docstring).

### 429 — per-client rate limit
- Constants (api.py:54-55): `RATE_MAX_REQUESTS = 20`, `RATE_WINDOW_SECONDS = 60`.
- Mechanism: `_SlidingWindowRateLimiter` (api.py:58-87) — an **in-memory,
  sliding-window** limiter keyed per client by socket peer IP
  (`request.client.host`, api.py:90-92 — not client-supplied data, so it cannot
  be forged without owning the TCP peer).
- A client exceeding 20 `/convert` hits in 60 s gets HTTP 429 with a
  `Retry-After` header (api.py:114-119).
- Rate limit + size cap both run inside `_enforce_security_gates`, wired as a
  FastAPI `Dependencies` on the endpoint, so they fire **before** the body is
  parsed (api.py:206, 95-119).
- **MED-1 CLOSED (phase-4, MC 530.3/530.4).** See the residual-findings section
  below. The bound is LRU-eviction cap `MAX_CLIENT_STATE_ENTRIES = 4096`
  (fixed api.py:58), so `_hits` can no longer grow without bound.

### Bumped secure web deps (requirements.txt)
Landed phase-3 pins (requirements.txt:25-28):

    fastapi==0.141.1
    starlette==1.6.0        # >=1.3.1 clears the ENTIRE remaining starlette CVE batch
    uvicorn[standard]==0.30.1
    python-multipart==0.0.32  # >=0.0.31 floor — closes the 0.0.9 multipart-parse DoS family

Why starlette==1.6.0 (not 0.47.2): teddy's first attempt (fastapi 0.117.0 +
starlette 0.48.0, i.e. >=0.47.2) still failed `pip-audit` — starlette 0.48.0
retained 8 CVEs (PYSEC-2026-161/248/249/1942/2280/2281). Five of those only
have fixes at 1.0.1/1.1.0/1.3.0/1.3.1, and fastapi 0.117..0.130 cap
starlette<1.0.0. fastapi>=0.135 drops the upper cap, so the **minimal
pip-audit-clean web pair** is fastapi>=0.135 + starlette>=1.3.1. This tree
lands fastapi 0.141.1 + starlette 1.6.0.

pip-audit clean: teddy 494.1 evidence ran
`/home/teddy/cadapi-venv/bin/python -m pip_audit -r requirements.txt` ->
`No known vulnerabilities found`, VERIFY_EXIT=0. sigrid 494.3 re-audit confirms
deps bump clean via its own pip-audit (exit 0).

### C7 -> HTTP mapping — INTACT (not changed by the hardening)
Read from `_cad_error_status` (api.py:125-129) + handler (api.py:132-136):

    UnsupportedFormatError -> 415  Unsupported Media Type
    ParseError             -> 400  Bad Request
    ConversionError        -> 500  Internal Server Error
    CadError (fallback)    -> 500  Internal Server Error
    invalid request shape (missing file/format, malformed form) -> 422 (FastAPI)
    413 / 429               -> the NEW security-gate statuses (above), pre-parse

The 413/429 sit at the boundary and are deliberately distinct from the 422
mapping; all C7 exception mappings are unchanged.

### Filename safety gate (unchanged, still present)
`_validate_upload_name` (api.py:142-154) still rejects NUL bytes, path
separators, absolute paths and `..` (sigrid 422.21 LOW) -> 400 before a hostile
multipart filename reaches `load`/`convert`.

### Residual findings after the phase-4 fix
- **MED-1 — CLOSED (phase-4).** `_SlidingWindowRateLimiter._hits` (old api.py:69)
  grew without bound (one permanent dict entry per distinct client key, never
  removed) — that WAS sigrid MED-1 (UnboundedGrowth). Fixed in MC 530.3 (teddy,
  TDD) and gated PASS by MC 530.4 (dobbie, independent clean-room, 2026-08-24T09:14):
  the map is now an LRU `OrderedDict` with `MAX_CLIENT_STATE_ENTRIES = 4096`;
  on a new key at cap the least-recently-used key is evicted. Bound is
  mutation-proven (3 concordant runs; a cap-removed UNBOUNDED mutant fails 4
  bounded-limiter tests and a 20000-distinct-client probe grows to 20000, not
  the cap). **DIVERGENCE (report vs artifact) to note:** the phase-3 production
  file `/srv/workspace/svarkor-cad-phase3/teddy/494.1-cad-api-hardening-20260823/server/api.py`
  is still the OLD UNBOUNDED version (mtime 2026-08-23 19:21, `_hits` defaultdict
  with no eviction). The MED-1 fix lives in teddy's build deliverable
  `/srv/workspace/svarkor-cad-phase4/teddy/530.3-bounded-rate-limiter-20260824T0712/api.py`
  (mtime 2026-08-24 07:12, LRU cap VERIFIED at lines 58/84/103-108) and in
  `/home/teddy/cadapi-build3`. It is NOT yet applied back into the phase-3 494.1
  tree; it lands in the repo at Svarkor integration. Until it lands there, the
  phase-3 494.1 `server/api.py` on disk still holds the unbounded limiter.
- **LOW-1 — REMAINS OPEN (reasoned, UNVERIFIED-future).** `_client_key` uses the
  socket peer IP. If a reverse proxy is ever placed in front (out of today's
  local scope), all clients collapse to one shared bucket — one client could
  exhaust it and 429 everyone else. Not exploitable today (no proxy in the
  local setup). Not addressed by MED-1's fix (different concern). UNVERIFIED-future.

---

## (b) Full 3x9 conversion-matrix correctness (MC 494.4, gate 494.5, phase-4 fix 530.1/530.2)

Production tree under test:
`/srv/workspace/svarkor-cad-phase3/teddy/494.4-validate-matrix-20260823/`
(tests/ exercise `cad.importers.load` C2 and `cad.formats.convert` C6 only;
the production fix for finding 3 lives in
`494.1-cad-api-hardening-20260823/cad/iges_adapter.py`). Authoritative matrix
doc: de-staled `530.5-matrix-restale-20260824T0940.md` (this dir); historical
`MATRIX.md` in the 494.4 dir.

### The matrix: 3 in x 9 out = 27 pairs
Registry basis (re-read this turn):
- inputs (C2 `cad/importers.py` `_READERS` -> `supported_inputs`): **step, iges,
  brep** (3)
- outputs (C6 `cad/formats.py` `SUPPORTED_FORMATS` -> `available_formats`):
  **step, brep, svg, iges, stl, obj, 3mf, gltf, ply** (9)
- 3 x 9 = **27 pairs**.

Source models (M-MODELS >= 3, all golden refs committed in
`tests/golden/in/`):

    box   = 10 x 20 x 30 cuboid      golden-box.{step,iges,brep}
    cyl   = cylinder r=5 h=20        golden-cyl.{step,iges,brep}
    holed = 10x10x10 box w/ hole     golden-holed.{step,iges,brep}

Per-(in,out) test-assertion legend (parametrized over model x in x out):
- **S** solid->solid identity: `test_matrix_solid_roundtrip_identity` — re-read
  of the produced solid matches the ORIGINAL input signature (surface_area +
  bbox universally; volume additionally in the pure solid domain).
- **V** `->svg`: `test_matrix_svg_well_formed` — well-formed non-empty SVG
  (flat projection, no solid signature).
- **M** `->mesh`: `test_matrix_mesh_topology` — mesh face count 1:1 with the
  core `brep.tessellate`/`to_trimesh` tessellation and watertight.
- bbox invariant for every solid+mesh pair: `test_matrix_bbox_invariant`.
- IGES volume diagnostic: `test_matrix_iges_volume_tracks_surface_area`.

Full matrix (rows=input, cols=output). NO cell is limited now — the former
`[iges,step]` holed cell is GREEN:

    in\out | step  brep  iges  svg  stl  obj  3mf  gltf  ply
    -------+--------------------------------------------------
    step   |  S     S     S     V    M    M    M    M     M
    iges   |  S     S     S     V    M    M    M    M     M
    brep   |  S     S     S     V    M    M    M    M     M

### What is PROVEN at host level (VERIFIED)
Suite result — **169 passed, 12 skipped, 10 xfailed, exit 0** (`pytest tests/`).
Re-derived this turn from the phase-4 landed gates (NOT from the phase-3 166/12/13
count, which is superseded):
- teddy 530.1 evidence (fix landed; `_seal_shell` in production tree at mtime
  08:45): 169/12/10. teddy 530.3 reversus: 169/12/10.
- dobbie gate 530.2 PASS (clean-room, independent; 2026-08-24T09:24): **two**
  concordant runs, both `169 passed, 12 skipped, 10 xfailed in 6.69s`, exit 0;
  targeted `[holed,iges,step]` runs PASS as real assertions (`6 passed, 3
  skipped`); independent OCCT bbox recompute — holed step re-read bbox exactly
  `(-10,-10,-5,10,10,5)` (z stays 5), `ALL_MODELS_OK=True`. VERDICT: PASS.
- The 3 old strict-xfails carried for the bbox/roundtrip/volume of
  `[holed,iges,step]` are GONE (removed from test_matrix.py, mtime 08:31) and
  their tests now PASS as real assertions.

Fidelity remains mutation-proven from phase 3 (dobbie corrupted
`golden.json["box.step"]["surface_area"]` -> 3 FAILED; restore -> green).

**Conclusion: all 27 pairs convert successfully; geometry (surface area, bbox,
face-count 1:1) is exact for ALL 27 pairs.** The one pair that phase-3 honestly
limited (holed iges->step, z 5->15) is now identical.

### Status of the three findings (phase-4 update of phase-3 findings)
- **FINDING 1 — IGES volume == surface_area (both in and out). REMAINING
  LIMITATION (NOT fixed).** OCCT does not rebuild a solid volume from IGES
  (faces/trimmed surfaces). True geometry (surface_area + bbox) is exact, only
  the *volume metric* degrades through IGES. Consequently **volume is only
  asserted through the pure solid domain (step/brep, no IGES endpoint)**. Pinned
  by `test_matrix_iges_volume_tracks_surface_area`. The 12 `skipped` tests are
  exactly this (IGES-volume diagnostic skipping non-IGES pairs by design).
- **FINDING 2 — IGES input of a curved or holed solid -> mesh is not watertight
  (10 strict-xfails, `(in_fmt=iges) & model in {cyl, holed}`). REMAINING
  LIMITATION (NOT fixed).** Cause: OCCT per-face IGES transfer shares no exact
  vertices along shared edges, so trimesh sees cracks. Face counts remain 1:1
  and bbox exact. Box (planar) from IGES **is** watertight; STEP/BREP input is
  always watertight. These 10 xfails are the ONLY remaining xfails (the count
  dropped 13 -> 10 because finding 3's three went real).
- **FINDING 3 — holed.iges -> step extends bbox z 5 -> 15 (deterministic).
  RESOLVED / FIXED (phase-4, MC 530.1/530.2).** No longer the escalated open
  pair. Root cause: OCCT's `IGESControl_Reader.OneShape()` transferred the holed
  model as UNGLUED faces (NbSolids()==0); the STEP writer serialized them as 7
  independent OPEN_SHELLs and mis-bounded the isolated hole-wall surface-of-
  revolution to z 5->15. Fix (in `cad/iges_adapter.read_iges`): sew transferred
  faces into ONE topology-sealed SHELL (`BRepBuilderAPI_Sewing`, `_seal_shell`),
  kept a shell (not promoted to SOLID) to preserve finding-1's volume==sa metric.
  holed.iges->step re-read bbox now exact `(-10,-10,-5,10,10,5)` (z stays 5);
  box/cyl round-trips unchanged. Artifact: `494.1/.../cad/iges_adapter.py` mtime
  2026-08-24 08:45, `_seal_shell` at line 39, called at line 100. Gate 530.2
  PASS 09:24 (supersedes the 08:04 FAIL, which ran against the pre-fix tree).

### How to add a new source model (unchanged from phase 3)
1. Create the new model's golden references in **all three solid input
   formats** under `tests/golden/in/`: `golden-<name>.{step,iges,brep}`.
2. Regenerate the per-format signatures into `tests/golden/golden.json` with
   `tests/golden/_gen_golden_all.py` (signatures: volume / surface_area / bbox).
3. The matrix tests are parametrized over the model set;
   `test_matrix_has_three_distinct_models` asserts >= 3 distinct models.
4. Re-run the suite (recipe below); add/adjust strict-xfails only for genuine
   engine-level limits, with a documented reason in the matrix doc.

### How to run the expanded suite
    cd /srv/workspace/svarkor-cad-phase3/teddy/494.4-validate-matrix-20260823
    PYTHONPATH=/srv/workspace/svarkor-cad-phase3/teddy/494.1-cad-api-hardening-20260823 \
      /home/teddy/cadapi-venv/bin/python -m pytest tests/ -q

Dobbie's clean-room equivalent:
`PYTHONPATH=<same production tree> /home/dobbie/verify/422.14-eng/bin/python -m pytest tests/ -q`
(clean-room copy of tests/ only; engine cadquery 2.8.0 / OCP 7.8 / trimesh 5.0.0).

**Honest caveat, labelled BLOCKED-for-me:** the engine (cadquery 2.8.0 / OCP /
trimesh) lives only in other users' 0750 home venvs (`/home/teddy/cadapi-venv`,
`/home/dobbie/verify/422.14-eng`), so I (Mirre, uid mirre) **could not re-execute**
`pytest tests/` under my own uid this turn. The 169/12/10 is VERIFIED-from-artifacts
(read directly from the phase-4 gates — teddy 530.1/530.3 + dobbie 530.2 PASS),
not re-executed-under-my-uid. If a reader needs a from-scratch run, use the recipe
above from teddy's or dobbie's venv.

---

## Verification label summary
- VERIFIED this turn (read direct from artifact): the iges->step fix present in
  production tree (`cad/iges_adapter.py` `_seal_shell` + call site), the three
  `[holed,iges,step]` xfails removed from test_matrix.py, the MED-1 LRU fix in
  teddy's 530.3 deliverable api.py (`MAX_CLIENT_STATE_ENTRIES`, `OrderedDict`,
  `popitem`, `move_to_end`), the 169/12/10 from two independent concordant
  phase-4 gates (530.2 PASS + 530.1/530.3), every api.py constant, every
  requirements.txt pin, C7->HTTP mapping, registries, matrix, models.
- BLOCKED: re-running `pytest tests/` / the api suite under my own uid (engine
  venvs are in 0750 homes I cannot read).
- DIVERGENCE (report vs artifact) found: the phase-3 production
  `494.1/server/api.py` is STILL the unbounded limiter (mtime 08-23 19:21) —
  the MED-1 fix exists only in teddy's build deliverable, pending integration;
  and the phase-3 hardening doc's 166/12/13 + "open escalated iges->step pair"
  are superseded by 169/12/10 + RESOLVED. Both noted above.
- UNVERIFIED: LOW-1 (reasoned, UNVERIFIED-future, unchanged from phase 3).

## Sources & recipes
- iges->step fix + gate: `/srv/workspace/svarkor-cad-phase4/dobbie/530.2-iges-step-gate-PASS-20260824T0924.md`
  (VERDICT PASS, 2 runs 169/12/10, independent recompute holed z=5) and
  `/srv/workspace/svarkor-cad-phase4/teddy/530.1-holed-iges-step-bbox-z-fix-20260824-084831.md`.
- iges fix artifact: `/srv/workspace/svarkor-cad-phase3/teddy/494.1-cad-api-hardening-20260823/cad/iges_adapter.py`
  (`_seal_shell` line 39, call line 100, mtime 08:45).
- MED-1 fix + gate: `/srv/workspace/svarkor-cad-phase4/teddy/530.3-bounded-rate-limiter-20260824T0712/api.py`
  (LRU cap 4096) and `/srv/workspace/svarkor-cad-phase4/dobbie/530.4-med1-bounded-gate-20260824T0914.md`
  (VERDICT PASS).
- api.py constants and gate code (unchanged parts): `/srv/workspace/svarkor-cad-phase3/teddy/494.1-cad-api-hardening-20260823/server/api.py`.
- Deps pins: `.../494.1-cad-api-hardening-20260823/requirements.txt`.
- Matrix, pairs, findings: phase-3 `.../494.4-.../MATRIX.md` + this dir's
  `530.5-matrix-restale-20260824T0940.md`.
- Phase-2 README being de-staled: `530.5-readme-restale-20260824T0940.md` (this dir).
