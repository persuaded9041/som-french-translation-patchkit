# HANDOFF — Secret of Mana FR — intro_skip promoted / opening credit accent research next

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
- `patches/all.ips`: `253ffde42f6977e714e9d27351089a2fbf0400bf46293ca8ed8967e38aad6b6d`

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
- `patches/all.ips`: `253ffde42f6977e714e9d27351089a2fbf0400bf46293ca8ed8967e38aad6b6d`
- validated autonomous FR+VWF+skip 120: `f9f21e070d898f8ef8f05709a6ce8796dbc70a2b2faf2979e56f6c2517ed5997`

A key regression lesson is now documented: the early global attempts that glitched
at boot had grown a helper past its C7 free-space slot and overwritten the shared
VWF helper at `$C7:43D0-$43E7`. The final design keeps all extensible helpers in
the owned `$ED:7400-$74FF` reserve, with size guards in the builder.

`intro_skip` now explicitly requires `french_intro` and `vwf_intro`, matching the
configuration actually used for runtime validation.
The standalone intro path is runtime-validated. The `$ED:73C0` aggregate
dispatcher was added only to compose that path with the pre-existing
`vwf_dialogues` mode-2 `$C0:16EA` hook; the resulting full `all.ips` has now also
been runtime-validated by the user. The standalone component patch and the
autonomous FR+VWF+skip test stack are likewise runtime-validated.

## Current `french_opening` state and next research target

The current `french_opening` implementation is a validated baseline and must be
preserved while the next opening-credit experiment is studied.

Current startup-credit behavior:

- five startup credits are sourced from `translations/opening_text_french.json`;
- the French-only fifth credit is `Traduction : E.CHAUVIRÉ`;
- credits use the stock fixed-width startup-credit renderer and the validated
  180-frame dwell;
- the current `É` in startup credits is a dedicated one-cell glyph in opening-font
  tile `$7A`, which replaces the original `Z` tile;
- because of that reservation, the builder currently rejects literal `Z` in the
  opening text/credits;
- the scrolling prologue already has a separate accent-overlay convention using
  `$7D` acute, `$7E` grave and `$7F` circumflex on the row above the base letters.

The **next project target** is to remove the startup-credit `$7A = É` compromise:
restore a normal `Z`, render the final `É` of `CHAUVIRÉ` as a base `E` on the
credit row plus an acute accent on the tile row immediately above, and make that
accent participate in the **same fade-in and fade-out** as the credit itself.

Important historical runtime evidence supplied by the user: an earlier
implementation had already succeeded in displaying the accent on the row above
the credit, but the accent row did **not** follow the credit line's fade-in /
fade-out. That is the key failure to explain before implementing a new solution.
Do not merely recreate the old overlay.

The dedicated research brief is `docs/OPENING_CREDIT_ACCENT_RESEARCH.md` and the
next-chat prompt is `docs/NEXT_CHAT_PROMPT.md`.

## Next work

The next discussion must focus on **`french_opening` startup-credit rendering**,
not on dialogues and not on further `intro_skip` development.

First perform a deep reverse-engineering study of the startup-credit renderer and
fade path. The first deliverable should be an evidence-based map of:

- the five-credit loop and record decoder;
- where the visible credit row is written in tilemap/WRAM/VRAM;
- what row exists immediately above it and how it is updated;
- how fade-in and fade-out are actually implemented (palette, tile attributes,
  buffer selection, brightness, or another mechanism);
- why an independently written accent row can remain visible or otherwise fail
  to track the credit fade;
- which existing prologue accent machinery can be reused and which cannot.

Only after the fade mechanism is proved should a new implementation be proposed.
The target design must restore the normal opening-font `Z`, keep `CHAUVIRÉ`, and
render the acute accent above its base `E` while following the credit line's
fade frame-for-frame.

The dialogue corpus remains frozen. `intro_skip` is promoted and should not be
modified as part of this opening-credit work.
