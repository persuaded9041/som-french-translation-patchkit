# HANDOFF — Secret of Mana FR — dialogue second exhaustive pass complete

Date: 2026-09-14

This archive is authoritative over GitHub. The reference ROM is **Secret of Mana (USA), unheadered** and must never be redistributed.

## Current promoted dialogue state

The second independent exhaustive playable-dialogue pass is complete. It reviewed all **701 accepted playable events** event-by-event in 12 lots and was followed by a dedicated cleanup/non-regression validation.

Final verified state:

- **701/701** accepted playable events simulator-clean;
- **1959 translated carriers**;
- Android alignment identity **1798/1838**;
- **0 errors / 0 warnings / 0 implicit wraps**;
- speaker-label guardrail: **0** hard-newline findings after `Nom :` / `%S(...) :`;
- rolling-scroll discovery guardrail: **0 new candidates**;
- redistribution: **302 active carriers**, 0 simulator-filtered;
- manual supplement schema v3: **17 carriers = 15 translations + 2 suppressions**;
- source round-trip: **713 events / 87,487 bytes**;
- all **2048 stock event scripts** parse successfully;
- source hygiene clean.

Final SHA-256:

- `translations/dialogues_french.json`: `3e4cacd926e31d6dfe9f9021d1026c4f71dc68ccd88ce4481749e47764d2b7d9`
- `patches/french_dialogues.ips`: `dfc94882e4162052ccd7195839ef7ef7f5a89f1bec51847d905ca6b05ad2de31`
- `patches/all.ips`: `9fc13efe50b7e315dab7238ee2142d9e245ea51ae9e51768a6ad9f6e42248029`

## Post-freeze targeted runtime correction — dialogue VWF

After the exhaustive dialogue corpus was frozen, a concrete runtime rendering defect was corrected in `vwf_dialogues` without changing dialogue text data:

- ordinary dialogue chunks start 1 px to the right so the left outline of the first glyph is not clipped by the window edge;
- interrupted same-line chunks preserve and restore the exact VWF sub-cell phase instead of resuming only at the next 8 px stock cell boundary;
- the opening falling-hero split cry was used as the runtime validation case: its first fragment ends at 54 px with the validated left inset, while whole-cell stock progression would resume at 56 px; the exact-continuation path therefore removes the measured 2 px artificial gap while preserving the final punctuation;
- the exact-continuation helpers live at `$ED:7930-$79F9`, outside `intro_skip`'s `$ED:7400-$74FF` reservation;
- because `$ED:7340` is a shared renderer helper, `vwf_ui` installs the same updated bytes; its non-dialogue path cannot reach the dialogue-only continuation helper.

The frozen dialogue corpus remains byte-identical: `translations/dialogues_french.json` and `patches/french_dialogues.ips` retain the hashes above. `vwf_dialogues.ips`, `vwf_ui.ips` and the combined `all.ips` were rebuilt twice and were byte-identical across both builds.

## Post-pass non-regression proof

The exact pre-second-pass baseline was recovered and compared carrier-by-carrier with the final cold-regenerated JSON.

- baseline carriers: **1959**;
- final carriers: **1959**;
- explicitly reviewed/validated carrier changes: **46**;
- non-target carriers byte-for-byte unchanged: **1913/1913**;
- carriers added: **0**;
- carriers removed: **0**.

The 46 changed carriers are **exactly** the validated target set from lots 1-12. There are no extra carrier differences outside that set.

Structural metadata differs only in the reviewed events:

- command overrides: `$0108`, `$0112`, `$0212`;
- command insertions: `$0022`, `$028A`, `$04B6`, `$04E1`, `$04EA`.

No other top-level semantic/source metadata changed between the second-pass starting checkpoint and the final state.

A fresh cold regeneration after cleanup reproduces the promoted JSON hash. A forced rebuild of `french_dialogues.ips` was run twice and both outputs are byte-identical to each other **and** to the promoted patch; `all.ips` was likewise recombined twice and matches the promoted patch byte-for-byte.

See `checkpoints/SECOND_PASS_POST_VALIDATION.md` for the final validation details.

## Core invariants

- Android FR remains the primary prose source.
- No localized French prose is hard-coded in formatter/layout recipes.
- `WAIT != NEWLINE`.
- Maximum 3 live lines, <=216 px, <=38 decoded characters.
- Dynamic names must remain valid for the 9-character worst case.
- `$0360` remains neutralized.
- `$035F / C9:D1B8` remains `Dryade fera réagir l'orbe !`.
- Android `%S(...)` vocatives remain real `PLAYER_NAME` commands.
- `$066D / CA:8D4B` is explicitly validated as a WAIT-only controlled-scroll case; controlled scrolling remains a manual layout decision, not a global rewrite rule.
- Existing choice/highlight geometry and timed event commands must be preserved unless a concrete runtime defect is demonstrated.

## Canonical dialogue inputs

`translations/dialogues_french.json` is a generated, fingerprint-validated cache/review artifact, not canonical prose provenance. Canonical dialogue generation uses the Android EN/FR sources, clean-USA extraction, reviewed alignment/redistribution metadata, manual supplements and structural/layout recipes.

The active dialogue recipe surface under `recipes/android/` remains:

- `dialogues_reviewed_alignment.json`
- `dialogues_redistribution.json`
- `dialogues_formatting.json`
- `dialogues_review.json`

## Next work

The dialogue audit is complete. The next planned subject is the **items/objects translation procedure**, beginning with design/discussion before changing translation data.

Do not reopen validated dialogue wording or structure merely for style. Reopen a dialogue only if a concrete runtime, serialization, source-identity, caller/sub-event, or layout regression is demonstrated.
