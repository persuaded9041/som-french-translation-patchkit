# Round 85.8 — modular dialogue pipeline

This checkpoint is a behavior-neutral modularization of the Android-derived dialogue generator.

## Changes

- Kept `tools/import_android_text.py` as the stable public CLI entry point.
- Extracted Android source/shared helpers to `tools/dialogue_pipeline/common.py`.
- Extracted reviewed policy constants to `tools/dialogue_pipeline/policies.py`.
- Extracted automatic/reviewed Android↔SNES alignment to `tools/dialogue_pipeline/alignment.py`.
- Extracted structural recipe loading/rendering and manual-supplement helpers to `tools/dialogue_pipeline/recipes.py`.
- Extracted mass formatting, layout repair and simulator gating to `tools/dialogue_pipeline/formatter.py`.
- Updated `check_dialogue_redistribution_recipes.py` to target the recipe module directly.
- Updated source-hygiene checks to scan the complete dialogue pipeline package.

No translated prose was introduced into code or recipes. `dialogues_french.json` remains an output only. Existing CLI commands are unchanged.

## Validation contract

Round 85.8 is acceptable only if intro, alignment, mass-format outputs, dialogue regressions, recipe provenance, manual supplements, all-event round-trip and rebuilt patches remain identical to the Round 85.7 baseline.
