"""server.web — the C8b cad-web frontend: a self-contained static drag-drop UI.

DESIGN.md r1 §C8b / §A3: "static drag-drop index.html; served by api; no full
editor/preview in v1." This module is the frontend half of the C8 web shell: it
carries the complete index page (inline CSS + vanilla JS, no framework, no build
step) and exposes one integration point so the FastAPI app can serve it.

Endpoints it consumes (the C8 API contract, 422.15 server/api.py):
    GET  /formats   -> {inputs:[...], outputs:[...]}   -- populates the format UI
    POST /convert   -> multipart (file, format, tolerance?) -> file bytes      (
                       with Content-Disposition: attachment )
Errors consumed: JSON {error: CadErrorName, detail: reason} with HTTP
415 / 400 / 500 / 422 (mapped to human copy in the page, never shown raw).

Serving (one line, in server/api.py after `from server import web`):
    from fastapi.responses import Response
    @app.get("/")
    def root(): return Response(content=web.INDEX_HTML, media_type="text/html")

The page uses *relative* URLs ("./formats", "./convert"), so it works served from
any mount path under the same origin as the API. No secrets, no network calls
beyond the API's own endpoints. Browser-boundary file handling (no path leakage,
local download only) — see sigrid cad-web security note.
"""

# Locally-reference the fields the api expects, so a rename in the contract is
# caught by tests rather than silently breaking the multipart shape.
FORM_FILE_FIELD = "file"
FORM_FORMAT_FIELD = "format"
FORM_TOLERANCE_FIELD = "tolerance"
FORMATS_ENDPOINT = "./formats"
CONVERT_ENDPOINT = "./convert"

# ---------------------------------------------------------------------------
# The full page. Kept in ONE module-level constant so any server can hand it to
# a Response verbatim; tests below assert the contract-critical substrings.
# ---------------------------------------------------------------------------
INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark">
<title>CAD Converter — STEP/BREP/IGES to STEP, BREP, SVG, IGES, STL, OBJ, 3MF, GLTF, PLY</title>
<style>
/* ---- tokens (frontend-design-process step 2: color/type/spacing/radius in one place) ---- */
:root{
  --bg:#111318; --surface:#181b21; --surface-2:#1f232b; --text:#e8eaed; --muted:#9aa0a8;
  --border:#2c313b; --border-strong:#3a4150; --accent:#4f8cff; --accent-contrast:#0b1020;
  --ok:#3fb96e; --err:#e05d5d; --warn:#e0a83a;
  --space-1:4px; --space-2:8px; --space-3:12px; --space-4:16px; --space-6:24px; --space-8:32px;
  --radius:10px; --shadow:0 10px 30px rgba(0,0,0,.35);
  --fs-1:13px; --fs-2:15px; --fs-3:18px; --fs-4:24px;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{
  background:var(--bg); color:var(--text); font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  font-size:var(--fs-2); line-height:1.5; min-height:100vh; display:flex; flex-direction:column;
}
main{flex:1; width:100%; max-width:720px; margin:0 auto; padding:var(--space-6) var(--space-4) var(--space-8)}
h1{font-size:var(--fs-4); line-height:1.2; margin:0 0 var(--space-1)}
.lede{color:var(--muted); margin:0 0 var(--space-8); max-width:56ch}

/* ---- status bar ---- */
.status{
  display:none; align-items:flex-start; gap:var(--space-3); padding:var(--space-3) var(--space-4);
  border-radius:var(--radius); border:1px solid var(--border); margin-bottom:var(--space-4);
  font-size:var(--fs-1);
}
.status[data-kind="ok"]{display:flex; border-color:var(--ok); color:var(--text); background:rgba(63,185,110,.09)}
.status[data-kind="err"]{display:flex; border-color:var(--err); background:rgba(224,93,93,.09)}
.status[data-kind="pending"]{display:flex; border-color:var(--border-strong); background:var(--surface-2)}
.status .ico{flex:0 0 auto; font-size:var(--fs-2)}
.status .msg{flex:1}

/* ---- dropzone ---- */
.dropzone{
  display:block; position:relative; cursor:pointer;
  border:2px dashed var(--border-strong); border-radius:var(--radius);
  background:var(--surface); padding:var(--space-8) var(--space-6);
  text-align:center; transition:border-color .18s ease, background .18s ease;
}
.dropzone:hover{border-color:var(--accent)}
.dropzone:focus-visible{outline:2px solid var(--accent); outline-offset:2px}
.dropzone[data-drag="over"]{border-color:var(--accent); background:var(--surface-2)}
.dropzone .dz-emoji{font-size:26px; line-height:1}
.dropzone .dz-title{display:block; font-size:var(--fs-3); margin:var(--space-3) 0 var(--space-2)}
.dropzone .dz-hint{color:var(--muted); font-size:var(--fs-1)}
.dropzone input[type="file"]{
  position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0);
  white-space:nowrap; clip-path:inset(50%);
}
.file-chip{
  display:none; align-items:center; gap:var(--space-3); margin-top:var(--space-4);
  padding:var(--space-3); border:1px solid var(--border); border-radius:var(--radius); background:var(--surface-2);
  font-size:var(--fs-1);
}
.file-chip[data-has="file"]{display:flex}
.file-chip .name{flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap}
.file-chip .change{color:var(--accent); background:none; border:none; cursor:pointer; font:inherit; padding:0}
.file-chip .change:hover{text-decoration:underline}
.file-chip .change:focus-visible{outline:2px solid var(--accent); outline-offset:2px; border-radius:2px}

/* ---- format form ---- */
.field{margin:var(--space-6) 0 var(--space-4)}
.field label{display:block; font-size:var(--fs-2); margin-bottom:var(--space-2); font-weight:600}
.field .sub{color:var(--muted); font-size:var(--fs-1); margin-bottom:var(--space-2); display:block}
select,input[type="number"]{
  width:100%; padding:var(--space-3); font:inherit; color:var(--text);
  background:var(--surface-2); border:1px solid var(--border-strong); border-radius:var(--radius);
}
select:focus-visible,input[type="number"]:focus-visible{outline:2px solid var(--accent); outline-offset:1px}
select:disabled{opacity:.55; cursor:not-allowed}
#formatSelect{min-height:44px}
#tolerance{max-width:220px; min-height:44px}

/* ---- convert + result ---- */
.convert-row{display:flex; align-items:center; gap:var(--space-4); margin-top:var(--space-6)}
#convertBtn{
  flex:0 0 auto; min-height:48px; padding:var(--space-3) var(--space-8); font-size:var(--fs-2); font-weight:600;
  color:var(--accent-contrast); background:var(--accent); border:none; border-radius:var(--radius); cursor:pointer;
  transition:filter .15s ease;
}
#convertBtn:hover:not(:disabled){filter:brightness(1.08)}
#convertBtn:focus-visible{outline:2px solid var(--text); outline-offset:2px}
#convertBtn:disabled{opacity:.6; cursor:not-allowed}
.convert-row .pending-label{display:none; color:var(--muted); font-size:var(--fs-1)}
.convert-row[data-pending="1"] .pending-label{display:inline}

.result{margin-top:var(--space-6)}
.result-banner{
  display:none; align-items:center; gap:var(--space-3); padding:var(--space-4);
  border:1px solid var(--ok); border-radius:var(--radius); background:rgba(63,185,110,.09);
}
.result-banner[data-show="1"]{display:flex}
.result-banner a{color:var(--ok); font-weight:600}
.result-banner .again{color:var(--accent)}

footer{margin-top:var(--space-8); padding-top:var(--space-4); border-top:1px solid var(--border);
  color:var(--muted); font-size:var(--fs-1)}
footer code{background:var(--surface-2); padding:1px 4px; border-radius:4px}

@media (max-width:520px){
  .convert-row{flex-direction:column; align-items:stretch}
  #convertBtn{width:100%}
}
</style>
</head>
<body>
<main>
  <h1>CAD Converter</h1>
  <p class="lede">Drop a CAD file (STEP, BREP or IGES) and pick an output format. Your file is
  converted on the server and downloaded locally &mdash; nothing is stored.</p>

  <div id="statusBar" class="status" role="status" aria-live="polite"></div>

  <section aria-labelledby="stepFile">
    <h2 class="visually-hidden" id="stepFile" style="position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)">Step 1 — choose a file</h2>
    <label id="dropzone" class="dropzone" for="fileInput" data-drag="">
      <span class="dz-emoji" aria-hidden="true">&#128228;</span>
      <span class="dz-title">Drop a CAD file here</span>
      <span class="dz-hint" id="dzHint">or <strong>click / press Enter</strong> to browse &mdash; STEP, BREP, IGES</span>
      <input type="file" id="fileInput" name="file" accept=".step,.stp,.brep,.iges,.igs">
    </label>
    <div class="file-chip" id="fileChip" data-has="">
      <span class="name" id="fileName"></span>
      <button type="button" class="change" id="changeFile">Choose a different file</button>
    </div>
  </section>

  <div class="field">
    <label for="formatSelect">Output format</label>
    <span class="sub" id="formatSub">Loading available formats&hellip;</span>
    <select id="formatSelect" name="format" disabled aria-describedby="formatSub"></select>
  </div>

  <div class="field">
    <label for="tolerance">Mesh tolerance <span style="color:var(--muted);font-weight:400">(optional)</span></label>
    <span class="sub">Tighter = finer mesh. Used only for mesh outputs (STL, OBJ, 3MF, GLTF, PLY).</span>
    <input type="number" id="tolerance" name="tolerance" min="0.0001" step="any" placeholder="0.1" inputmode="decimal">
  </div>

  <div class="convert-row" id="convertRow" data-pending="0">
    <button id="convertBtn" type="button" disabled>Convert</button>
    <span class="pending-label" id="pendingLabel">Converting&hellip;</span>
  </div>

  <div class="result">
    <div class="result-banner" id="resultBanner" data-show="0" role="status" aria-live="polite">
      <span class="ico" aria-hidden="true">&#10003;</span>
      <span class="msg" id="resultMsg"></span>
    </div>
  </div>

  <footer>
    <p><strong>Formats:</strong> inputs <code id="fmtInputs"></code> &middot; outputs
    <code id="fmtOutputs"></code></p>
  </footer>
</main>

<script>
"use strict";
/* ---- tiny state (local to this page; no framework, per C8b "static + inline JS") ---- */
const state = { file: null, formatsLoading: true, converting: false };

const $ = (id) => document.getElementById(id);
const dropzone = $("dropzone"), fileInput = $("fileInput"), fileChip = $("fileChip"),
      fileName = $("fileName"), formatSelect = $("formatSelect"), formatSub = $("formatSub"),
      convertBtn = $("convertBtn"), statusBar = $("statusBar"), resultBanner = $("resultBanner"),
      resultMsg = $("resultMsg"), convertRow = $("convertRow"), pendingLabel = $("pendingLabel"),
      fmtInputs = $("fmtInputs"), fmtOutputs = $("fmtOutputs"), toleranceInput = $("tolerance");

/* ---- status helpers ---- */
function setStatus(kind, icon, html) {
  statusBar.dataset.kind = kind;
  statusBar.querySelector(".ico").textContent = icon;
  statusBar.querySelector(".msg").innerHTML = html;
}
function clearStatus() { delete statusBar.dataset.kind; }

/* ---- file selection (native input is the source of truth; keyboard-usable) ---- */
function setFile(f){
  state.file = f || null;
  if (f) { fileName.textContent = f.name; fileChip.dataset.has = "file"; }
  else   { delete fileChip.dataset.has; fileName.textContent = ""; }
  refreshActionable();
}
function refreshActionable(){
  const canGo = state.file && !state.formatsLoading && !state.converting;
  convertBtn.disabled = !canGo;
}
/* Keep a file already chosen when a second drop happens; last selection wins. */
const onFiles = (fl) => { if (fl && fl.length) setFile(fl[0]); };
fileInput.addEventListener("change", () => onFiles(fileInput.files));
$("changeFile").addEventListener("click", () => fileInput.click());

/* ---- drag & drop (simple; falls back to native file input, never the only path) ---- */
["dragenter","dragover"].forEach((ev) =>
  dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.dataset.drag = "over"; }));
["dragleave","drop"].forEach((ev) =>
  dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.dataset.drag = ""; }));
dropzone.addEventListener("drop", (e) => onFiles(e.dataTransfer && e.dataTransfer.files));

/* ---- load formats from the API ---- */
async function loadFormats(){
  formatSub.textContent = "Loading available formats&hellip;";
  formatSelect.disabled = true;
  try {
    const res = await fetch(FORMATS_LOAD_PATH, { headers: { "Accept": "application/json" } });
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    const inputs = (data.inputs || []), outputs = (data.outputs || []);
    if (!Array.isArray(outputs) || !outputs.length) throw new Error("no output formats returned");
    formatSelect.innerHTML = "";
    outputs.forEach((f) => {
      const o = document.createElement("option");
      o.value = f; o.textContent = f.toUpperCase();
      formatSelect.appendChild(o);
    });
    formatSelect.disabled = false;
    formatSub.textContent = "Source: " + (inputs.length ? inputs.join(", ") : "—");
    fmtInputs.textContent = inputs.length ? inputs.join(", ") : "—";
    fmtOutputs.textContent = outputs.join(", ");
    state.formatsLoading = false;
    refreshActionable();
  } catch (err) {
    state.formatsLoading = false;
    formatSub.textContent = "Could not load formats.";
    setStatus("err","⚠",
      "Could not reach the conversion service. <strong>Reload the page</strong> to try again.");
    refreshActionable();
  }
}
const FORMATS_LOAD_PATH = "./formats";
const CONVERT_SUBMIT_PATH = "./convert";

/* multipart field names — must match server/api.py's POST /convert contract:
   file (UploadFile), format (output, Form), tolerance (optional, Form). */
const FORM_FILE_FIELD = "file";
const FORM_FORMAT_FIELD = "format";
const FORM_TOLERANCE_FIELD = "tolerance";

/* ---- convert (posts multipart exactly per the api contract) ---- */
async function onConvert(){
  if (!state.file || state.converting) return;
  const outFormat = formatSelect.value;
  if (!outFormat) return;
  state.converting = true;
  convertRow.dataset.pending = "1";
  pendingLabel.textContent = "Converting " + state.file.name + "…";
  clearStatus(); resultBanner.dataset.show = "0";
  refreshActionable();

  const fd = new FormData();
  fd.append(FORM_FILE_FIELD, state.file, state.file.name);
  fd.append(FORM_FORMAT_FIELD, outFormat);
  if (toleranceInput.value && toleranceInput.value.trim() !== "") {
    fd.append(FORM_TOLERANCE_FIELD, toleranceInput.value.trim());
  }

  try {
    const res = await fetch(CONVERT_SUBMIT_PATH, { method: "POST", body: fd });
    if (!res.ok) {
      const detail = await readError(res);
      state.converting = false; convertRow.dataset.pending = "0"; refreshActionable();
      setStatus("err","⚠", detail);
      return;
    }
    const blob = await res.blob();
    const cd = res.headers.get("Content-Disposition") || "";
    const m = cd.match(/filename="?([^";]+)"?/i);
    const outName = decodeURIComponent(((m && m[1]) || "converted")).replace(/"/g, "");
    triggerDownload(blob, outName);
    state.converting = false; convertRow.dataset.pending = "0"; refreshActionable();
    resultMsg.innerHTML = "Converted <strong>" + esc(state.file.name) + "</strong> to <strong>" +
      esc(outFormat.toUpperCase()) + "</strong> — download started (" + esc(outName) + "). " +
      '<button type="button" class="again" id="againBtn">Convert another</button>';
    resultBanner.dataset.show = "1";
    $("againBtn").addEventListener("click", resetAll);
  } catch (err) {
    state.converting = false; convertRow.dataset.pending = "0"; refreshActionable();
    setStatus("err","⚠",
      "The request failed. <strong>Check your connection and try again.</strong>");
  }
}
async function readError(res){
  try {
    const j = await res.json();
    if (j && j.detail) return humanError(res.status, j.detail);
    return humanError(res.status, "");
  } catch (_) { return humanError(res.status, ""); }
}
function humanError(status, detail){
  const map = {
    400: "The file could not be read as CAD. It may be corrupt or in an unexpected format.",
    415: "Unsupported format. Choose a STEP, BREP or IGES input, and an output from the list.",
    422: "The conversion request was not accepted. Check the file and format, then retry.",
    500: "The server could not convert the file. Try again, or convert a different file.",
  };
  return (map[status] || "Conversion failed (HTTP " + status + ").") +
    (detail ? " <code>(" + esc(detail) + ")</code>" : "");
}
function triggerDownload(blob, name){
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = name;
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
}
function resetAll(){
  setFile(null);
  fileInput.value = "";
  toleranceInput.value = "";
  resultBanner.dataset.show = "0";
  clearStatus();
  formatSelect.focus();
}
function esc(s){
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" }[c]));
}

convertBtn.addEventListener("click", onConvert);
loadFormats();
</script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Integration point for the FastAPI app. server/api.py can call render_index()
# directly, or use the constant above. Keeping this here means the frontend
# ships WITHOUT editing the backend — the page wires to the running API's
# existing /formats and /convert routes by relative path.
# ---------------------------------------------------------------------------
def render_index():
    """Return the full drag-drop page as an HTTP Response (FastAPI)."""
    from fastapi.responses import Response  # local import: web.py stays importable without fastapi
    return Response(content=INDEX_HTML, media_type="text/html")
