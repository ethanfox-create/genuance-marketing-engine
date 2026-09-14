"""
Stage 3: DALL-E API client.

Calls OpenAI's image generation API to produce the background artwork for
one poster, from a prompt built by prompt_builder.py.

Requires an OPENAI_API_KEY environment variable. Never hardcode an API key
in a source file -- this repo is version-controlled and pushed to GitHub
(per CLAUDE.md), so a hardcoded key would be leaked the moment it's
committed.
"""

import os
import urllib.request
from pathlib import Path

from openai import OpenAI

MODEL = "dall-e-3"
SIZE = "1024x1792"  # tallest native DALL-E 3 size -- closest fit to a poster


def _client() -> OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Create a key at platform.openai.com, "
            "then set it as an environment variable before running this script.\n"
            "  PowerShell:  $env:OPENAI_API_KEY = 'sk-...'\n"
            "  bash:        export OPENAI_API_KEY='sk-...'"
        )
    return OpenAI(api_key=api_key)


def generate_background_image(prompt: str, output_path: Path) -> Path:
    """
    Call DALL-E with `prompt`, download the resulting image, and save it to
    output_path. Returns output_path.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    client = _client()
    response = client.images.generate(
        model=MODEL,
        prompt=prompt,
        size=SIZE,
        n=1,
    )

    image_url = response.data[0].url
    urllib.request.urlretrieve(image_url, output_path)
    return output_path
