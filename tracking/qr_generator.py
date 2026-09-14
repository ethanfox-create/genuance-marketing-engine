"""
Stage 2: QR code generator.

Takes a genotype record (from the Stage 1 catalogue) and a location code,
builds a unique tracking URL that encodes both, and renders that URL as a
QR code image. Also provides a utility to overlay a QR code onto a poster
image, which Stage 3 will call once real poster templates exist.

The tracking URL points at a scan-tracking server (Stage 4) that doesn't
exist yet -- BASE_TRACKING_URL below is a placeholder. Nothing will
actually resolve in a browser until Stage 4 is built and deployed and a
real domain is wired in. That's expected at this point; see the
dependency table in CLAUDE.md.
"""

from pathlib import Path

import qrcode
from PIL import Image

# Placeholder until Stage 4 (scan tracker) is deployed and a domain is
# chosen. IMPORTANT: once you print QR codes with a given base URL, every
# one of those physical posters is locked to that URL forever -- you can't
# edit a printed poster. Get this right before your first live print run,
# not after.
BASE_TRACKING_URL = "https://track.prowler.example/s"


def build_tracking_url(design_id: str, location_code: str, base_url: str = BASE_TRACKING_URL) -> str:
    """
    Build the URL a printed QR code will encode.

    Path-based (not query-string), e.g.:
        https://track.prowler.example/s/gen1-20b2d3fc/loc001

    Stage 4's server will parse this path to know exactly which design, in
    which location, produced the scan -- log it, then redirect the visitor
    to Prowler's landing page or app store listing.
    """
    return f"{base_url.rstrip('/')}/{design_id}/{location_code}"


def generate_qr_code(url: str, output_path: Path) -> Path:
    """Render `url` as a QR code PNG and save it to output_path."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    image = qrcode.make(url)
    image.save(output_path)
    return output_path


def generate_qr_codes_for_catalogue(
    catalogue: list[dict],
    location_codes: list[str],
    output_dir: Path,
    base_url: str = BASE_TRACKING_URL,
) -> list[dict]:
    """
    For every (design, location) pair, build a tracking URL and render its
    QR code as a PNG.

    Returns a manifest: a list of dicts, one per QR code, recording
    everything Stage 3 (poster overlay) and Stage 5 (analysis) need to look
    the code back up -- design_id, location_code, the URL it encodes, and
    where the PNG file lives on disk.
    """
    output_dir = Path(output_dir)
    manifest = []

    for genotype in catalogue:
        design_id = genotype["design_id"]
        for location_code in location_codes:
            url = build_tracking_url(design_id, location_code, base_url)
            filename = f"{design_id}_{location_code}.png"
            path = generate_qr_code(url, output_dir / filename)
            manifest.append(
                {
                    "design_id": design_id,
                    "location_code": location_code,
                    "url": url,
                    "qr_image_path": str(path),
                }
            )

    return manifest


def overlay_qr_on_image(
    base_image_path: Path,
    qr_image_path: Path,
    output_path: Path,
    position: tuple[int, int],
    qr_size: tuple[int, int] | None = None,
) -> Path:
    """
    Paste a QR code onto a poster image and save the result.

    position -- (x, y) pixel coordinates for the QR code's top-left corner.
    qr_size  -- optional (width, height) in pixels to resize the QR code to
                before pasting; omit to paste it at its native size.

    Stage 3 will call this once real poster templates and layout
    coordinates exist -- the genotype's qr_placement value ("bottom_right",
    "bottom_centre", "integrated", "dominant_centre") determines what
    position to pass in.
    """
    base_image_path = Path(base_image_path)
    qr_image_path = Path(qr_image_path)
    output_path = Path(output_path)

    base = Image.open(base_image_path).convert("RGBA")
    qr = Image.open(qr_image_path).convert("RGBA")

    if qr_size is not None:
        qr = qr.resize(qr_size)

    # The third argument reuses the QR image itself as the paste mask, so
    # its transparent pixels (there are none here, but there would be for
    # any image with an alpha channel) stay transparent in the result.
    base.paste(qr, position, qr)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    base.save(output_path)
    return output_path
