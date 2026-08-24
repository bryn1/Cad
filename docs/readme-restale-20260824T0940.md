# CAD-filkonverterare (svarkor-ai/Cad) — projekt-README

> Skriven av Mirre (doc) — MC 530.5, 2026-08-24T0940 UTC — **från landade
> artefakter**. Detta är en SUPERSEDE av fas-3-README
> `/srv/workspace/svarkor-cad-phase3/mirre/494.6-readme-restale-20260823T2225.md`
> (som i sin tur supersedade `422.24-project-readme-…`). Fas-4 ändrade två
> saker som fas-3-texten hann bli inaktuell på: **holed IGES→STEP-z-defekten är
> FIXAD** (det enda "ärligt begränsade paret" är borta) och **MED-1 (rate-
> limiter-minnesläckan) är STÄNGD**. Båda markerade `[UPDATE]`. Läs hela; varje
> siffra har recept i "Källuppgifter".

_Detta README dokumenterar projektet som det LANDAT efter fas 2 + härdnings-/
matrixarbetet i fas 3 + fas-4-fixarna. Koden ligger i per-modul-arbetsmappar
under `teddy/` — den har ÄNNU inte commitats in i repot `/srv/workspace/Cad`
(gren `main` saknar helt commits). Det är därför en "as-built / landed"-
beskrivning, inte en "as-in-git"-beskrivning. När integratorn monterat trädet
ska denna text flyttas till repots kanoniska hem `README.md` och ersätta de
tidigare versionerna._

---

## Vad är det här?

Ett CAD-filkonverterar-bibliotek (+ CLI + webbskal) som läser **STEP, IGES och
BREP** och skriver ut till **STEP, BREP, SVG, IGES, STL, OBJ, 3MF, GLTF, PLY** —
totalt 3 in-format, 9 ut-format. Ett kärn-`BRep` (B-rep) är den enda
representationsform som alla konverteringar går igenom (invariant I1), och allt
ut går genom ett enda register `cad.formats.convert()` (invariant I2).

Målet är `A4` (mätbart): en golden-file + roundtrip-testsvit (C10) som gör att
konverteringen är mätbar, plus gate-kort som verifierar att hela grafen bygger
och klarar testerna. Fas 3 (494) körde full matrix över alla 27 in/ut-par med 3
olika källmodeller; fas 4 (530) fixade det enda avvikande paret och stängde en
residual — se "Verifiering" nedan.

---

## Paket & arkitektur — `cad` (v0.1.0) [oförändrat]

Ett enda Python-paket `cad` med moduler som speglar designkontrakten (DESIGN.md r1 §C1–C7):

| Modul (`cad/…`) | Kontrakt | Ansvar |
|---|---|---|
| `brep.py` | C1 (kärna) | `BRep` — den enda kärnrepresentationsformen (I1); `BRep.from_shape`, `.shape`, `.tessellate(tolerance) -> (vertices, faces)` |
| `importers.py` | C2 | `load(path, fmt=None) -> BRep` — läser STEP/BREP via CadQuery, IGES via adapter; format löses från filändelse när ej given |
| `exporters.py` | C3 | `export_brep(brep, out_path, fmt)` — STEP/BREP/SVG via CadQuery, IGES delegerad till adaptern |
| `mesh.py` | C4 | `export_mesh(brep, out_path, fmt, tolerance=0.1)` — STL/OBJ/3MF/GLTF/PLY via trimesh (den ENDA plats trimesh används) |
| `iges_adapter.py` | C5 | `read_iges/write_iges` — driver OCCT `IGESControl_Reader/Writer` direkt; enda modulen som rör OCCT-IGES |
| `formats.py` | C6 | `SUPPORTED_FORMATS`-registret, `get_handler`, `convert`, `available_formats` — ENDA dispatchpunkten (I2) |
| `errors.py` | C7 | Typad felhierarki: `CadError` → `UnsupportedFormatError` / `ParseError` / `ConversionError` |

### Registret (`cad/formats.py` — C6/I2) [oförändrat]

Allt ut konvergerar igenom `SUPPORTED_FORMATS`. `convert(brep, fmt, out_path, **opts)`
slår upp en handler för `fmt` och skriver filen. Format-specifika inställningar
(tex mesh-`tolerance`) följer med i `opts`.

Verifierade ut-format (full matrix, från registret):
    step, brep, svg · iges · stl, obj, 3mf, gltf, ply
Verifierade in-format (`cad.importers.supported_inputs()`): step, iges, brep.

### Fel (C7) → användarutfall [oförändrat]

| Typad undantag | Betydelse |
|---|---|
| `UnsupportedFormatError` | Formatet stöds inte (C7.1) |
| `ParseError` | Indata kunde inte läsas/tolkas (C7.2) |
| `ConversionError` | Utdata kunde inte skrivas (C7.3) |

---

## CLI — `cadconv` (C9) [oförändrat]

Ett tunt skal (endast argparse + felkartläggning, ingen konverteringslogik) över
`cad.importers.load` + `cad.formats.convert`:

    usage: cadconv [-v] <input> --to <fmt> [-o <out>] [--tolerance <t>] [--list-formats]

- `--list-formats` — listar in-/ut-format och avslutar (exit 0)
- `-v/--verbose` — skriv ut en sammanfattningsrad på framgång
- `-o/--out` — utsökväg; default: indatats basnamn + nytt format i CWD
- `--tolerance <t>` — bara mesh-format; finare ju mindre

Exitkoder (C9): `0` = ok; `2` = usage/ej stött format; `3` = parse-fel;
`4` = konverteringsfel. Installeras som console-script `cadconv = "cli:main"`.

---

## API — `server` (C8, FastAPI `cad-api` v0.1.0) [UPDATE: MED-1 stängd]

Ett FastAPI-webbskal som INTE håller någon konverteringslogik (invariant C8/I2) —
det routar, gater och rör temp-filer:

| Endpoint | Beskrivning |
|---|---|
| `GET /` | Minimal HTML-landningssida |
| `GET /formats` | `{inputs: [...], outputs: [...]}` från registret |
| `POST /convert` | multipart-uppladdning (`file`, `format`, `tolerance?`) → filbytes |

C7 → HTTP-karta (oförändrad): `UnsupportedFormatError` → **415**,
`ParseError` → **400**, `ConversionError` → **500**, ogiltig formulärform →
**422**.

### Härdning av `/convert` (sigrid 422.22 → MC 494.1, verifierad 494.3/494.5)

Två gater körs **före** kroppen parsas (FastAPI-`Dependencies` på endpointen):

- **413 — 15 MiB-storlekscap.** `MAX_UPLOAD_BYTES = 15 * 1024 * 1024` (15,728,640 B).
  Två lager: (1) en över-stor `Content-Length` returnerar 413 innan starlette-
  multipart-persaren nuddar kroppen; (2) en strömmande cap stannar även en
  chunked-overföring utan Content-Length vid gränsen med 413 (stänger
  chunked-bypass). 413 skiljs från FastAPIs egen 422 (request-formvalidering).
- **429 — per-klient rate limit.** `RATE_MAX_REQUESTS = 20` per 60 s
  (glidande fönster, in-memory), nycklad per clients socket-peer-IP (inte
  klientstyrda data). Överskrids gränsen svarar endpointen 429 med `Retry-After`.

Filnamnsgaten `_validate_upload_name` (avvisar NUL / sökvägsseparation / absoluta
sökvägar / `..` → 400, sigrid 422.21 LOW) finns kvar.

**[UPDATE] MED-1 — rate-limiter-minnesläckan är STÄNGD (fas 4, MC 530.3/530.4):**
den gamla `_hits`-kartan (en permanent dict-post per distinkt klient, aldrig
borttagen) var sigrid MED-1 (UnboundedGrowth). Nu är kartan en LRU-`OrderedDict`
med `MAX_CLIENT_STATE_ENTRIES = 4096` — på ny nyckel vid cap evicteras den
minst nyligen använda posten. Gated PASS av dobbie (530.4, ren miljö): en
cap-borttagen UNBOUNDED-mutant failar 4 bounded-limiter-tester och en
20000-distinkta-klienter-probe växer till 20000, inte cap:en. **Divergens
(report vs artefakt):** fas-3-produktionsfilen
`494.1-cad-api-hardening-…/server/api.py` (mtime 08-23 19:21) är FORTFARANDE
den obundna limiteraren — MED-1-fixen ligger i teddy:s leverans
`/srv/workspace/svarkor-cad-phase4/teddy/530.3-bounded-rate-limiter-20260824T0712/api.py`
(mtime 08-24 07:12) och i `/home/teddy/cadapi-build3`, och landar i repot vid
Svarkors integration. Tills dess gäller den obundna versionen i den
fas-3-produktionsfilen.

**[UPDATE] LOW-1 — kvar, oförändrad (reasoned, UNVERIFIED-future):** nyckeln är
socket-peer-IP; sätts en reverse-proxy framför (utanför dagens lokala scope)
kollapsar alla klienter till EN bucket. Ej utnyttjbar idag; ej i fas-4-scopet.

---

## Beroenden (pinnade, Python ≥ 3.11) [oförändrat]

Från `requirements.txt` i de landade modulmapparna (494.1):

    cadquery==2.8.0
    numpy==2.4.6
    trimesh==5.0.0      # C4 mesh — enda trimesh-användaren (invariant C4)
    networkx==3.6.1     # trimesh-optional, krävs av 3mf/GLTF-exportrar
    lxml==6.1.2         # trimesh-optional, krävs av 3mf-exporten
    fastapi==0.141.1     # cad-api (C8) — var 0.115.6; upphöjd
    starlette==1.6.0     # >=1.3.1 rensar hela starlette-CVE-batchen
    uvicorn[standard]==0.30.1
    python-multipart==0.0.32  # var 0.0.9 (känd sårbar); >=0.0.31 golvet

Varför upphöjt: den gamla pinningen `python-multipart==0.0.9` /
`fastapi==0.115.6` var det kända sårbara web-lagret (sigrid 422.22: två HIGH —
multipart-parse-DoS + helt öppen `/convert`). `python-multipart==0.0.32`
(>=0.0.31 golv) stänger DoS-familjen. fastapi 0.141.1 + starlette 1.6.0 är
minsta pip-audit-rena paret: starlette>=1.3.1 rensar de sista 8 starlette-CVE:erna
(PYSEC-2026-161/248/249/1942/2280/2281). `pip-audit -r requirements.txt` →
`No known vulnerabilities found`, exit 0 (verifierat av teddy 494.1 + sigrid 494.3).

---

## Verifiering & kvalitet (A4-mätbar, C10) [UPDATE: full matrix, alla par gröna]

### Full 3x9-konverteringsmatrix (fas 3, MC 494.4 / gate 494.5; fas-4-fix 530.1/530.2)

Den gamla fas-2-verifieringen (422.20) täckte EN modell / partiella par (19
tester, en 10x20x30-box). Detta ersätts av den fulla matrixen:

- **3 in-format** × **9 ut-format = 27 par**, driven över **3 distinkta
  källmodeller** (box, cyl, holed), alla golden-refar i alla 3 in-format:
  - `box`   = 10×20×30 kuboid
  - `cyl`   = cylinder r=5 h=20
  - `holed` = 10x10x10 låda med genomgående hål
- **[UPDATE] Resultat: `169 passed, 12 skipped, 10 xfailed`, exit 0** — verifierat
  av dobbie (530.2 PASS, ren miljö, 2026-08-24T09:24) med **två** samstämmiga
  körningar, plus teddy 530.1/530.3. (Fas-3-talen `166/12/13` och `26 av 27 par`
  är SUPERSEDED: fixen av det avvikande paret gjorde tre gamla xfails till
  riktiga asserts → 166→169 passed, 13→10 xfailed, och alla 27 par är nu
  identiska.) Mutation-bevisat (fas 3): korrumpera golden-signaturen → 3 FAILED
  → återställ → grönt. Testerna biter.
- **[UPDATE] Alla 27 av 27 par konverterar med exakt geometri (surface area +
  bbox + face-count 1:1).** Inget par är längre begränsat.

### [UPDATE] Det enda avvikande paret är FIXAT (holed IGES→STEP)

Fas-3-texten listade som "enda ärligt begränsade paret (escalerad
defektkandidat)": **holed IGES→STEP förlängde bbox i z (5→15), deterministiskt
3/3.** Detta är FIXAT i fas 4 (MC 530.1, teddy; gated PASS 530.2, dobbie
2026-08-24T09:24). Orsak: OCCT:s `IGESControl_Reader.OneShape()` överförde den
hål-bärande modellen som OGLUADE ytor (NbSolids()==0); STEP-skrivaren
serialiserade dem som 7 oberoende OPEN_SHELLs och fel-bounds den isolerade
hålväggens rotationsyta till z 5→15. Fixen (i `cad/iges_adapter.read_iges`):
sy ihop överförda ytor till en topologiskt sluten SHELL
(`BRepBuilderAPI_Sewing`, `_seal_shell()`), avsiktligt kvar som shell (inte
SOLID) för att bevara IGES-metriken i fyndet nedan. Nu läses holed.iges→step
med exakt bbox `(-10,-10,-5,10,10,5)` (z stannar på 5), oberoende omräknat av
dobbie. De tre gamla strict-xfail:en för `[holed,iges,step]` är borttagna och
kör nu som riktiga asserts (`6 passed, 3 skipped`).

### Ärligt begränsade / spårade motorbeteenden (ej testbuggar) [oförändrat]

- **IGES volym == surface area (både in och ut).** OCCT bygger inte om en solid-
  volym från IGES (ytor/trimmat). Sann geometri (surface area + bbox) är exakt;
  bara *volym-metriken* degraderar genom IGES. Volym assertas därför ENDAST i
  rena solid-domänen (step/brep, ingen IGES-endpoint). De **12 `skipped`**
  testerna är just detta: IGES-volym-diagnostiken hoppar över par som inte
  involverar IGES.
- **IGES-in av kurvad/hålad solid → mesh är inte vattentät** (10 strict-xfails,
  `(in_fmt=iges)` & modell i {cyl, holed}). Orsak: OCCT per-face IGES-transfer
  delar inga exakta hörn längs delade kanter → trimesh ser sprickor.
  Face-count 1:1 + bbox exakta. Box (planar) från IGES ÄR vattentät; STEP/BREP-
  in är alltid vattentätt. **Dessa 10 xfails är de ENDA kvarvarande** (fas-3-talet
  13 sjönk till 10 när fynd-3:ans tre gick från xfail till riktiga asserts).

### Köra den utökade sviten

    cd /srv/workspace/svarkor-cad-phase3/teddy/494.4-validate-matrix-20260823
    PYTHONPATH=/srv/workspace/svarkor-cad-phase3/teddy/494.1-cad-api-hardening-20260823 \
      /home/teddy/cadapi-venv/bin/python -m pytest tests/ -q

### Lägga till en ny källmodell

1. Skapa modellens golden-refar i **alla tre in-format** under
   `tests/golden/in/`: `golden-<namn>.{step,iges,brep}`.
2. Återskapa signaturerna i `tests/golden/golden.json` med
   `tests/golden/_gen_golden_all.py`.
3. Matrix-testerna är parametriserade över modellmängden;
   `test_matrix_has_three_distinct_models` kräver ≥3 distinkta modeller.
4. Kör sviten; lägg strict-xfails bara för äkta motor-begränsningar, med
   motivering i MATRIX.md.

### Den gamla IGES-volym-divergensen (fortfarande sann, nu spårad)

Kontexten från fas 2 kvarstår: **IGES-volymen är 2200 medan STEP/BREP är 6000**
för samma 10×20×30-box. Det är formatets natur (OCCT bygger inte om volym från
IGES), inte en regression. Se "[Ärligt begränsade]" ovan.

---

## Repo-/landningsstatus (per granskning 2026-08-24T0940 UTC)

- Repo: `/srv/workspace/Cad`, gren `main` — **inga commits ännu**; allt untracked.
  Kod lever i modulmappar under `teddy/` (fas 2: `svarkor-cad-phase2/teddy/`;
  fas 3 härdning/matrix: `svarkor-cad-phase3/teddy/`; fas-4-fixar som separata
  leveranser under `svarkor-cad-phase4/teddy/`).
- DESIGN.md r1 (fas 1) ligger på `/srv/workspace/Cad/bernie/DESIGN.md`.
- Denna README beskriver koden som den landat — när integratorn monterat trädet
  ska texten flyttas till repots kanoniska hem `README.md` och ersätta de
  tidigare versionerna (422.24, 494.6). De fas-4-restale-dokumenten
  (`530.5-hardening-doc-restale-…`, `530.5-matrix-restale-…`) ska tas in
  tillsammans med denna.

---

## Källuppgifter (artefakt-recept — varje tal återhärlett, ej återberättat)

- IGES→STEP-fix + gate: `/srv/workspace/svarkor-cad-phase4/dobbie/530.2-iges-step-gate-PASS-20260824T0924.md`
  (VERDICT PASS, 2 körningar `169/12/10`, oberoende recompute holed z=5) och
  `/srv/workspace/svarkor-cad-phase4/teddy/530.1-holed-iges-step-bbox-z-fix-20260824-084831.md`.
- IGES-fix-artefakt: `/srv/workspace/svarkor-cad-phase3/teddy/494.1-cad-api-hardening-20260823/cad/iges_adapter.py`
  (`_seal_shell` rad 39, anrop rad 100, mtime 08:45).
- MED-1-fix + gate: `/srv/workspace/svarkor-cad-phase4/teddy/530.3-bounded-rate-limiter-20260824T0712/api.py`
  (LRU-cap 4096) och `/srv/workspace/svarkor-cad-phase4/dobbie/530.4-med1-bounded-gate-20260824T0914.md`
  (VERDICT PASS).
- api.py-konstanter + gater (oförändrade delar): `/srv/workspace/svarkor-cad-phase3/teddy/494.1-cad-api-hardening-20260823/server/api.py`.
- Deps-pins: `.../494.1-.../requirements.txt`.
- Matrix (27 par, 3 modeller, fynd): de-staled `530.5-matrix-restale-20260824T0940.md` (denna dir).
- Fas-3-dokument som SUPERSEDES:
  `/srv/workspace/svarkor-cad-phase3/mirre/494.6-readme-restale-20260823T2225.md` och
  `/srv/workspace/svarkor-cad-phase3/mirre/494.6-hardening-and-full-matrix-doc-20260823T2225.md`.

### BLOCKED-notering
Jag (Mirre) kunde INTE själv köra `pytest tests/` i egen användare: motorn
(cadquery/OCP/trimesh) lever bara i andras 0750-hem-venv:s
(`/home/teddy/cadapi-venv`, `/home/dobbie/verify/422.14-eng`). 169/12/10 och
MED-1-mutationen är därför VERIFIED-från-artefakter (läst direkt ur de
fas-4-landade gate:erna 530.2 PASS + 530.4 PASS), inte omkörda av mig. För en
från-grunden-körning: se receptet ovan.
