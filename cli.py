"""cli — the C9 CLI shell over the cad registry (MC 422.13, cad-cli).

DESIGN.md r1 §C9:
    usage: cadconv [-v] <input> --to <fmt> [-o <out>] [--tolerance <t>] [--list-formats]
    exit codes: 0 success; 2 usage/unsupported format; 3 parse error; 4 conversion error.
    Invariant: cli calls formats.convert(C6) only — identical pipeline to web, no HTTP.
    No conversion logic here beyond argparse + status-mapping from C7.

This module is a THIN shell. It does not contain any format/geometry logic — it
parses args, delegates to cad.importers.load / cad.formats.convert (invariant
I2/ISO), and maps cad.errors to process exit codes (C9). ``main(argv)`` returns
the exit code so it is testable directly; the ``__main__`` block forwards it to
sys.exit for real process semantics (exit 0..4).

C7 -> exit-code mapping (C9):
    UnsupportedFormatError -> 2
    ParseError            -> 3
    ConversionError       -> 4
    CadError (fallback)   -> 4
"""
from __future__ import annotations

import argparse
import os
import sys

from cad.errors import CadError, ConversionError, ParseError, UnsupportedFormatError
from cad.formats import convert, available_formats
from cad.importers import load, supported_inputs

_PROG = "cadconv"

# C9: C7 -> process exit codes.
_C7_EXIT = {
    UnsupportedFormatError: 2,  # usage/unsupported format
    ParseError: 3,              # parse error
    ConversionError: 4,         # conversion error
}


def _build_parser() -> argparse.ArgumentParser:
    """Argparse surface only — no conversion logic (invariant C9/ISO)."""
    p = argparse.ArgumentParser(
        prog=_PROG,
        description="Convert CAD files (STEP/BREP/IGES) between formats."
        " Thin shell over the cad registry (DESIGN.md r1 §C9).",
    )
    p.add_argument("-v", "--verbose", action="store_true", help="print a summary line on success")
    p.add_argument("input", nargs="?", type=str, help="source CAD file (step/iges/brep)")
    p.add_argument("--to", dest="output_format", type=str, help="output format/fmt")
    p.add_argument("-o", "--out", dest="output_path", type=str, help="output path (default: input basename + new ext in CWD)")
    p.add_argument("--tolerance", dest="tolerance", type=str, help="for mesh formats only; finer when smaller")
    p.add_argument("--list-formats", action="store_true", dest="list_formats", help="list supported formats and exit")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.list_formats:
        _print_formats()
        return 0

    # usage guards: both input path and --to are required for a convert.
    if args.input is None or args.output_format is None:
        parser.print_usage(sys.stderr)
        return 2

    tolerance = None
    if args.tolerance is not None:
        try:
            tolerance = float(args.tolerance)
        except ValueError:
            parser.error(f"--tolerance must be a number, got '{args.tolerance}'")

    out_path = args.output_path or _default_output(args.input, args.output_format)

    try:
        brep = load(args.input)          # ParseError -> 3, Unsupported -> 2
        opts = {}
        if tolerance is not None:
            opts["tolerance"] = tolerance
        convert(brep, args.output_format, out_path, **opts)  # Unsupported->2, Conversion->4
    except CadError as exc:
        rc = _C7_EXIT.get(type(exc), 4)
        print(f"{_PROG}: {exc}", file=sys.stderr)
        return rc

    if args.verbose:
        print(f"wrote {out_path}")
    return 0


def _default_output(input_path: str, out_fmt: str) -> str:
    """Derive the output path from the input basename + new extension (C9)."""
    base = os.path.basename(input_path)
    stem = os.path.splitext(base)[0]
    return f"{stem}.{out_fmt}"


def _print_formats() -> None:
    print("inputs:  " + ", ".join(supported_inputs()))
    print("outputs: " + ", ".join(available_formats()))


if __name__ == "__main__":
    sys.exit(main())
