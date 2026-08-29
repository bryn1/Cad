"""Input-extension SPELLINGS must reach the reader they name (cad.importers C2).

Measured on the live product 2026-08-29 (sibbamala.com/cad): the drag-drop page's file picker
accepts `.step,.stp,.brep,.iges,.igs`, but POST /convert with `box.stp` answered
415 "Unsupported input format 'stp'" (and `cyl.igs` likewise) while `box.step` converted.
These tests pin the one resolver both `load()` and the API pre-check now share, and that
`supported_inputs()` is still exactly the registry (aliases are spellings, not formats).

Pure: no engine needed for the resolver itself; the engine-backed round trip below is skipped
(never faked) when cadquery is absent.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest

import cad
from cad import importers
from cad.importers import INPUT_ALIASES, resolve_input_format, supported_inputs

GOLDEN_IN = os.path.join(os.path.dirname(__file__), "golden", "in")

try:  # engine present -> real .stp/.igs loads, else skipped (reported, never faked)
    import cadquery  # noqa: F401
    _HAS_ENGINE = True
except Exception:  # noqa: BLE001
    _HAS_ENGINE = False


class ResolveInputFormatTests(unittest.TestCase):
    def test_aliases_map_to_registry_names(self):
        for alias, target in INPUT_ALIASES.items():
            self.assertIn(target, supported_inputs(), alias)
            self.assertEqual(resolve_input_format(alias), target)
            self.assertEqual(resolve_input_format("." + alias.upper()), target)
            self.assertEqual(resolve_input_format("model." + alias), target)

    def test_ui_accept_list_all_resolve(self):
        # the exact spellings server/web.py advertises: accept=".step,.stp,.brep,.iges,.igs"
        for ext, want in ((".step", "step"), (".stp", "step"), (".brep", "brep"),
                          (".iges", "iges"), (".igs", "iges")):
            self.assertEqual(resolve_input_format("upload" + ext), want, ext)
            self.assertIn(want, supported_inputs())

    def test_registry_names_pass_through_and_case_folds(self):
        for name in supported_inputs():
            self.assertEqual(resolve_input_format(name), name)
            self.assertEqual(resolve_input_format(name.upper()), name)
            self.assertEqual(resolve_input_format("a.b." + name.upper()), name)

    def test_unknown_spelling_is_returned_lowercased_not_invented(self):
        self.assertEqual(resolve_input_format("thing.DXF"), "dxf")
        self.assertNotIn("dxf", supported_inputs())
        self.assertEqual(resolve_input_format("noext"), "noext")

    def test_supported_inputs_is_still_exactly_the_registry(self):
        self.assertEqual(supported_inputs(), list(importers._READERS))
        for alias in INPUT_ALIASES:
            self.assertNotIn(alias, supported_inputs())

    def test_exported_from_the_package(self):
        self.assertIs(cad.resolve_input_format, resolve_input_format)

    def test_load_unknown_spelling_names_what_it_saw(self):
        with self.assertRaises(cad.UnsupportedFormatError) as cm:
            cad.load("model.dxf")
        self.assertIn("'dxf'", str(cm.exception))


@unittest.skipUnless(_HAS_ENGINE, "cadquery/OCCT engine not installed -- alias round trip skipped")
class AliasLoadRoundTripTests(unittest.TestCase):
    def _copy_as(self, src_name: str, dst_name: str, td: str) -> str:
        dst = os.path.join(td, dst_name)
        shutil.copyfile(os.path.join(GOLDEN_IN, src_name), dst)
        return dst

    def test_stp_and_igs_load_like_their_long_forms(self):
        from cad_validate_helpers import brep_signature  # tests/ is on sys.path, as test_golden
        with tempfile.TemporaryDirectory() as td:
            long_step = brep_signature(cad.load(os.path.join(GOLDEN_IN, "golden-box.step")))
            short_step = brep_signature(cad.load(self._copy_as("golden-box.step", "box.stp", td)))
            self.assertEqual(short_step["bbox"], long_step["bbox"])
            long_iges = brep_signature(cad.load(os.path.join(GOLDEN_IN, "golden-cyl.iges")))
            short_iges = brep_signature(cad.load(self._copy_as("golden-cyl.iges", "cyl.IGS", td)))
            self.assertEqual(short_iges["bbox"], long_iges["bbox"])


if __name__ == "__main__":
    unittest.main()
