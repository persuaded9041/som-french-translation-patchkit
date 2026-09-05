# Dialogue VWF memory map

Component-local ROM hooks, helpers and WRAM scratch for the current `$C9`
checkpoint. The root `docs/MEMORY_MAP.md` keeps only the cross-component view.

| Range | Size | Purpose | Status |
| --- | ---: | --- | --- |
| ROM `$C0:1168-$116B` | 4 bytes | Post-stock-outline hook | Runtime-validated |
| ROM `$C0:167D-$1680` | 4 bytes | Renderer initialization hook | Runtime-validated |
| ROM `$C0:1686-$1689` | 4 bytes | Per-character destination hook | Runtime-validated |
| ROM `$C0:16A4-$16A7` | 4 bytes | Stock-selected font-row compositor hook | Runtime-validated |
| ROM `$C0:16B1-$16B6` | 6 bytes | Cursor advance / stock loop termination hook | Runtime-validated |
| ROM `$ED:7040-$706A` | 43 bytes | `$C9` renderer initialization / bitmap preparation / decoded-count capture | Runtime-validated |
| ROM `$ED:70C0-$70F2` | 51 bytes reserved | Table-driven cursor advance / termination helper | Runtime-validated |
| ROM `$ED:7100-$7152` | 83 bytes | Shift/merge/spill row compositor | Runtime-validated |
| ROM `$ED:7180-$71AD` | 46 bytes | Per-character Y helper + chunk-boundary snapshot call | Runtime-validated; fixed entry |
| ROM `$ED:71B0-$71E7` | 56 bytes | Lowercase framing selector | Runtime-validated |
| ROM `$ED:71E8-$71F7` | 16 bytes | Post-lowercase selector / dispatch | Runtime-validated; `$ED:71F4` pinned |
| ROM `$ED:7200-$727F` | 128 bytes | Dialogue advance table | Runtime-validated |
| ROM `$ED:7280-$72E9` | 106 bytes | Cross-cell outline-boundary repair | Runtime-validated |
| ROM `$ED:72F0-$733F` | 80 bytes reserved | Extended uppercase/punctuation/French framing selector | Runtime-validated |
| ROM `$ED:7340-$7368` | 41 bytes | Generic interrupted-chunk physical-cell commit | Runtime-validated |
| ROM `$ED:7380-$73AA` | 43 bytes | Useful-width -> physical-cell snapshot helper | Runtime-validated |
| WRAM `$7E:9382` | 1 byte | Private dialogue pixel cursor | `$C9` only |
| WRAM `$7E:9383-$9384` | 2 bytes | Row shift/composition scratch | `$C9` only |
| WRAM `$7E:9386-$9387` | 2 bytes | Multiply-by-12 scratch for destination Y | `$C9` only |
| WRAM `$7E:9388-$9389` | 2 bytes | Row spill/composition scratch | `$C9` only |
| WRAM `$7E:938A-$938B` | 2 bytes | Zero-extended width-table index | `$C9` only |
| WRAM `$7E:938C-$938D` | 2 bytes | Outline-repair scratch | `$C9` only |
| WRAM `$7E:938E` | 1 byte | Saved decoded-character count for current chunk | `$C9` only |
| WRAM `$7E:938F` | 1 byte | Saved physical-cell count for current useful chunk | `$C9` only |

Component 05 reuses part of the same WRAM neighborhood only under its mutually
exclusive `$CA` intro scope. Component 07 uses `$7E:938A-$938B` only under that
same `$CA` intro scope. Any attempt to broaden component 06 beyond `$C9` must
audit this ownership again.

The stock progression code at `$C0:13A3` is intentionally unmodified.
