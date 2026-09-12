# Round 85.3 maintenance target — simplify before optimizing

`docs/HANDOFF.md` is the authoritative operational state. Repository cleanup is checkpointed in
`docs/CLEANUP_ROUND85_3.md`.

## Current repository policy

- `artifacts/` is gone; one-off reports should be generated outside the repository.
- historical round review HTML/CSV/JSON snapshots are not active inputs.
- `mappings/android/` should contain only structural recipes, generated data still needed by
  current guardrails, and small persistent review state.
- `translations/dialogues_french.json` is a generated output, never a source/cache dependency.
- `patches/` remains versioned for now because stored component IPS files are still an intentional
  `build.py --combine` workflow.

## Next step: simplify dialogue import/generation

Before performance changes, inventory the active `import_android_text.py` modes and dataflow.
Classify every file touched by `dialogue-auto` and `dialogue-format-mass` as:

1. canonical source/input;
2. structural human-reviewed recipe;
3. optional reproducible cache;
4. final generated output/report.

Remove or isolate legacy pilot/review code that no longer participates in current generation.
A clean run must regenerate `dialogues_french.json` without reading an older copy.

## Then optimize

Profile the simplified path. Prefer eliminating redundant work and memoizing pure repeated
computations before parallelism. If coarse event-local work remains CPU-bound, benchmark explicit
`--jobs N` process parallelism on the target i5-10600K starting around 4–6 workers. Serial and
parallel output must be byte-identical and deterministically ordered.
