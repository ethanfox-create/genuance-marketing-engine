"""
Demo / smoke-test for Stage 1.

Creates a handful of example genotype records for Generation 1 and writes
them into the catalogue at data/catalogue.json. This is here to prove the
schema and catalogue modules work together end to end -- the real
Generation 1 batch (all the designs you actually want to print) gets
written the same way, just with more calls to create_genotype().

Run it with:
    python genotype/build_generation_1.py
"""

from schema import create_genotype
from catalogue import add_genotype, load_catalogue

EXAMPLE_DESIGNS = [
    dict(
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
    ),
    dict(
        audience_hypothesis="young_professionals",
        visual_style="typographic_only",
        visual_tone="sophisticated",
        headline="Dating, without the small talk.",
        headline_strategy="statement",
        subtext="",
        colour_scheme="monochrome",
        typography_style="elegant_serif",
        call_to_action="Find your match",
        cta_prominence="integrated",
        qr_placement="integrated",
        format="a4_poster",
        brand_safety="conservative",
    ),
    dict(
        audience_hypothesis="queer_community",
        visual_style="abstract_graphic",
        visual_tone="playful",
        headline="Age is just a filter you turned off.",
        headline_strategy="humour",
        subtext="Prowler. For grown-up chemistry.",
        colour_scheme="warm_tones",
        typography_style="hand_drawn",
        call_to_action="",
        cta_prominence="dominant",
        qr_placement="dominant_centre",
        format="large_sticker",
        brand_safety="moderate",
    ),
]


def main() -> None:
    for design in EXAMPLE_DESIGNS:
        genotype = create_genotype(1, **design)
        add_genotype(genotype)
        print(f"Added {genotype['design_id']}: {genotype['headline']!r}")

    catalogue = load_catalogue()
    print(f"\nCatalogue now has {len(catalogue)} genotype record(s).")


if __name__ == "__main__":
    main()
