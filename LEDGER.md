# LEDGER — CAD-filkonverterare (3D industri)

## Goal
Ett verktyg som tar en 3D-industriell CAD-fil (t.ex. STEP) och konverterar till valfritt
önskat format.

## Acceptance (övergripande)
- [ ] Tar STEP/IGES/BREP som ingång, kan exportera till: STEP, IGES, BREP, STL, OBJ, 3MF, GLTF, PLY, SVG
- [ ] Driver på beprövad motor (OCCT via CadQuery, + trimesh för mesh-vägen)
- [ ] CLI + enkelt webbgränssnitt (dra-och-släpp)
- [ ] Verifierad av dobbie med verkligt build+test, ej "ser bra ut"
- [ ] Push till github.com/svarkor-ai/Cad vid varje milstolpe

## Repo-status (2026-08-22)
- svarkor-ai/Cad = TOMT (greenfield). Inga specs.

## Engine-spike (svarkor, VERIFIERAD 2026-08-22)
- CadQuery 2.x / OCCT fungerar i miljön (Python 3.11 venv)
- EXPORT verifierad: STEP, STL, BREP, 3MF, SVG
- IMPORT+rondtripp verifierad: STEP -> objekt -> re-export
- BEHÖVER mesh-väg (trimesh) för: IGES(nu exporteras ej direkt), GLTF, OBJ, PLY

## Module status
| Fas | Modul | Status |
|---|---|---|
| P1 | plan (sickan) | ✅ DONE → PLAN.md |
| P1 | arkitektur (bernie) | ✅ DONE → DESIGN.md r1 |
| P1 | DA-review (neo) | ✅ SHIP (r1-ship) |
| P2 | byggmoduler | ⏳ 24 kort filade (MC 422), cad-core körs |

## Sign-off (fas 2, 2026-08-23)
- SO-1: IGES **fullt i fas 1** (in + ut) — ägaren bekräftat
- SO-2: **CLI först**, webb därefter — ägaren bekräftat
- SO-3: Python 3.11 mål — antagen (ej blockerande)

## Öppna frågor
- Formatuppsättning exakt (definieras i plan/arkitektur)
- Webb vs CLI-prioritet
