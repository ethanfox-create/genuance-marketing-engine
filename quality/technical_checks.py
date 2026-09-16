"""
Stage 7, Tier 1: automated technical checks.

Runs before any human or AI reviews a poster: catches broken files,
under-resolution images, and QR codes that don't actually scan. These are
objective pass/fail checks, unlike Tier 2's judgment call.
"""

from pathlib import Path

import cv2
from PIL import Image, UnidentifiedImageError

# Minimum pixel dimensions per format, at 150 DPI -- a common minimum for
# posters viewed from a short distance (not the stricter 300 DPI standard
# for close-up print like magazines). Physical sizes are approximate,
# since the genotype schema doesn't pin down exact mm/inch dimensions per
# format value -- only the label.
FORMAT_MIN_RESOLUTION = {
    "a3_poster": (1754, 2480),  # 297x420mm
    "a4_poster": (1240, 1754),  # 210x297mm
    "large_sticker": (600, 900),  # approx 100x150mm
    "small_sticker": (350, 550),  # approx 60x90mm, business-card-ish
}


def check_file_integrity(image_path: Path) -> dict:
    """Confirm the file exists and is a valid, non-corrupt image."""
    image_path = Path(image_path)
    if not image_path.exists():
        return {"passed": False, "detail": "file does not exist"}
    try:
        with Image.open(image_path) as img:
            img.verify()
        return {"passed": True, "detail": "ok"}
    except (UnidentifiedImageError, OSError) as exc:
        return {"passed": False, "detail": f"corrupt or unreadable image: {exc}"}


def check_resolution(image_path: Path, format_value: str) -> dict:
    """Confirm the image meets the minimum pixel dimensions for its physical format."""
    min_w, min_h = FORMAT_MIN_RESOLUTION.get(format_value, (0, 0))
    with Image.open(image_path) as img:
        width, height = img.size

    passed = width >= min_w and height >= min_h
    detail = f"{width}x{height}px, needs at least {min_w}x{min_h}px for {format_value}"
    return {"passed": passed, "detail": detail}


def check_qr_readable(image_path: Path, expected_url: str) -> dict:
    """
    Re-scan the QR code baked into the final poster and confirm it decodes
    to the URL it's supposed to. Catches QR codes that got corrupted,
    obscured, or scaled unreadably small during compositing -- a QR code
    that "looks right" but doesn't actually scan is a broken poster.
    """
    image = cv2.imread(str(image_path))
    if image is None:
        return {"passed": False, "detail": "could not load image for QR scan"}

    detector = cv2.QRCodeDetector()
    decoded_text, _points, _ = detector.detectAndDecode(image)

    if not decoded_text:
        return {"passed": False, "detail": "no QR code detected in image"}
    if decoded_text != expected_url:
        return {"passed": False, "detail": f"QR decodes to {decoded_text!r}, expected {expected_url!r}"}
    return {"passed": True, "detail": "ok"}


def run_tier1_checks(image_path: Path, format_value: str, expected_url: str) -> dict:
    """Run all Tier 1 checks and return a combined result."""
    checks = {
        "file_integrity": check_file_integrity(image_path),
        "resolution": check_resolution(image_path, format_value),
        "qr_readable": check_qr_readable(image_path, expected_url),
    }
    passed = all(c["passed"] for c in checks.values())
    return {"passed": passed, "checks": checks}
