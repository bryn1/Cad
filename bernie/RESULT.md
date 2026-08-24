# MC 398.2 (T2) RESULT — CAD-konverterare DESIGN (arkitektur + MODULE TASK BREAKDOWN)

UTC: 20260822T1815 (r1)   |   Seat: bernie   |   Project: svarkor-cad-phase1   |   Parent 398

STATUS: DONE (r1 — design-gate cycle 1/3 FIX folded in; re-submitted for done-gate)
REVISION r1 (20260822T1815): Neo 398.3 returned FAIL->FIX. Two refutations folded into
DESIGN.md: (1) cad-validate depends_on now includes cad-cli + cad-api (its test_cli.py /
test_api.py import cli.py and server/api.py — must dispatch after them, no import race);
(2) cad-iges depends_on now [cad-core] (option a — imports cad-core's CONCRETE BRep, so
C5 stays on the ONE representation I1; sealed, dispatch right behind cad-core).
FILES (revision r1):
/srv/workspace/Cad/bernie/DESIGN.md   (r1, 20,608 B)
/srv/workspace/svarkor-cad-phase1/bernie/398.2-cad-konverterare-design-module-breakdown-r1-20260822T1815.md  (byte-identical copy)
(prior copy 398.2-cad-konverterare-design-module-breakdown-20260822T1756.md superseded, retained append-only)
DID:
- Läste dispatch-brief (t2.txt) + LEDGER + förälder 398 + 398.1 PLAN.md + spike-venv (verifierade python 3.11.15, cadquery 2.8.0, numpy 2.4.6, trimesh SAKNAS; /srv/workspace/Cad greenfield).
- Skrev DESIGN.md med fil-struktur, gränssnitt mellan moduler (input-parse, core BRep, export-register per format, webb-API, CLI), risker, invariants I1-I6, och MODULE TASK BREAKDOWN i architecture-breakdown-formatet exakt (capability-vokabulär, buildable, depends_on, DoD).
- Pinnade interface-contract ids C1-C9 (BRep, importers, exporters, mesh, iges_adapter, formats/registry, errors, api/web, cli) och reuse-beslut (REUSE CadQuery/OCCT/numpy/FastAPI/OCCT-tessellate/IGESControl; NEW trimesh + app-moduler).
VERIFY: DESIGN.md r1 skriven (bytes 20608, byte-identisk kopija i runner-workspace); gate-refutations (cad-validate -> +cad-cli+cad-api; cad-iges -> [cad-core]) greppade tillbaka i DESIGN.md (VERIFY_EXIT=0); spike-venv-pkg-kontroll redan pastad i tidigare bevis-fil (python3.11, cadquery2.8.0, numpy2.4.6, trimesh-not-found).
BLOCKERS: none
