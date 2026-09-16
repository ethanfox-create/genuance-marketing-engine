"""
Stage 8: orchestration.

Ties Stages 1-7 together into one command that takes a campaign from "we
have real scan data for the current generation" to "here's a folder of
approved, print-ready posters for the next generation, plus a deployment
map telling you which poster goes where."

This is specifically for running generation N -> N+1: it requires real
scan data to already exist for the current generation, because Stage 6's
survivor selection needs real performance evidence to breed from. It is
NOT how you create generation 1 -- that's hand-authored (see
genotype/build_generation_1.py), since there's no prior generation to
learn from yet.

Steps, in order:
  1. Load the catalogue, scan log, and QR manifest.
  2. Compute performance (Stage 5) and confirm there's enough real scan
     data to select survivors from -- refuses to proceed on absent or
     insufficient data rather than silently breeding a generation from
     nothing.
  3. Reproduce (Stage 6): crossover + mutation + exploration -> new
     genotypes for the next generation.
  4. Save the new genotypes to the catalogue.
  5. Generate QR codes (Stage 2) for the new genotypes x active locations,
     appending to the existing manifest.
  6. Generate posters (Stage 3) for the new genotypes -- this calls the
     image API and costs real money.
  7. Run the quality gate (Stage 7) on the new posters.
  8. Copy only APPROVED posters into a deployment-ready folder for this
     generation, and write a deployment map (CSV + JSON) of exactly which
     poster goes to which location. Flagged posters stay out of the
     deployment folder until a human clears them.

Run it with:
    python orchestration/run_cycle.py --generation 2
"""

import argparse
import csv
import json
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
for _subfolder in ("genotype", "tracking", "generation", "analysis", "reproduction", "quality"):
    sys.path.insert(0, str(PROJECT_ROOT / _subfolder))

from catalogue import add_genotype, load_catalogue  # noqa: E402
from locations import active_location_codes  # noqa: E402
from performance import build_design_performance  # noqa: E402
from pipeline import build_posters  # noqa: E402
from qr_generator import generate_qr_codes_for_catalogue  # noqa: E402
from quality_gate import run_quality_gate  # noqa: E402
from reproduce import build_next_generation  # noqa: E402
from scans import load_scans  # noqa: E402

QR_MANIFEST_PATH = PROJECT_ROOT / "data" / "qr_manifest.json"
QR_CODES_DIR = PROJECT_ROOT / "data" / "qr_codes"
DEPLOYMENT_DIR = PROJECT_ROOT / "data" / "deployment_ready"


def load_qr_manifest() -> list[dict]:
    if not QR_MANIFEST_PATH.exists():
        return []
    with open(QR_MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_qr_manifest(manifest: list[dict]) -> None:
    with open(QR_MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def run_cycle(generation: int, min_survivors: int = 2) -> dict:
    """
    Run one full generation-to-generation cycle. Returns a summary dict.
    Raises ValueError if there isn't enough real performance data to
    breed a new generation from yet.
    """
    catalogue = load_catalogue()
    scans = load_scans()
    qr_manifest = load_qr_manifest()

    performance = build_design_performance(catalogue=catalogue, scans=scans, qr_manifest=qr_manifest)
    # A design with QR exposure but zero real scans has scan_rate=0.0, which
    # is NOT null -- so filtering on "scan_rate is not null" alone would let
    # a batch of designs that have never actually been scanned (all tied at
    # 0.0) slip past this gate as if that were real signal. The actual
    # requirement is genuine scan activity: scan_count > 0.
    scanned = performance[performance["scan_count"] > 0]
    if len(scanned) < min_survivors:
        raise ValueError(
            f"Only {len(scanned)} design(s) have actually been scanned (need at least {min_survivors}). "
            "Deploy the current generation, collect real scans via the Stage 4 scan tracker, "
            "then run this again."
        )

    print(f"Breeding generation {generation} from {len(scanned)} scanned design(s)...")
    new_genotypes = build_next_generation(performance, catalogue, generation=generation)

    for genotype in new_genotypes:
        add_genotype(genotype)
    print(f"Added {len(new_genotypes)} new genotype(s) to the catalogue.")

    locations = active_location_codes()
    new_manifest_entries = generate_qr_codes_for_catalogue(new_genotypes, locations, QR_CODES_DIR)
    full_manifest = qr_manifest + new_manifest_entries
    save_qr_manifest(full_manifest)
    print(f"Generated {len(new_manifest_entries)} QR code(s) across {len(locations)} location(s).")

    print("Generating posters (this calls the image API and costs real money)...")
    poster_result = build_posters(new_genotypes, new_manifest_entries)
    posters = poster_result["posters"]
    failed_designs = poster_result["failed_designs"]
    if failed_designs:
        print(f"{len(failed_designs)} design(s) failed image generation and were skipped:")
        for design_id, error in failed_designs.items():
            print(f"  {design_id}: {error}")

    catalogue_by_id = {g["design_id"]: g for g in new_genotypes}
    manifest_by_key = {(e["design_id"], e["location_code"]): e for e in new_manifest_entries}
    quality_results = run_quality_gate(posters, catalogue_by_id, manifest_by_key)

    approved = [r for r in quality_results if r["status"] == "approved"]
    flagged = [r for r in quality_results if r["status"] == "flagged"]
    print(f"Quality gate: {len(approved)} approved, {len(flagged)} flagged for review.")

    generation_dir = DEPLOYMENT_DIR / f"generation_{generation}"
    generation_dir.mkdir(parents=True, exist_ok=True)
    deployment_map = []
    for r in approved:
        genotype = catalogue_by_id[r["design_id"]]
        dest = generation_dir / Path(r["poster_image_path"]).name
        shutil.copy(r["poster_image_path"], dest)
        deployment_map.append(
            {
                "design_id": r["design_id"],
                "location_code": r["location_code"],
                "headline": genotype["headline"],
                "format": genotype["format"],
                "poster_image_path": str(dest),
            }
        )

    map_json_path = generation_dir / "deployment_map.json"
    map_csv_path = generation_dir / "deployment_map.csv"
    map_json_path.write_text(json.dumps(deployment_map, indent=2), encoding="utf-8")
    with open(map_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["design_id", "location_code", "headline", "format", "poster_image_path"]
        )
        writer.writeheader()
        writer.writerows(deployment_map)

    print(f"\n{len(deployment_map)} print-ready poster(s) in {generation_dir}")
    print(f"Deployment map: {map_csv_path}")

    return {
        "new_genotypes": new_genotypes,
        "posters": posters,
        "failed_designs": failed_designs,
        "quality_results": quality_results,
        "deployment_map": deployment_map,
        "generation_dir": str(generation_dir),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one generation-to-generation cycle of the marketing engine.")
    parser.add_argument("--generation", type=int, required=True, help="The generation number being produced (e.g. 2).")
    args = parser.parse_args()

    try:
        run_cycle(args.generation)
    except ValueError as exc:
        print(f"Cannot run cycle: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
