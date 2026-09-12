# Round 85.10 — second conservative dialogue optimization pass

Round 85.10 profiles the already-optimized Round 85.9 pipeline again and retains only local, deterministic changes that improve repeated work without changing provenance, algorithms, simulator acceptance, or serialized outputs.

## Retained changes

### Session-local span preparation

The dynamic-programming aligner reused the same one-to-three-element SNES spans across many Android positions and the same Android spans across many SNES positions, but reconstructed those strings each time. Each short structural span is now prepared once per session. The DP transitions and scoring are unchanged.

### Candidate ranking reuse

`_AutoCandidateIndex` is immutable for one alignment run. Rankings for an identical normalized source and `limit` are now reused within that index. Returned lists are copied so callers cannot share mutable list state.

### Prepared positional-neighborhood evidence

The equivalent-duplicate and isolated-event positional rules repeatedly flattened the same frozen accepted-record context for each target. Each pass now prepares that immutable context once; target-specific distance filtering, ordering, scoring, margins and emitted evidence are unchanged.

### Normalized lexical-metric cache

Lexical metrics are mathematically defined on normalized strings. Their cache is now keyed by those normalized forms rather than raw strings. Hot paths that already hold normalized source/candidate values call this helper directly instead of normalizing the same values again.

### Consistent prepared formatter index

Round 85.9 introduced a private prepared index for the immutable source document. A few formatter-local helpers still called the public uncached `event_text_index()` directly. Formatter internals now consistently use the prepared index; the public helper remains unchanged for external extraction/checking callers.

## Explicit non-changes

- No Android/SNES identity, recipe, translation or layout policy changed.
- No generated output is used as an input/cache dependency.
- No simulator rule or state machine changed.
- No multiprocessing was added.
- No hardcoded Android-derived prose was introduced.

The remaining simulator hotspot was inspected but deliberately left untouched: making line-fit metrics incremental would couple more mutable state to the simulator and is not justified by the remaining runtime.

## Measurements

Round 85.9 reference: about **6.9–7.1 s** in this environment.

Round 85.10 mass `--check` runs:

- 5.722 s
- 5.778 s
- 5.862 s
- 5.768 s
- 5.838 s

Median: **5.778 s**.

Strict from-scratch generation with `translations/dialogues_french.json` physically absent: **5.64 s**.

## Reproducibility proof

The following remain byte-identical to Round 85.9:

- `mappings/android/dialogues_auto.json`
- `mappings/android/dialogues_unmapped.csv`
- `translations/dialogues_french.json`
- `mappings/android/dialogues_format_mass.json`
- `mappings/android/dialogues_format_mass_excluded.csv`
- all 14 component IPS files and `patches/all.ips`

`dialogues_french.json` remains 264,463 bytes with SHA-256 `bcc26f2c6fe137e64a80644fcead4c7b50a00f881748236ed8323f68bba465da`.

`patches/all.ips` remains SHA-256 `ccfcc93a2d7c5dd60eb883496313b5f2f9634cf07ae70deededac4e9fcef7092`; final ROM checksum remains `$84C5`.
