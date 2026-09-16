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
Batches of several designs generated back to back can trip OpenAI's
per-minute image generation rate limit, especially on newer/lower-usage
accounts -- this showed up for real generating a batch of 15 designs at
once (every one failed identically, but a lone retry immediately
succeeded, confirming it was rate limiting, not a content problem).
generate_background_image() retries transient failures (rate limits,
timeouts, connection errors, server errors) with exponential backoff;
content-based failures (e.g. a moderation rejection) are NOT retried,
since retrying the same prompt will just fail the same way again.
"""

import base64
import os
import time
from pathlib import Path

from openai import APIConnectionError, APITimeoutError, InternalServerError, OpenAI, RateLimitError

MODEL = "gpt-image-1"
SIZE = "1024x1536"  # tallest supported size -- closest fit to a poster

RETRYABLE_ERRORS = (RateLimitError, APIConnectionError, APITimeoutError, InternalServerError)
MAX_ATTEMPTS = 4
INITIAL_BACKOFF_SECONDS = 5


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
    output_path. Returns output_path. Retries transient failures
    (rate limits, timeouts, server errors) with exponential backoff before
    giving up; a content-based rejection (e.g. moderation) is raised
    immediately since retrying won't change the outcome.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    client = _client()
    backoff = INITIAL_BACKOFF_SECONDS
    response = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = client.images.generate(model=MODEL, prompt=prompt, size=SIZE, n=1)
            break
        except RETRYABLE_ERRORS as exc:
            if attempt == MAX_ATTEMPTS:
                raise
            print(f"    {type(exc).__name__}, retrying in {backoff}s ({attempt}/{MAX_ATTEMPTS})...")
            time.sleep(backoff)
            backoff *= 2

    image_bytes = base64.b64decode(response.data[0].b64_json)
    output_path.write_bytes(image_bytes)
    return output_path
