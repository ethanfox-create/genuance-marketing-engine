"""
Stage 3: OpenAI image generation client.

Calls OpenAI's image generation API to produce the background artwork for
one poster, from a prompt built by prompt_builder.py.

Originally written against DALL-E 3, which OpenAI has since retired --
this now targets gpt-image-1, the current stable model in the same
`images.generate` family. Unlike DALL-E 3, gpt-image-1 returns the image
as base64-encoded data directly in the response rather than a URL to
download, so there's no separate fetch step.

Requires an OPENAI_API_KEY environment variable. Never hardcode an API key
in a source file -- this repo is version-controlled and pushed to GitHub
(per CLAUDE.md), so a hardcoded key would be leaked the moment it's
committed.
"""

import base64
import os
from pathlib import Path

from openai import OpenAI

MODEL = "gpt-image-1"
SIZE = "1024x1536"  # tallest supported size -- closest fit to a poster


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
    Call the image model with `prompt` and save the resulting image to
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

    image_bytes = base64.b64decode(response.data[0].b64_json)
    output_path.write_bytes(image_bytes)
    return output_path
