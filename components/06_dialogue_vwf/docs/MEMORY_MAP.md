# Dialogue VWF memory map

Component-local ROM hooks, helpers and WRAM scratch for the current caller-gated
stock event-dialogue checkpoint. The root `docs/MEMORY_MAP.md` keeps only the
cross-component view.

| Range | Size | Purpose | Status |
| --- | ---: | --- | --- |
| ROM `$C0:1168-$116B` | 4 bytes | Post-stock-outline hook | Runtime-validated on `$C9` |
| ROM `$C0:167D-$1680` | 4 bytes | Shared-renderer entry / caller classification hook | Runtime-validated |
| ROM `$C0:1686-$1689` | 4 bytes | Per-character destination hook | Runtime-validated |
| ROM `$C0:16A4-$16A7` | 4 bytes | Stock-selected font-row compositor hook | Runtime-validated |
| ROM `$C0:16B1-$16B6` | 6 bytes | Cursor advance / stock loop termination hook | Runtime-validated |
| ROM `$ED:7040-$7081` | 66 bytes | Caller/bank gate, renderer initialization, bitmap preparation, decoded-count capture | Runtime-validated |
| ROM `$ED:70C0-$70F0` | 49 bytes | Table-driven cursor advance / termination helper | Runtime-validated |
| ROM `$ED:7100-$7150` | 81 bytes | Shift/merge/spill row compositor | Runtime-validated |
| ROM `$ED:7180-$71AB` | 44 bytes | Per-character Y helper + chunk-boundary snapshot call | Runtime-validated; fixed entry |
| ROM `$ED:71B0-$71E7` | 56 bytes | Lowercase framing selector | Runtime-validated |
| ROM `$ED:71E8-$71F7` | 16 bytes | Post-lowercase selector / dispatch | Runtime-validated; `$ED:71F4` pinned |
| ROM `$ED:7200-$727F` | 128 bytes | Dialogue advance table | Runtime-validated |
| ROM `$ED:7280-$72E9` | 106 bytes | Cross-cell outline-boundary repair | Runtime-validated on `$C9` |
| ROM `$ED:72F0-$733F` | 80 bytes | Extended uppercase/punctuation/French framing selector | Runtime-validated |
| ROM `$ED:7340-$7366` | 39 bytes | Generic interrupted-chunk physical-cell commit | Runtime-validated |
| ROM `$ED:7380-$73AA` | 43 bytes | Useful-width -> physical-cell snapshot helper | Runtime-validated |
| ROM `$ED:73B0-$73B8` | 9 bytes | Test private renderer-active tag for internal hooks | Runtime-validated |
| WRAM `$7E:9382` | 1 byte | Private dialogue pixel cursor | Tagged `$C9/$CA` event render |
| WRAM `$7E:9383-$9384` | 2 bytes | Row shift/composition scratch | Tagged `$C9/$CA` event render |
| WRAM `$7E:9385` | 1 byte | Component-06 renderer-active tag | Per `$C0:1664` invocation |
| WRAM `$7E:9386-$9387` | 2 bytes | Multiply-by-12 scratch for destination Y | Tagged `$C9/$CA` event render |
| WRAM `$7E:9388-$9389` | 2 bytes | Row spill/composition scratch | Tagged `$C9/$CA` event render |
| WRAM `$7E:938A-$938B` | 2 bytes | Zero-extended width-table index | Tagged `$C9/$CA` event render |
| WRAM `$7E:938C-$938D` | 2 bytes | Outline-repair scratch | `$C9` post-outline path only |
| WRAM `$7E:938E` | 1 byte | Saved decoded-character count for current chunk | Tagged `$C9/$CA` event render |
| WRAM `$7E:938F` | 1 byte | Saved physical-cell count for current useful chunk | Tagged `$C9/$CA` event render |

`$7E:9385` overlaps component 05's intro-only glyph-advance scratch. This is safe
because translated intro event `$0400` is intercepted by component 05 at
`$C0:1664` and exits before component 06 reaches `$C0:167D`. Any renderer call
that does reach component 06 clears `$9385` before classifying the caller.

Component 07 reuses `$7E:938A-$938B` only during that same translated intro.
Again, component 05's early renderer interception prevents component 06's
`$C9/$CA` VWF path from using those bytes during event `$0400`.

The stock progression code at `$C0:13A3` is intentionally unmodified.
