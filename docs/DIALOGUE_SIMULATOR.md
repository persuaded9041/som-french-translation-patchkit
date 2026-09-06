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
  `TEXT_CLOSE`;
- models `TEXT_X $nn` only when it starts a fresh line: the command's absolute
  decoded-text position becomes `nn` leading `$80` padding cells, matching the
  private-buffer path used by component 06;
- models the stock three-line rolling window: `WAIT` snapshots a readable state, while a fourth line generated **before** a WAIT is reported as unpaused scroll;
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
excluding the stock closing `)` when present. Component 06 therefore sends only a parsed `CHOICE_BEGIN` row through the complete
stock fixed-width renderer. The simulator
rejects any translation that would be overwritten by a later option anchor or exceed
the 32-cell selectable row. Dynamic item/enemy/weapon/magic/list-value rendering and
other unproven geometry remain unsupported. The stock-rendered choice-row path is
runtime-validated on event `$0331`; the simulator remains a static guardrail for the
rest of the corpus rather than a substitute for playthrough validation.

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

The simulator-filtered generator currently accepts **404 complete events / 719
translated source IDs (737 JSON entries)**. Re-running the simulator on the candidate
mass translation produces **0 errors, 0 warnings and 0 implicit runtime wraps**. The
13 formatter-compatible events still rejected by the simulator are choices whose
French text would overlap a stock option anchor or overflow the selectable row. The HTML remains a static guardrail
rather than a substitute for the planned full-game
playthrough. Representative runtime tests have validated the simulator-driven layout
repairs used by the mass formatter, including clean WAIT-separated pages and exact
interactive-WAIT overlap removal.
