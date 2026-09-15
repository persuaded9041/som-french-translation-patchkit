# HANDOFF — Secret of Mana FR — opening credit accent fade promoted

Date: 2026-09-15

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
- current `patches/all.ips`: `74e66682ede9226cf5d14cbe681b8f917f4a4cbf87055403a888485889280079`

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

## Intro `$0400` / validated `intro_skip`

The static introduction map remains in `docs/INTRO_EVENT_ARCHITECTURE.md`. The
isolated proof ladder in `docs/INTRO_SKIP_RESTART_PLAN.md` is now **complete**;
its detailed runtime record is `docs/INTRO_SKIP_VALIDATION.md`.

The former legacy/NMI component has been replaced by the validated implementation:

- input source: synchronized pad 1 `$7E:0042`, R bit `$10`;
- required hold: **120 continuous normal-loop ticks**;
- release before expiry cancels completely; short presses do not accumulate;
- state: 16-bit `$7E:938A-$938B` (`$FFFF` inactive, `$0000` completed);
- active-text observation: `$C0:012C -> $ED:7488`;
- standalone live mid-carrier commit: `$C0:16EA -> $CA:FFC8`;
- aggregate with `vwf_dialogues`: shared `$C0:16EA -> $ED:73C0`, mode 2 -> `$ED:7500`, other modes -> `$CA:FFC8`;
- normal-loop / timed-WAIT handling: `$C2:C786 -> $ED:7400`;
- validated private tail: `$CA:FFC0-$FFC7` = `51 18 00 2A F8 11 06 00`;
- C1 timed-WAIT handler itself remains stock; there is no NMI hook.

The implementation covers all eight normal narrative text/WAIT phases before
`$CA:0E82 = 1D 7F`. The final Mode-7/flyover engine remains deliberately outside
the validated scope.

Promoted patch SHA-256:

- `patches/intro_skip.ips`: `b37d529eb25eae572212d6f7179461785e463dfef9055fd840e00f5754136c16`
- current `patches/all.ips`: `74e66682ede9226cf5d14cbe681b8f917f4a4cbf87055403a888485889280079`
- validated autonomous FR+VWF+skip 120: `f9f21e070d898f8ef8f05709a6ce8796dbc70a2b2faf2979e56f6c2517ed5997`

A key regression lesson is now documented: the early global attempts that glitched
at boot had grown a helper past its C7 free-space slot and overwritten the shared
VWF helper at `$C7:43D0-$43E7`. The final design keeps all extensible helpers in
the owned `$ED:7400-$74FF` reserve, with size guards in the builder.

`intro_skip` now explicitly requires `french_intro` and `vwf_intro`, matching the
configuration actually used for runtime validation.
The standalone intro path is runtime-validated. The `$ED:73C0` aggregate
dispatcher was added only to compose that path with the pre-existing
`vwf_dialogues` mode-2 `$C0:16EA` hook; that composed full-build baseline was
runtime-validated by the user before the later opening-credit promotion. The
current `all.ips` changes only `french_opening` relative to that baseline; all
other standalone component IPS files remain byte-identical. The standalone
`intro_skip` component patch and the autonomous FR+VWF+skip test stack remain
runtime-validated.

## Promoted `french_opening` startup-credit accent

The final startup-credit treatment is now **runtime-validated and promoted**.
The authoritative implementation is the one in this archive.

Promoted patch SHA-256:

- `patches/french_opening.ips`: `c7b0b0e8b821a6f9dbbfc6b4591c5ebada18c0df1a4320fb3b1dbd15010b2d27`
- `patches/all.ips`: `74e66682ede9226cf5d14cbe681b8f917f4a4cbf87055403a888485889280079`


Current behavior:

- five startup credits remain sourced from `translations/opening_text_french.json`;
- the French-only fifth credit remains `Traduction : E.CHAUVIRÉ`;
- the visible dwell remains 180 frames;
- opening-font tile `$7A` is restored to the stock `Z`;
- startup-credit `É` is rendered as ordinary `E` on the normal row plus acute
  tile `$7D` on the tile row immediately above;
- a wrapper in existing decompressed-title-code padding at CPU `$BCED` renders
  an overlay record and then the normal credit record through stock `$8820`;
- a final blank overlay record clears the upper row after the fifth credit;
- the credit-only CGRAM HDMA segmentation is changed from `120+15+8+1` to
  `120+7+16+1`, preserving the same 144-scanline extent while extending the
  animated band upward by exactly one tile row;
- `$8B5D`, the 31-step fade-in/fade-out loops and their timing remain stock.

The critical reverse-engineering result is that the historical overlay did not
miss the fade because of tile geometry or a second timer. The stock HDMA fade
band covered only the 8 scanlines of the normal credit row, so an accent one
tile above sat outside the animated CGRAM region. Extending that same band to 16
scanlines makes both rows share exactly the same per-frame fade state.

Validation was intentionally split:

1. Stage A restored stock `Z` and the historical two-row geometry. Runtime test
   reproduced the known behavior: accent correct, fade absent. **Validated.**
2. Stage B changed only the credit-specific HDMA scanline boundary (`15/8` ->
   `7/16`). Runtime test: accent placement remained correct and fade became
   synchronized. The user reported the result as **perfect**.

Preserved architecture:

- arrangement literal stream remains `$EE:A000-$BFFF`;
- loader remains stock `$C1:0014`;
- helper reserve remains `$EE:9000-$9FFF`;
- `$EF` remains unused by `french_opening`;
- no dialogue data was reopened;
- `intro_skip` was not modified by this work.

Detailed research and the corrected historical explanation are in
`docs/OPENING_CREDIT_ACCENT_RESEARCH.md`. Component implementation notes are in
`components/french_opening/README.md` and its memory map.

## Next work

No new functional task is prescribed by this checkpoint. Treat the dialogue
corpus, `intro_skip`, and the startup-credit accent/fade as promoted baselines.
The next discussion should read the archive first and follow the user's next
explicit target rather than reopening any of those validated areas.
