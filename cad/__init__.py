"""cad — the CAD-file converter package (svarkor-ai/Cad).

Module seed (MC 422.1, cad-core): exposes the ONE core B-rep representation.
MC 422.7 (cad-iges): adds the IGES import/export adapter (C5) and the C7
typed-error hierarchy.
MC 422.3 (cad-import): adds the unified input path (C2, cad/importers.py).
MC 422.5 (cad-export-brep): adds the B-rep/vector output path (C3, cad/exporters.py).
MC 422.9 (cad-mesh): adds the mesh output path (C4, cad/mesh.py).
MC 422.11 (cad-registry): adds the ONE central dispatch point (C6, cad/formats.py)
and the CANONICAL C7 typed errors (cad/errors.py).

The public face is ``convert(brep, fmt, out_path, **opts)`` — both the CLI (C9) and
the web shell (C8) call THIS function and nothing else (invariant I2).
"""
from cad.brep import BRep, Vert, Face, Tessellation
from cad.errors import CadError, UnsupportedFormatError, ParseError, ConversionError
from cad.iges_adapter import read_iges, write_iges
from cad.importers import load, supported_inputs
from cad.formats import convert, get_handler, available_formats

__all__ = [
    "BRep", "Vert", "Face", "Tessellation",
    "CadError", "UnsupportedFormatError", "ParseError", "ConversionError",
    "read_iges", "write_iges",
    "load", "supported_inputs",
    "convert", "get_handler", "available_formats",
]
__version__ = "0.1.0"
