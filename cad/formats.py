"""cad.formats — the ONE central registry + dispatch for ALL conversions (contract C6).

DESIGN.md r1 §C6 + invariant I2: every output converges through this single registry.
The CLI (C9) and the web shell (C8) both call ``convert()`` here and nothing else;
no other module in the package hands a BRep to an exporter directly at the top level.

    SUPPORTED_FORMATS: dict[str, Handler] where
        Handler = Callable[[BRep, str, dict], None]   # (brep, out_path, opts) -> writes file
    def get_handler(fmt: str) -> Handler               # raise UnsupportedFormatError if absent
    def convert(brep: BRep, fmt: str, out_path: str, **opts) -> None
        # dispatches by fmt to: export_brep (step/brep/svg), export_mesh (stl/obj/3mf/gltf/ply),
        #   iges_adapter.write_iges (iges)
    def available_formats() -> list[str]               # all output handlers' names

Format-specific options ride in the ``opts`` dict (Handler 3rd arg) — e.g. the mesh
path's ``tolerance``. Errors (C7): UnsupportedFormatError (unknown fmt), TypeError
(bad arguments), and the underlying ConversionError/ParseError propagate unwrapped
from the exporting module so the CLI/API map them to user outcomes.
"""
from __future__ import annotations

import os
from typing import Callable, Dict, List

from .brep import BRep  # cad-core edge, I1
from .errors import UnsupportedFormatError
from . import exporters, mesh, iges_adapter  # C3 / C4 / C5 output edges

# Handler = (brep, out_path, opts) -> writes file. Each wrapper adapts the format's
# canonical exporting module to the single registry signature; the module owns the
# actual file-writing (C3/C4/C5), this file only registers + dispatches (C6/I2).
Handler = Callable[[BRep, str, Dict], None]


def _brep_handler(fmt: str) -> Handler:
    """A C6 handler that routes a B-rep/vector fmt to cad.exporters (C3)."""

    def _write(brep: BRep, out_path: str, opts: dict) -> None:
        exporters.export_brep(brep, out_path, fmt)

    return _write


def _mesh_handler(fmt: str) -> Handler:
    """A C6 handler that routes a mesh fmt to cad.mesh (C4), honoring its opts."""

    def _write(brep: BRep, out_path: str, opts: dict) -> None:
        mesh.export_mesh(brep, out_path, fmt, tolerance=opts.get("tolerance", 0.1))

    return _write


def _iges_handler(brep: BRep, out_path: str, opts: dict) -> None:
    """A C6 handler for IGES via the sealed cad-iges adapter (C5)."""
    iges_adapter.write_iges(brep, out_path)


# C6 registry: B-rep/vector (C3) + mesh (C4) + IGES (C5). Build order here is the
# design narrative — B-rep/vector, then IGES, then the five mesh formats. Every key
# here is an output the registry can write, so SUPPORTED_FORMATS == available_formats().
SUPPORTED_FORMATS: Dict[str, Handler] = {
    "step": _brep_handler("step"),
    "brep": _brep_handler("brep"),
    "svg": _brep_handler("svg"),
    "iges": _iges_handler,
    "stl": _mesh_handler("stl"),
    "obj": _mesh_handler("obj"),
    "3mf": _mesh_handler("3mf"),
    "gltf": _mesh_handler("gltf"),
    "ply": _mesh_handler("ply"),
}


def get_handler(fmt: str) -> Handler:
    """Return the registered handler for ``fmt`` (case-insensitive; C6).

    Raises UnsupportedFormatError (C7.1) when no handler is registered for the
    format, and TypeError for a non-string argument.
    """
    if not isinstance(fmt, str):
        raise TypeError(
            f"get_handler expects a format string, got {type(fmt).__name__}"
        )
    handler = SUPPORTED_FORMATS.get(fmt.lower())
    if handler is None:
        raise UnsupportedFormatError(
            f"Unsupported output format '{fmt}'; "
            f"supported: {', '.join(available_formats())}"
        )
    return handler


def convert(brep: BRep, fmt: str, out_path: str, **opts) -> None:
    """Convert one clamped BRep to ``fmt`` at ``out_path`` (C6; C7 errors).

    This is the SINGLE dispatch point (invariant I2): it looks up the handler for
    ``fmt`` and calls it with the ``(brep, out_path, opts)`` tuple the Handler type
    declares. ``**opts`` is packed into the dict the handler receives, letting
    format-specific knobs (e.g. the mesh ``tolerance``) flow through unchanged.
    """
    handler = get_handler(fmt)

    if not isinstance(brep, BRep):
        raise TypeError(
            f"convert expects a cad.brep.BRep, got {type(brep).__name__} — "
            "wrap raw shapes with BRep.from_shape first"
        )
    if out_path is None:
        raise TypeError("convert requires an output path")
    if not isinstance(out_path, (str, os.PathLike)):
        raise TypeError(
            f"convert expects a path, got {type(out_path).__name__}"
        )

    handler(brep, os.fspath(out_path), dict(opts))


def available_formats() -> List[str]:
    """Return the names of every registered output handler (C6).

    The list is a fresh copy in SUPPORTED_FORMATS' registration order, so mutating
    the return value cannot disturb the registry.
    """
    return list(SUPPORTED_FORMATS)
