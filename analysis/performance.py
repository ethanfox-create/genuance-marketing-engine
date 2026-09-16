"""
Stage 5: analysis pipeline.

Joins scan data (tracking/scans.py, Stage 4) with the genotype catalogue
(Stage 1) to compute attribute-level performance: for each value an enum
attribute can take (e.g. visual_tone="provocative"), how designs using
that value performed on average, across how many designs and how many
total scans backed that number.

"Performance" here is scan RATE, not raw scan count: a design placed in 5
locations will rack up more raw scans than one placed in 1 location even
if the design itself is weaker, so raw scan counts aren't comparable
across designs with different exposure. scan_rate = total scans /
exposure, where exposure is the number of locations that design has a QR
code for (from the Stage 2 manifest -- the closest available measure of
"how many chances did this design get" until real field placement data
in tracking/placements.py exists).

audience_hypothesis is deliberately NOT grouped here, even though it's a
genotype field. It's free text by design (see project memory
"design_free_text_audience_hypothesis") specifically so new audience
segments can emerge over generations rather than being capped by a fixed
list -- but that means exact-string grouping would silently miss
near-duplicate phrasings ("divorced dads in their 40s" vs "recently single
fathers") and misrepresent the data. Proper handling needs LLM-based
clustering of the free-text values; audience_hypothesis_raw() below just
lists per-design values so a human (or a future clustering step) can look
at them directly, rather than a half-correct groupby pretending to be one.

A basic statistical caveat, worth stating plainly rather than hiding in a
number: with only a handful of designs and scans -- which any early
generation will have -- an average built from one or two designs isn't a
reliable signal, it's a single data point wearing an average's clothing.
Every group in the report below carries its n_designs and total_scans
alongside the rate, and a low_confidence flag when n_designs is small, so
the report can't be misread as more certain than the data supports.
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "genotype"))
sys.path.insert(0, str(PROJECT_ROOT / "tracking"))

import pandas as pd  # noqa: E402
from catalogue import load_catalogue  # noqa: E402
from schema import GENOTYPE_SCHEMA  # noqa: E402
from scans import load_scans  # noqa: E402

QR_MANIFEST_PATH = PROJECT_ROOT / "data" / "qr_manifest.json"

# Fewer designs than this backing a group's average -> flag it as low confidence.
LOW_CONFIDENCE_DESIGN_THRESHOLD = 2


def _load_qr_manifest() -> list[dict]:
    if not QR_MANIFEST_PATH.exists():
        return []
    with open(QR_MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def build_design_performance(
    catalogue: list[dict] | None = None,
    scans: list[dict] | None = None,
    qr_manifest: list[dict] | None = None,
) -> pd.DataFrame:
    """
    One row per design: its genotype fields, plus scan_count, exposure
    (number of locations it has a QR code for), and scan_rate = scan_count
    / exposure. A design with zero exposure gets a null scan_rate rather
    than a division-by-zero error.

    Accepts explicit catalogue/scans/qr_manifest for testing against
    simulated data (per CLAUDE.md: this stage should be testable before
    live scan data exists); defaults to loading the real files.
    """
    catalogue = load_catalogue() if catalogue is None else catalogue
    scans = load_scans() if scans is None else scans
    qr_manifest = _load_qr_manifest() if qr_manifest is None else qr_manifest

    catalogue_df = pd.DataFrame(catalogue)

    scans_df = pd.DataFrame(scans, columns=["design_id", "location_code", "timestamp"])
    scan_counts = (
        scans_df.groupby("design_id").size().rename("scan_count").reset_index()
        if not scans_df.empty
        else pd.DataFrame(columns=["design_id", "scan_count"])
    )

    manifest_df = pd.DataFrame(qr_manifest, columns=["design_id", "location_code", "url", "qr_image_path"])
    exposure = (
        manifest_df.groupby("design_id").size().rename("exposure").reset_index()
        if not manifest_df.empty
        else pd.DataFrame(columns=["design_id", "exposure"])
    )

    performance = catalogue_df.merge(scan_counts, on="design_id", how="left")
    performance = performance.merge(exposure, on="design_id", how="left")
    performance["scan_count"] = performance["scan_count"].fillna(0).astype(int)
    performance["exposure"] = performance["exposure"].fillna(0).astype(int)
    performance["scan_rate"] = performance.apply(
        lambda row: row["scan_count"] / row["exposure"] if row["exposure"] > 0 else None,
        axis=1,
    )
    return performance


def attribute_performance_report(performance: pd.DataFrame) -> dict:
    """
    For every enum field in the genotype schema, group designs by the
    value they used and compute n_designs, total_scans, and avg_scan_rate.
    Returns {field_name: [group records, sorted best-performing first]}.
    """
    report = {}

    for field, spec in GENOTYPE_SCHEMA.items():
        if spec["type"] != "enum":
            continue  # audience_hypothesis and other free-text fields: see audience_hypothesis_raw()

        groups = []
        for value, rows in performance.groupby(field):
            rated = rows.dropna(subset=["scan_rate"])
            avg_rate = round(rated["scan_rate"].mean(), 3) if not rated.empty else None
            groups.append(
                {
                    "value": value,
                    "n_designs": int(len(rows)),
                    "total_scans": int(rows["scan_count"].sum()),
                    "avg_scan_rate": avg_rate,
                    "low_confidence": len(rows) < LOW_CONFIDENCE_DESIGN_THRESHOLD,
                }
            )

        groups.sort(key=lambda g: (g["avg_scan_rate"] is None, -(g["avg_scan_rate"] or 0)))
        report[field] = groups

    return report


def audience_hypothesis_raw(performance: pd.DataFrame) -> list[dict]:
    """Per-design audience_hypothesis values alongside performance -- not grouped. See module docstring."""
    columns = ["design_id", "audience_hypothesis", "scan_count", "exposure", "scan_rate"]
    return performance[columns].to_dict("records")


def format_report(report: dict, audience_rows: list[dict]) -> str:
    """Render the attribute performance report as readable text."""
    lines = []
    for field, groups in report.items():
        lines.append(f"\n{field}")
        lines.append("-" * len(field))
        for g in groups:
            rate = f"{g['avg_scan_rate']:.3f}" if g["avg_scan_rate"] is not None else "n/a"
            flag = "  [low confidence -- fewer than 2 designs]" if g["low_confidence"] else ""
            lines.append(
                f"  {g['value']:<25} avg_scan_rate={rate:<8} "
                f"n_designs={g['n_designs']:<3} total_scans={g['total_scans']}{flag}"
            )

    lines.append("\naudience_hypothesis (free text -- not grouped, see module docstring)")
    lines.append("-" * 60)
    for row in audience_rows:
        rate = f"{row['scan_rate']:.3f}" if row["scan_rate"] is not None else "n/a"
        lines.append(f"  {row['design_id']}: \"{row['audience_hypothesis']}\" -- scan_rate={rate}")

    return "\n".join(lines)
