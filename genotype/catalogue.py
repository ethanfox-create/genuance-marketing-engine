"""
The catalogue: a JSON file on disk that stores every genotype record ever
created, across every generation. This is the system's persistent memory
of what's been designed -- Stage 5 (analysis) reads it to see which
attribute values performed well, and Stage 6 (reproduction) reads it to
pick survivors.

We're using a plain JSON file rather than a database like SQLite for now:
a genotype record is just a dictionary, a list of them is just a list of
dictionaries, and json.dump / json.load handle converting that straight
to and from a text file. That's the whole "database" at this stage.
"""

import json
from pathlib import Path

# Path(__file__) is this file's own location. .parent goes up one directory
# (from genotype/ to the project root), then back down into data/. Building
# the path this way means the script works no matter what folder you run it
# from.
DEFAULT_CATALOGUE_PATH = Path(__file__).resolve().parent.parent / "data" / "catalogue.json"


def load_catalogue(path: Path = DEFAULT_CATALOGUE_PATH) -> list[dict]:
    """Return the list of genotype records stored on disk (empty list if none yet)."""
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_catalogue(catalogue: list[dict], path: Path = DEFAULT_CATALOGUE_PATH) -> None:
    """Write the full list of genotype records to disk, pretty-printed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(catalogue, f, indent=2)


def add_genotype(genotype: dict, path: Path = DEFAULT_CATALOGUE_PATH) -> list[dict]:
    """Append one genotype record to the catalogue on disk and return the updated catalogue."""
    catalogue = load_catalogue(path)
    catalogue.append(genotype)
    save_catalogue(catalogue, path)
    return catalogue
