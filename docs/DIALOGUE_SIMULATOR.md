# Dialogue-box simulator

`tools/simulate_dialogues.py` is the user-validated downstream static guardrail
for components 06 and 08. It exists specifically so formatter bugs are not hidden by reusing the same
high-level line calculations that produced `translations/dialogues_french.json`.

The tool requires the clean unheadered USA ROM locally. It never embeds or writes
ROM bytes into the HTML output.

```bash
python3 tools/simulate_dialogues.py "Secret of Mana (USA).sfc" \
  -o dialogue_preview.html \
  --issues-csv dialogue_preview_issues.csv
```

By default it simulates every event touched by the current sparse dialogue
translation. `--event 010F` may be repeated to restrict the report.

## What is independently simulated

For each selected event the tool first calls the normal event serializer, then
works from the resulting **encoded event byte stream**. It independently:

- decodes direct glyphs with the dialogue `$E8` direct/DTE boundary;
- expands lower and upper stock DTE source bytes;
- expands `PLAYER_NAME` using a configurable test name (default `000000000`, a
  deliberately wide 9-character case);
- reapplies the runtime-validated component-06 advance and framing tables from
  the stock font plus the canonical PNG glyphs;
- models the 38-decoded-glyph runtime capacity;
- models component 06's visible-ink preflight against the 32-cell / 256-pixel
  physical bitmap and its safe-space rewind behavior;
- checks the conservative formatter target of 240 pixels separately;
- follows explicit `$7F` line breaks, `WAIT`, `TEXT_CLEAR`, `TEXT_OPEN` and
  `TEXT_CLOSE`; runtime validation on `$0106` established that `WAIT` is pause-only and **does not advance the text cursor**; following text therefore remains on the same physical line until `$7F` or `TEXT_CLEAR`;
- models `TEXT_X $nn` only when it starts a fresh line: the command's absolute
  decoded-text position becomes `nn` leading `$80` padding cells, matching the
  private-buffer path used by component 06;
- models the stock three-line rolling window: `WAIT` snapshots the current readable state without consuming a line, while a fourth line generated **before** the next pause is reported as unpaused scroll;
- emits review-only `WAIT_SAME_LINE_CONTINUATION` when translated text resumes after a WAIT on a still-live line, making missing explicit `$7F` boundaries visible instead of silently inventing them;
- detects the runtime-validated `$0106` pagination hazard separately: after `WAIT $00`, two retained visible lines plus an empty newline can consume physical line 3 and make following prose scroll before the next pause; this is emitted as review-only `WAIT00_THIRD_LINE_SCROLL_RISK`, never auto-fixed;
- renders the resulting pages with the actual 8x12 glyph bitmaps in a standalone
  HTML report;
- shows a side-by-side comparison for every event: generated French/VWF on the
  left and the canonical clean-USA SNES source on the right, preserving its hard
  line breaks but deliberately applying no VWF to that source column.

The empirical one-unit `PLAYER_NAME` safety reserve validated during batch 1 is
also checked independently from the visible glyph count.

## Conservative limitations

This is not a 65816/event-engine emulator. Commands whose dialogue geometry is
not established are **reported as unsupported rather than guessed**. `TEXT_X`
is accepted only at a fresh-line position whose behavior is established; a
mid-line `TEXT_X` remains unsupported because it resets an absolute text
position/count. `MONEY_PRINT` (`$5F`) is modeled as consuming no dialogue-buffer
geometry: static event-engine analysis shows that it redraws the separate money
window rather than appending dialogue glyphs. Interactive choice geometry is now modeled conservatively. `CHOICE_OPTION $xx` resets
the decoded-buffer X to the stock absolute cell and records the same boundary later
used by the selection/highlight code; `CHOICE_END` supplies the terminal boundary,
excluding the stock closing `)` when present. Component 06 currently renders choice rows
through the ordinary VWF path, but the simulator deliberately keeps the stricter stock
anchor model as a safety gate: it rejects any translation that would be overwritten by a
later option anchor or exceed the 32-cell selectable row. Dynamic item/enemy/weapon/magic/
list-value rendering and other unproven geometry remain unsupported. The simulator remains
a static guardrail rather than a substitute for runtime validation of selection/highlight
behavior.

The source comparison column is informational only; it is not fed back into the
formatter or simulator. The simulator cannot prove timing, animation interaction or compositor pixel
artifacts. Runtime playthrough remains the final validation. In particular, the
known position-dependent final `e` artifact from `cascade` remains a separate
component-06 follow-up.

## Intended mass-import workflow

1. Generate a candidate `translations/dialogues_french.json` from accepted
   Android mappings.
2. Run the simulator on every translated event.
3. Automatically exclude events with simulator errors or unsupported geometry.
4. Regenerate the final sparse translation and `08_dialogue_text.ips`.
5. Use the HTML report for a visual corpus pass, then validate the large patch in
   a complete game playthrough.

## Current mass-pass result

The simulator-filtered generator currently accepts **526 events / 1138 visible
semantic source IDs (1196 JSON entries)**: 525 events treated as complete plus 1
PARTIEL event. `$0103`, `$017F` and `$01DC` are user-validated visually complete Android
adaptations and therefore have no PARTIEL badge despite retaining unmapped SNES-only
fragments. `$01DC` additionally omits the exact final stock `PLAYER_NAME(0)` command tied
to suppressed `C9:804A`. `$0278` is the sole PARTIEL event; its two SNES-only controller carriers are user-validated absent from Android and are staged in the manual supplement JSON.
Re-running the simulator on the candidate mass translation produces **0 errors, 0 warnings
and 0 implicit runtime wraps**. The HTML marks that event with a `PARTIEL · français
incomplet` badge so incomplete scenes can be revisited during playthrough. When
`--baseline-translation` points to the previous generated JSON, the preview also tags
events as `NEW` when newly translated source IDs appear, `MODIFIED` when the final
serialized event bytes differ from the baseline, and `TO REVIEW` for PARTIEL,
warning/error events, or `WAIT00_THIRD_LINE_SCROLL_RISK`. `--preserve-tags <json>` may carry forward an explicit
NEW/MODIFIED/TO REVIEW snapshot while a user review is still in progress, so a later technical change cannot silently
remove an unread badge. The repository keeps the active snapshot at
`mappings/android/dialogue_preview_state.json`. Dedicated toolbar buttons filter these tags and can be combined with the text search. The simulator now mirrors component 06's private measured-end choice geometry for undecorated two-option rows while leaving logical `$A1D7[]` storage anchors untouched. The first private visual/highlight boundary is `max(logical_first, $03) - 2`; the second option normally keeps one blank cell after the rounded first measured endpoint, except once that rounded endpoint reaches cell `$11`, where the extra separator is omitted to protect the right edge. `$00CE`, `$00CF`, `$00D0`, `$00D1` and `$0202` are now admitted by this model. In the final two-cell-left geometry `$00D0` uses the normal separator and terminal boundary `$1B`; the cell-`$11` separator-omission fallback remains modeled because it was separately runtime-validated on the earlier right-edge checkpoint. The rejected `$00CE` **logical-anchor** probes (`$00/$0F`, `$01/$10`) remain invalid. The HTML remains a static guardrail
rather than a substitute for the planned full-game
playthrough. Representative runtime tests have validated the simulator-driven page layout used by
the mass formatter. Exact visible carry-over after interactive `WAIT $00` is preserved as stock rolling-window
presentation rather than automatically removed. `$0106/C9:2994` remains the only runtime-validated
fresh-page exception. For one user-requested combined runtime-test batch, the eight exact round13
detector matches (`$00FB`, `$0134`, `$016D`, `$01CA`, `$029C`, `$03EE`, `$04A1`, `$04EA`)
now receive the same targeted newline-carrier -> `TEXT_CLEAR` change while preserving their stock
`WAIT $00`. The guard reports **0 remaining third-line-scroll risks** after this batch. These eight
events remain TO REVIEW until runtime validation; no generic WAIT cleanup is enabled.

A separate live-window guard protects against formatter-added semantic line breaks
that consume an extra physical line before the next pause.  When
`UNPAUSED_LIVE_LINE_SCROLL_RISK` is present, the mass formatter may retry one
mapping at a time with the compact width-only wrapper.  It accepts that change
only if independent resimulation removes the complete risk with no error, warning
or implicit wrap; choice rows are excluded, and partial risk reductions are
rejected.  This keeps short source utterances such as `$0083`
`Gestahl : Ha ! Imbécile !` on one line when the official French already fits,
instead of letting a purely aesthetic sentence break push later text through the
rolling three-line window.
