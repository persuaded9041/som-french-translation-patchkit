# HANDOFF — Secret of Mana FR — opening credit accent fade promoted
## dialogue_background — promoted standalone v1 (2026-09-15)

The hardware semi-transparent dialogue-window experiment is now promoted under semantic component ID `dialogue_background`. Runtime validation covers a normal animated dialogue frame and the inn reservation sequence with asynchronous ordinary + GP/type-2 frames (`1 opens -> 2 opens -> 1 closes -> 2 closes`). The successful model tracks explicit ownership of global live bounds `$A165-$A168`; `$A162` context restoration must never be treated as geometry ownership.

The component remains `aggregate_enabled: false`: it preserves the exact validated Stage-11 allocation (`$7E:93D0-$93F1`, HDMA ch6), which conflicts with `vwf_dialogues` continuation scratch and has not yet been composed with existing map color-math/HDMA effects. `all.ips` remains unchanged. See `docs/DIALOGUE_TRANSPARENCY_RESEARCH.md`.


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

## Promoted Ring Menu title translation + dedicated VWF backend (2026-09-16)

The top-level in-game Ring Menu title work is now **runtime-validated and promoted**.
The dialogue corpus and Android dialogue mapping were not modified.

Validated French labels (`$CA` resources `$0C6-$0CE`):

- `$0C6` `Équipement`
- `$0C7` `Désigner la cible à attaquer`
- `$0C8` `Caractéristiques des personnages`
- `$0C9` `Niveaux des armes et de la magie`
- `$0CA` `Actions des personnages`
- `$0CB` `Réglages manette`
- `$0CC` `Choix des fenêtres de dialogue`
- `$0CD` `Jeter`
- `$0CE` `Tous`

Text ownership is intentionally data-driven. Android identity/French remains generated through the
existing `$CA` resource pipeline; the reviewed SNES wording above lives canonically in
`translations/text_resources_reviewed_overrides.json` and is loaded/validated by
`french_resources`. No Ring French prose is hard-coded in Python.

Runtime tracing established the title path:

`Ring Menu -> C0:6943 -> D0:D397 -> $00:19D0 -> stock parser -> C0:167D -> vwf_ui`

The root cause of the former long-title corruption was not a 20-character hard limit: the
Forge-specific overlapping slot-20..31 suffix compaction was being applied to a continuous Ring
title because both families share the same `$00:19D0` submit. The production fix gives each
family its own one-shot tag at the exact shared submit:

- `$1847 == 0` -> Ring tag `$A8`, unchanged decoded-row VWF rendering, exact **+4** logical
  capacity = full 33-byte stock buffer (32 visible characters + following control);
- `$1847 == 3` -> Forge tag `$A7`, previously validated **+3** capacity and suffix compaction;
- modes 1/2 or unexpected values -> no UI tag, stock fallback.

The +4 boundary is runtime-validated by the complete 32-character
`Niveaux des armes et de la magie`, including its final `e`. The other long titles no longer lose
words or repeat glyphs. The user explicitly validated this architecture before the final wording
change `$0CA: Définir les actions des PNJ -> Actions des personnages`; that wording-only change
is shorter and does not alter the VWF runtime.

Current promoted patch SHA-256 values:

- `patches/vwf_ui.ips`: `e0abffa45d64aaf9b42dededf2923a43d9f6bc9a94020756ddfc8e9a1b849189`
- `patches/french_resources.ips`: `a809910e815ee312556de313800386d8904661c7b364cf366afbc3aec0a72a6d`
- `patches/all.ips`: `273d8268c9925e858ad631357953c38f50134e0bfabee01fa323ebcdea69f69a`

`french_resources` now translates 358 resources; its rebuilt `$CA` blob is 7,103 / 7,315 bytes
and remains fully inside the stock allocation (`$CA:98E1-$B49F`, maximum `$CA:B573`).

## Next work

No new functional task is prescribed by this checkpoint. Treat the dialogue
corpus, `intro_skip`, and the startup-credit accent/fade as promoted baselines.
The next discussion should read the archive first and follow the user's next
explicit target rather than reopening any of those validated areas.
