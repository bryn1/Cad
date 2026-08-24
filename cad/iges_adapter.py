"""cad.iges_adapter — IGES import/export (contract C5, the highest-risk NEW module).

DESIGN.md r1 §C5: cad-iges BYPASSES CadQuery for IGES and drives the OCCT
IGESControl_Reader / IGESControl_Writer directly. Its ONLY module edge is cad-core's
concrete BRep (invariant I1); it must NOT reach into other modules' concerns.

    def read_iges(path: str) -> BRep          # OCCT IGESControl_Reader -> BRep
    def write_iges(brep: BRep, out_path: str) -> None  # OCCT IGESControl_Writer -> file

Hard-won real-engine facts (verified against this OCCT build, 20260823):
  - a missing input makes ReadFile return IFSelect_RetError  -> ParseError
  - a PRESENT but corrupt/empty file can still return
    IFSelect_RetDone while NbRootsForTransfer()==0. The caller
    MUST treat 0 transferable roots as a parse failure, never
    as a valid (degenerate) model. IGES is untrusted input: a
    bad file must fail loudly (security-relevant, C7.2).
  - IGESControl_Writer.Write returns a plain bool (True on OK).

Errors (C7): ParseError (input), ConversionError (output), TypeError (bad args).
"""
from __future__ import annotations

import os

from .brep import BRep  # cad-core edge, I1
from .errors import ConversionError, ParseError

# OCCT engine access — only this module touches the IGESControl classes (I1).
from OCP.IFSelect import IFSelect_ReturnStatus  # noqa: E402
from OCP.IGESControl import (  # noqa: E402
    IGESControl_Reader,
    IGESControl_Writer,
)
from OCP.BRepBuilderAPI import BRepBuilderAPI_Sewing  # noqa: E402 - seal shells (I1)
from OCP.TopAbs import TopAbs_ShapeEnum  # noqa: E402
from OCP.TopExp import TopExp_Explorer  # noqa: E402


def _seal_shell(shape: "TopoDS_Shape") -> "TopoDS_Shape":
    """Sew an open IGES-transferred shell into a topologically-sealed shell.

    OCCT's IGES transfer of a solid-with-holes routinely yields a set of UNGLUED
    faces (NbSolids()==0) instead of one connected shell. Downstream writers
    (STEP) then mis-bound the unglued faces — measured as a deterministic bbox
    z-growth (holed.iges -> step, z 5->15: the isolated hole-wall surface of
    revolution is re-bounded to z 5->15 on re-read). Sewing welds the faces along
    shared edges into one SEALED SHELL, which is exactly the topology the IGES
    file describes and which the STEP writer then emits as a correct, closed
    topology (bbox z stays at 5).

    The result is deliberately kept as a SHELL, not promoted to a SOLID: OCCT
    (and the matrix suite, see test_matrix_iges_volume_tracks_surface_area)
    reports volume == surface_area for a shell — the documented engine metric
    that must be preserved for the IGES domain. Promoting to a solid would turn
    that real enclosed volume (3874) into the reported volume and break the
    documented sa-tracking invariant. A shape that is already a solid, or cannot
    be sewn into a sealed shell, is returned unchanged.
    """
    if shape is None:
        return shape
    # already a bounded solid — nothing to seal
    if TopExp_Explorer(shape, TopAbs_ShapeEnum.TopAbs_SOLID).More():
        return shape

    sewing = BRepBuilderAPI_Sewing(1e-5)
    sewing.Add(shape)
    sewing.Perform()
    sewed = sewing.SewedShape()
    if sewed.IsNull():
        return shape

    # keep it a SHELL (preserve vol==sa); only accept a genuinely-sealed shell
    if TopExp_Explorer(sewed, TopAbs_ShapeEnum.TopAbs_SHELL).More():
        return sewed
    return shape


def read_iges(path: str) -> BRep:
    """Parse an IGES file into a BRep (C5, C7.2 ParseError on any input failure)."""
    if path is None:
        raise TypeError("read_iges requires a path string")
    if not isinstance(path, (str, os.PathLike)):
        raise TypeError(f"read_iges expects a path, got {type(path).__name__}")
    path = os.fspath(path)

    if not os.path.isfile(path):
        raise ParseError(f"IGES input not found: {path}")

    reader = IGESControl_Reader()
    status = reader.ReadFile(path)
    if status != IFSelect_ReturnStatus.IFSelect_RetDone:
        raise ParseError(
            f"IGESControl failed to read {path} (status={status})"
        )
    if reader.NbRootsForTransfer() == 0:
        # present-but-unparseable content must never yield an empty shape silently
        raise ParseError(f"No transferable IGES entities in {path} (corrupt or empty)")

    reader.TransferRoots()
    shape = _seal_shell(reader.OneShape())
    return BRep.from_shape(shape)


def write_iges(brep: BRep, out_path: str) -> None:
    """Serialize a BRep to an IGES file (C5, C7.3 ConversionError on output failure).

    Accepts ONLY the concrete cad.brep.BRep (I1) — a raw OCP shape or anything else
    is refused with TypeError, keeping the module's single edge clean.
    """
    if not isinstance(brep, BRep):
        raise TypeError(
            f"write_iges expects a cad.brep.BRep, got {type(brep).__name__} — "
            "wrap raw shapes with BRep.from_shape first"
        )
    if out_path is None:
        raise TypeError("write_iges requires an output path")
    if not isinstance(out_path, (str, os.PathLike)):
        raise TypeError(f"write_iges expects a path, got {type(out_path).__name__}")
    out_path = os.fspath(out_path)

    try:
        writer = IGESControl_Writer()
        writer.AddShape(brep.shape)
        ok = writer.Write(out_path)
    except Exception as exc:  # noqa: BLE001 - surface any engine failure as typed
        raise ConversionError(
            f"IEGS export failed for {out_path}: {exc.__class__.__name__}: {exc}"
        ) from exc

    if not ok:
        raise ConversionError(f"IGESControl failed to write {out_path}")
