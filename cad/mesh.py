"""cad.mesh — the mesh output path (contract C4, cad-mesh).

DESIGN.md r1 §C4: the mesh path takes the ONE core BRep, tessellates it through
cad-core (C1), and writes any of the 5 mesh formats via trimesh. This module is THE
only place trimesh is used anywhere in the converter (invariant C4); every mesh
format (stl, obj, 3mf, gltf, ply) shares this single path. No mesh code lives in
cad/exporters.py (C3), which is the B-rep/vector path.

    def to_trimesh(brep: BRep, tolerance: float = 0.1) -> "trimesh.Trimesh"
        # calls brep.tessellate(tolerance) -> trimesh.Trimesh(vertices=..., faces=...)
    def export_mesh(brep: BRep, out_path: str, fmt: str, tolerance: float = 0.1) -> None
        # fmt in {stl,obj,3mf,gltf,ply}; delegates to trimesh.export(mesh, file_obj, file_type=fmt)
    def supported_mesh_formats() -> list[str]    # ['stl','obj','3mf','gltf','ply']
    Data crossing: BRep.tessellate tuples -> trimesh.Trimesh -> file.

Errors (C7): UnsupportedFormatError (unknown format), ConversionError (write failed
or produced no file), TypeError (bad arguments). Only plain vertex/face tuples cross
from cad-core; no OCP/CadQuery internals are held here (I1).
"""
from __future__ import annotations

import os

from .brep import BRep  # cad-core edge, I1
from .errors import ConversionError, UnsupportedFormatError

try:  # pragma: no cover - import guard keeps the module importable pre-install
    import trimesh
    from trimesh.exchange.export import export_mesh as _trimesh_export
    _HAS_TRIMESH = True
except Exception:  # noqa: BLE001 - tolerate the module being imported w/o trimesh
    trimesh = None  # type: ignore[assignment]
    _trimesh_export = None  # type: ignore[assignment]
    _HAS_TRIMESH = False

# C4: the five mesh formats register here. All of them funnel through trimesh, so a
# format is "supported" iff trimesh can write it via this one path (R3: v1 simple).
_MESH_FORMATS = ["stl", "obj", "3mf", "gltf", "ply"]


def supported_mesh_formats() -> list:
    """Return the mesh output format names this module can write (C4)."""
    return list(_MESH_FORMATS)


def to_trimesh(brep: BRep, tolerance: float = 0.1) -> "trimesh.Trimesh":
    """Tessellate a BRep into a trimesh.Trimesh (C4; C7 errors).

    Calls brep.tessellate(tolerance) (cad-core C1) to get plain vertex/face tuples,
    then wraps them in a trimesh.Trimesh. The caller must hold a concrete
    cad.brep.BRep, never a raw OCP shape.
    """
    if not isinstance(brep, BRep):
        raise TypeError(
            f"to_trimesh expects a cad.brep.BRep, got {type(brep).__name__} — "
            "wrap raw shapes with BRep.from_shape first"
        )
    if not _HAS_TRIMESH:
        raise ImportError("cad.mesh needs trimesh to build a Trimesh mesh")

    vertices, faces = brep.tessellate(tolerance)  # plain tuples cross cad-core (C1)
    return trimesh.Trimesh(vertices=vertices, faces=faces)


def export_mesh(
    brep: BRep, out_path: str, fmt: str, tolerance: float = 0.1
) -> None:
    """Serialize a BRep to a mesh file via trimesh (C4; C7 errors).

    fmt in {stl,obj,3mf,gltf,ply}. Delegates to trimesh.export(mesh, file_obj,
    file_type=fmt) — the single mesh-writing path (invariant C4). Any other fmt is
    refused with UnsupportedFormatError; an unreachable/unwritten output surfaces
    ConversionError (trimesh can swallow a failed write and leave no file behind).
    """
    if not isinstance(brep, BRep):
        raise TypeError(
            f"export_mesh expects a cad.brep.BRep, got {type(brep).__name__} — "
            "wrap raw shapes with BRep.from_shape first"
        )
    if out_path is None or fmt is None:
        raise TypeError("export_mesh requires an output path and a format")
    if not isinstance(out_path, (str, os.PathLike)):
        raise TypeError(f"export_mesh expects a path, got {type(out_path).__name__}")
    if not isinstance(fmt, str):
        raise TypeError(f"export_mesh expects a format string, got {type(fmt).__name__}")
    out_path = os.fspath(out_path)
    fmt = fmt.lower()

    if fmt not in _MESH_FORMATS:
        raise UnsupportedFormatError(
            f"Unsupported mesh export format '{fmt}'; "
            f"supported: {', '.join(supported_mesh_formats())}"
        )

    if not _HAS_TRIMESH:
        raise ImportError("cad.mesh needs trimesh to export a mesh")

    mesh = to_trimesh(brep, tolerance=tolerance)
    try:
        # The single mesh-writing path (C4 invariant) — trimesh.exchange.export
        # with an explicit file_type, shared by all 5 formats.
        _trimesh_export(mesh, out_path, file_type=fmt)
    except Exception as exc:  # noqa: BLE001 - surface any engine failure as typed
        raise ConversionError(
            f"Mesh export failed for {out_path} ({fmt}): "
            f"{exc.__class__.__name__}: {exc}"
        ) from exc

    # C7.3: trimesh can raise without writing, or write nothing — a failed write is
    # still a failure, so surface it as a typed ConversionError rather than pretending
    # success (mirrors cad/exporters.py C3 post-write guard, I1).
    if not os.path.isfile(out_path) or os.path.getsize(out_path) == 0:
        raise ConversionError(
            f"Mesh export produced no readable file at {out_path} ({fmt})"
        )
