# MC 398.1 (T1, seat sickan) — Plan: CAD-filkonverterare (moduler, ordning, reuse-vs-nytt)

UTC: 20260822T1749
Project: svarkor-cad-phase1   |   Board parent 398 "[relayed] CAD-filkonverterare — plan+arkitektur+review"
Dispatch brief (this card): plan CAD-konverteraren — vilka moduler, i vilken ordning,
vad som återanvänds (OCCT/CadQuery/trimesh) vs nytt, + en 1-radig "modul -> ansvar"-lista.
Chain: sickan(T1, detta) -> bernie(T2 arkitektur, läser DENNA fil) -> neo(T3 DA-review).

Detta är PLAN-ONLY. Ingenting nedan ändrar kod; det är indata bernie läser för att skriva
DESIGN.md + MODULE TASK BREAKDOWN. Slutar med MODULE LIST i den korta shape
architecture-breakdown-tabellen förväntar sig (via plan-module-breakdown-skillen).

--------------------------------------------------------------------------------
## 1. GOAL (från LEDGER + dispatch-brief, VERIFIERAD)

Ett verktyg som tar en 3D-industriell CAD-fil (t.ex. STEP) och konverterar till valfritt
önskat format. 3D-fokus, industriell. Motor redan vald + spike-verifierad:
OCCT via CadQuery 2.x (Python). Bygget ska ha CLI + enkelt webbgränssnitt (drag-och-släpp).

### Acceptance (övergripande, från LEDGER — VERIFIERAD 2026-08-22 av svarkor)
- A1. Ingång: STEP / IGES / BREP. Utgång: STEP, IGES, BREP, STL, OBJ, 3MF, GLTF, PLY, SVG.
- A2. Drivs på beprövad motor: OCCT via CadQuery, + trimesh för mesh-vägen.
- A3. CLI + enkelt webbgränssnitt (dra-och-släpp).
- A4. Verifierad av dobbie med verkligt build+test, ej "ser bra ut".
- A5. Push till github.com/svarkor-ai/Cad vid varje milstolpe (repo just nu TOMT — greenfield).

### Testbar acceptance för DENNA plan-kort (vad T1 levererar)
- P1. PLAN.md listar alla moduler, i ordning, med "modul -> ansvar" (denna fil).
- P2. Varje reuse-beslut (OCCT/CadQuery/trimesh vs nytt) är grundat i VERIFIERAD motor-fakta
      (se §3; jag körde själv export/import/tesselate i spike-venv:an), inte antaget.
- P3. Format-uppsättningen + input/output-matrisen är uttömd per mål-format (inga hål som
      T3/neo måste hitta).
- P4. Planen ger en ren handed-off till T2: modul-namn, ansvar, interface-rygg mot
      input->core->export-register->(CLI|webb), och den enda genuina motorklyftan (IGES)
      surfacad som en skarp modul, inte gömd.

--------------------------------------------------------------------------------
## 2. APPROACH (vald) + ALTERNATIV

### Vald: Modulär greenfield runt en VERIFIERAD motorkärna (OCCT/CadQuery) + mesh-sidocar (trimesh)
Eftersom repot är tomt (greenfield) bygger vi från scratch, MEN vi bygger på den redan
spike-verifierade motorn och återanvänder dess verifierade kapacitet bit-för-bit. Arkitekturen
delar verktyget i SMÅ, komponerbara moduler längs en enda data-pipeline:

    input-parse -> core-CAD-representation (Namn:BREP i OCCT) -> export-register (per format)
                                                                    -> CLI | webb-API
                                                                    -> mesh-väg (trimesh)

Kärn-idén: ALLA ingångar (STEP/IGES/BREP) matas in till EN OCCT B-rep-representation;
ALLA utgångar är antingen (a) direkt B-rep-export via OCCT (STEP/BREP; IGES via OCCT-adapter),
eller (b) meshad-triangel-export via OCCT `tessellate()` -> trimesh (STL/OBJ/3MF/GLTF/PLY),
eller (c) 2D/vektor-export via CadQuery (SVG). Inget format får ha en egen separat pipeline —
de delar samma in- och ut-kranar.

### Alternativ 1 — Ett stort "converter.py" som allt sitter i
REJECTED: bryter plan-module-breakdown + job-sizing (monolit). 9 mål-format + 3 ingångar +
CLI + webb i en fil = ofattbar test-yta och omöjlig för en 35B-executor att hålla. Flera
format delar mekanik (mesh-export) — en per-format-fil skulle duplicera den.

### Alternativ 2 — Varje format får en egen isolerad modul (inget gemensamt export-register)
REJECTED: duplicerar B-rep+vägnings-logiken 12 gånger (input-format + output-format). Ett
gemensamt export-register (format -> handler) ger EN mekanism per koncern (job-sizing:
one concern, one pinned mechanism). Registret gör det trivialt att lägga till ett format
utan att röra CLI/webb/kärna.

### Alternativ 3 — Lita helt på att "trimesh fixar IGES"
REJECTED efter VERIFIERAD test: varken CadQuery `exporters.export` (IGES EXPORT-FAIL,
ValueError) eller `importers.importShape` ("Unsupported import type") hanterar IGES.
trimesh hanterar IGES inte alls (IGES är B-rep, trimesh är mesh-only). IGES kräver en
egen OCCT-adapter (IGESControl_Reader/Writer). Detta är den ENDA genuint nya, riskfyllda
motormodulen — den får eget scope i planen, inte dolt.

--------------------------------------------------------------------------------
## 3. REUSE vs NYTT (allt VERIFIERAT denna session)

### ÅTERANVÄND (finns och fungerar — VI BYGGER PÅ, inte om):
- **CadQuery 2.8.0 + OCP/OCCT 7.9.3.1.1** — spike-venv `/tmp/cadspike` (Python 3.11).
  VERIFIERAD jag själv nu: export STEP (15426 B), STL (684 B), BREP (4291 B), 3MF (1236 B),
  SVG (2405 B) all OK; STEP import-ok (Workplane); `val().tessellate(0.1)` -> 24 verts/12 faces.
  => CadQuery/OCCT ÄR core-motorn. REUSE.
- **OCCT tessellering** (`Shape.tessellate`) — producerar trianglar som matar mesh-vägen.
  VERIFIERAD (24/12 ovan). REUSE som in-kran till trimesh.
- **OCCT IGESControl_Reader/Writer** (lägnivå-OCCT) — den väg IGES kan gå in/ut. Den IGES-fil
  jag producerade via IGESControl_Writer skrevs OK (12393 B). REUSE som grund för IGES-adaptern.
- **numpy 2.4.6** — redan i spike-venv; trimesh-beroende. REUSE.

### NYTT (inget i repot, inget i spike-venv täcker det — VERIFIERAT):
- **trimesh** — INTE installerat i `/tmp/cadspike` (VERIFIERAT: pip list visar cadquery, ocp,
  numpy, INGET trimesh). Krävs för mesh-EXPORT av STL/OBJ/3MF/GLTF/PLY från tessellerade
  trianglar. Trimesh självt kan läsa SKRIVA OBJ/PLY/GLTF/glb/STL — MEN det importerar INTE
  IGES (B-rep). => NYTT beroende, mesh-SIDOCAR enbart (ut-sidan), inte in-sidan.
- **Hela app-strukturen** (modulerna i §5) — grönt fält, repot är tomt. Allt under
  /srv/workspace/Cad/ (eller /srv/workspace/svarkor-cad-phase1, se §8 plats-not).
- **IGES-adaptern** (OCCT-level) — den enda genuint svåra nya motordelen (se §2 Alt-3).

### Prior-art-checklista (STEP 0, reuse-research-gate)
- `kb recall "CAD converter STEP IGES converter tool"` + "CAD konverterare ... trimesh
  CadQuery" — INGEN tidigare CAD-konverterare i flottan. `grep -ri "cadquery\|trimesh"`
  över /srv/workspace träffar BARA /srv/workspace/Cad/LEDGER.md. (UNVERIFIED-negativ: kb är
  ett recall-index, inte bevis på frånvaro; flaggat.)
- Prior-plan-kort i samma kedjetyp (hotell 142.1, kvällsmats 166.1) är FORMAT-mallar, inget
  återanvändbart bibliotek för CAD. REUSE formatet; inte innehållet.
- Repo svarkor-ai/Cad = TOMT (LEDGER, VERIFIERAD). Inga specs att återanvända.

--------------------------------------------------------------------------------
## 4. INPUT/OUTPUT-MATRIS (per mål-format; uttömmer A1)

| mål-format | typ        | väg                              | beroende          | mekanism (pin)              |
|---|---|---|---|---|
| STEP       | in+ut B-rep | direkt export/import            | OCCT               | CadQuery exporters/importers |
| BREP       | in+ut B-rep | direkt export/import            | OCCT               | CadQuery exporters/importers |
| IGES       | in+ut B-rep | OCCT-adapter                    | OCCT+NY adapter    | IGESControl_Reader/Writer   |
| SVG        | ut 2D/vektor| CadQuery export (2D)            | OCCT               | CadQuery exporters.export   |
| STL        | ut mesh     | B-rep -> tessellate -> trimesh  | OCCT+trimesh       | NFT -> trimesh.export(mesh) |
| OBJ        | ut mesh     | B-rep -> tessellate -> trimesh  | OCCT+trimesh       | trimesh.export(mesh)        |
| PLY        | ut mesh     | B-rep -> tessellate -> trimesh  | OCCT+trimesh       | trimesh.export(mesh)        |
| 3MF        | ut mesh     | B-rep -> tessellate -> trimesh  | OCCT+trimesh       | trimesh.export(mesh)        |
| GLTF/glb   | ut mesh     | B-rep -> tessellate -> trimesh  | OCCT+trimesh       | trimesh.export(mesh)        |

Ingång -> core: STEP/BREP via CadQuery importers; IGES via IGES-adaptern. Alla -> EN OCCT
B-rep i core. Utgång -> alla via export-registret. Mesh-utgångarna delar EXAKT samma
trimesh-väg (EN mekanism, registret lägger bara format-poster).

Märk: A1 säger GLTF och PLY; trimesh exporterar .glb/.gltf och .ply naturligt; OBJ/STL/3MF
också. SVG är vektor-väg via CadQuery (ej mesh) — separat post i registret.

--------------------------------------------------------------------------------
## 5. MODULER I ORDNING (filer, modulärt, inga monoliter) + 1-radig modul->ansvar

Byggordning följer data-pipeline + beroende: först motor-kärnan (som redan är verifierad),
sedan in-/ut-kranar, sedan registret, sedan skal (CLI/webb), sedan verk-verktyg. Varje
modul = ett jobb (job-sizing: en koncern, en pinnad mekanism, < 18k tok).

- **mod_core** (`cad/brep.py`) — den enda B-rep-representationen i systemet; wrappar en OCCT
  Shape; alla andra moduler ser bara denna. Ansvar: hålla en OCCT B-rep + tessellate()
  till trianglar. REUSE: CadQuery/OCCT. (Detta stänger monolit-risken: core ÄR motorn.)

- **mod_import** (`cad/importers.py`) — input-kranarna. STEP/BREP -> mod_core (CadQuery
  importers); IGES -> IGES-adaptern. En in-matris (format -> reader). Ansvar: alla
  ingångsformat till EN OCCT B-rep. REUSE: CadQuery importers + IGESControl.

- **mod_export** (`cad/exporters.py`) — output-kranarna (B-rep-vägen): STEP/BREP direkt,
  SVG via CadQuery, IGES via adaptern. Ansvar: B-rep -> B-rep/2D-format. REUSE: CadQuery
  exporters + IGESControl.

- **mod_mesh** (`cad/mesh.py`) — mesh-vägen: mod_core.tessellate() -> trimesh ->
  STL/OBJ/3MF/GLTF/PLY. ANSVAR: trianglar -> alla mesh-format. REUSE: OCCT tessellate +
  NY trimesh. (NY beroende.)

- **mod_iges** (`cad/iges_adapter.py`) — den enda genuint nya motordelen (low-level OCCT
  IGESControl_Reader/Writer; förbikopplar de CadQuery-funktioner som INTE stödjer IGES —
  VERIFIERAT). Ansvar: IGES in+ut. REUSE: OCCT-lägnivå. (NY kod, högst risk i bygget.)

- **mod_registry** (`cad/formats.py`) — export-registret: format-namn -> handler (från
  mod_export/mod_mesh/mod_iges). EN mekanism för alla utgångar. Ansvar: central dispatch
  av "konvertera till format X". (NY kod, trivial; gör format-tillägg billiga.)

- **mod_api** (`server/api.py`) — webb-API-lagret (FastAPI/Starlette): POST-upload ->
  konvertering -> nedladdning. Ansvar: HTTP-yta över core. REUSE: FastAPI (finns i flera
  andra flott-projekt, t.ex. Hotell). (NY för detta repo.)

- **mod_cli** (`cli.py`) — kommandorads-yta: `cadconv in.step --to obj`. Ansvar: samma
  pipeline som webb, utan HTTP. (NY; skal runt core+registry.)

- **mod_web** (`server/web.py`) — det enkla drag-och-släpp-gränssnittet (statisk HTML/JS
  -> mod_api). Ansvar: användaryta. (NY; A3.)

- **mod_validate** (`tests/`) — bygg+verifierings-hjälp för dobbie (A4): golden-file-tester
  per format (convertera referens-STEP -> X, jämför strukturellt/geometriskt), roundtrip-tester
  (STEP->BREP->STEP), henvista till spike-venv som bas. Ansvar: gör A4 mätbart. (NY, enkel.)

### Ordnings-/beroendegraf
    mod_core (först — motorn redan verifierad)
      -> mod_import, mod_export (läser mod_core; kan byggas parallellt)
      -> mod_iges (oberoende, högst risk; kan börja tidigt)
      -> mod_mesh (läser mod_core + NY trimesh-dep)
      -> mod_registry (läser mod_export/mod_mesh/mod_iges; efter dessa)
      -> mod_api + mod_cli (läser registry; parallellt)
      -> mod_web (läser mod_api)
      -> mod_validate (löper genom hela kedjan; avslutar med dobbie-gate)

Rekommenderas som separata MC-jobb (en koncern var, job-sizing): 1) mod_core+mod_import,
2) mod_export (+SVG), 3) mod_iges, 4) mod_mesh (+trimesh dep), 5) mod_registry, 6) mod_api+
mod_cli, 7) mod_web, 8) mod_validate+gate. (Lägg bara ihop självständiga steg.)

--------------------------------------------------------------------------------
## 6. RISKER / TRADE-OFFS / ROLLBACK / SIGN-OFF

R1 (HÖG, men isolerad): IGES — varken CadQuery exporters eller importers stödjer det
(VERIFIERAT fatt) => kräver egen OCCT-adapter. MITIGERING: ge mod_iges eget jobb + egen
DoD; neo (T3) bör FIXA på just detta om det fallerar. Om IGES är nödvändigt för fas 1 måste
denna modul vara klar tidigt, inte sist.

R2 (MED): trimesh saknas i spike-venv (VERIFIERAT) => ny dep. Risken är liten (ren
pip-install + trimesh är mogen), men mesh-exporter måste golden-testas per format (en
trimesh-version kan ändra default-egenskaper). MITIGERING: mod_mesh har golden-files; pinna
trimesh-version i requirements.

R3 (MED): format-svängrum — A1 vill ha 9 utgångar; en del (GLTF draco-kompression, 3MF)
har options som ändrar resultat. MITIGERING: v1 = enkla, okomprimerade varianter; options
kommer i senare fas. Explicitera i mod_mesh/mod_registry-DoD.

R4 (LÅG): SVG är 2D/vektor-väg (ej mesh) via CadQuery direkt — måste registreras som en
separat handler-post, inte dras in i mesh-vägen. MITIGERING: registret har tydlig
format->handler-typ per väg (B-rep | mesh | vector); verifierat av T3.

ROLLBACK: greenfield => ingen gammal funktion att bryta. "Rollback" = att INTE merge:a en
modul som missar DoD; varje modul är en separat commit/branch mot svarkor-ai/Cad (A5 pushar
per milstolpe), så en dålig modul droppas utan att skada resten. Inget live-state, inga
secrets, ingen production.

SIGN-OFF (ägare/örkestrator, INNAN bernie T2): 
- SO-1: Bekräfta IGES i fas-1-scope. IGES är den enda riktigt dyra modulen (egen OCCT-adapter).
  Alta: (a) inkludera IGES fullt i fas 1 (rekommenderat om kund kräver IGES-in/ut), eller
  (b) fas-1a levererar IGES-IN men IGES-UT som stretch. Vill ägaren att IGES faller ur fas 1,
  justeras matrisen. — Detta vore också där neo (T3) bör granska hårdast.
- SO-2: Webbens prioritet — LEDGER öppna fråga "Webb vs CLI-prioritet". Rekommendation: CLI
  först (billigare, testbar, dobbie-verifierbar), webb som skal därefter. Ägare bekräftar ordning.
- SO-3: Python-version — spike-venv är Python 3.11 (VERIFIERAT, /tmp/cadspike). Bekräfta 3.11
  som mål för repot (inte 3.12) så spike-resultaten gäller. Inte blockerande; noterar.

--------------------------------------------------------------------------------
## 7. OUT OF SCOPE (explicit inte detta bygge)

- Inte fas-1-prioritet: GLTF-advanced options (draco), 2D-XF/DXF-in, CAM/CNC-in, materials/
  toleranser-lagring, stora-assembly-hantering (>ROM-minne), cloud/queue, auth/multiuser.
- Inte clusters/paralell-konvertering i v1 (single-shot konvertering).
- Inte deployment/hosting-pipeline (det är senare fas via flottans hosting-kedja, ej detta kort).
- Webb-gränssnittet är "enkelt drag-och-släpp" (A3) — ingen full editor/preview i v1.
- Detta kort skriver INGEN produktionskod — bara PLAN.md (+RESULT.md). bernie (T2) designar
  fil-struktur; fas 2 bygger.

--------------------------------------------------------------------------------
## 8. PLATS-NOT (deliverable + varför)

Dispatch-briefen (min task-spec) säger uttryckligen: "Allt ska vara filbaserat under
/srv/workspace/Cad/" och DoD = "PLAN.md under WORKSPACE" samt "skriv ... till
/srv/workspace/Cad/sickan/RESULT.md". T2 (bernie) kedjeläser `/srv/workspace/Cad/sickan/PLAN.md`
(VERIFIERAT ur t2-brief: READ /srv/workspace/Cad/sickan/PLAN.md).

Min utskicks-projekt-workspace (beräknad av runner:n) är `/srv/workspace/svarkor-cad-phase1/
sickan/`. Båda platserna skrivs (append-only, ingen overhead): PRIMÄR chain-deliverable på
/srv/workspace/Cad/sickan/PLAN.md (det kedjan/T2 faktiskt läser), och en IDENTISK kopia +
evidenfil i /srv/workspace/svarkor-cad-phase1/sickan/398.1-*.md (där orkestratorn tittar).
Båda är gruppläsbara; inga secrets.

--------------------------------------------------------------------------------
## 9. CONFIDENCE

HÖG på all motor-fakta: jag körde själv export (STEP/STL/BREP/3MF/SVG OK), STEP-import OK,
tessellate OK (24v/12f), IGES-export-fail via CadQuery, IGES-import-fail via importShape,
IGES-fil skrivbar via IGESControl_Writer, trimesh SAKNAS i venv — allt i /tmp/cadspike
denna session (VERIFIERAT, pastat i §3/§4). HÖG på greenfield (LEDGER + show 398). MEDIUM
på ägarens exakta fas-1-scope för IGES och webb/CLI-prioritet — surfacat som SO-1/SO-2.
MEDIUM på att T2/T3 läser exakt /srv/workspace/Cad/sickan/PLAN.md (utlärt ur t2-brief, som
är en /tmp-fil — se §8). UNVERIFIED-negativ: ingen tidigare CAD-konverterare i flottan (kb
är recall-index, inte bevis).

--------------------------------------------------------------------------------
## 10. MODULE LIST (hand-off till bernie, T2)

MODULE LIST:
- module: cad-core
  path: cad/brep.py
  concern: enda B-rep-representationen; wrappar OCCT Shape; tessellate till trianglar
  interfaces: BRep class wrapping OCP Shape; .shape, .tessellate(tol)->(verts,faces)
  reuse: REUSE CadQuery 2.8.0 / OCCT 7.9.3.1.1 (spike-verifierad) | NEW: inget i repot
  open_question: (none)

- module: cad-import
  path: cad/importers.py
  concern: input-kranar; alla ingångsformat (STEP/BREP/IGES) -> EN OCCT B-rep i mod_core
  interfaces: load_shapes(path, fmt) -> BRep; internal reader-register fmt->reader
  reuse: REUSE CadQuery importers (STEP/BREP) + OCCT IGESControl (IGES via mod_iges) | NEW: filen
  open_question: (none)

- module: cad-export-brep
  path: cad/exporters.py
  concern: output B-rep/vector-vägen: STEP/BREP direkt, SVG via CadQuery, IGES via adapter
  interfaces: export_brep(brep, path, fmt); register entries under cad/formats.py
  reuse: REUSE CadQuery exporters (STEP/BREP/SVG) + OCCT IGESControl via mod_iges | NEW: filen
  open_question: (none)

- module: cad-mesh
  path: cad/mesh.py
  concern: mesh-vägen: B-rep tessellate -> trimesh -> STL/OBJ/3MF/GLTF/PLY
  interfaces: to_trimesh(brep)->trimesh.Trimesh; export_mesh(brep, path, fmt)
  reuse: REUSE OCCT tessellate + numpy | NEW: trimesh dependency (INTE installerad, VERIFIERAT)
  open_question: pin trimesh version i requirements (R2)

- module: cad-iges
  path: cad/iges_adapter.py
  concern: enda genuint nya motordelen; IGES in+ut via low-level OCCT IGESControl
  interfaces: read_iges(path)->BRep; write_iges(brep, path)  [bypasses CadQuery importers/exporters]
  reuse: REUSE OCCT IGESControl_Reader/Writer (low-level) | NEW: koden (högst risk i bygget)
  open_question: SO-1 — ägare bekräftar IGES i fas-1-scope (och ev. IGES-UT stretch)

- module: cad-registry
  path: cad/formats.py
  concern: central format->handler-dispatch för alla utgångar (B-rep | mesh | vector)
  interfaces: SUPPORTED_FORMATS dict; convert(brep, out_fmt, path)
  reuse: channels mod_export/mod_mesh/mod_iges | NEW: filen (trivial; gör format-tillägg billiga)
  open_question: (none)

- module: cad-api
  path: server/api.py
  concern: webb-API-lager: POST-upload -> konvertering -> nedladdning
  interfaces: POST /convert (multipart->format->file); GET /formats; FastAPI app
  reuse: REUSE FastAPI (finns i flottan, t.ex. Hotell) | NEW: för detta repo
  open_question: SO-2 — webb/CLI-prioritet; webb efter CLI (rekommenderat)

- module: cad-cli
  path: cli.py
  concern: kommandorad: `cadconv in.step --to obj`
  interfaces: argparse; same pipeline via cad-registry (ingen HTTP)
  reuse: channels cad-registry | NEW: filen
  open_question: SO-2 — CLI först (rekommenderat)

- module: cad-web
  path: server/web.py
  concern: enkelt drag-och-släpp-gränssnitt (statisk HTML/JS -> mod_api)
  interfaces: serves index.html; JS posts file to /convert
  reuse: channels cad-api | NEW: filen
  open_question: (none — efter SO-2)

- module: cad-validate
  path: tests/
  concern: golden-file + roundtrip-tester per format; gör dobbie A4 mätbart
  interfaces: pytest suite; golden meshes; convert(ref.step, fmt) compare
  reuse: REUSE spike-venv /tmp/cadspike som bas | NEW: test/tooling-filer
  open_question: (none)

OPEN QUESTION (blockerande för fas 1-SCOPE, ej för plan-strukturen):
1) Är IGES i fas-1-scope (SO-1) — den enda dyra modulen; rekommenderas ja, ev. IGES-UT som stretch.
2) CLI-först vs webb-först (SO-2) — rekommenderas CLI först (billigare, dobbie-verifierbar).
Båda surfacade till ägaren/örkestrator; bernie (T2) kan börja oavsett eftersom modul-gränserna
är identiska under båda valen.
