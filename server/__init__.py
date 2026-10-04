"""server — the C8 web shell package (bryn1/Cad, cad-api).

DESIGN.md r1: the FastAPI HTTP surface wraps the cad library. It owns routing,
multipart decoding, the upload-boundary filename-safety gate (sigrid 422.21 LOW:
reject path traversal / absolute paths / null bytes before a caller-controlled
filename reaches load/convert), and C7->HTTP status mapping. Per invariant
C8/I2 it holds NO conversion logic — every conversion is delegated verbatim to
``cad.formats.convert`` and every file read to ``cad.importers.load``.
"""
