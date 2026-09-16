"""
Stage 6: reproduction pipeline.

Takes Stage 5's performance data, selects survivors, and generates the
next generation's genotypes via crossover, mutation, and exploration --
the three operations described in CLAUDE.md's "Generation 2" section.

A design question worth stating up front: crossover and mutation are only
cleanly defined for genotype fields with a fixed set of legal values (the
"enum" fields in GENOTYPE_SCHEMA). headline, subtext, call_to_action, and
audience_hypothesis are free text -- there's no list of valid values to
randomly draw a mutation from, and CLAUDE.md itself says these fields'
content is "to be written per generation," implying a writing step, not a
randomization step. So:

  - crossover() copies each field -- enum AND free-text alike -- wholesale
    from one parent or the other. This matches CLAUDE.md's definition
    exactly ("some fields from one parent, some from the other") and
    needs no text generation, since it only ever reuses real copy a human
    already wrote for one of the two parents.
  - mutate() only touches enum fields, swapping one to a different legal
    value. Free-text fields are left as inherited from the parent --
    "mutating" a headline into new coherent text is a creative-writing
    task, not something `random.choice` can do meaningfully. A future
    version could call an LLM to write fresh copy for a mutated genotype's
    changed attributes; that's out of scope here.
  - explore() draws enum field values uniformly at random from the schema
    (true "no reference to survivors" randomness). For free-text fields,
    since fabricating new copy from nothing isn't something this module
    can do without an LLM call either, it draws from the full historical
    catalogue instead (not filtered to survivors) -- reusing real written
    copy in a new combination, rather than inventing placeholder text.
"""

import random
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "genotype"))

from schema import GENOTYPE_SCHEMA, create_genotype  # noqa: E402

ENUM_FIELDS = [field for field, spec in GENOTYPE_SCHEMA.items() if spec["type"] == "enum"]
TEXT_FIELDS = [field for field, spec in GENOTYPE_SCHEMA.items() if spec["type"] == "text"]

# Hyperparameters -- settings that shape how the algorithm behaves, not
# facts about the genotype schema itself. Tune these between generations
# based on how much you want to exploit known winners vs. keep exploring.
SURVIVOR_COUNT = 3
CROSSOVER_COUNT = 4
MUTATION_COUNT = 3
EXPLORATION_COUNT = 2
MUTATIONS_PER_CHILD = 1


def select_survivors(performance, top_n: int = SURVIVOR_COUNT) -> list[dict]:
    """
    Pick the top_n performing designs by scan_rate, restricted to designs
    that actually had exposure (a QR code out in the field) -- a design
    with no scan_rate has no evidence behind it and shouldn't be treated
    as a winner just because it's absent from the bottom of the list.

    `performance` is the DataFrame from analysis/performance.py's
    build_design_performance(). Returns plain genotype field dicts (just
    the GENOTYPE_SCHEMA keys, no design_id/generation/created_at metadata)
    so they're ready to feed into crossover/mutate/create_genotype.
    """
    rated = performance.dropna(subset=["scan_rate"]).sort_values("scan_rate", ascending=False)
    survivors = rated.head(top_n)
    schema_fields = list(GENOTYPE_SCHEMA.keys())
    return survivors[schema_fields].to_dict("records")


def crossover(parent_a: dict, parent_b: dict) -> dict:
    """Combine two parent genotypes field by field, each field a 50/50 coin flip between parents."""
    return {field: random.choice([parent_a[field], parent_b[field]]) for field in GENOTYPE_SCHEMA}


def mutate(genotype: dict, n_mutations: int = MUTATIONS_PER_CHILD) -> dict:
    """
    Return a copy of `genotype` with n_mutations enum fields changed to a
    different legal value. Free-text fields are left untouched -- see
    module docstring.
    """
    mutated = dict(genotype)
    fields_to_mutate = random.sample(ENUM_FIELDS, k=min(n_mutations, len(ENUM_FIELDS)))

    for field in fields_to_mutate:
        current_value = mutated[field]
        alternatives = [v for v in GENOTYPE_SCHEMA[field]["values"] if v != current_value]
        mutated[field] = random.choice(alternatives)

    return mutated


def explore(catalogue: list[dict]) -> dict:
    """
    Build a genotype with no reference to survivors: enum fields drawn
    uniformly at random from the schema, free-text fields drawn from the
    full historical catalogue (reusing real written copy, since inventing
    new copy isn't something this module does -- see module docstring).
    """
    genotype = {field: random.choice(spec["values"]) for field, spec in GENOTYPE_SCHEMA.items() if spec["type"] == "enum"}

    for field in TEXT_FIELDS:
        candidates = [design[field] for design in catalogue if design.get(field)]
        genotype[field] = random.choice(candidates) if candidates else "TBD -- write new copy for this generation"

    return genotype


def build_next_generation(
    performance,
    catalogue: list[dict],
    generation: int,
    survivor_count: int = SURVIVOR_COUNT,
    crossover_count: int = CROSSOVER_COUNT,
    mutation_count: int = MUTATION_COUNT,
    exploration_count: int = EXPLORATION_COUNT,
) -> list[dict]:
    """
    Run the full reproduction step: select survivors, then produce
    crossover_count crossover children, mutation_count mutated children,
    and exploration_count fully-random children. Every child is passed
    through create_genotype() to get a fresh, validated record (new
    design_id, generation number, timestamp).

    Returns the new generation's genotype records -- not yet saved to the
    catalogue; the caller decides whether/when to persist them (Stage 1's
    add_genotype()), same as Stage 1's own demo scripts do.
    """
    survivors = select_survivors(performance, top_n=survivor_count)
    if len(survivors) < 2:
        raise ValueError(
            f"Only {len(survivors)} survivor(s) with scan data -- need at least 2 to run crossover. "
            "Run this after real scan data exists for at least 2 designs."
        )

    new_generation = []

    for _ in range(crossover_count):
        parent_a, parent_b = random.sample(survivors, k=2)
        child_fields = crossover(parent_a, parent_b)
        new_generation.append(create_genotype(generation, **child_fields))

    for _ in range(mutation_count):
        base = random.choice(survivors)
        child_fields = mutate(base)
        new_generation.append(create_genotype(generation, **child_fields))

    for _ in range(exploration_count):
        child_fields = explore(catalogue)
        new_generation.append(create_genotype(generation, **child_fields))

    return new_generation
