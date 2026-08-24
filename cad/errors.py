"""cad.errors — the C7 typed error hierarchy (CANONICAL copy, cad-registry 422.11).

DESIGN.md r1 §C7: every module surfaces failures through typed, named exceptions so
the C9 ``convert()`` facade (and the CLI/UI layer) can map them to user outcomes
without knowing file-format internals. This file is the authoritative C7 hierarchy;
the early modules that shipped during rollout (cad-iges 422.7, cad-import 422.3,
cad-export-brep 422.5, cad-mesh 422.9) each carried a temporary copy whose docstring
states these names reconcile 1:1 with this canonical file — the SAME hierarchy, the
SAME module path ``cad/errors.py``. No later module should fork another copy.

    CadError                  -- base of the whole hierarchy (C7.0)
    └── UnsupportedFormatError -- format is not one this converter handles (C7.1)
    └── ParseError             -- input file could not be parsed (C7.2)
    └── ConversionError        -- output could not be produced (C7.3)
"""
from __future__ import annotations

__all__ = [
    "CadError",
    "UnsupportedFormatError",
    "ParseError",
    "ConversionError",
]


class CadError(Exception):
    """Base class for every typed error raised by the CAD converter modules."""


class UnsupportedFormatError(CadError):
    """The requested format is not supported by the converter."""


class ParseError(CadError):
    """An input file could not be parsed (missing, corrupt, or unreadable)."""


class ConversionError(CadError):
    """A conversion/output step could not be completed."""
