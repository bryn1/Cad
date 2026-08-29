"""cad.importers — the unified CAD input path (contract C2, cad-import).

DESIGN.md r1 §C2: ``load()`` turns any supported input file (STEP, IGES, BREP)
into the ONE core BRep (cad.brep.BRep, I1). It resolves the format from the file
extension when not given, then dispatches to the reader registered for that format.

    def load(path, fmt=None) -> BRep          # fmt from extension when None
    def supported_inputs() -> list[str]       # ['step','iges','brep']
    def resolve_input_format(name) -> str     # '.stp'->'step', '.igs'->'iges' (spellings)

Reader dispatch (internal register ``_READERS: dict[fmt, Callable[[str], BRep]]``):
    step/brep -> CadQuery importers.importShape (wrapped into a BRep)
    iges      -> the sealed cad-iges adapter (C5), the ONLY module that may touch
                 OCCT IGESControl (I1)

Data crossing boundary: file bytes -> BRep (nothing else leaves here).

Errors (C7): UnsupportedFormatError (unknown format), ParseError (input file
missing / corrupt / unreadable), ImportError (engine unavailable), TypeError
(bad arguments). I1/C2 exception: this module (like the exporters it mirrors) is
one of the few that may call the CadQuery importers to build a BRep from a file.
"""
from __future__ import annotations

import os
from typing import Callable, Dict

from .brep import BRep  # cad-core edge, I1
from .errors import UnsupportedFormatError, ParseError
from . import iges_adapter  # C5 edge — the ONLY module that may touch OCCT IGESControl

try:  # pragma: no cover - import guard keeps the module importable pre-install
    from cadquery import importers as _cqimporters
    from cadquery.occ_impl.shapes import Shape as _CqShape
    _HAS_ENGINE = True
except Exception:  # noqa: BLE001 - tolerate the module being imported w/o engine
    _cqimporters = None  # type: ignore[assignment]
    _CqShape = None  # type: ignore[assignment]
    _HAS_ENGINE = False


def _read_step_brep(fmt: str, path: str) -> BRep:
    """Read a STEP or BREP file via CadQuery into a BRep (C2)."""
    if not _HAS_ENGINE:
        raise ImportError("cad.importers needs cadquery/OCCT to read a STEP/BREP file")
    # CadQuery importers.importShape maps the fmt string straight onto its own enum.
    try:
        workplane = _cqimporters.importShape(fmt, path)
        shape = workplane.val().wrapped  # TopoDS_Shape from the loaded model
    except Exception as exc:  # noqa: BLE001 - any engine/load failure is a parse error
        raise ParseError(
            f"Could not parse {path} as {fmt}: {exc.__class__.__name__}: {exc}"
        ) from exc
    return BRep.from_shape(shape)


# C2: the internal format -> reader register. Dispatch is by this exact key, and
# supported_inputs() mirrors the canonical order from DESIGN.md r1 (step, iges,
# brep), so register and supported_inputs can never disagree on what is supported.
_READERS: Dict[str, Callable[[str], BRep]] = {
    "step": lambda p: _read_step_brep("STEP", p),
    "iges": lambda p: iges_adapter.read_iges(p),
    "brep": lambda p: _read_step_brep("BREP", p),
}


def supported_inputs() -> list:
    """Return the input format names this module can read (C2: step, iges, brep)."""
    return list(_READERS)


# Common file-extension SPELLINGS of a supported input format. The web UI's file picker
# advertises `.stp` and `.igs` (server/web.py `accept=`), and CAD tools write them at least
# as often as the long forms -- so they must resolve to the reader they name, not 415.
# Keys are registry names in _READERS; these are spellings, not new formats, so
# supported_inputs() stays exactly the registry.
INPUT_ALIASES: Dict[str, str] = {
    "stp": "step",
    "igs": "iges",
}


def resolve_input_format(name_or_ext: str) -> str:
    """Return the registry input format for a filename, extension or format string.

    ``"box.stp"`` / ``".STP"`` / ``"stp"`` -> ``"step"``; ``"model.igs"`` -> ``"iges"``;
    a registry name passes through lower-cased. Unknown spellings are returned as-is
    (lower-cased) so the caller's own UnsupportedFormatError names what it saw.
    """
    if not isinstance(name_or_ext, str):
        raise TypeError(f"resolve_input_format expects a string, got {type(name_or_ext).__name__}")
    s = name_or_ext
    if "." in s:
        tail = os.path.splitext(s)[1]   # '.stp' for 'box.stp'; '' for a bare '.stp'
        s = tail or s
    s = s.lstrip(".").lower()
    return INPUT_ALIASES.get(s, s)


def load(path: str, fmt: str | None = None) -> BRep:
    """Load a CAD file into the core BRep (C2; C7 errors).

    fmt is taken verbatim when given (case-insensitive); otherwise it is resolved
    from the file's extension. An unsupported format raises UnsupportedFormatError;
    a missing/unreadable/corrupt input surfaces ParseError.
    """
    if path is None:
        raise TypeError("load requires a path string")
    if not isinstance(path, (str, os.PathLike)):
        raise TypeError(f"load expects a path, got {type(path).__name__}")
    if fmt is not None and not isinstance(fmt, str):
        raise TypeError(f"load expects a format string, got {type(fmt).__name__}")
    path = os.fspath(path)

    if fmt is None:
        # resolve the format from the extension (.step /.STEP / .stp / .iges / .igs ...)
        fmt = resolve_input_format(os.path.splitext(path)[1])
    fmt = resolve_input_format(fmt)

    if fmt not in _READERS:
        raise UnsupportedFormatError(
            f"Unsupported input format '{fmt}'; "
            f"supported: {', '.join(supported_inputs())}"
        )

    if not os.path.isfile(path):
        raise ParseError(f"Input file not found: {path}")

    return _READERS[fmt](path)
