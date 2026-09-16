"""
Demo / smoke-test for Stage 3.

Loads the Generation 1 catalogue (Stage 1) and QR manifest (Stage 2),
generates DALL-E background art for each design, composites the final
posters, and saves them to data/posters/.

Checks for OPENAI_API_KEY up front and exits with setup instructions if
it's missing, rather than failing partway through a batch and leaving a
half-finished set of posters.

Run it with:
    python generation/build_generation_1_posters.py
"""

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# genotype/ is a sibling folder, not part of a shared package -- add it to
# sys.path so `from catalogue import ...` can find it (same pattern used in
# tracking/build_generation_1_qr_codes.py for Stage 2).
sys.path.insert(0, str(PROJECT_ROOT / "genotype"))

from catalogue import load_catalogue  # noqa: E402
from pipeline import build_posters  # noqa: E402

QR_MANIFEST_PATH = PROJECT_ROOT / "data" / "qr_manifest.json"


def main() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        print(
            "OPENAI_API_KEY is not set -- nothing to run yet.\n\n"
            "Once you have a key from platform.openai.com:\n"
            "  PowerShell:  $env:OPENAI_API_KEY = 'sk-...'\n"
            "  bash:        export OPENAI_API_KEY='sk-...'\n\n"
            "then re-run this script."
        )
        return

    catalogue = load_catalogue()
    if not catalogue:
        print("Catalogue is empty -- run genotype/build_generation_1.py first.")
        return

    if not QR_MANIFEST_PATH.exists():
        print("No QR manifest found -- run tracking/build_generation_1_qr_codes.py first.")
        return

    with open(QR_MANIFEST_PATH, "r", encoding="utf-8") as f:
        qr_manifest = json.load(f)

    result = build_posters(catalogue, qr_manifest)
    posters = result["posters"]
    failed_designs = result["failed_designs"]

    print(f"\nGenerated {len(posters)} poster(s) in {PROJECT_ROOT / 'data' / 'posters'}")
    if failed_designs:
        print(f"{len(failed_designs)} design(s) failed and were skipped:")
        for design_id, error in failed_designs.items():
            print(f"  {design_id}: {error}")


if __name__ == "__main__":
    main()
