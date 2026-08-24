"""cad.brep — the ONE core B-rep representation (contract C1).

Wraps an OCCT TopoDS_Shape in BRep. Every other module reads/writes the CAD
model ONLY through BRep (invariant I1); no other module holds an OCP Shape not
obtained from a BRep. Only plain vertex/face tuples leave BRep (via tessellate)
so the mesh path (C4) depends on plain values, not on OCP/CadQuery internals.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

# C1 signature is written against OCP's base shape type.
try:  # pragma: no cover - import guard keeps the module importable pre-install
    from OCP.TopoDS import TopoDS_Shape
    from cadquery.occ_impl.shapes import Shape as _CqShape
    _HAS_SHAPE = True
except Exception:  # noqa: BLE001 - tolerate the module being imported w/o engine
    TopoDS_Shape = object  # type: ignore[assignment,misc]
    _CqShape = None  # type: ignore[assignment]
    _HAS_SHAPE = False

Vert = Tuple[float, float, float]
Face = Tuple[int, int, int]
Tessellation = Tuple[List[Vert], List[Face]]


@dataclass(frozen=True)
class BRep:
    """Immutable wrapper around one OCCT TopoDS_Shape."""

    _shape: "TopoDS_Shape"

    @classmethod
    def from_shape(cls, shape: "TopoDS_Shape") -> "BRep":
        """Wrap an OCCT TopoDS_Shape in the core B-representation."""
        if shape is None:
            raise TypeError("BRep.from_shape requires a non-None OCCT shape")
        if not _HAS_SHAPE:
            raise ImportError(
                "cad.brep needs cadquery/OCCT to wrap a TopoDS_Shape"
            )
        if not isinstance(shape, TopoDS_Shape):
            raise TypeError(
                f"BRep.from_shape expects an OCP.TopoDS.TopoDS_Shape, "
                f"got {type(shape).__name__}"
            )
        return cls(_shape=shape)

    @property
    def shape(self) -> "TopoDS_Shape":
        """The wrapped OCCT TopoDS_Shape (I1: only brep.py touches it directly)."""
        return self._shape

    def tessellate(
        self, tolerance: float = 0.1
    ) -> Tessellation:
        """Return (vertices, triangle_faces) plain tuples — seam into C4 mesh path.

        vertices: list of (x, y, z) float triples (de-duplicated by OCCT).
        faces:    list of (i, j, k) int triples indexing into vertices.
        Only plain verts/faces tuples cross this boundary (C1).
        """
        if _CqShape is None:
            raise ImportError(
                "cad.brep needs cadquery/OCCT to tessellate a TopoDS_Shape"
            )
        cq_shape = _CqShape(self._shape)
        verts, faces = cq_shape.tessellate(tolerance)
        vertices: List[Vert] = [
            (float(p.x), float(p.y), float(p.z)) for p in verts
        ]
        triangle_faces: List[Face] = [
            (int(a), int(b), int(c)) for (a, b, c) in faces
        ]
        return vertices, triangle_faces
