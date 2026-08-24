"""cad-validate golden-file tests — one full pipeline per golden format.

Verifies (DESIGN.md r1 §C10 + dobbie-gate requirement that cad-validate makes
A4 measurable): for each golden reference file in tests/golden/in, loading it
and re-exporting through the ONE registry (C2 load -> C6 convert) reproduces the
committed geometric signature in tests/golden/golden.json. Because STEP/IGES
carry timestamps and non-deterministic entity order, we assert on the stable
measurable signature (volume / surface area / bounding box), not bytes.
"""
from __future__ import annotations

import os
import tempfile
import unittest

import cad_validate_helpers as H
from cad_validate_helpers import (
    brep_signature,
    convert_to,
    GOLDEN_DIR,
    GOLDEN_IN,
    load_brep,
    read_golden_db,
)

_HAS_ENGINE = False
try:  # engine present -> real golden pipeline (not a stub)
    import cadquery  # noqa: F401

    _HAS_ENGINE = True
except Exception:  # noqa: BLE001
    pass


def _assert_signature(test, actual: dict, expected: dict, fmt: str):
    """Compare computed signature to golden with a small float tolerance.

    The bbox/volume/surface area of the freshly written file must match the
    committed golden (within float tolerance). We only compare the keys present
    for that format, so mesh-only records don't collide with B-rep ones.
    """
    test.assertEqual(set(actual), set(expected), f"{fmt}: signature key set")
    for key, want in expected.items():
        got = actual[key]
        if isinstance(want, (list, tuple)):
            test.assertEqual(len(want), len(got), f"{fmt}.{key}: len mismatch")
            for i, (g, w) in enumerate(zip(got, want)):
                test.assertAlmostEqual(
                    g, w, places=4, msg=f"{fmt}.{key}[{i}] golden mismatch"
                )
        else:
            test.assertAlmostEqual(
                got, want, places=4, msg=f"{fmt}.{key} golden mismatch"
            )


@unittest.skipUnless(_HAS_ENGINE, "cadquery/OCCT engine not installed")
class GoldenFormatTests(unittest.TestCase):
    """Golden-file format-by-format: load + re-export reproduces the signature."""

    maxDiff = None

    def test_golden_db_is_populated_and_has_all_formats(self):
        db = read_golden_db()
        for fmt in ("box.step", "box.iges", "box.brep"):
            self.assertIn(fmt, db, f"golden.json missing {fmt}")

    def test_step_golden_roundtrip_reproduces_signature(self):
        brep = load_brep(os.path.join(GOLDEN_IN, "golden-box.step"))
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "box.step")
            convert_to(brep, "step", out)
            self.assertGreater(os.path.getsize(out), 0)
            re_read = load_brep(out)
            _assert_signature(
                self, brep_signature(re_read), read_golden_db()["box.step"], "step"
            )

    def test_brep_golden_roundtrip_reproduces_signature(self):
        brep = load_brep(os.path.join(GOLDEN_IN, "golden-box.brep"))
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "box.brep")
            convert_to(brep, "brep", out)
            re_read = load_brep(out)
            _assert_signature(
                self, brep_signature(re_read), read_golden_db()["box.brep"], "brep"
            )

    def test_iges_golden_roundtrip_reproduces_signature(self):
        # IGES is face/trimmed-surface based; volume is NOT reconstructed (golden
        # db captures its true golden value) — so assert the full committed
        # signature, which for iges = surface_area + bbox (volume also recorded).
        brep = load_brep(os.path.join(GOLDEN_IN, "golden-box.iges"))
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "box.iges")
            convert_to(brep, "iges", out)
            re_read = load_brep(out)
            _assert_signature(
                self, brep_signature(re_read), read_golden_db()["box.iges"], "iges"
            )

    def test_svg_export_writes_identifiable_svg(self):
        # SVG is a flat 2D projection — no solid signature; assert it is a real
        # non-empty SVG document (C3).
        brep = load_brep(os.path.join(GOLDEN_IN, "golden-box.step"))
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "box.svg")
            convert_to(brep, "svg", out)
            self.assertGreater(os.path.getsize(out), 0)
            with open(out, "r", encoding="utf-8", errors="ignore") as fh:
                content = fh.read()
            self.assertIn("svg", content[:400].lower())


if __name__ == "__main__":
    unittest.main()
