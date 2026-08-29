"""server.api — the C8 web shell: FastAPI routes over the cad registry.

Endpoints (DESIGN.md r1 §C8):
    GET  /formats   -> {inputs: [...], outputs: [...]} from cad's registry
    POST /convert   -> multipart upload (file, format, tolerance?) -> file bytes
    GET  /          -> minimal HTML landing page

Security (sigrid 422.21 / 422.22):
  - the multipart filename is attacker-controlled and MUST be gated against
    traversal/abs/NUL (422.21 LOW) as below.
  - /convert has NO auth and NO unbounded upload (422.22 two HIGH: multipart DoS +
    fully-open endpoint). Two gating measures are added here, run BEFORE the flow:
        . size cap    -> HTTP 413 when a request/upload exceeds the cap
        . rate limit  -> HTTP 429 per client identity (in-memory, sliding window)
    These close the body-bomb + unbounded-parser class while keeping the local-tool
    scope (auth deliberately not added).

C7 -> HTTP mapping:
    UnsupportedFormatError -> 415 Unsupported Media Type
    ParseError             -> 400 Bad Request (input could not be read/parsed)
    ConversionError        -> 500 Internal Server Error (output failed to write)
    CadError (fallback)    -> 500 Internal Server Error
Invalid request shape (missing file/format, malformed form) -> 422 (FastAPI).
CAP/mapping note (422.22 addendum): a request/upload exceeding the byte cap is a
413-at-the-boundary (content too large), which is distinct from FastAPI's own 422
(validation: missing/invalid fields) — the 413 fires first (before parsing) so the
over-cap control status and the request-shape control status never collide.
"""
from __future__ import annotations

import mimetypes
import os
import tempfile
import time
from collections import defaultdict

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response

from cad import CadError, ConversionError, ParseError, UnsupportedFormatError
from cad import convert as _convert
from cad import load as _load
from cad import available_formats, resolve_input_format, supported_inputs

app = FastAPI(title="cad-api", version="0.1.0", description=__doc__)

# --------------------------------------------------------------------------
# Security config (422.22 hardening): request/upload cap + per-client rate limit.
# Sigrid HIGH-2 (fully-open /convert): a bounded upload + per-client throttle turns
# the unbounded unauthenticated endpoint into a capped local tool. Local-tool scope:
# auth is deliberately NOT added (sigrid ruling).
# --------------------------------------------------------------------------
MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MiB body/upload cap before parsing.
RATE_MAX_REQUESTS = 20               # max /convert hits per client per window.
RATE_WINDOW_SECONDS = 60             # sliding window length (seconds).


class _SlidingWindowRateLimiter:
    """Minimal in-memory per-key sliding-window limiter (no external state).

    Keeps a monotonically-clocked hit list per key; drops entries older than the
    window, then admits or rejects. Safe for a single-process local tool; a
    multi-process/replica deployment would need a shared store (out of scope).
    """

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str, *, now: float | None = None) -> tuple[bool, float | None]:
        """Return (allowed, retry_after) — retry_after is seconds until a slot frees."""
        t = now if now is not None else time.monotonic()
        window_start = t - self.window_seconds
        bucket = [hit for hit in self._hits[key] if hit > window_start]
        if len(bucket) >= self.max_requests:
            retry_after = max(0.0, bucket[0] + self.window_seconds - t)
            return False, retry_after
        bucket.append(t)
        self._hits[key] = bucket
        return True, None

    def clear(self) -> None:
        self._hits.clear()


_rate_limiter = _SlidingWindowRateLimiter(RATE_MAX_REQUESTS, RATE_WINDOW_SECONDS)


def _client_key(request: Request) -> str:
    """Best-effort per-client identity for the rate limiter (remote IP)."""
    return request.client.host if request.client is not None else "unknown"


def _enforce_security_gates(request: Request) -> None:
    """Run BEFORE the endpoint body is parsed.

    1) Size cap: an over-cap request (Content-Length) is rejected with 413 up front,
       before starlette's multipart parser ever consumes the attacker-controlled body
       (closes the 422.22 multipart-parse DoS surface at the boundary).
    2) Rate limit: per-client 429 once the sliding window is exhausted, with
       Retry-After so polite clients can back off.
    """
    length = request.headers.get("content-length")
    if length is not None:
        try:
            if int(length) > MAX_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=413, detail=f"request/upload exceeds {MAX_UPLOAD_BYTES} byte cap"
                )
        except ValueError:
            pass  # malformed content-length is not our gate; body parse will 400/422

    allowed, retry_after = _rate_limiter.check(_client_key(request))
    if not allowed:
        headers = {}
        if retry_after is not None:
            headers["Retry-After"] = str(max(1, int(retry_after)))
        raise HTTPException(status_code=429, detail="too many /convert requests", headers=headers)

# --------------------------------------------------------------------------
# C7 -> HTTP error mapping (implemented once, applied to every CadError raised
# anywhere in a handler, so the mapping can never drift between endpoints).
# --------------------------------------------------------------------------
_cad_error_status = {
    UnsupportedFormatError: 415,  # unknown in/out format
    ParseError: 400,              # input missing / unreadable / corrupt (C7.2)
    ConversionError: 500,         # output write failure
}


@app.exception_handler(CadError)
async def _cad_error_handler(request, exc: CadError) -> JSONResponse:
    status = _cad_error_status.get(type(exc), 500)
    reason = getattr(exc, "message", None) or str(exc)
    return JSONResponse(status_code=status, content={"error": type(exc).__name__, "detail": reason})


# --------------------------------------------------------------------------
# Upload-boundary filename safety gate (sigrid 422.21 LOW).
# --------------------------------------------------------------------------
def _validate_upload_name(name: str | None) -> str:
    """Return a bare, safe basename or 400 for a hostile multipart filename.

    Rejects NUL bytes, path separators, absolute paths, and ".." traversal so an
    attacker-controlled filename can never steer load/convert outside the tmpdir.
    """
    if not name:
        raise HTTPException(status_code=400, detail="uploaded file has no filename")
    if "\x00" in name:
        raise HTTPException(status_code=400, detail="filename contains a NUL byte")
    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(status_code=400, detail="filename must be a bare basename")
    return name


_EXTENSION_CONTENT_TYPE = {
    ".step": "model/step",
    ".stp": "model/step",
    ".brep": "application/octet-stream",
    ".iges": "model/iges",
    ".igs": "model/iges",
    ".stl": "model/stl",
    ".obj": "model/obj",
    ".3mf": "model/3mf",
    ".gltf": "model/gltf",
    ".ply": "application/octet-stream",
    ".svg": "image/svg+xml",
}


def _content_type_for(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return _EXTENSION_CONTENT_TYPE.get(ext) or mimetypes.guess_type(path)[0] or "application/octet-stream"


# --------------------------------------------------------------------------
# GET /formats — the registry shape (inputs + outputs) for the UI/CLI.
# --------------------------------------------------------------------------
@app.get("/formats")
def list_formats():
    return {"inputs": supported_inputs(), "outputs": available_formats()}


# --------------------------------------------------------------------------
# GET / — minimal HTML landing (the full drag-drop UI is the separate cad-web
# frontend module, C8b/server.web.py; this shell just points to the API).
# --------------------------------------------------------------------------
# GET / serves the cad-web drag-drop UI (server/web.py, C8b). The single-line
# integration: web.render_index() owns the root; this shell kept /formats and
# /convert. The hardcoded _INDEX_HTML fallback below is used only if web is absent.
try:
    from . import web as _web  # noqa: E402
    _INDEX_HTML = _web.INDEX_HTML
except Exception:  # pragma: no cover - web.py optional in minimal installs
    _INDEX_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>cad-api</title></head>
<body><h1>cad-api</h1>
<p>Convert CAD files (STEP/BREP/IGES) to STEP, BREP, SVG, IGES, STL, OBJ, 3MF, GLTF, PLY.</p>
<p><a href="/formats">GET /formats</a></p>
<pre>POST /convert   multipart: file, format (output), tolerance (optional)</pre>
</body></html>"""


@app.get("/")
def root():
    return Response(content=_INDEX_HTML, media_type="text/html")


# --------------------------------------------------------------------------
# POST /convert — the single conversion endpoint (C8).
# --------------------------------------------------------------------------
@app.post("/convert", dependencies=[Depends(_enforce_security_gates)])
async def convert(
    file: UploadFile = File(...),
    format: str = Form(...),  # noqa: A002 - shadows builtin `format`; matches the API contract
    tolerance: str | None = Form(None),
):
    # 1) The multipart filename is attacker-controlled. Gate it BEFORE it can
    #    reach load/convert (sigrid 422.21 LOW: traversal / abs / NUL).
    safe_name = _validate_upload_name(file.filename)

    # 2) Resolve the input format from the safe basename's extension early so an
    #    unsupported source format is a clean 415, not a mid-pipeline surprise.
    #    The SAME resolver load() uses, so `.stp`/`.igs` (which the UI's file picker
    #    accepts) reach the step/iges readers instead of a 415 for a spelling.
    src_fmt = resolve_input_format(safe_name)
    if src_fmt not in supported_inputs():
        raise UnsupportedFormatError(
            f"Unsupported input format '{src_fmt}'; supported: {', '.join(supported_inputs())}"
        )

    # 3) Float-validate tolerance (optional, mesh formats only).
    tol = None
    if tolerance is not None:
        try:
            tol = float(tolerance)
        except ValueError:
            raise HTTPException(status_code=422, detail="tolerance must be a number")

    # 4) Temp-plumb: load()/convert() operate on real filesystem paths, so write
    #    the upload to a private temp file (safe basename keeps the extension).
    #    Defense-in-depth: even without a Content-Length (chunked transfer), stream
    #    the upload and hard-stop at MAX_UPLOAD_BYTES with a 413.
    with tempfile.TemporaryDirectory(prefix="cad-api-") as tmpdir:
        in_path = os.path.join(tmpdir, safe_name)
        written = 0
        with open(in_path, "wb") as fh:
            while chunk := await file.read(1024 * 1024):
                written += len(chunk)
                if written > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413, detail=f"upload exceeds {MAX_UPLOAD_BYTES} byte cap"
                    )
                fh.write(chunk)

        brep = _load(in_path)  # ParseError -> 400, UnsupportedFormatError -> 415

        out_name = os.path.splitext(safe_name)[0] + "." + format
        out_path = os.path.join(tmpdir, out_name)
        opts = {}
        if tol is not None:
            opts["tolerance"] = tol
        _convert(brep, format, out_path, **opts)  # Unsupported -> 415, Conversion -> 500

        with open(out_path, "rb") as fh:
            body = fh.read()

    # Emit a log-safe basename (no traversal possible: it is built from safe_name
    # which already passed the gate).
    disposition = f'attachment; filename="{out_name}"'
    return Response(
        content=body,
        media_type=_content_type_for(out_name),
        headers={"Content-Disposition": disposition},
    )
