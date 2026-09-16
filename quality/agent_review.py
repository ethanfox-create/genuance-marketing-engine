"""
Stage 7, Tier 2: agent-based screening.

Sends a poster image to Claude and asks it to judge whether the design is
usable -- not a technical check (Tier 1 already covers that), but a
judgment call: is the text legible, does the composition look broken or
glitchy, is there anything inappropriate for public street advertising.

Requires an ANTHROPIC_API_KEY environment variable -- a real, billed API
key, separate from the Claude Code subscription this session runs on (see
CLAUDE.md's Tools and Accounts Needed). If it's not set, review_poster()
returns a clear "not configured" result rather than crashing or silently
approving -- the same graceful-degradation pattern used for
OPENAI_API_KEY in generation/dalle_client.py.
"""

import base64
import json
import os
from pathlib import Path

from anthropic import Anthropic

MODEL = "claude-haiku-4-5-20251001"  # cheap and fast is appropriate for a screening pass, not final judgment

REVIEW_PROMPT = """You are screening a street-poster advertisement before it goes to print. \
Look at the attached image and answer only with a JSON object, no other text, in this exact shape:

{"usable": true or false, "concerns": ["short phrase", ...], "notes": "one sentence summary"}

Flag usable=false if: any text is illegible, garbled, or cut off; the image looks visually broken, \
glitchy, or has obvious AI-generation artifacts (extra limbs, warped faces, nonsense shapes); the QR \
code area looks obscured or unreadable; or the content is inappropriate for public outdoor advertising \
(nudity, graphic content). Being provocative or flirtatious in a tasteful way for a dating app is fine \
and should NOT be flagged. If it looks like a normal, usable advertisement, usable=true with an empty \
concerns list."""


def _strip_markdown_fence(text: str) -> str:
    """
    Strip a ```json ... ``` or ``` ... ``` code fence if the model wrapped
    its answer in one, despite the prompt asking for JSON only -- this is
    common enough LLM behavior that it's worth handling rather than
    treating every fenced response as a parse failure.
    """
    text = text.strip()
    if text.startswith("```"):
        text = text[3:]
        if text.startswith("json"):
            text = text[4:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    return text


def _client() -> Anthropic | None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    return Anthropic(api_key=api_key)


def review_poster(image_path: Path) -> dict:
    """
    Ask Claude to evaluate one poster image. Returns
    {"configured": bool, "usable": bool|None, "concerns": [...], "notes": str}.
    configured=False (with usable=None) means ANTHROPIC_API_KEY isn't set --
    the caller should treat that design as needing human review, not as
    having silently passed.
    """
    client = _client()
    if client is None:
        return {
            "configured": False,
            "usable": None,
            "concerns": [],
            "notes": (
                "ANTHROPIC_API_KEY is not set -- agent screening skipped. "
                "Set that environment variable to enable Tier 2 review."
            ),
        }

    image_path = Path(image_path)
    image_b64 = base64.b64encode(image_path.read_bytes()).decode("utf-8")

    response = client.messages.create(
        model=MODEL,
        max_tokens=300,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/png", "data": image_b64},
                    },
                    {"type": "text", "text": REVIEW_PROMPT},
                ],
            }
        ],
    )

    raw_text = response.content[0].text
    try:
        result = json.loads(_strip_markdown_fence(raw_text))
    except json.JSONDecodeError:
        return {
            "configured": True,
            "usable": None,
            "concerns": ["agent response was not valid JSON"],
            "notes": raw_text[:200],
        }

    return {
        "configured": True,
        "usable": result.get("usable"),
        "concerns": result.get("concerns", []),
        "notes": result.get("notes", ""),
    }
