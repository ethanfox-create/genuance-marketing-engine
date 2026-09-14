"""
Stage 3: poster generation pipeline.

Ties together prompt_builder, dalle_client, and poster_composer to turn a
genotype record (plus its QR codes from Stage 2) into finished, printable
poster files.

One DALL-E image is generated per *design*, not per design-location pair:
the background artwork is identical everywhere a given design is placed,
only the QR code differs by location. The background is cached to disk by
design_id, so re-running the pipeline never re-spends API credit on a
design you've already generated artwork for.
"""

from pathlib import Path

from dalle_client import generate_background_image
from poster_composer import compose_poster
from prompt_builder import build_image_prompt

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKGROUNDS_DIR = PROJECT_ROOT / "data" / "poster_backgrounds"
POSTERS_DIR = PROJECT_ROOT / "data" / "posters"


def get_or_generate_background(genotype: dict) -> Path:
    """Return this design's background image, generating it via DALL-E if it isn't cached yet."""
    background_path = BACKGROUNDS_DIR / f"{genotype['design_id']}.png"
    if background_path.exists():
        return background_path

    prompt = build_image_prompt(genotype)
    return generate_background_image(prompt, background_path)


def build_posters(catalogue: list[dict], qr_manifest: list[dict]) -> list[dict]:
    """
    For every QR manifest entry (one per design x location), produce a
    finished poster: a DALL-E background (generated once per design, reused
    across its locations) composited with that design's headline, subtext,
    CTA, and the location-specific QR code.

    Returns a list of records -- design_id, location_code, poster_image_path
    -- for Stage 7 (quality gate) and the deployment map to consume.
    """
    catalogue_by_id = {genotype["design_id"]: genotype for genotype in catalogue}
    results = []

    for entry in qr_manifest:
        genotype = catalogue_by_id[entry["design_id"]]
        background_path = get_or_generate_background(genotype)

        output_path = POSTERS_DIR / f"{entry['design_id']}_{entry['location_code']}.png"
        compose_poster(
            genotype=genotype,
            background_path=background_path,
            qr_image_path=entry["qr_image_path"],
            output_path=output_path,
        )
        results.append(
            {
                "design_id": entry["design_id"],
                "location_code": entry["location_code"],
                "poster_image_path": str(output_path),
            }
        )

    return results
