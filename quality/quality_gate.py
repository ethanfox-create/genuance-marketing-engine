"""
Stage 7: quality gate orchestrator.

Runs every poster from Stage 3's output through all three tiers and
returns a verdict for each: "approved" (passed Tier 1, and Tier 2 actively
found no concerns) or "flagged" (failed a Tier 1 check, Tier 2 raised
concerns, or Tier 2 wasn't configured to run at all). A tier that
couldn't run is never treated as a silent pass -- an unconfigured Tier 2
flags for human review rather than approving by default.
"""

from pathlib import Path

from agent_review import review_poster
from notify import send_flagged_notification
from technical_checks import run_tier1_checks


def run_quality_gate(poster_records: list[dict], catalogue_by_id: dict, qr_manifest_by_key: dict) -> list[dict]:
    """
    poster_records: Stage 3's build_posters() "posters" list --
        {design_id, location_code, poster_image_path}
    catalogue_by_id: {design_id: genotype dict} -- to look up each poster's format
    qr_manifest_by_key: {(design_id, location_code): manifest entry} -- to
        look up the URL each poster's QR code should decode to

    Returns one result per poster: the input fields plus tier1, tier2, and
    status ("approved" or "flagged"). Also sends the Tier 3 notification
    for whatever ends up flagged.
    """
    results = []

    for poster in poster_records:
        genotype = catalogue_by_id[poster["design_id"]]
        manifest_entry = qr_manifest_by_key[(poster["design_id"], poster["location_code"])]

        tier1 = run_tier1_checks(Path(poster["poster_image_path"]), genotype["format"], manifest_entry["url"])

        tier2 = None
        if tier1["passed"]:
            tier2 = review_poster(poster["poster_image_path"])

        needs_review = not tier1["passed"] or tier2 is None or tier2["usable"] is not True
        status = "flagged" if needs_review else "approved"

        results.append({**poster, "tier1": tier1, "tier2": tier2, "status": status})

    flagged = [r for r in results if r["status"] == "flagged"]
    send_flagged_notification(flagged)

    return results
