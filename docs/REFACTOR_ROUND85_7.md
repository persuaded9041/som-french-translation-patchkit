# Round 85.7 — dialogue-generation refactor

This checkpoint is intentionally a refactor/simplification pass, not a translation or layout-content pass.

## Changes

- Moved 406 user-reviewed alignment records out of `tools/import_android_text.py` into `mappings/android/dialogues_reviewed_alignment_recipes.json`.
- Removed the executable `DIALOGUE_PILOT_SCENES` / `DIALOGUE_REVIEW_ROUND*` tables from the importer.
- Reviewed identity recipes contain SNES carriers / structural `PLAYER_NAME` references, Android IDs and provenance only; translated payload still comes from Android resources at generation time.
- Replaced round-numbered active helper names with semantic names.
- Unified structural recipe document loading/marker validation.
- Unified Android-token rendering for scene redistribution and mapping-local layout recipes.
- Removed orphaned historical comments left behind by earlier cleanup.
- Extended `check_text_source_hygiene.py` to validate the new reviewed-alignment recipe schema and forbid translation payload fields.
- Static call-graph audit: all 133 top-level functions in `import_android_text.py` are reachable from the active CLI.

## Reproducibility

The refactor is byte-neutral:

- `dialogues_auto.json`: byte-identical.
- `dialogues_unmapped.csv`: byte-identical.
- `dialogues_french.json`: byte-identical (SHA-256 `bcc26f2c6fe137e64a80644fcead4c7b50a00f881748236ed8323f68bba465da`).
- `dialogues_format_mass.json`: byte-identical.
- `dialogues_format_mass_excluded.csv`: byte-identical.

No existing generated dialogue JSON is required as an input.
