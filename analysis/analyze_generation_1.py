"""
Demo / entry point for Stage 5.

Loads the real catalogue, QR manifest, and scan log, computes
attribute-level performance, prints a readable report, and saves the
underlying data as JSON for Stage 6 (reproduction) to consume.

If no scans have been logged yet (expected before any posters are
actually placed and scanned), this still runs -- every design just shows
scan_count=0 and scan_rate=0.0, an accurate reflection of "no data yet"
rather than an error.

Run it with:
    python analysis/analyze_generation_1.py
"""

import json
from pathlib import Path

from performance import attribute_performance_report, audience_hypothesis_raw, build_design_performance, format_report

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORT_PATH = PROJECT_ROOT / "data" / "analysis_report.json"


def main() -> None:
    performance = build_design_performance()
    if performance.empty:
        print("Catalogue is empty -- run genotype/build_generation_1.py first.")
        return

    total_scans = int(performance["scan_count"].sum())
    if total_scans == 0:
        print(
            "No scans logged yet (data/scans.json is empty or missing) -- "
            "this report will show zeros everywhere until real posters are "
            "placed and scanned. Running anyway so the pipeline is proven "
            "before live data exists.\n"
        )

    report = attribute_performance_report(performance)
    audience_rows = audience_hypothesis_raw(performance)

    print(format_report(report, audience_rows))

    REPORT_PATH.write_text(
        json.dumps({"attribute_performance": report, "audience_hypothesis": audience_rows}, indent=2),
        encoding="utf-8",
    )
    print(f"\nSaved to {REPORT_PATH}")


if __name__ == "__main__":
    main()
