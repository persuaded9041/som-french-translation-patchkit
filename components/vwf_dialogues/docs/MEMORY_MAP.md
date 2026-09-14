# Dialogue VWF memory map

Component-local ROM hooks, helpers and WRAM scratch for the current caller-gated
stock event-dialogue checkpoint. The root `docs/MEMORY_MAP.md` keeps only the
cross-component view.

| Range | Size | Purpose | Status |
| --- | ---: | --- | --- |
| ROM `$C0:16B8-$16BB` | 4 bytes | Shared parser-buffer initializer hook | Runtime-validated; byte-identical with `vwf_intro` |
| ROM `$C0:16C6-$16CF` | 10 bytes | Shared parser-capacity hook | Runtime-validated; byte-identical with `vwf_intro` |
| ROM `$C0:17CE-$17D1` | 4 bytes | Shared parser destination hook | Runtime-validated; byte-identical with `vwf_intro` |
| ROM `$C0:18DE-$18E1` | 4 bytes | Shared previous-character source hook | Runtime-validated; byte-identical with `vwf_intro` |
| ROM `$C7:43D0-$43E7` | 24 bytes | Shared parser write helper | Runtime-validated |
| ROM `$C7:4AC0-$4B3B` | 124 bytes | Shared caller-gated buffer initializer | Runtime-validated |
| ROM `$C7:4B40-$4B5A` | 27 bytes | Shared previous-character helper | Runtime-validated |
| ROM `$C7:4BC0-$4C01` | 66 bytes | Shared capacity helper | Runtime-validated; byte-identical with `vwf_intro` / `vwf_ui` infrastructure |
| ROM `$C7:4C84` | 1 byte | `vwf_dialogues` dialogue private-buffer feature marker `$06` | Runtime-validated |
| ROM `$C7:4C85` | 1 byte | Extended dialogue DTE marker `$E8` | Runtime-validated; byte-identical with `french_dialogues` |
| ROM `$C7:4570-$45EE` | 127 bytes | Shared context-sensitive direct/DTE router | Runtime-validated; byte-identical with `french_dialogues` |
| ROM `$C7:4C90-$4CCE` | 63 bytes | Shared 8x12 row shift/merge/spill compositor | Runtime-validated; byte-identical with `vwf_intro` and the previously validated dialogue compositor bytes |
| ROM `$C7:44C0-$4557` | 152 bytes | Shared runtime framing selector bundle | Runtime-validated; byte-identical overlap with `vwf_intro` |
| ROM `$C7:4560-$456C` | 13 bytes | Shared stock-font row load + framing + compositor helper | Runtime-validated; byte-identical overlap with `vwf_intro` |
| ROM `$C0:163D` | 1 byte | Shared outline preparation (`ROL` -> `ASL`) | Runtime-validated; byte-identical with `vwf_intro` |
| ROM `$C0:1168-$116B` | 4 bytes | Post-stock-outline hook | Runtime-validated exact-tag scope for stock `$C9/$CA` and relocated `$E8-$EC` dialogue |
| ROM `$C0:167D-$1680` | 4 bytes | Shared-renderer entry / caller classification hook | Runtime-validated |
| ROM `$C0:1686-$1689` | 4 bytes | Per-character destination hook | Runtime-validated |
| ROM `$C0:16A4-$16A7` | 4 bytes | Stock-selected font-row compositor hook | Runtime-validated |
| ROM `$C0:16B1-$16B6` | 6 bytes | Cursor advance / stock loop termination hook | Runtime-validated |
| ROM `$C0:16F5-$16F8` | 4 bytes | Context-sensitive direct/DTE router hook (`$E6` base, `$E8` dialogue) | Runtime-validated for `♪`, `°`, `;` and intro/dialogue separation |
| ROM `$C0:1B5F-$1B6C` | 14 bytes | Choice highlight geometry hook; private measured-end bounds when valid, stock `$A1D7[]` otherwise | Runtime-validated on wide and decorated Potos choices |
| ROM `$C0:16EA-$16ED` | 4 bytes | Dialogue-only source-fetch / pixel-wrap preflight hook | Runtime-validated on known right-edge overflow case; stock replay outside parser mode 2 |
| ROM `$ED:7040-$7092` | 83 bytes | Caller/bank gate + normal bitmap/decoded-count/38-slot VWF initialization for every accepted event-render invocation, including choices | Ordinary dialogue scope runtime-validated; choice rows intentionally use the same path |
| ROM `$ED:70C0-$70F4` | 53 bytes | Table-driven cursor advance / termination helper | Runtime-validated |
| ROM `$ED:7100-$710F` | 16 bytes | Dialogue scope wrapper; shared-row call or stock font-row fallback | Runtime-validated shared-row path |
| ROM `$ED:7180-$71D9` | 90 bytes | Per-character Y helper + chunk-boundary snapshot + stock-choice option/terminal anchor resync + private-buffer load | Runtime-validated on `$0331`; GAME SELECT remains stock |
| ROM `$ED:7200-$727F` | 128 bytes | Dialogue advance table | Runtime-validated |
| ROM `$ED:7280-$72E9` | 106 bytes | Cross-cell outline-boundary repair | Runtime-validated exact-tag repair on stock and relocated dialogue |
| ROM `$ED:7340-$7378` | 57 bytes | Generic physical-cell commit + >32 line-break safety conversion + exact-continuation capture call | Runtime-validated ordinary-dialogue path; byte-identical shared install with `vwf_ui` |
| ROM `$ED:7380-$73AA` | 43 bytes | Useful-width -> physical-cell snapshot helper | Runtime-validated |
| ROM `$ED:73B0-$73B8` | 9 bytes | Test private renderer-active tag for internal hooks | Runtime-validated |
| ROM `$ED:7500-$76A8` | 425 bytes | Dialogue parser pixel-budget preflight / safe-space rewind helper | Runtime-validated ordinary-dialogue path; choice commands receive no `vwf_dialogues` parser special case |
| ROM `$ED:7700-$7760` | 97 bytes | Single-glyph visible-extent + advance preflight helper | Runtime-validated as part of right-edge fix |
| ROM `$ED:7780-$77FF` | 128 bytes | Generated framed-right-edge table for decoded codes `$80-$FF` | Runtime-validated as part of right-edge fix |
| ROM `$ED:7800-$782D` | 46 bytes | Choice highlight geometry helper | Runtime-validated on `$00CE/$00CF/$00D0/$00D1/$0202` and short-choice fallback |
| ROM `$ED:7880-$7901` | 130 bytes | Two-option visual-boundary helper with decorated-choice fallback, two-cell private left compaction and late-first-option right-edge compaction | Runtime-validated on `$00CE/$00CF/$00D0/$00D1/$0202` |
| ROM `$ED:7910-$792A` | 27 bytes | Last non-space VWF endpoint tracker for active two-option rows | Runtime-validated as part of the measured-end path |
| ROM `$ED:7930-$7986` | 87 bytes | Exact interrupted-chunk continuation restore / partial-cell rewind helper | Runtime-validated with the opening falling-hero split cry |
| ROM `$ED:7990-$79F9` | 106 bytes | Exact useful-phase + partial-bitmap-cell continuation capture helper | Runtime-validated with the opening falling-hero split cry |
| ROM `$ED:7A00-$7A2B` | 44 bytes | Shared renderer-entry dispatcher installed by `vwf_dialogues` / `vwf_ui` | Current payload inside the shared `$ED:7A00-$7A7F` reservation; choice-helper growth is guarded before this block |
| ROM `$D2:DFE4-$E0DF` | 252 bytes | `dialogue_french` glyph span `$D3-$E7` | Canonical shared glyph bytes; overlaps the intro `$D4-$E5` subset byte-identically |
| WRAM `$7E:9380` | 1 byte | Shared parser mode (`2` during `vwf_dialogues` private dialogue decoding) | Runtime-validated; parser phase only |
| WRAM `$7E:9381` | 1 byte | Parser-local fresh-left-edge marker (`1` when stock remaining width is 29 cells at parser start) | Historical scratch retained by parser preflight; renderer does **not** read it; `vwf_intro` use is mutually exclusive |
| WRAM `$7E:9390-$93BB` | 44 bytes | Shared decoded-text private buffer; up to 38 dialogue glyphs + control/padding | Runtime-validated |
| WRAM `$7E:9382` | 1 byte | Private dialogue pixel cursor | Tagged event render (`$C9/$CA` or validated `$E8-$EC`) |
| WRAM `$7E:9383-$9384` | 2 bytes | Row shift/composition scratch | Tagged event render (`$C9/$CA` or validated `$E8-$EC`) |
| WRAM `$7E:9385` | 1 byte | `vwf_dialogues` renderer-active tag | Per `$C0:1664` invocation |
| WRAM `$7E:9386-$9387` | 2 bytes | Multiply-by-12 scratch for destination Y | Tagged event render (`$C9/$CA` or validated `$E8-$EC`) |
| WRAM `$7E:9388-$9389` | 2 bytes | Row spill/composition scratch | Tagged event render (`$C9/$CA` or validated `$E8-$EC`) |
| WRAM `$7E:938A-$938B` | 2 bytes | Zero-extended width-table index | Tagged event render (`$C9/$CA` or validated `$E8-$EC`) |
| WRAM `$7E:938C-$938D` | 2 bytes | Outline-repair scratch | Runtime-validated exact-tag post-outline repair on `vwf_dialogues` dialogue |
| WRAM `$7E:938E` | 1 byte | Saved decoded-character count for current chunk | Tagged event render (`$C9/$CA` or validated `$E8-$EC`) |
| WRAM `$7E:938F` | 1 byte | Saved physical-cell count for current useful chunk | Tagged event render (`$C9/$CA` or validated `$E8-$EC`) |
| WRAM `$7E:93D0-$93DF` | 16 bytes | Exact interrupted-chunk continuation state: valid flag, 0-7 px phase, expected stock cell/line and preserved 12-byte partial bitmap cell | Tagged event dialogue only; consumed once on a structurally matching same-line continuation |
| WRAM `$7E:93BC` | 1 byte | Last non-space VWF endpoint for active two-option row | Choice render only |
| WRAM `$7E:93BD-$93BF` | 3 bytes | Private visual boundaries: first option, second option, terminal | Runtime-validated wide-choice geometry |
| WRAM `$7E:93C0` | 1 byte | Private choice geometry valid flag | Choice render only |

The shared parser buffer is activated only when the `$C0:16B8` caller return is
`$114B`; GAME SELECT's `$235B` parser call stays on `$A1A4`. `$A1C5-$A1C7` are
live stock state and are never used as extra decoded slots.

`$7E:9385` overlaps `vwf_intro`'s intro-only glyph-advance scratch. This is safe
because translated intro event `$0400` is intercepted by `vwf_intro` at
`$C0:1664` and exits before `vwf_dialogues` reaches `$C0:167D`. Any renderer call
that does reach `vwf_dialogues` clears `$9385` before classifying the caller.

`intro_skip` reuses `$7E:938A-$938B` only during that same translated intro.
Again, `vwf_intro`'s early renderer interception prevents `vwf_dialogues`'s
event VWF path from using those bytes during event `$0400`.

The stock progression code at `$C0:13A3` is intentionally unmodified.

During parser mode 2, `$7E:9382-$938F` is reused temporarily by the pixel-wrap
preflight for its 16-bit current/test cursors, physical pixel budget, last safe
source-space checkpoint, DTE pair and fit flags. Parser and renderer phases do not
overlap; renderer entry reinitializes its own state before any of these bytes are
used for rendering.
