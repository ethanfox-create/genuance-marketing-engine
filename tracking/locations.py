"""
Placement locations catalogue.

Each location is a physical spot -- a specific block, lamp post cluster,
or neighbourhood -- where posters get put up. Stored in data/locations.json:
a list of dict records read and written as JSON, the same pattern as the
Stage 1 genotype catalogue. Scouting a new spot or listing existing ones
never means hand-editing a Python file -- you call add_location() (or,
later, whatever front-end calls it on your behalf).
"""

import json
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_LOCATIONS_PATH = Path(__file__).resolve().parent.parent / "data" / "locations.json"


def load_locations(path: Path = DEFAULT_LOCATIONS_PATH) -> list[dict]:
    """Return every location record on disk (empty list if none yet)."""
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_locations(locations: list[dict], path: Path = DEFAULT_LOCATIONS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(locations, f, indent=2)


def add_location(
    location_code: str,
    description: str,
    neighbourhood: str,
    path: Path = DEFAULT_LOCATIONS_PATH,
) -> dict:
    """
    Record a newly scouted placement spot.

    location_code   -- short, stable, unique identifier (e.g. "annex_01").
                        Pick it once and never reuse or repurpose it: it
                        gets baked into every QR code printed for this
                        spot, and into every placement log entry.
    description      -- something you can match to the physical spot later,
                        e.g. "lamp post, Bloor & Bathurst NW corner".
    neighbourhood     -- e.g. "the_annex".

    Raises ValueError if location_code is already in use.
    """
    locations = load_locations(path)
    if any(loc["location_code"] == location_code for loc in locations):
        raise ValueError(f"location_code {location_code!r} already exists")

    record = {
        "location_code": location_code,
        "description": description,
        "neighbourhood": neighbourhood,
        "status": "active",
        "scouted_at": datetime.now(timezone.utc).isoformat(),
    }
    locations.append(record)
    save_locations(locations, path)
    return record


def active_location_codes(path: Path = DEFAULT_LOCATIONS_PATH) -> list[str]:
    """Location codes currently in rotation -- what the QR generator and poster pipeline should target."""
    return [loc["location_code"] for loc in load_locations(path) if loc["status"] == "active"]


def retire_location(location_code: str, note: str = "", path: Path = DEFAULT_LOCATIONS_PATH) -> dict:
    """Mark a location inactive (e.g. the spot's no longer accessible) without deleting its history."""
    locations = load_locations(path)
    for loc in locations:
        if loc["location_code"] == location_code:
            loc["status"] = "retired"
            loc["retired_note"] = note
            save_locations(locations, path)
            return loc
    raise ValueError(f"location_code {location_code!r} not found")
