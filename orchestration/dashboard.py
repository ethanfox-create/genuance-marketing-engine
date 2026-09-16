"""
Local mission-control dashboard for the marketing engine.

Runs on your own machine, not deployed anywhere -- deliberately separate
from the public Stage 4 scan tracker on Render. The reasons: generating
posters and running agent review call paid APIs (OpenAI, Anthropic) that
can take a minute or more per batch, too long for a normal web request on
free-tier hosting; and there's no good reason to put those billed API
keys on a third-party platform when they already live safely on this
machine via `setx`.

Shows the current generation, the full genotype catalogue grouped by
generation with lineage (which designs bred which -- see
genotype/schema.py's "parents" field), poster thumbnails, and the latest
quality gate results. Lets you trigger each pipeline stage with a click
instead of running scripts by hand or asking through a chat session.

Run it with:
    python orchestration/dashboard.py
Then open http://localhost:5050 in your browser.
"""

import json
import sys
from html import escape
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _subfolder in ("genotype", "tracking", "generation", "analysis", "reproduction", "quality"):
    sys.path.insert(0, str(PROJECT_ROOT / _subfolder))

from catalogue import add_genotype, load_catalogue  # noqa: E402
from flask import Flask, request, send_from_directory  # noqa: E402
from locations import active_location_codes  # noqa: E402
from pipeline import build_posters  # noqa: E402
from qr_generator import BASE_TRACKING_URL, build_tracking_url, generate_qr_code  # noqa: E402
from quality_gate import run_quality_gate  # noqa: E402
from reproduce import explore  # noqa: E402
from schema import GENOTYPE_SCHEMA, create_genotype  # noqa: E402

import run_cycle  # Stage 8 orchestrator, lives alongside this file  # noqa: E402

app = Flask(__name__)

QR_MANIFEST_PATH = PROJECT_ROOT / "data" / "qr_manifest.json"
QR_CODES_DIR = PROJECT_ROOT / "data" / "qr_codes"
QUALITY_REPORT_PATH = PROJECT_ROOT / "data" / "quality_gate_report.json"
POSTERS_DIR = PROJECT_ROOT / "data" / "posters"

PAGE = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Marketing engine -- mission control</title>
<style>
  body {{ background: #111; color: #eee; font-family: -apple-system, "Segoe UI", sans-serif; margin: 0; padding: 24px; }}
  h1 {{ font-size: 1.3rem; }}
  .summary {{ color: #999; margin-bottom: 20px; }}
  .actions {{ display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 24px; }}
  .actions form {{ margin: 0; }}
  button {{ padding: 10px 16px; font-size: 14px; font-weight: bold; border-radius: 6px;
            border: none; background: #39FF88; color: #000; cursor: pointer; }}
  .result {{ background: #1c2e1c; border: 1px solid #2a4; padding: 12px; border-radius: 6px; margin-bottom: 20px; }}
  .result.error {{ background: #2e1c1c; border-color: #a42; }}
  h2 {{ font-size: 1rem; color: #ccc; margin-top: 28px; border-bottom: 1px solid #333; padding-bottom: 6px; }}
  .card {{ display: flex; gap: 14px; background: #1a1a1a; border-radius: 8px; padding: 12px; margin-top: 10px; align-items: flex-start; }}
  .meta {{ flex: 1; font-size: 0.9rem; }}
  .sub {{ color: #999; font-size: 0.8rem; }}
  .thumbs {{ display: flex; gap: 6px; flex-wrap: wrap; }}
  .thumb {{ width: 70px; height: 105px; object-fit: cover; border-radius: 4px; border: 1px solid #333; }}
  .status-approved {{ color: #39FF88; }}
  .status-flagged {{ color: #ffb020; }}
  details {{ margin-top: 8px; }}
  summary {{ cursor: pointer; color: #7ab8ff; font-size: 0.82rem; }}
  .attrs {{ width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 0.8rem; }}
  .attrs td {{ padding: 3px 8px 3px 0; border-bottom: 1px solid #262626; }}
  .attrs td:first-child {{ color: #888; white-space: nowrap; }}
  .diff {{ margin-top: 8px; font-size: 0.8rem; }}
  .diff-line {{ padding: 2px 0; }}
  .from-a {{ color: #7ab8ff; }}
  .from-b {{ color: #ff9ecf; }}
  .from-both {{ color: #888; }}
  .changed {{ color: #ffb020; }}
</style>
</head>
<body>
  <h1>Marketing engine -- mission control</h1>
  <div class="summary">Current generation: {current_generation} &middot; {total_designs} design(s) total &middot; {total_posters} poster(s) on disk</div>

  {result_banner}

  <div class="actions">
    <form method="POST" action="/run/generate-posters">
      <button type="submit">Generate posters for current generation</button>
    </form>
    <form method="POST" action="/run/quality-gate">
      <button type="submit">Run quality gate on current generation</button>
    </form>
    <form method="POST" action="/run/next-generation">
      <button type="submit">Breed next generation (needs real scan data)</button>
    </form>
    <form method="POST" action="/run/add-variants">
      <button type="submit" style="background:#7ab8ff;">Add 3 more variants (no scan data needed)</button>
    </form>
  </div>

  {generations_html}
</body>
</html>
"""

RESULT_BANNER = '<div class="result{error_class}">{message}</div>'


def _load_qr_manifest() -> list[dict]:
    if not QR_MANIFEST_PATH.exists():
        return []
    return json.loads(QR_MANIFEST_PATH.read_text(encoding="utf-8"))


def _save_qr_manifest(manifest: list[dict]) -> None:
    QR_MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _load_quality_report() -> list[dict]:
    if not QUALITY_REPORT_PATH.exists():
        return []
    return json.loads(QUALITY_REPORT_PATH.read_text(encoding="utf-8"))


def _ensure_qr_manifest(designs: list[dict], manifest: list[dict]) -> list[dict]:
    """Fill in any missing (design, location) QR codes without duplicating existing ones -- safe to call repeatedly."""
    existing_keys = {(e["design_id"], e["location_code"]) for e in manifest}
    locations = active_location_codes()
    new_entries = []

    for design in designs:
        for location_code in locations:
            if (design["design_id"], location_code) in existing_keys:
                continue
            url = build_tracking_url(design["design_id"], location_code)
            filename = f"{design['design_id']}_{location_code}.png"
            path = generate_qr_code(url, QR_CODES_DIR / filename)
            new_entries.append(
                {"design_id": design["design_id"], "location_code": location_code, "url": url, "qr_image_path": str(path)}
            )

    if new_entries:
        manifest = manifest + new_entries
        _save_qr_manifest(manifest)

    return manifest


def _describe_lineage(genotype: dict, catalogue_by_id: dict) -> str:
    parents = genotype.get("parents") or []
    if not parents:
        return "hand-authored" if genotype["generation"] == 1 else "exploration (no parents)"
    labels = [catalogue_by_id[pid]["design_id"] if pid in catalogue_by_id else pid for pid in parents]
    kind = "crossover" if len(parents) == 2 else "mutation"
    return f"{kind} of " + " + ".join(labels)


def _full_attributes_table(genotype: dict) -> str:
    """All GENOTYPE_SCHEMA fields for one design, as a compact table -- the full genotype breakdown."""
    rows = "".join(
        f"<tr><td>{escape(field)}</td><td>{escape(str(genotype[field]))}</td></tr>" for field in GENOTYPE_SCHEMA
    )
    return f'<table class="attrs">{rows}</table>'


def _lineage_diff_html(genotype: dict, catalogue_by_id: dict) -> str:
    """
    Field-by-field breakdown of how this design's attributes trace back to
    its parent(s) -- this is the actual "evolution" view: which specific
    attributes came from which parent (crossover), or which specific
    attribute(s) changed (mutation). Empty for hand-authored/exploration
    designs, which have nothing to diff against.
    """
    parents = genotype.get("parents") or []
    if not parents:
        return ""

    if len(parents) == 2:
        parent_a = catalogue_by_id.get(parents[0])
        parent_b = catalogue_by_id.get(parents[1])
        if not parent_a or not parent_b:
            return "<div class='diff sub'>(a parent record is missing from the catalogue)</div>"

        lines = []
        for field in GENOTYPE_SCHEMA:
            value = genotype[field]
            matches_a = value == parent_a[field]
            matches_b = value == parent_b[field]
            if matches_a and matches_b:
                css_class, source = "from-both", "either parent (same value)"
            elif matches_a:
                css_class, source = "from-a", f"parent A ({escape(parent_a['design_id'])})"
            elif matches_b:
                css_class, source = "from-b", f"parent B ({escape(parent_b['design_id'])})"
            else:
                css_class, source = "changed", "neither parent (unexpected)"
            lines.append(f'<div class="diff-line {css_class}">{escape(field)}: {escape(str(value))} -- from {source}</div>')
        return "<div class='diff'>" + "".join(lines) + "</div>"

    if len(parents) == 1:
        parent = catalogue_by_id.get(parents[0])
        if not parent:
            return "<div class='diff sub'>(parent record is missing from the catalogue)</div>"

        lines = [
            f'<div class="diff-line changed">{escape(field)}: '
            f'{escape(str(parent[field]))} &rarr; {escape(str(genotype[field]))}</div>'
            for field in GENOTYPE_SCHEMA
            if genotype[field] != parent[field]
        ]
        if not lines:
            lines = ["<div class='diff-line sub'>no attribute changed (unexpected for a mutation)</div>"]
        return "<div class='diff'>" + "".join(lines) + "</div>"

    return ""


def render_dashboard(result_message: str = "", is_error: bool = False) -> str:
    catalogue = load_catalogue()
    catalogue_by_id = {g["design_id"]: g for g in catalogue}
    qr_manifest = _load_qr_manifest()
    quality_by_key = {(r["design_id"], r["location_code"]): r for r in _load_quality_report()}

    generations: dict[int, list[dict]] = {}
    for g in catalogue:
        generations.setdefault(g["generation"], []).append(g)

    current_generation = max(generations) if generations else 0
    total_posters = sum(1 for _ in POSTERS_DIR.glob("*.png")) if POSTERS_DIR.exists() else 0

    generations_html = []
    for gen_num in sorted(generations, reverse=True):
        designs = generations[gen_num]
        generations_html.append(f"<h2>Generation {gen_num} ({len(designs)} design(s))</h2>")

        for g in designs:
            lineage = _describe_lineage(g, catalogue_by_id)
            poster_entries = [e for e in qr_manifest if e["design_id"] == g["design_id"]]

            thumbs = "".join(
                f'<a href="/poster/{escape(g["design_id"])}_{escape(e["location_code"])}.png" target="_blank" '
                f'title="Open full-size (right-click to save)">'
                f'<img src="/poster/{escape(g["design_id"])}_{escape(e["location_code"])}.png" class="thumb" '
                f'onerror="this.parentElement.remove()"></a>'
                for e in poster_entries
            )

            statuses = []
            for e in poster_entries:
                r = quality_by_key.get((g["design_id"], e["location_code"]))
                if r:
                    css_class = "status-approved" if r["status"] == "approved" else "status-flagged"
                    statuses.append(f'<span class="{css_class}">{escape(e["location_code"])}: {r["status"]}</span>')
            status_line = " &middot; ".join(statuses) if statuses else "not yet checked"

            genotype_detail = _full_attributes_table(g)
            lineage_diff = _lineage_diff_html(g, catalogue_by_id)
            details_body = genotype_detail + (
                f"<div class='sub' style='margin-top:10px;'>Attribute lineage:</div>{lineage_diff}" if lineage_diff else ""
            )

            generations_html.append(
                f'''<div class="card">
                  <div class="thumbs">{thumbs or "<span class=\'sub\'>no posters yet</span>"}</div>
                  <div class="meta">
                    <strong>{escape(g["design_id"])}</strong> -- {escape(g["headline"])}<br>
                    <span class="sub">{escape(lineage)}</span><br>
                    <span class="sub">audience: {escape(g["audience_hypothesis"])} &middot; tone: {escape(g["visual_tone"])} &middot; format: {escape(g["format"])}</span><br>
                    <span class="sub">quality: {status_line}</span>
                    <details>
                      <summary>Full genotype &amp; lineage breakdown</summary>
                      {details_body}
                    </details>
                  </div>
                </div>'''
            )

    return PAGE.format(
        current_generation=current_generation,
        total_designs=len(catalogue),
        total_posters=total_posters,
        result_banner=(
            RESULT_BANNER.format(error_class=" error" if is_error else "", message=escape(result_message))
            if result_message
            else ""
        ),
        generations_html="".join(generations_html) or "<p class='sub'>No designs yet.</p>",
    )


@app.route("/")
def dashboard():
    return render_dashboard()


@app.route("/poster/<path:filename>")
def serve_poster(filename):
    return send_from_directory(POSTERS_DIR, filename)


@app.route("/run/add-variants", methods=["POST"])
def run_add_variants():
    """
    Add more candidate designs to the CURRENT generation via pure
    exploration (Stage 6's explore() function) -- unlike breeding a new
    generation, this needs no real scan data, since exploration doesn't
    select survivors, it just samples the schema randomly. This is the
    button for "I want more options to choose from right now," separate
    from real evolutionary selection.
    """
    catalogue = load_catalogue()
    current_gen = max((g["generation"] for g in catalogue), default=1)
    count = int(request.form.get("count", 3))

    new_designs = []
    for _ in range(count):
        fields = explore(catalogue)
        genotype = create_genotype(current_gen, parents=[], **fields)
        add_genotype(genotype)
        new_designs.append(genotype)
        catalogue.append(genotype)  # so the next explore() call can also draw text from designs just added

    return render_dashboard(f"Added {len(new_designs)} new variant(s) to generation {current_gen}.")


@app.route("/run/generate-posters", methods=["POST"])
def run_generate_posters():
    catalogue = load_catalogue()
    if not catalogue:
        return render_dashboard("Catalogue is empty.", is_error=True)

    current_gen = max(g["generation"] for g in catalogue)
    current_designs = [g for g in catalogue if g["generation"] == current_gen]

    if not active_location_codes():
        return render_dashboard("No active locations -- add one via the /admin page first.", is_error=True)

    qr_manifest = _ensure_qr_manifest(current_designs, _load_qr_manifest())
    current_design_ids = {g["design_id"] for g in current_designs}
    current_manifest = [e for e in qr_manifest if e["design_id"] in current_design_ids]

    try:
        result = build_posters(current_designs, current_manifest)
    except Exception as exc:  # noqa: BLE001 -- surface any failure to the dashboard rather than crashing it
        return render_dashboard(f"Poster generation failed: {exc}", is_error=True)

    message = f"Generated {len(result['posters'])} poster(s) for generation {current_gen}."
    if result["failed_designs"]:
        message += f" {len(result['failed_designs'])} design(s) failed (see terminal for details)."
    return render_dashboard(message, is_error=bool(result["failed_designs"]))


@app.route("/run/quality-gate", methods=["POST"])
def run_quality_gate_action():
    catalogue = load_catalogue()
    if not catalogue:
        return render_dashboard("Catalogue is empty.", is_error=True)

    current_gen = max(g["generation"] for g in catalogue)
    catalogue_by_id = {g["design_id"]: g for g in catalogue if g["generation"] == current_gen}
    qr_manifest = _load_qr_manifest()
    manifest_by_key = {(e["design_id"], e["location_code"]): e for e in qr_manifest if e["design_id"] in catalogue_by_id}

    poster_records = []
    for (design_id, location_code), entry in manifest_by_key.items():
        poster_path = POSTERS_DIR / f"{design_id}_{location_code}.png"
        if poster_path.exists():
            poster_records.append({"design_id": design_id, "location_code": location_code, "poster_image_path": str(poster_path)})

    if not poster_records:
        return render_dashboard("No posters on disk for the current generation -- generate posters first.", is_error=True)

    results = run_quality_gate(poster_records, catalogue_by_id, manifest_by_key)
    QUALITY_REPORT_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")

    approved = sum(1 for r in results if r["status"] == "approved")
    flagged = len(results) - approved
    return render_dashboard(f"Quality gate: {approved} approved, {flagged} flagged.", is_error=flagged > 0)


@app.route("/run/next-generation", methods=["POST"])
def run_next_generation_action():
    catalogue = load_catalogue()
    current_gen = max((g["generation"] for g in catalogue), default=0)

    try:
        result = run_cycle.run_cycle(current_gen + 1)
    except ValueError as exc:
        return render_dashboard(str(exc), is_error=True)

    message = (
        f"Bred generation {current_gen + 1}: {len(result['new_genotypes'])} new design(s), "
        f"{len(result['deployment_map'])} approved poster(s) ready in {result['generation_dir']}."
    )
    return render_dashboard(message)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050, debug=False)
