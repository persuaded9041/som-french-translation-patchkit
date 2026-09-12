# Round 85.8 — modular dialogue pipeline

This checkpoint is a behavior-neutral modularization of the Android-derived dialogue generator.

## Changes

- Kept `tools/dialogue/import_android.py` as the stable public CLI entry point.
- Extracted Android source/shared helpers to `shared/dialogue/pipeline/common.py`.
- Extracted reviewed policy constants to `shared/dialogue/pipeline/policies.py`.
- Extracted automatic/reviewed Android↔SNES alignment to `shared/dialogue/pipeline/alignment.py`.
- Extracted structural recipe loading/rendering and manual-supplement helpers to `shared/dialogue/pipeline/recipes.py`.
- Extracted mass formatting, layout repair and simulator gating to `shared/dialogue/pipeline/formatter.py`.
- Updated `check_dialogue_redistribution_recipes.py` to target the recipe module directly.
- Updated source-hygiene checks to scan the complete dialogue pipeline package.

No translated prose was introduced into code or recipes. `dialogues_french.json` remains an output only. Existing CLI commands are unchanged.

## Validation contract

Round 85.8 is acceptable only if intro, alignment, mass-format outputs, dialogue regressions, recipe provenance, manual supplements, all-event round-trip and rebuilt patches remain identical to the Round 85.7 baseline.
