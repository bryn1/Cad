"""cad-validate roundtrip tests — format-to-format fidelity over the ONE registry.

DESIGN.md r1 §C10: the roundtrip gate proves no information is lost moving a
model through two or more formats. Every roundtrip flows through the graph's
single dispatch (cad.importers.load C2 -> cad.formats.convert C6), the same path
the CLI (C9) and web shell (C8) use, so passing here means the integrated graph
is sound, not just one module.

Roundtrips covered:
  - STEP -> BREP -> STEP (explicit "STEP->BREP->STEP" from the card)
  - STEP -> IGES -> STEP  and IGES -> STEP -> IGES (solid-preserving check)
  - mesh formats (stl/obj/3mf/gltf/ply) -> trimesh re-read with pinned counts
Golden reference inputs in tests/golden/in are REUSED as roundtrip sources so the
two suites agree on the personality of the model under test (a 10x20x30 box).
"""
from __future__ import annotations

import os
import tempfile
import unittest

import cad_validate_helpers as H
from cad_validate_helpers import (
    brep_signature,
    convert_to,
    GOLDEN_IN,
    load_brep,
    mesh_counts,
)

_HAS_ENGINE = False
try:  # engine present -> real roundtrips (not stubs)
    import cadquery  # noqa: F401

    _HAS_ENGINE = True
except Exception:  # noqa: BLE001
    pass


def _box_brep():
    from cad.brep import BRep

    import cadquery as cq

    return BRep.from_shape(cq.Workplane("XY").box(10, 20, 30).val().wrapped)


@unittest.skipUnless(_HAS_ENGINE, "cadquery/OCCT engine not installed")
class RoundtripSolidTests(unittest.TestCase):
    """Solid-preserving roundtrips through C2 load + C6 convert."""

    maxDiff = None

    def _assert_volume_unity(self, original, target_fmt, out_name):
        """load(convert(brep, fmt, out)) has the same volume as the input brep."""
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, out_name)
            convert_to(original, target_fmt, out)
            self.assertGreater(os.path.getsize(out), 0)
            re_read = load_brep(out)
            return brep_signature(re_read)["volume"]

    def test_step_brep_step_roundtrip_preserves_volume(self):
        # The explicit "STEP->BREP->STEP" from the card: load a STEP, write it as
        # BREP, read that BREP, convert back to STEP, read again — volume intact.
        src = load_brep(os.path.join(GOLDEN_IN, "golden-box.step"))
        v_orig = brep_signature(src)["volume"]
        with tempfile.TemporaryDirectory() as td:
            brep_of = os.path.join(td, "mid.brep")
            convert_to(src, "brep", brep_of)
            mid = load_brep(brep_of)
            final_step = os.path.join(td, "final.step")
            convert_to(mid, "step", final_step)
            final_brep = load_brep(final_step)
        v_final = brep_signature(final_brep)["volume"]
        self.assertAlmostEqual(v_orig, v_final, places=2,
            msg="STEP->BREP->STEP lost volume")

    def test_step_iges_step_roundtrip_preserves_bbox(self):
        src = load_brep(os.path.join(GOLDEN_IN, "golden-box.step"))
        bbox_orig = brep_signature(src)["bbox"]
        with tempfile.TemporaryDirectory() as td:
            igs = os.path.join(td, "mid.iges")
            convert_to(src, "iges", igs)
            mid = load_brep(igs)
            step_back = os.path.join(td, "back.step")
            convert_to(mid, "step", step_back)
            final = load_brep(step_back)
        bbox_final = brep_signature(final)["bbox"]
        self.assertEqual(bbox_orig, bbox_final,
            "STEP->IGES->STEP must preserve the bounding box")

    def test_iges_step_iges_roundtrip_preserves_iges_golden_surface(self):
        src = load_brep(os.path.join(GOLDEN_IN, "golden-box.iges"))
        area_orig = brep_signature(src)["surface_area"]
        with tempfile.TemporaryDirectory() as td:
            step_path = os.path.join(td, "box.step")
            convert_to(src, "step", step_path)
            mid = load_brep(step_path)
            igs_back = os.path.join(td, "box-back.iges")
            convert_to(mid, "iges", igs_back)
            final = load_brep(igs_back)
        area_final = brep_signature(final)["surface_area"]
        self.assertAlmostEqual(area_orig, area_final, places=2,
            msg="IGES->STEP->IGES lost surface area")


@unittest.skipUnless(_HAS_ENGINE, "cadquery/OCCT engine not installed")
class RoundtripMeshTests(unittest.TestCase):
    """Mesh formats: export_mesh -> trimesh re-read, counts + watertightness."""

    def test_each_mesh_format_roundtrips_through_trimesh(self):
        brep = _box_brep()
        # reference tessellation from the core BRep (C1)
        verts, faces = brep.tessellate(tolerance=0.1)
        ref_nv, ref_nt = len(verts), len(faces)
        self.assertGreaterEqual(ref_nv, 8)
        self.assertGreaterEqual(ref_nt, 12)

        with tempfile.TemporaryDirectory() as td:
            for fmt in ("stl", "obj", "3mf", "gltf", "ply"):
                out = os.path.join(td, f"box.{fmt}")
                convert_to(brep, fmt, out, tolerance=0.1)
                self.assertGreater(os.path.getsize(out), 0, msg=f"{fmt}: no file")
                stats = mesh_counts(out)
                # trimesh reports the same tessellation the core produced — the
                # triangle count is 1:1 (face loop is exact), and the deduplicated
                # vertex count must sit between the 8 real box corners and the raw
                # per-face list (OCCT tessellate emits per-face duplicates).
                self.assertEqual(stats["faces"], ref_nt, msg=f"{fmt}: face count")
                self.assertGreaterEqual(stats["vertices"], 8, msg=f"{fmt}: <8 corners")
                self.assertLessEqual(stats["vertices"], ref_nv,
                    msg=f"{fmt}: verts exceed raw list")
                self.assertTrue(stats["is_watertight"], msg=f"{fmt}: not watertight")


if __name__ == "__main__":
    unittest.main()
