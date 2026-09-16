"""
Demo / entry point for Stage 7.

Runs every Generation 1 poster (Stage 3's real output) through the
three-tier quality gate and reports a verdict for each.

Run it with:
    python quality/run_quality_gate_generation_1.py
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "genotype"))

from catalogue import load_catalogue  # noqa: E402
from quality_gate import run_quality_gate  # noqa: E402

QR_MANIFEST_PATH = PROJECT_ROOT / "data" / "qr_manifest.json"
POSTERS_DIR = PROJECT_ROOT / "data" / "posters"
REPORT_PATH = PROJECT_ROOT / "data" / "quality_gate_report.json"


def main() -> None:
    catalogue = load_catalogue()
    catalogue_by_id = {g["design_id"]: g for g in catalogue}

    if not QR_MANIFEST_PATH.exists():
        print("No QR manifest found -- run tracking/build_generation_1_qr_codes.py first.")
        return
    with open(QR_MANIFEST_PATH, "r", encoding="utf-8") as f:
        qr_manifest = json.load(f)
    qr_manifest_by_key = {(e["design_id"], e["location_code"]): e for e in qr_manifest}

    poster_records = []
    for entry in qr_manifest:
        poster_path = POSTERS_DIR / f"{entry['design_id']}_{entry['location_code']}.png"
        if poster_path.exists():
            poster_records.append(
                {
                    "design_id": entry["design_id"],
                    "location_code": entry["location_code"],
                    "poster_image_path": str(poster_path),
                }
            )

    if not poster_records:
        print("No posters found -- run generation/build_generation_1_posters.py first.")
        return

    print(f"Running quality gate on {len(poster_records)} poster(s)...\n")
    results = run_quality_gate(poster_records, catalogue_by_id, qr_manifest_by_key)

    for r in results:
        print(f"{r['design_id']}/{r['location_code']}: {r['status'].upper()}")
        for check_name, check in r["tier1"]["checks"].items():
            mark = "OK" if check["passed"] else "FAIL"
            print(f"    tier1 [{check_name}]: {mark} -- {check['detail']}")
        if r["tier2"]:
            print(f"    tier2: usable={r['tier2']['usable']} concerns={r['tier2']['concerns']}")
        print()

    approved = [r for r in results if r["status"] == "approved"]
    flagged = [r for r in results if r["status"] == "flagged"]
    print(f"Summary: {len(approved)} approved, {len(flagged)} flagged for review")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"Saved to {REPORT_PATH}")


if __name__ == "__main__":
    main()
