"""
Placement history log.

Tracks, over time, which design is posted at which location -- and every
change made to that: a design's first placement at a spot, keeping the
current design into a new generation, replacing it with a new design, or
removing it. This is an append-only log (like a changelog), not a table
you edit in place: every change is a new timestamped record, so
"how many times has this location's ad changed, and to what" is always a
query against history, never something you have to reconstruct from memory
or a spreadsheet someone forgot to update.

The workflow this is built for: you go out, look at what's posted where,
and come back with a list of changes -- which locations got a new design,
which kept their current one, which got torn down and are no longer live.
bulk_update() takes that whole list in one call, rather than requiring one
function call (or one manual spreadsheet row edit) per location.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_PLACEMENTS_PATH = Path(__file__).resolve().parent.parent / "data" / "placements.json"

VALID_ACTIONS = {"initial_placement", "kept", "replaced", "removed"}
ACTIONS_REQUIRING_NEW_DESIGN = {"initial_placement", "replaced"}


def load_placements(path: Path = DEFAULT_PLACEMENTS_PATH) -> list[dict]:
    """Return the full placement history log (empty list if none yet)."""
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_placements(placements: list[dict], path: Path = DEFAULT_PLACEMENTS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(placements, f, indent=2)


def get_current_placements(path: Path = DEFAULT_PLACEMENTS_PATH) -> dict:
    """
    The latest placement record for every location that has one, keyed by
    location_code -- i.e. "what's posted where right now" (a location whose
    latest action is "removed" has no live design; check record["action"]).

    Because the log is append-only and read in file order, later entries
    for the same location_code simply overwrite earlier ones in this dict
    -- the last write for a key naturally becomes "the current one".
    """
    current: dict = {}
    for record in load_placements(path):
        current[record["location_code"]] = record
    return current


def location_history(location_code: str, path: Path = DEFAULT_PLACEMENTS_PATH) -> list[dict]:
    """Every placement record for one location, in chronological order -- its full change history."""
    return [r for r in load_placements(path) if r["location_code"] == location_code]


def bulk_update(generation: int, changes: list[dict], path: Path = DEFAULT_PLACEMENTS_PATH) -> list[dict]:
    """
    Log a batch of placement changes for one round of re-deployment, e.g.:

        bulk_update(2, [
            {"location_code": "annex_01", "action": "replaced",
             "new_design_id": "gen2-abc123", "note": "gen1 design underperformed"},
            {"location_code": "kensington_03", "action": "kept"},
            {"location_code": "queen_west_02", "action": "removed",
             "note": "spot torn down"},
        ])

    Each change needs location_code and action ("kept" / "replaced" /
    "removed" -- use "initial_placement" for a design's first-ever posting
    at a spot). "replaced" and "initial_placement" additionally need
    new_design_id. Appends one timestamped record per change to the log in
    a single write and returns the new records.
    """
    current = get_current_placements(path)
    new_records = []

    for change in changes:
        location_code = change["location_code"]
        action = change["action"]
        if action not in VALID_ACTIONS:
            raise ValueError(f"Unknown action {action!r} for {location_code!r}")

        previous = current.get(location_code)
        previous_design_id = previous["design_id"] if previous else None

        if action in ACTIONS_REQUIRING_NEW_DESIGN:
            if "new_design_id" not in change:
                raise ValueError(f"{action!r} action for {location_code!r} needs 'new_design_id'")
            design_id = change["new_design_id"]
        elif action == "kept":
            if previous_design_id is None:
                raise ValueError(f"Cannot 'keep' {location_code!r} -- it has no prior placement")
            design_id = previous_design_id
        else:  # removed
            design_id = None

        new_records.append(
            {
                "location_code": location_code,
                "generation": generation,
                "action": action,
                "design_id": design_id,
                "previous_design_id": previous_design_id,
                "note": change.get("note", ""),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    placements = load_placements(path)
    placements.extend(new_records)
    save_placements(placements, path)
    return new_records
