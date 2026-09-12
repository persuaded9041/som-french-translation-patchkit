# Round 85.3 repository cleanup checkpoint

This checkpoint is intentionally a repository-maintenance change. It does not reopen
validated dialogue content and does not begin object/item translation.

## Scope

Starting from the delivered Round 85.2 cleanup checkpoint archive:

- source/archive file count before this pass: **239**;
- source/archive file count after this pass: **226**;
- `mappings/` files after cleanup: **12**;
- `patches/` remains **15 files** (14 component IPS + `all.ips`) by deliberate choice.

Python `__pycache__` files created during local validation are excluded from the archive.

## Removed

- all of `artifacts/postaudit/` — orphaned one-off post-audit output;
- obsolete Round-67 `$04E2` focused HTML and its dedicated generator;
- historical `dialogues_pilot.json` snapshot;
- old Round-74 UI-VWF review HTML;
- generated charset-audit CSV;
- generated text-resource review/audit HTML/JSON snapshots.

These reports remain reproducible by their generic audit/import tools where useful, but
are now generated to temporary/output paths rather than stored in the repository.

## Checker cleanup

`tools/check_round67_targeted_dialogues.py` no longer parses the historical Round-67
HTML. Its durable assertions already live in structured translation/mass-format data,
so the HTML was duplicate evidence rather than a proper machine dependency.

## `mappings/android/` policy

The directory now distinguishes three active classes:

1. **canonical structural inputs** — the dialogue/layout recipe JSON files;
2. **generated mapping/guardrail data still consumed by current checks** — notably
   `dialogues_auto.json`, `dialogues_format_mass.json`, their small CSV companions and
   `text_resources_android.json`;
3. **small active review state** — `dialogue_preview_state.json` and the current manual
   supplement provenance HTML.

Historical review snapshots and optional audit reports are no longer versioned.

`translations/dialogues_french.json` remains a generated output and must never become a
cache/input dependency. A future clean checkout may omit it entirely.

## Patches

No component IPS was orphaned: there are exactly 14 component patches for 14 active
components. They are retained for now because `build.py --combine` deliberately supports
combining stored component IPS files without rebuilding every component. Moving
`patches/` to fully generated output is deferred until the clean-clone rebuild workflow is
made the only supported path and proved byte-identical.

## Validation

The following passed after cleanup:

- redistribution recipe checker: 18 events;
- manual supplements: 17 = 15 translated + 2 suppressions;
- current manual-supplement HTML regeneration/check;
- Round 67 / 68 / 69 / 85 regression checks;
- text-source hygiene;
- structural parsing of all 2048 events;
- dialogue round-trip for 713 events / 87,487 bytes;
- all other source/text round-trip and translation-binding checks;
- Android text-resource importer `--check`;
- deleted charset/resource audit reports regenerated successfully to `/tmp`;
- aggregate rebuild of all 14 components.

`patches/all.ips` is unchanged from Round 85.2:

`f4f8e8450882f8520b618814e53c043cf935462b6d29dbd31ed697fa48ed9ec0`

Combined ROM remains 3 MiB with SNES checksum **`$8E10`**.

## Next maintenance step

Simplify the dialogue import/generation pipeline before optimizing it. In particular,
make the distinction between canonical inputs, optional reproducible caches and final
outputs explicit, and remove legacy pilot/review modes from the active importer where
safe. Only after that simplification should performance work resume.
