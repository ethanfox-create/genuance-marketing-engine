"""
Genotype schema for the Prowler ground campaign.

A "genotype" is a dictionary that records one specific combination of
poster attribute values: this design uses photography for its visual
style, a provocative tone, a black/white/red colour scheme, and so on.
The printed poster that results from rendering that combination is the
"phenotype" -- the schema below only ever describes the genotype.

This file defines:
  1. GENOTYPE_SCHEMA  -- the allowed fields, and the allowed values per field.
  2. validate_genotype() -- checks a dict of values against the schema.
  3. create_genotype()   -- builds a new, validated genotype record.
"""

import uuid
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# The schema
# ---------------------------------------------------------------------------
# GENOTYPE_SCHEMA is a dictionary of dictionaries: the outer keys are field
# names, and each inner dictionary describes that field.
#
#   "type": "enum" -> the value must be one of the strings listed in "values".
#                      These are the fields the Stage 5 analysis pipeline can
#                      group by -- e.g. "did 'provocative' outperform 'playful'?"
#   "type": "text" -> free text. Headlines, subtext, and CTAs are written
#                      fresh each generation, so there's no fixed value list.

GENOTYPE_SCHEMA = {
    "audience_hypothesis": {
        "type": "text",
        "description": (
            "Free-text note on who you think this design will attract, e.g. "
            "'young professionals', 'nightlife crowd', 'divorced parents'. "
            "Not a fixed list -- write whatever hypothesis the design was built for."
        ),
    },
    "visual_style": {
        "type": "enum",
        "description": "The dominant imagery.",
        "values": [
            "photography_couple",
            "photography_solo",
            "illustrated",
            "typographic_only",
            "abstract_graphic",
        ],
    },
    "visual_tone": {
        "type": "enum",
        "description": "The mood of the image.",
        "values": ["provocative", "playful", "sophisticated", "edgy", "warm"],
    },
    "headline": {
        "type": "text",
        "description": "The main text on the poster.",
    },
    "headline_strategy": {
        "type": "enum",
        "description": "The rhetorical approach of the headline.",
        "values": ["question", "statement", "challenge", "invitation", "humour"],
    },
    "subtext": {
        "type": "text",
        "description": "Secondary text beneath the headline.",
        "allow_empty": True,
    },
    "colour_scheme": {
        "type": "enum",
        "description": "The palette.",
        "values": [
            "dark_neon_accent",
            "black_white_red",
            "warm_tones",
            "cool_tones",
            "monochrome",
        ],
    },
    "typography_style": {
        "type": "enum",
        "description": "The type treatment.",
        "values": ["bold_sans", "elegant_serif", "hand_drawn", "mixed", "condensed"],
    },
    "call_to_action": {
        "type": "text",
        "description": "What the poster asks the viewer to do. Empty means QR-code-only.",
        "allow_empty": True,
    },
    "cta_prominence": {
        "type": "enum",
        "description": "How prominent the CTA is relative to the rest of the design.",
        "values": ["dominant", "subordinate", "integrated"],
    },
    "qr_placement": {
        "type": "enum",
        "description": "Where the QR code sits.",
        "values": ["bottom_right", "bottom_centre", "integrated", "dominant_centre"],
    },
    "format": {
        "type": "enum",
        "description": "The physical format.",
        "values": ["a3_poster", "a4_poster", "large_sticker", "small_sticker"],
    },
    "brand_safety": {
        "type": "enum",
        "description": "A constraint on how provocative the creative is allowed to be.",
        "values": ["conservative", "moderate", "bold"],
    },
}


def validate_genotype(values: dict) -> None:
    """
    Check a dict of attribute values against GENOTYPE_SCHEMA.

    Raises ValueError with a specific message on the first problem found.
    Returns nothing (None) on success -- the "if it didn't raise, it's valid"
    pattern that's common in Python.
    """
    for field, spec in GENOTYPE_SCHEMA.items():
        if field not in values:
            raise ValueError(f"Missing required field: '{field}'")
        value = values[field]

        if spec["type"] == "enum":
            if value not in spec["values"]:
                raise ValueError(
                    f"'{field}' = {value!r} is not one of {spec['values']}"
                )
        elif spec["type"] == "text":
            if not isinstance(value, str):
                raise ValueError(f"'{field}' must be a string, got {type(value).__name__}")
            if not spec.get("allow_empty", False) and not value.strip():
                raise ValueError(f"'{field}' cannot be empty")

    # Fields the caller passed that aren't part of the schema at all --
    # almost always a typo, so we fail loudly rather than silently ignore it.
    unknown = set(values) - set(GENOTYPE_SCHEMA)
    if unknown:
        raise ValueError(f"Unknown field(s) not in schema: {sorted(unknown)}")


def create_genotype(generation: int, **attribute_values) -> dict:
    """
    Build one validated genotype record.

    generation         -- which generation this design belongs to (1, 2, 3, ...)
    **attribute_values -- one keyword argument per field in GENOTYPE_SCHEMA, e.g.:

        create_genotype(
            1,
            audience_hypothesis="nightlife_crowd",
            visual_style="photography_couple",
            visual_tone="provocative",
            headline="Still swiping at 2am?",
            headline_strategy="question",
            subtext="Prowler cuts to the chase.",
            colour_scheme="dark_neon_accent",
            typography_style="bold_sans",
            call_to_action="Scan to join",
            cta_prominence="subordinate",
            qr_placement="bottom_right",
            format="a3_poster",
            brand_safety="bold",
        )

    Returns a dict of the attribute values plus record metadata:
      design_id  -- unique identifier for this design (used later by the
                     QR generator to build per-location tracking URLs)
      generation -- which generation produced it
      created_at -- ISO-8601 UTC timestamp
    """
    validate_genotype(attribute_values)

    return {
        "design_id": f"gen{generation}-{uuid.uuid4().hex[:8]}",
        "generation": generation,
        "created_at": datetime.now(timezone.utc).isoformat(),
        **attribute_values,
    }
