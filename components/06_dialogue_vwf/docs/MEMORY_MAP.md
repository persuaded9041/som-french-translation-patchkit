# Dialogue VWF memory map

Component-local ROM hooks, helpers and WRAM scratch for the current caller-gated
stock event-dialogue checkpoint. The root `docs/MEMORY_MAP.md` keeps only the
cross-component view.

| Range | Size | Purpose | Status |
| --- | ---: | --- | --- |
| ROM `$C0:16B8-$16BB` | 4 bytes | Shared parser-buffer initializer hook | Runtime-validated; byte-identical with component 05 |
| ROM `$C0:16C6-$16CF` | 10 bytes | Shared parser-capacity hook | Runtime-validated; byte-identical with component 05 |
| ROM `$C0:17CE-$17D1` | 4 bytes | Shared parser destination hook | Runtime-validated; byte-identical with component 05 |
| ROM `$C0:18DE-$18E1` | 4 bytes | Shared previous-character source hook | Runtime-validated; byte-identical with component 05 |
| ROM `$C7:43D0-$43E7` | 24 bytes | Shared parser write helper | Runtime-validated |
| ROM `$C7:4AC0-$4B3B` | 124 bytes | Shared caller-gated buffer initializer | Runtime-validated |
| ROM `$C7:4B40-$4B5A` | 27 bytes | Shared previous-character helper | Runtime-validated |
| ROM `$C7:4BC0-$4BE9` | 42 bytes | Shared capacity helper | Runtime-validated |
| ROM `$C7:4C84` | 1 byte | Component-06 dialogue private-buffer feature marker `$06` | Runtime-validated |
| ROM `$C7:4C90-$4CCE` | 63 bytes | Shared 8x12 row shift/merge/spill compositor | Runtime-validated; byte-identical with component 05 and with prior validated 06 compositor bytes |
| ROM `$C7:44C0-$4557` | 152 bytes | Shared runtime framing selector bundle | Runtime-validated; byte-identical overlap with component 05 |
| ROM `$C7:4560-$456C` | 13 bytes | Shared stock-font row load + framing + compositor helper | Runtime-validated; byte-identical overlap with component 05 |
| ROM `$C0:1168-$116B` | 4 bytes | Post-stock-outline hook | Runtime-validated exact-tag `$C9/$CA` scope; same tag used by relocation candidate |
| ROM `$C0:167D-$1680` | 4 bytes | Shared-renderer entry / caller classification hook | Runtime-validated |
| ROM `$C0:1686-$1689` | 4 bytes | Per-character destination hook | Runtime-validated |
| ROM `$C0:16A4-$16A7` | 4 bytes | Stock-selected font-row compositor hook | Runtime-validated |
| ROM `$C0:16B1-$16B6` | 6 bytes | Cursor advance / stock loop termination hook | Runtime-validated |
| ROM `$C0:16EA-$16ED` | 4 bytes | Dialogue-only source-fetch / pixel-wrap preflight hook | Runtime-validated on known right-edge overflow case; stock replay outside parser mode 2 |
| ROM `$ED:7040-$7092` | 83 bytes | Caller/bank gate, renderer initialization, bitmap preparation, decoded-count capture, 38-slot loop setup | Runtime-validated |
| ROM `$ED:70C0-$70F0` | 49 bytes | Table-driven cursor advance / termination helper | Runtime-validated |
| ROM `$ED:7100-$710F` | 16 bytes | Dialogue scope wrapper; shared-row call or stock font-row fallback | Runtime-validated shared-row path |
| ROM `$ED:7180-$71AC` | 45 bytes | Per-character Y helper + chunk-boundary snapshot + private-buffer load | Runtime-validated; fixed entry |
| ROM `$ED:7200-$727F` | 128 bytes | Dialogue advance table | Runtime-validated |
| ROM `$ED:7280-$72E9` | 106 bytes | Cross-cell outline-boundary repair | Runtime-validated exact-tag repair on ordinary `$C9/$CA` dialogue; relocation-bank path pending runtime validation |
| ROM `$ED:7340-$736D` | 46 bytes | Generic physical-cell commit + >32 line-break safety conversion | Runtime-validated |
| ROM `$ED:7380-$73AA` | 43 bytes | Useful-width -> physical-cell snapshot helper | Runtime-validated |
| ROM `$ED:73B0-$73B8` | 9 bytes | Test private renderer-active tag for internal hooks | Runtime-validated |
| ROM `$ED:7500-$76A8` | 425 bytes | Dialogue parser pixel-budget preflight / safe-space rewind helper | Runtime-validated on known right-edge overflow case |
| ROM `$ED:7700-$7760` | 97 bytes | Single-glyph visible-extent + advance preflight helper | Runtime-validated as part of right-edge fix |
| ROM `$ED:7780-$77FF` | 128 bytes | Generated framed-right-edge table for decoded codes `$80-$FF` | Runtime-validated as part of right-edge fix |
| WRAM `$7E:9380` | 1 byte | Shared parser mode (`2` during component-06 private dialogue decoding) | Runtime-validated; parser phase only |
| WRAM `$7E:9390-$93BB` | 44 bytes | Shared decoded-text private buffer; up to 38 dialogue glyphs + control/padding | Runtime-validated |
| WRAM `$7E:9382` | 1 byte | Private dialogue pixel cursor | Tagged event render (`$C9/$CA`; relocation candidate `$E8-$EC`) |
| WRAM `$7E:9383-$9384` | 2 bytes | Row shift/composition scratch | Tagged event render (`$C9/$CA`; relocation candidate `$E8-$EC`) |
| WRAM `$7E:9385` | 1 byte | Component-06 renderer-active tag | Per `$C0:1664` invocation |
| WRAM `$7E:9386-$9387` | 2 bytes | Multiply-by-12 scratch for destination Y | Tagged event render (`$C9/$CA`; relocation candidate `$E8-$EC`) |
| WRAM `$7E:9388-$9389` | 2 bytes | Row spill/composition scratch | Tagged event render (`$C9/$CA`; relocation candidate `$E8-$EC`) |
| WRAM `$7E:938A-$938B` | 2 bytes | Zero-extended width-table index | Tagged event render (`$C9/$CA`; relocation candidate `$E8-$EC`) |
| WRAM `$7E:938C-$938D` | 2 bytes | Outline-repair scratch | Runtime-validated exact-tag post-outline repair on component-06 dialogue |
| WRAM `$7E:938E` | 1 byte | Saved decoded-character count for current chunk | Tagged event render (`$C9/$CA`; relocation candidate `$E8-$EC`) |
| WRAM `$7E:938F` | 1 byte | Saved physical-cell count for current useful chunk | Tagged event render (`$C9/$CA`; relocation candidate `$E8-$EC`) |

The shared parser buffer is activated only when the `$C0:16B8` caller return is
`$114B`; GAME SELECT's `$235B` parser call stays on `$A1A4`. `$A1C5-$A1C7` are
live stock state and are never used as extra decoded slots.

`$7E:9385` overlaps component 05's intro-only glyph-advance scratch. This is safe
because translated intro event `$0400` is intercepted by component 05 at
`$C0:1664` and exits before component 06 reaches `$C0:167D`. Any renderer call
that does reach component 06 clears `$9385` before classifying the caller.

Component 07 reuses `$7E:938A-$938B` only during that same translated intro.
Again, component 05's early renderer interception prevents component 06's
event VWF path from using those bytes during event `$0400`.

The stock progression code at `$C0:13A3` is intentionally unmodified.

During parser mode 2, `$7E:9382-$938F` is reused temporarily by the pixel-wrap
preflight for its 16-bit current/test cursors, physical pixel budget, last safe
source-space checkpoint, DTE pair and fit flags. Parser and renderer phases do not
overlap; renderer entry reinitializes its own state before any of these bytes are
used for rendering.
