# Dialogue full-audit checkpoint — 2026-09-14

This checkpoint follows the 12-batch deep dialogue audit plus a dedicated global Android-FR dynamic-name/vocative scan.

## Scope

Every one of the 701 playable dialogue events was reviewed in batches against:

- the aligned Android EN identity layer;
- canonical Android FR (`sources/android/scrtxt_fr.bin`);
- the final generated SNES translation carriers;
- the clean-USA event token stream and calls/branches;
- the independent dialogue simulator.

A second global pass specifically searched for Android-FR `%S(n,0)` dynamic names that historical formatting policy had removed when no equivalent SNES/Android-EN `PLAYER_NAME` existed.

## Final state

- 701/701 playable events simulator-clean.
- 0 errors.
- 0 warnings.
- 0 implicit runtime wraps.
- 1957 translated source carriers.
- Android alignment identity unchanged at 1798/1838.
- 3 historical exclusions unchanged (`$0269`, `$02DE`, `$0603`).
- 302 active redistribution carriers preserve their Android-FR semantic payload.
- `translations/dialogues_french.json` fresh regeneration SHA-256: `79d1e6f737a7f6393d03dab4af8a31e6697f09c55c27faa8b3ab338070749f45`.

## Dedicated vocative pass

The final dedicated pass restored 19 remaining Android-FR dynamic-name cases that had escaped the earlier batch review. Restoration is source-backed: recipes reference Android IDs and carriers, never localized prose.

The pass also corrected the attribution of Android FR 1800: its stock semantic carrier is `$038C/C9:DA79` (`... ?`), not `$0384`; it is now materialized there as `%S(0,0) : ... ?`.

All dynamic placeholders are serialized as real `PLAYER_NAME(n)` commands by the dialogue codec. Long restored labels are VWF-reflowed structurally, with new page boundaries where required.

## Additional corrections retained

The checkpoint preserves all previously validated fixes from the audit, including:

- `$0236` speaker separator;
- `$026A` Android FR 1409–1410 continuation;
- `$0295` inline Android dynamic name;
- pagination/page-boundary fixes in `$02B7`, `$036F`, `$038C`, `$038D`;
- the validated dynamic vocatives from lots 7–12;
- `$04E2` Android FR 1280 before 1281 while preserving both stock dynamic speakers;
- `$01B5`, `$042D`, `$055E`, `$0592` spacing/page/coverage fixes;
- `$0592` Android FR 1021–1022;
- `$05F8` continuation after `CA:8010`.

## Validation

Passed:

- `tools/dialogue/check_regressions.py`;
- `tools/dialogue/check_redistribution_recipes.py`;
- `tools/dialogue/check_manual_supplements.py`;
- `tools/text/check_source_hygiene.py`;
- `tools/text/check_roundtrip.py`;
- full simulator: 701 events, 0 error, 0 warning, 0 implicit wrap;
- cold-regeneration byte identity for `translations/dialogues_french.json`;
- two successive reproducible builds of `french_dialogues.ips` and `all.ips`.

Final IPS SHA-256:

- `patches/french_dialogues.ips`: `75a06c3070aead2cf00931582adfe3684800237e698d38c5caed4286c7789333`
- `patches/all.ips`: `f1609b97bf6c82b431b64458cee8ee64fd9e33db8aca2057fab70ee921fde83a`

## Pending discussion

The `$035F / C9:D1B8` follow-up is resolved. Runtime tracing proved that stock `$035F` concatenates the `Dryad` carrier with the shared `$0360` suffix (`'s magic will work!`). Because French `$0360` is intentionally neutralized for the seven Android-aligned elemental branches, `$035F` now carries the full validated manual message `Dryade fera réagir l'orbe !`. `$0360` remains neutralized.
