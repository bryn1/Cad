"""cad.exporters — the B-rep/vector output path (contract C3, cad-export-brep).

DESIGN.md r1 §C3: the B-rep/vector output registers STEP/BREP/SVG via the CadQuery
exporters and delegates IGES to the sealed cad-iges adapter (C5). NO mesh output lives
here — that is cad/mesh.py (C4). Every output converges the ONE core BRep (I1) out to a
file; the caller must hold a concrete cad.brep.BRep, never a raw OCP shape.

    def export_brep(brep: BRep, out_path: str, fmt: str) -> None
        # STEP/BREP => CadQuery exporters.export ; SVG => CadQuery exporters.export(svg)
        # IGES      => iges_adapter.write_iges (see C5)
    def supported_brep_formats() -> list[str]    # ['step','brep','svg','iges']

Errors (C7): UnsupportedFormatError (unknown format), ConversionError (write failed),
TypeError (bad arguments). I1/C3 exceptions: this module (like the CadQuery importers it
mirrors) is one of the few that may call the CadQuery exporters to move a BRep to a file.
"""
from __future__ import annotations

import os

from .brep import BRep  # cad-core edge, I1
from .errors import ConversionError, UnsupportedFormatError
from . import iges_adapter  # C5 edge — the ONLY module that may touch OCCT IGESControl

try:  # pragma: no cover - import guard keeps the module importable pre-install
    from cadquery import exporters as _cqexporters
    from cadquery.occ_impl.shapes import Shape as _CqShape
    _HAS_ENGINE = True
except Exception:  # noqa: BLE001 - tolerate the module being imported w/o engine
    _cqexporters = None  # type: ignore[assignment]
    _CqShape = None  # type: ignore[assignment]
    _HAS_ENGINE = False

# C3: B-rep/vector outputs. STEP/BREP/SVG map to CadQuery export types; IGES delegates
# to the sealed adapter. Mesh formats (stl/obj/3mf/gltf/ply) are C4, NOT here.
_CQ_EXPORT_TYPES = {
    "step": "STEP",
    "brep": "BREP",
    "svg": "SVG",
}
_IGES = "iges"


def supported_brep_formats() -> list:
    """Return the B-rep/vector output format names this module can write (C3)."""
    return ["step", "brep", "svg", "iges"]


def export_brep(brep: BRep, out_path: str, fmt: str) -> None:
    """Serialize a BRep to a B-rep/vector file (C3; C7 errors).

    fmt in {"step","brep","svg"} goes through the CadQuery exporters; fmt == "iges"
    delegates to the sealed cad-iges adapter (C5). Any other fmt is refused with
    UnsupportedFormatError; an unreadable/unwritable output surfaces ConversionError.
    """
    if not isinstance(brep, BRep):
        raise TypeError(
            f"export_brep expects a cad.brep.BRep, got {type(brep).__name__} — "
            "wrap raw shapes with BRep.from_shape first"
        )
    if out_path is None or fmt is None:
        raise TypeError("export_brep requires an output path and a format")
    if not isinstance(out_path, (str, os.PathLike)):
        raise TypeError(f"export_brep expects a path, got {type(out_path).__name__}")
    if not isinstance(fmt, str):
        raise TypeError(f"export_brep expects a format string, got {type(fmt).__name__}")
    out_path = os.fspath(out_path)
    fmt = fmt.lower()

    if fmt == _IGES:
        # C3 -> C5: the sealed adapter is the ONLY owner of OCCT IGESControl (I1)
        iges_adapter.write_iges(brep, out_path)
        return

    if fmt not in _CQ_EXPORT_TYPES:
        raise UnsupportedFormatError(
            f"Unsupported B-rep export format '{fmt}'; "
            f"supported: {', '.join(supported_brep_formats())}"
        )

    if not _HAS_ENGINE:
        raise ImportError("cad.exporters needs cadquery/OCCT to export a BRep")

    export_type = _CQ_EXPORT_TYPES[fmt]
    try:
        # wrap the ONE BRep's OCCT shape in a CadQuery Shape (I1: no OCP held here)
        cq_shape = _CqShape(brep.shape)
        _cqexporters.export(cq_shape, out_path, export_type)
    except Exception as exc:  # noqa: BLE001 - surface any engine failure as typed
        raise ConversionError(
            f"B-rep export failed for {out_path} ({fmt}): "
            f"{exc.__class__.__name__}: {exc}"
        ) from exc

    # C7.3: the CadQuery exporters swallow an unreachable output path and return
    # silently, leaving no file behind — a failed write is still a failure, so
    # surface it as a typed ConversionError rather than pretending success.
    if not os.path.isfile(out_path) or os.path.getsize(out_path) == 0:
        raise ConversionError(
            f"B-rep export produced no readable file at {out_path} ({fmt})"
        )

