"""
Stage 3: poster generation pipeline.

Ties together prompt_builder, the image client, and poster_composer to
turn a genotype record (plus its QR codes from Stage 2) into finished,
printable poster files.

One background image is generated per *design*, not per design-location
pair: the artwork is identical everywhere a given design is placed, only
the QR code differs by location. The background is cached to disk by
design_id, so re-running the pipeline never re-spends API credit on a
design you've already generated artwork for.

Generating one design's background can fail independently of the others
-- a moderation rejection, a transient API error, a rate limit -- so a
failure for one design is logged and skipped rather than crashing the
whole batch. build_posters() returns both what succeeded and what didn't,
so the caller can report a clear summary and decide what to do about the
failures (rewrite that genotype's prompt, retry, drop it from this
generation).

A batch of many new designs generated back to back can also trip the
image API's per-minute rate limit outright (dalle_client.py retries
individual transient failures, but a large batch is better off not
hammering the API in the first place) -- REQUEST_DELAY_SECONDS spaces out
fresh generation calls. Cached backgrounds (already on disk) are unaffected
and composite immediately with no delay.
"""

import time
from pathlib import Path

from dalle_client import generate_background_image
from poster_composer import compose_poster
from prompt_builder import build_image_prompt

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKGROUNDS_DIR = PROJECT_ROOT / "data" / "poster_backgrounds"
POSTERS_DIR = PROJECT_ROOT / "data" / "posters"

REQUEST_DELAY_SECONDS = 3


def get_or_generate_background(genotype: dict) -> Path:
    """Return this design's background image, generating it via the image API if it isn't cached yet."""
    background_path = BACKGROUNDS_DIR / f"{genotype['design_id']}.png"
    if background_path.exists():
        return background_path

    prompt = build_image_prompt(genotype)
    return generate_background_image(prompt, background_path)


def build_posters(catalogue: list[dict], qr_manifest: list[dict]) -> dict:
    """
    For every QR manifest entry (one per design x location), produce a
    finished poster: a background image (generated once per design, reused
    across its locations) composited with that design's headline, subtext,
    CTA, and the location-specific QR code.

    Returns {"posters": [...], "failed_designs": {design_id: error_message}}.
    Entries in "posters" -- design_id, location_code, poster_image_path --
    are what Stage 7 (quality gate) and the deployment map consume next.
    """
    catalogue_by_id = {genotype["design_id"]: genotype for genotype in catalogue}
    posters = []
    failed_designs: dict[str, str] = {}
    fresh_generation_count = 0

    for entry in qr_manifest:
        design_id = entry["design_id"]
        genotype = catalogue_by_id[design_id]

        if design_id in failed_designs:
            continue  # already failed to generate a background for this design earlier in this run

        needs_generation = not (BACKGROUNDS_DIR / f"{design_id}.png").exists()
        if needs_generation:
            if fresh_generation_count > 0:
                time.sleep(REQUEST_DELAY_SECONDS)
            fresh_generation_count += 1
            print(f"Generating background for {design_id}...")

        try:
            background_path = get_or_generate_background(genotype)
        except Exception as exc:
            failed_designs[design_id] = str(exc)
            print(f"  FAILED: {design_id} -- {exc}")
            continue

        output_path = POSTERS_DIR / f"{design_id}_{entry['location_code']}.png"
        compose_poster(
            genotype=genotype,
            background_path=background_path,
            qr_image_path=entry["qr_image_path"],
            output_path=output_path,
        )
        posters.append(
            {
                "design_id": design_id,
                "location_code": entry["location_code"],
                "poster_image_path": str(output_path),
            }
        )

    return {"posters": posters, "failed_designs": failed_designs}
