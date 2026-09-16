"""
Stage 7, Tier 1: automated technical checks.

Runs before any human or AI reviews a poster: catches broken files,
under-resolution images, and QR codes that don't actually scan. These are
objective pass/fail checks, unlike Tier 2's judgment call.
"""

import sys
from pathlib import Path

import cv2
from PIL import Image, UnidentifiedImageError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "generation"))
from poster_composer import compute_qr_card_geometry  # noqa: E402

# Minimum pixel dimensions per format, at 85 DPI -- calibrated for the
# real requirement (clearly readable at 5-7 feet, a lamp-post poster
# viewing distance), not close-up print quality. Common viewing-distance
# DPI guidelines put 5-7ft in the 70-100 DPI range; 85 is a reasonable
# middle of that band. This replaces an earlier, stricter 150 DPI
# (magazine/handheld distance) that this project's actual use case never
# needed. Physical sizes are approximate, since the genotype schema
# doesn't pin down exact mm/inch dimensions per format value -- only the
# label.
FORMAT_MIN_RESOLUTION = {
    "a3_poster": (995, 1403),  # 297x420mm
    "a4_poster": (706, 995),  # 210x297mm
    "large_sticker": (340, 510),  # approx 100x150mm
    "small_sticker": (200, 310),  # approx 60x90mm, business-card-ish
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


def check_qr_readable(image_path: Path, expected_url: str, qr_placement: str | None = None) -> dict:
    """
    Re-scan the QR code baked into the final poster and confirm it decodes
    to the URL it's supposed to. Catches QR codes that got corrupted,
    obscured, or scaled unreadably small during compositing -- a QR code
    that "looks right" but doesn't actually scan is a broken poster.

    When qr_placement is given, this first crops to the exact region
    poster_composer.py placed the QR card in (via the same
    compute_qr_card_geometry() the compositor uses) before decoding,
    rather than searching the whole poster. This matters: verified that
    OpenCV's QRCodeDetector can fail to locate a small, genuinely-scannable
    QR code within a large, busy full poster image, even though the exact
    same code decodes correctly the instant it's cropped down -- a false
    negative from the detector's search step, not a real defect. A phone
    scanning a physical poster is effectively always "cropped in" close to
    the code, so checking the known region matches real-world scanning
    conditions better than a blind full-image search. Falls back to a
    full-image scan if the cropped attempt doesn't decode, so a QR that's
    genuinely misplaced (geometry mismatch, bug elsewhere) still gets caught.
    """
    image = cv2.imread(str(image_path))
    if image is None:
        return {"passed": False, "detail": "could not load image for QR scan"}

    detector = cv2.QRCodeDetector()
    decoded_text = ""

    if qr_placement:
        height, width = image.shape[:2]
        geometry = compute_qr_card_geometry(width, height, qr_placement)
        pad = int(geometry["card_size"] * 0.25)  # a little slack around the card for detector tolerance
        x0 = max(0, geometry["card_x"] - pad)
        y0 = max(0, geometry["card_y"] - pad)
        x1 = min(width, geometry["card_x"] + geometry["card_size"] + pad)
        y1 = min(height, geometry["card_y"] + geometry["card_size"] + pad)
        crop = image[y0:y1, x0:x1]
        decoded_text, _points, _ = detector.detectAndDecode(crop)

    if not decoded_text:
        decoded_text, _points, _ = detector.detectAndDecode(image)  # fall back to a full-image search

    if not decoded_text:
        return {"passed": False, "detail": "no QR code detected in image"}
    if decoded_text != expected_url:
        return {"passed": False, "detail": f"QR decodes to {decoded_text!r}, expected {expected_url!r}"}
    return {"passed": True, "detail": "ok"}


def run_tier1_checks(image_path: Path, format_value: str, expected_url: str, qr_placement: str | None = None) -> dict:
    """Run all Tier 1 checks and return a combined result."""
    checks = {
        "file_integrity": check_file_integrity(image_path),
        "resolution": check_resolution(image_path, format_value),
        "qr_readable": check_qr_readable(image_path, expected_url, qr_placement),
    }
    passed = all(c["passed"] for c in checks.values())
    return {"passed": passed, "checks": checks}
