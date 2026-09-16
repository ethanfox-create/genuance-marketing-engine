"""
Scan event log.

Records every QR code scan that hits the tracking server: which design,
which location, and when. Append-only JSON, the same pattern as the
genotype catalogue (Stage 1) and the placement history log
(tracking/placements.py) -- this is the raw data Stage 5 (analysis) joins
against the genotype catalogue to compute attribute-level performance.

Known limitation: this does a plain read-modify-write of the whole file
per scan, with no file locking. Two scans arriving in the exact same
instant could race and one could be lost. At this campaign's expected
scale (QR scans off physical posters, not viral web traffic) that risk is
acceptable; if scan volume ever gets large enough for this to matter,
replace this with a real database rather than adding locking to a JSON
file.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_SCANS_PATH = Path(__file__).resolve().parent.parent / "data" / "scans.json"


def load_scans(path: Path = DEFAULT_SCANS_PATH) -> list[dict]:
    """Return every scan event logged so far (empty list if none yet)."""
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_scans(scans: list[dict], path: Path = DEFAULT_SCANS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(scans, f, indent=2)


def record_scan(design_id: str, location_code: str, path: Path = DEFAULT_SCANS_PATH) -> dict:
    """Log one scan event and return the record that was written."""
    scan = {
        "design_id": design_id,
        "location_code": location_code,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    scans = load_scans(path)
    scans.append(scan)
    save_scans(scans, path)
    return scan
