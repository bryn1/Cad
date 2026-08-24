"""cad-validate (C10) — shared helpers for the golden + roundtrip suite.

This module is the seam between the cad-validate tests and the rest of the CAD
graph (DESIGN.md r1): every test here drives the ONE public faces of the graph —
cad.importers.load (C2) and cad.formats.convert (C6) — never the internals. That
keeps cad-validate a true end-to-end gate over the full registry rather than a
re-test of a single module.

The geometric "signature" of a BRep is the stable, measurable summary this suite
commits to golden.json and checks the freshly-produced files against. IGES/STEP
carry timestamps + non-deterministic entity ordering, so byte equality is NOT a
valid cross-run assertion; the volume/surface-area/bounding-box signature is
(r3 golden test tolerance). Mesh formats are asserted on vertex/face counts and
watertightness, which trimesh recomputes from the same tessellation.

validate-expansion (T4): this copy of the helpers adds a MULTI-MODEL registry
(box, cyl, holed) and per-format roundtrip assertions so a single parametrised
test drives the full 3x9 in/out matrix across three distinct reference solids.
"""

from __future__ import annotations

import json
import os

# Anchored to this file so the suite runs from its own tree regardless of CWD
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
GOLDEN_DIR = os.path.join(TESTS_DIR, "golden")
GOLDEN_IN = os.path.join(GOLDEN_DIR, "in")
GOLDEN_DB = os.path.join(GOLDEN_DIR, "golden.json")

# --- T4: multi-model registry ------------------------------------------------
# model name -> dict of input/OUTPUT loadable formats -> golden input filename
# Every model has golden references in all three SOLID input formats (step/iges/brep),
# so the full matrix (3 x 9) is driven three times, once per model.
MODELS = ["box", "cyl", "holed"]          # distinct source geometries
SOLD_INPUT_FMTS = ["step", "iges", "brep"]  # loadable input formats (solid)
# the 9 OUTPUT formats (matrix columns): solid outputs, one vector format, mesh outputs
SOLD_OUTPUT_FMTS = ["step", "brep", "iges"]   # re-loadable solid (signature) outputs
VECTOR_OUTPUT_FMTS = ["svg"]                  # flat vector, no solid signature
MESH_OUTPUT_FMTS = ["stl", "obj", "3mf", "gltf", "ply"]  # topology outputs

# test node names -> all 27 pairs via parametrization
def golden_input(model: str, fmt: str) -> str:
    """Path of the golden reference for a model in a given input format."""
    return os.path.join(GOLDEN_IN, f"golden-{model}.{fmt}")


def _cq_shape(brep):
    """Wrap a cad.brep.BRep's OCCT shape in a CadQuery Shape for metrics."""
    from cadquery.occ_impl.shapes import Shape as _CqShape

    return _CqShape(brep.shape)


def brep_signature(brep) -> dict:
    """Compute the measurable geometric signature of a BRep.

    Returns {volume, surface_area, bbox: (min_x,min_y,min_z,max_x,max_y,max_z)}
    rounded to 6 decimals — the stable values compared against golden.json.
    """
    s = _cq_shape(brep)
    bb = s.BoundingBox()
    return {
        "volume": round(s.Volume(), 6),
        "surface_area": round(s.Area(), 6),
        "bbox": tuple(round(float(v), 6) for v in (bb.xmin, bb.ymin, bb.zmin,
                                                   bb.xmax, bb.ymax, bb.zmax)),
    }


def load_brep(path: str):
    """C2 load of a file into a BRep (the graph's single input face)."""
    from cad.importers import load

    return load(path)


def convert_to(brep, fmt: str, out_path: str, **opts) -> None:
    """C6 convert of a BRep to fmt at out_path (the graph's single dispatch)."""
    from cad.formats import convert

    convert(brep, fmt, out_path, **opts)


def read_golden_db() -> dict:
    """Load the committed golden.json signature database."""
    with open(GOLDEN_DB, "r", encoding="utf-8") as fh:
        return json.load(fh)


def mesh_counts(path: str) -> dict:
    """Recompute vertex/face/watertight metrics from a written mesh file.

    Trimesh re-reads the file we just wrote and reports the same tessellation,
    so these counts are a stable cross-run check for the mesh formats.
    """
    import trimesh

    m = trimesh.load(path, force="mesh")
    return {
        "vertices": int(len(m.vertices)),
        "faces": int(len(m.faces)),
        "is_watertight": bool(m.is_watertight),
    }


# --- T4: per-format roundtrip assertions -------------------------------------

def assert_signature_close(actual: dict, expected: dict, tol: float = 1e-4) -> None:
    """Assert two signatures agree within an absolute tolerance on every value."""
    assert abs(actual["volume"] - expected["volume"]) <= tol, (
        f"volume {actual['volume']} != {expected['volume']}")
    assert abs(actual["surface_area"] - expected["surface_area"]) <= tol, (
        f"surface_area {actual['surface_area']} != {expected['surface_area']}")
    assert len(actual["bbox"]) == len(expected["bbox"]) == 6
    for a, e in zip(actual["bbox"], expected["bbox"]):
        assert abs(a - e) <= tol, f"bbox {actual['bbox']} != {expected['bbox']}"


def assert_svg_well_formed(path: str) -> None:
    """SVG output must be a well-formed, non-empty SVG document."""
    with open(path, "r", encoding="utf-8") as fh:
        head = fh.read(4000)
    assert "<svg" in head, "SVG output missing <svg> root"
    assert os.path.getsize(path) > 0, "SVG output empty"
    import xml.etree.ElementTree as ET

    ET.parse(path)  # raises ParseError on malformed XML


def assert_mesh_interior(actual: dict, ref: dict) -> None:
    """Mesh topology must match the reference tessellation within tolerance.

    Faces reflect the same triangulation, so they must be identical in count;
    vertex count reflects OCCT dedup and may shift by a few for IGES input.
    """
    assert actual["faces"] == ref["faces"], (
        f"face count {actual['faces']} != reference {ref['faces']}")
    assert actual["is_watertight"] is True, "mesh must be watertight"


def output_bbox(path: str, fmt: str):
    """Bounding box of a file output, solid+vector via C2 load, mesh via C4.

    The graph's B-rep loader (cad.importers.load, C2) reads ONLY solid formats
    (step/iges/brep); mesh outputs are re-read through trimesh, the same tool the
    C4 mesh path writes with, so the bbox comparison is uniformly valid.
    """
    if fmt in ("step", "iges", "brep"):
        return brep_signature(load_brep(path))["bbox"]
    import trimesh

    m = trimesh.load(path, force="mesh")
    return tuple(round(float(v), 6) for v in m.bounds.flatten())

