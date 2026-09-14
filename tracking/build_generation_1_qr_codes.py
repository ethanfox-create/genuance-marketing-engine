"""
Demo / smoke-test for Stage 2.

Loads the Generation 1 catalogue (built in Stage 1), generates a QR code
for every (design, location) combination, writes a manifest, and
demonstrates overlaying one QR code onto a placeholder poster image.

Run it with:
    python tracking/build_generation_1_qr_codes.py
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# genotype/ and tracking/ are sibling folders, not a single installed
# package -- Python only auto-adds *this script's own* folder to its
# module search path (sys.path), not its siblings. So to import
# catalogue.py from genotype/, we add that folder to sys.path ourselves
# before importing from it.
sys.path.insert(0, str(PROJECT_ROOT / "genotype"))

from catalogue import load_catalogue  # noqa: E402
from locations import active_location_codes  # noqa: E402
from qr_generator import generate_qr_codes_for_catalogue, overlay_qr_on_image  # noqa: E402
from PIL import Image  # noqa: E402

QR_OUTPUT_DIR = PROJECT_ROOT / "data" / "qr_codes"
MANIFEST_PATH = PROJECT_ROOT / "data" / "qr_manifest.json"


def main() -> None:
    catalogue = load_catalogue()
    if not catalogue:
        print("Catalogue is empty -- run genotype/build_generation_1.py first.")
        return

    locations = active_location_codes()
    if not locations:
        print("No active locations -- add some with tracking/locations.py's add_location() first.")
        return

    manifest = generate_qr_codes_for_catalogue(catalogue, locations, QR_OUTPUT_DIR)

    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(
        f"Generated {len(manifest)} QR codes "
        f"({len(catalogue)} design(s) x {len(locations)} location(s))."
    )
    print(f"Images saved to: {QR_OUTPUT_DIR}")
    print(f"Manifest saved to: {MANIFEST_PATH}")

    # Prove the overlay utility works, using a blank canvas as a stand-in
    # poster until Stage 3 has real templates.
    placeholder_poster = QR_OUTPUT_DIR / "_placeholder_poster.png"
    Image.new("RGBA", (1000, 1400), "white").save(placeholder_poster)

    first = manifest[0]
    overlay_path = QR_OUTPUT_DIR / "_placeholder_overlay_demo.png"
    overlay_qr_on_image(
        base_image_path=placeholder_poster,
        qr_image_path=first["qr_image_path"],
        output_path=overlay_path,
        position=(700, 1100),
        qr_size=(250, 250),
    )
    print(f"Overlay demo saved to: {overlay_path}")


if __name__ == "__main__":
    main()
