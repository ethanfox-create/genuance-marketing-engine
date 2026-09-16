"""
Stage 3: image generation prompt builder.

Turns a genotype's *visual* fields into a text prompt for the image
generation API. Deliberately says nothing about the headline, subtext, or
call-to-action text -- image models are unreliable at rendering legible
text, so those are composited on afterward with Pillow (poster_composer.py)
instead of being requested from the image model. We explicitly tell it not
to include any text or logos, to keep the background clean for that.

Word choice matters here beyond style: this is dating-app advertising, so
"provocative" / "bold" genotype values sit close to the line automated
moderation systems flag, even when the actual intent is tasteful. Every
tone and brand_safety phrase below leans toward "confident/flirtatious
editorial photography" rather than words like "intimate" or "charged" that
read as sexual content to a moderation classifier -- and every prompt ends
with an explicit editorial/fully-clothed/no-nudity clause. If a specific
genotype still gets rejected, pipeline.py catches that per-design rather
than crashing the whole batch.
"""

VISUAL_STYLE_PROMPTS = {
    "photography_couple": "a candid photograph of a couple",
    "photography_solo": "a candid photograph of a single person",
    "illustrated": "a stylized illustration",
    "typographic_only": "an abstract textured background with no people, designed to sit behind bold typography",
    "abstract_graphic": "an abstract graphic composition of shapes and gradients",
}

VISUAL_TONE_PROMPTS = {
    "provocative": "confident, flirtatious, high-energy",
    "playful": "playful, lighthearted, fun energy",
    "sophisticated": "sophisticated, refined, upscale mood",
    "edgy": "edgy, bold, unconventional mood",
    "warm": "warm, inviting, approachable mood",
}

COLOUR_SCHEME_PROMPTS = {
    "dark_neon_accent": "a dark background with a single vivid neon accent colour",
    "black_white_red": "a high-contrast black, white and red palette",
    "warm_tones": "warm orange and red tones",
    "cool_tones": "cool blue and teal tones",
    "monochrome": "a monochrome, single-colour palette",
}

BRAND_SAFETY_PROMPTS = {
    "conservative": "tasteful and understated",
    "moderate": "confident and a little daring, tasteful",
    "bold": "bold and eye-catching, tasteful rather than explicit",
}


def build_image_prompt(genotype: dict) -> str:
    """Build an image-generation prompt from a genotype record's visual attributes."""
    parts = [
        VISUAL_STYLE_PROMPTS.get(genotype["visual_style"], "a striking photograph"),
        f"with a {VISUAL_TONE_PROMPTS.get(genotype['visual_tone'], 'compelling')} feel",
        f"using {COLOUR_SCHEME_PROMPTS.get(genotype['colour_scheme'], 'a bold colour palette')}",
        f"intended to appeal to: {genotype['audience_hypothesis']}",
        BRAND_SAFETY_PROMPTS.get(genotype["brand_safety"], "tasteful"),
        "editorial advertising photography style, all subjects fully clothed, no nudity, no sexual content",
        "no text, no words, no letters, no logos in the image",
        "vertical poster composition, professional advertising photography quality",
    ]
    return ", ".join(parts)
