# Handoff — `06_dialogue_vwf` next phase

## Start from this checkpoint only

Before changing anything, inspect the archive actually provided. Do not assume a
file, address, helper or behavior still exists because it existed in an older
conversation. At minimum read `README.md`, `docs/COMPATIBILITY.md`,
`docs/MEMORY_MAP.md`, `docs/SHARED_CHARSET.md`, `build.py`, every
`component.json`, component `05_intro_vwf_french`, and all of
`06_dialogue_vwf` including `docs/EVENT_INTERRUPTION_NOTES.md`.

Never download, redistribute, archive or commit the commercial ROM. A clean
unheadered US ROM may be supplied only as a local build input.

## Runtime-validated renderer architecture — preserve exactly

- Current scope: `$001D03 == $C9`. Do not broaden it yet.
- Keep stock `$C0:168A-$C0:16B0` intact for `code -> glyph -> x12 -> $D2:DC00`.
- Do not relocate the full renderer or replace the stock lookup.
- `$C0:13A3` remains the stock-equivalent `INC $A181 / INC $A1D0` trampoline.
- `dialogue_char_start` stays at **`$ED:7180`**. Moving it to `$ED:7190` made
  almost all dialogue disappear.
- Destination `Y = floor(pixel_cursor / 8) * 12`.
- Compose each already-selected row at `pixel_cursor & 7`, OR with the current
  cell and spill into the following 12-byte cell.
- The cursor is continuous; never realign it to an 8 px boundary.
- The 128-entry advance table is `$ED:7200-$ED:727F`.
- Zero-extend its 7-bit index through `$7E:938A-$938B` **without changing A's
  width**. Runtime has validated actual advances of 3, 4, 5, 6, 7 and 8 px.
- Complete lowercase framing is selected at `$ED:71B0-$ED:71E7`; the bitmap is
  transformed at the already validated point in `dialogue_font_row`.
- Runtime-validated lowercase framing: `a-h/k/m-s/u-z=1`, `i/l=3`, `j/t=2`.
- Runtime-validated lowercase advances: `a-h/k/m-q/s/u-z=7`, `i/l=3`, `j=4`,
  `r=6`, `t=5`; space is 4 px.
- The stock outline routine `JSR $162C` at `$C0:1165` must execute normally.
  The validated repair hooks **after** it at `$C0:1168` and uses helper
  `$ED:7280-$ED:72E9`.

## Runtime-validated punctuation checkpoint

Punctuation uses a different visual policy from lowercase: keep **one black pixel
before the ink and one after it**. The earlier fully compacted punctuation was
functional but looked too close to preceding text.

Validated framing / advances:

- `$BF-$C2` (`.`, `,`, `/`, apostrophe): shifts `0/0/0/0`, advances `4/4/7/4`;
- `$C3/$C4` paired quotes: shifts `0/1`, advances `7/7`;
- `$C6/$C7/$C9/$CA` (`-`, `%`, `&`, `?`): shift `0`, advance `8`;
- `$C8/$CB/$CC` (`!`, `(`, `)`): shifts `2/2/1`, advances `5/5/5`.

Colon `$C5` is runtime-validated: stock ink columns 3-4, `shift=1`, `advance=7`, for 2 px black framing on the left and 3 px on the right. Do not generalize this to other punctuation.

### `$CD`: do not touch

`$CD` must remain completely outside active special handling: no framing branch,
no dedicated metric, no self-test and no diagnostic text. It falls through to
the generic conservative path. It appeared as an X-like glyph rather than a
normal `#`; an isolated 6 px metric experiment coincided with massive dialogue
loss, and excluding `$CD` restored normal rendering. It is unnecessary for the
current French work. Revisit it only if the user explicitly requests a dedicated
investigation.

### Fixed punctuation trampoline

The punctuation selector starts at `$ED:71E8`. Its batch-2 `JML` trampoline is
**pinned at `$ED:71F4`** and the builder asserts that offset. A rejected build
removed one byte from the selector, moved the JML to `$ED:71F3`, while existing
dispatch still entered at `$ED:71F4`; the ROM no longer started. Keep generated
relative branches symbolic and keep this fixed trampoline stable unless every
dispatch path is intentionally updated.

## Convenient runtime test slot

When upcoming glyphs are hard to reach naturally, the user explicitly allows
temporary replacement of the first dialogue's `Wait ` text. The clean US bytes
at ROM `0x0928CC-0x0928D0` are:

`B1 81 89 94 80` = `Wait `

This is exactly five bytes immediately before event command `$32`. A temporary
test candidate may replace those five bytes with glyph codes, but:

- never modify the following `$32`;
- record the original bytes;
- restore `Wait ` in every cleaned checkpoint.

The current checkpoint contains the original `Wait ` and no active text
diagnostic.

## Current clean charset checkpoint

The useful charset calibration is complete and runtime-validated without redesigning
the renderer:

- Uppercase `A-Z`: `A-H/J-Z = shift 1 / advance 7`, `I = shift 3 / advance 3`.
- Colon `$C5`: `shift=1, advance=7`.
- `$B5-$BE` are digits `0-9`; runtime inspection showed their stock widths are
  satisfactory. Leave them generic/stock.
- Shared French direct glyphs `$D4-$E5` are runtime-validated: `$D4-$E3 =
  shift 1 / advance 7`, `$E4/$E5 = shift 0 / advance 8`. Component 06 consumes
  the canonical mapping/artwork from `shared/french_charset`, installs all 18
  glyphs itself, and changes the direct/DTE boundary to `$E6`.
- `$CD` remains the only explicit do-not-touch glyph.

The cleaned checkpoint contains the original dialogue text and **no active runtime
diagnostic**. The temporary `$D4-$E5` exposure at `0x092930-0x092941` has been
removed.

## Next planned VWF work

1. Review whether any **behavior-preserving** factorization/generalization now has
   a clear maintainability benefit. Do not refactor validated runtime helpers merely
   to reduce byte count.
2. Then investigate broadening the dialogue scope beyond `$C9`, explicitly auditing
   event-bank selection and the WRAM scratch assumptions first.
3. Only after the renderer scope is stable, implement dialogue extraction and
   reinsertion from CSV.
4. Keep the separate `Wait   up!` event-interruption issue deferred unless the user
   explicitly asks to resume it.

## Rejected approaches / errors not to repeat

- Do not relocate the whole stock renderer.
- Do not replace the stock glyph lookup.
- Do not hand off custom rendering back to stock in the middle of a line.
- Do not restore forced 8 px realignment.
- Do not index the width table with an X whose high byte is not explicitly zero;
  this made glyphs such as `q` and `y` disappear.
- Do not use `REP/SEP` in `dialogue_char_end` to build a 16-bit index; the stock
  renderer relies on the hidden B byte of A and almost all text disappeared.
- Do not reintroduce the rejected generic `left_shift[128]` implementation.
- Do not move `dialogue_char_start` away from `$ED:7180`.
- Always generate 65816 relative branches from labels. A stale hard-coded `BNE`
  once jumped into the middle of `LDA $A1A4,X / INX` and broke GAME SELECT.
- Do not infer a renderer limit from the old `i=7/l=7` crash; a clean rebuild of
  the same test worked.
- Do not hook `$C0:1165` for the outline repair: that replaces the stock
  `JSR $162C` and removes most black outlines. Hook only after it at `$C0:1168`.
- Do not shorten the punctuation selector so that the `$ED:71F4` trampoline
  moves silently.
- Do not touch `$CD`.

## Deferred `Wait   up!` spacing problem

The large gap before `up!` in event `$0106` around `$C9:28A0` is caused by an
event interruption around command `$32`, not by the general continuous cursor.
The `$A1CE` sync, `$32` bridge at `$C0:13A3`, renderer-end bridge and `$A17C`
probe were rejected and are absent from active source. Details are preserved in
`components/06_dialogue_vwf/docs/EVENT_INTERRUPTION_NOTES.md`.

**Do not investigate this at the start of the next conversation.**

## Working method

For each batch: inspect current sources, make the smallest coherent change, build
`06`, verify reproducibility/collisions, build all six components, provide one
combined IPS, then wait for runtime validation. After validation, remove temporary
diagnostics, restore `Wait `, clean generated files, and update documentation.

Final deliverables after a cleaned checkpoint: only the complete project ZIP and
one combined IPS. Never include the commercial ROM.
