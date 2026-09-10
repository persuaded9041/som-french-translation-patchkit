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
- models forward/equal `TEXT_X $nn` as the stock absolute decoded-buffer-index reset: static analysis of `$C0:1883` / `$C0:18FB` proves writes to both `$7E:A1CE` and `$7E:A173`, so already-decoded prefix cells are retained and clean `$80` cells pad up to `nn`; backward overwrite remains unsupported;
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
is accepted for forward/equal absolute resets whose decoded-buffer behavior is
proved from the stock handler; a backward reset remains unsupported because it
would overwrite already-decoded cells. `MONEY_PRINT` (`$5F`) is modeled as consuming no dialogue-buffer
geometry: static event-engine analysis shows that it redraws the separate money
window rather than appending dialogue glyphs. Special `ending_text` (`$7D...$7E`)
geometry is still not simulated; those blocks are accepted only when their final
serialized bytes, count and order are exactly identical to the clean-USA event.
Interactive choice geometry is now modeled conservatively. `CHOICE_OPTION $xx` resets
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

The Round-69 simulator-filtered generator accepts **701 events / 1810 accepted semantic source IDs
(1946 JSON entries)**: **701 complete + 0 PARTIEL**. Fifteen former PARTIEL events were promoted
after scene-level semantic review; manual-JP supplements, validated suppressions and shared-prefix
resegmentations remain traceable in `user_validated_visually_complete_events`. Exactly three
routing-audited unused/orphan stock events remain excluded (`$0269`, `$02DE`, `$0603`).

Re-running the simulator on the candidate mass translation produces **0 errors, 0 warnings and
0 implicit runtime wraps**. `WAIT00_THIRD_LINE_SCROLL_RISK` remains a review-only informational
flag and is not a simulator error/warning. The HTML still supports NEW/MODIFIED/TO REVIEW tags
and preserved review state.
