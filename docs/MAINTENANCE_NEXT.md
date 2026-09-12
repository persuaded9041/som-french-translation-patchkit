# Round 85 maintenance target — performance and repository simplification

This document is a short working index for the next maintenance session. `docs/HANDOFF.md` remains
the authoritative state description.

## Baseline

- Approximate file count before Round-85 cleanup: 327 files.
- `mappings/android/` top-level files: 74.
- Dialogue mass pass is CPU-bound enough to make normal iteration expensive and appears effectively
  single-core on the user's i5-10600K (6C/12T).
- Canonical output must stay deterministic; performance work must not change semantic decisions or
  serialized output.

## Performance acceptance criteria

Record a serial baseline first. For every optimization, compare:

- wall-clock time;
- peak memory if practical;
- `translations/dialogues_french.json` hash;
- `mappings/android/dialogues_format_mass.json` hash/content;
- accepted/excluded counts and simulator defects;
- regression-checker results.

Prefer cache/memoization when repeated pure computations dominate. If event-level work is independent,
use process-based parallelism rather than threads for CPU-bound Python. Expose worker count explicitly,
keep a serial mode, preserve deterministic collection/sorting, and benchmark 4–6 workers first.

## Repository-cleanup acceptance criteria

Classify each candidate as one of:

1. canonical input required to regenerate outputs;
2. canonical generated output/check input;
3. current human-review artifact worth keeping;
4. historical evidence worth moving to `docs/history/` or `mappings/android/history/`;
5. redundant generated artifact safe to delete.

Never infer safety from filename alone: grep/import-reference every candidate family first. Consolidate
round-specific checkers only after their assertions are represented declaratively and the replacement
checker catches intentional negative tests.

The goal is a smaller active surface, not loss of provenance.
