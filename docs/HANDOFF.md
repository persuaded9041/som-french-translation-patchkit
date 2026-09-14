# LATEST DIALOGUE AUDIT CHECKPOINT — 2026-09-14

The 12-batch deep dialogue audit and the subsequent global Android-FR vocative scan are complete. See `docs/DIALOGUE_FULL_AUDIT_CHECKPOINT.md`. The generated dialogue state is 701/701 simulator-clean with 1957 translated carriers. All validated audit fixes are canonicalized and reproducible. The pending `$035F / C9:D1B8` question is resolved: the validated manual surcharge is now `Dryade fera réagir l'orbe !`, while `$0360` remains neutralized.

Current post-audit reproducible artifacts after the validated `$035F` Dryade fix:

- `translations/dialogues_french.json`: `79d1e6f737a7f6393d03dab4af8a31e6697f09c55c27faa8b3ab338070749f45`;
- `patches/french_dialogues.ips`: `75a06c3070aead2cf00931582adfe3684800237e698d38c5caed4286c7789333`;
- `patches/all.ips`: `f1609b97bf6c82b431b64458cee8ee64fd9e33db8aca2057fab70ee921fde83a`.

See `reports/LOT1_TO_FINAL_CORRECTIONS_VERIFICATION.md` for the post-regeneration correction sentinels.

Recipe cleanup (2026-09-14): the eight historical stage-specific dialogue recipe files were consolidated into `recipes/android/dialogues_formatting.json` and `recipes/android/dialogues_review.json`. The active dialogue recipe surface is now four JSON files (alignment, redistribution, formatting, review). Fresh dialogue generation and full IPS builds are byte-identical to the pre-cleanup state. See `reports/RECIPES_CLEANUP.md`.

---

# HANDOFF — Round 85.68 promoted checkpoint

This archive is authoritative over GitHub.

### Recipe hygiene checkpoint (2026-09-14)

After the recipe-file consolidation, a liveness audit removed 15 dead/superseded rule units (3 unmatched mapping-layout recipes, 8 final-layout carriers fully replayed by `review_delta`, 2 late no-op layout/review rules, and 2 superseded reviewed-alignment records). Fresh dialogue generation remains byte-identical (`79d1e6f7…749f45`). Apparent coverage-repair overlaps were tested and retained where removal changes generated dialogue. Details: `reports/RECIPES_CLEANUP.md`.


## Promoted state

Round **85.68** canonizes the entire user-validated review chain from 85.57 through 85.67. There is no longer a split between a promoted 85.56 source state and later review-only JSON. `translations/dialogues_french.json` is again fully reproducible from canonical inputs.

Fresh regeneration SHA-256: `a507bd8b715cef6f6f2d81165c3fab62a2e8c4d27d090cc5b68ddfbb07769728`.

Current dialogue state:

- Android identity: **1798/1838 (97.8%)**;
- **701 events = 701 complete + 0 PARTIEL**;
- **1813 accepted semantic source IDs / 1957 sparse JSON entries**;
- exclusions remain only `$0269`, `$02DE`, `$0603`;
- simulation: **0 errors / 0 warnings / 0 implicit wraps**.

## What Round 85.68 promotes

- validated batches 85.57-85.65 (choice geometry, quotes, local wrapping, rewards/status presentation, `$04E2/$04E8/$07FD`, full `$0429`, full `$0555`);
- validated Round-85.66 `$04E1` structural repair;
- `$05F8` audit: the `pour venir chercher l'Épée.` tail was already present in serialized bytes; the missing preview was a simulator snapshot bug, now fixed;
- caller/context findings for `$0358/$035F/$07FA/$07FB`; `$035F/C9:D1B8` is now the full validated message `Dryade fera réagir l'orbe !`;
- global Android-FR completeness audit and the three recovered source-backed omissions: `$0399 <- 1897`, `$04E4 <- 1373`, `$0511 <- 1988`.

## Canonical recipe architecture

`recipes/android/dialogues_review.json#review_delta` is the late replay layer for the accepted 85.57-85.67 delta. It stores **no localized prose**. It contains only:

- Android-FR IDs for source-backed append operations;
- carrier IDs and generic structural operations (merge/split/clear/punctuation/control);
- reviewed structural-command and choice-coordinate metadata;
- semantic SHA-256 fingerprints plus spaces/newlines/page separators for layout replay.

If Android/source semantics drift, generation fails instead of silently replaying stale layout. The seven review-created carriers retain the exact validated append order so a fresh generator is byte-identical to the accepted review JSON.

## Proofs

`checkpoints/round85_68/` contains generation/build/check logs and the final visual simulator output.

- clean regeneration equals the accepted 85.67 review JSON byte-for-byte;
- all 2048 scripts parse; 713 clean-source dialogue events round-trip exactly;
- manual supplements, redistribution recipes, source hygiene and dialogue regressions pass;
- 701-event simulator: 0 errors, 0 warnings, 0 implicit wraps;
- double fresh build is reproducible.

Promoted IPS hashes:

- `patches/french_dialogues.ips`: `ff5890b9284dc25231fa8b9bbae05f6f43b03c131c91dfe7f2fb1f11259f92c1`
- `patches/all.ips`: `b9ed5221ad54b653aa98713e59b72191cdc9cca668b9b44e9aa4f1f2c44dcfd5`

## Core invariants

Android FR remains the prose source of truth; no hard-coded localized prose in formatter recipes; `WAIT != NEWLINE`; max 3 live lines; <=216 px / <=38 decoded glyphs; 9-character dynamic-name worst case; preserve reviewed choice/highlight geometry and timed controls.

## Next work

Dialogue visual/completeness consolidation is complete. The next planned subject is the **items/objects translation procedure**, beginning with design/discussion before changing translation data. Do not reopen validated dialogue wording or structure unless a concrete runtime regression is observed.
