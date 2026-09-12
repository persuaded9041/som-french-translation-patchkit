# Round 85.5 — dialogue pipeline architecture cleanup

This checkpoint freezes the cleaned dialogue-generation architecture before dedicated performance optimization.

## Provenance contract

- `translations/dialogues_french.json` is a generated output only and is never consumed by dialogue generation.
- French prose is read from the original Android French resource at generation time; Android English remains the identity layer.
- Special mapping/layout cases are represented by structural recipes: Android IDs/token references, SNES carriers, punctuation/case/layout operations and reviewed cut offsets. Recipes must not store translated prose.
- Genuine reviewed non-Android exceptions remain isolated in `translations/dialogues_manual_supplements.json`.

## Cleanup

- historical dialogue pilot/review/batch CLI modes removed;
- obsolete top-level helpers removed from `tools/import_android_text.py`;
- active CLI reduced to `intro`, `dialogue-auto`, and `dialogue-format-mass`;
- legacy round-specific French payloads migrated to structural Android-token recipes;
- orphan `dialogue_preview_state.json` removed;
- mass-format outputs can all be redirected outside the repository for clean verification.

## From-scratch proof

With `translations/dialogues_french.json` physically absent, a full mass generation from Android/SNES sources produced:

- 701 simulator-clean events;
- 1947 translated source tokens;
- 3 validated exclusions;
- 264463-byte `dialogues_french.json`;
- SHA-256 `bcc26f2c6fe137e64a80644fcead4c7b50a00f881748236ed8323f68bba465da`;
- byte-for-byte identity with the accepted baseline;
- measured wall time in the checkpoint environment: 25.22 s.

## Build proof

All 14 component patches rebuild successfully. Combined `patches/all.ips`:

- SHA-256 `ccfcc93a2d7c5dd60eb883496313b5f2f9634cf07ae70deededac4e9fcef7092`;
- final ROM size `0x300000`;
- SNES checksum `$84C5`.

This matches the user-provided clean baseline for this checkpoint.

## Next work

Profile the cleaned canonical `dialogue-format-mass` path. Optimize only measured remaining hotspots, require byte-identical output after every change, and keep serial generation as the reference behavior.
