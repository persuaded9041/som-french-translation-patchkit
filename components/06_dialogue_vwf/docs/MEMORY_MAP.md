# Dialogue VWF memory map

| Range | Size | Purpose | Runtime status |
| --- | ---: | --- | --- |
| ROM `$C0:167D-$C0:1680` | 4 bytes | Renderer initialization hook | Runtime-validated in current `$C9` checkpoint |
| ROM `$C0:1686-$C0:1689` | 4 bytes | Per-character destination-position hook replacing `LDA $A1A4,X / INX` | Runtime-validated in current `$C9` checkpoint |
| ROM `$C0:16B1-$C0:16B6` | 6 bytes | Per-character cursor advance / stock loop termination hook | Runtime-validated in current `$C9` checkpoint |
| ROM `$C0:13A3-$C0:13A8` | 6 bytes | Stock-equivalent progression hook | Runtime-validated |
| ROM `$ED:7010-$ED:7019` (`0x2D7010-0x2D7019`) | 10 bytes | Stock-equivalent progression trampoline | Runtime-validated |
| ROM `$ED:7040-$ED:705F` (`0x2D7040-0x2D705F`) | 32 bytes | Renderer initialization helper / `$C9` cursor reset and bitmap preparation | Runtime-validated in current `$C9` checkpoint |
| ROM `$ED:7180-$ED:71A9` (`0x2D7180-0x2D71A9`) | 42 bytes | Per-character Y helper derived from the true cumulative pixel cursor; no diagnostic tile-boundary realignment | Runtime-tested limited VWF |
| ROM `$ED:70C0-$ED:70F2` (`0x2D70C0-0x2D70F2`) | 50 bytes | Table-driven cursor advance and stock loop termination helper | Runtime-validated |
| ROM `$ED:7100-$ED:7152` (`0x2D7100-0x2D7152`) | 83 bytes | Stock-selected font-row compaction/shift/spill compositor; calls the framing selector at the same application point | Runtime-validated with complete lowercase framing selector |
| ROM `$ED:71B0-$ED:71E7` (`0x2D71B0-0x2D71E7`) | 56 bytes | Lowercase framing selector (`a-h/k/m-s/u-z=1`, `i/l=3`, `j/t=2`); rows after `z` branch into the adjacent punctuation selector | Lowercase path runtime-validated; preserves validated `$ED:7180` char-start allocation |
| ROM `$ED:71E8-$ED:71F7` (`0x2D71E8-0x2D71F7`) | 16 bytes | Punctuation selector for `$BF-$C2`; runtime-validated: these rows keep their stock 1 px left margin. The batch-2 `JML` entry is pinned at `$ED:71F4` | Runtime-validated; first left-gap build was rejected after accidentally moving the trampoline to `$ED:71F3` |
| ROM `$ED:72F0-$ED:733F` (`0x2D72F0-0x2D733F`) | 80 bytes reserved | Extended post-lowercase selector. Preserves runtime-validated A-Z/punctuation handling; keeps `$B5-$BE` and `$CD-$D3` unshifted; adds runtime-validated French framing `$D4-$E3=1 px`, `$E4/$E5=0 px` | Runtime-validated for A-Z, punctuation and French charset |
| ROM `$ED:7200-$ED:727F` (`0x2D7200-0x2D727F`) | 128 bytes | Editable dialogue advance table, indexed by decoded glyph `$80-$FF` | Runtime-validated lookup and lowercase `ink_width + 1` metrics |
| WRAM `$7E:9382` | 1 byte | Private dialogue pixel cursor; component 05 uses the same byte only in its mutually exclusive `$CA` intro scope | Runtime-validated in both mutually exclusive scoped uses |
| WRAM `$7E:9386-$9387` | 2 bytes | Temporary multiply-by-12 scratch in per-character Y calculation | Runtime-validated in current `$C9` checkpoint |
| WRAM `$7E:938A-$938B` | 2 bytes | Zero-extended width-table index; used only in `$C9` dialogue scope | Runtime-validated |

The shared scratch is mutually exclusive in the current scoped implementation: component 05 uses it only for its scoped `$CA` intro renderer while component 06 modifies it only for `$C9`.

### Continuous-cursor checkpoint

Keeps the selected stock font-row hook at ROM `$C0:16A4-$C0:16A7` (`JSL $ED:7100`). The helper at `$ED:7100` repositions the already stock-selected row using the pixel cursor and writes any right-side spill to the next 12-byte text cell. WRAM `$7E:9383-$9384` and `$7E:9388-$9389` are temporary shift/row scratch used only in the `$C9` dialogue scope.

The per-character start helper at `$ED:7180` now performs no character-history test and no realignment. It derives the destination tile solely from the true cumulative pixel cursor for every `$C9` glyph. The old `$ED:7080` slot is not written.

### Runtime-validated width-table checkpoint

Runtime micro-diagnostics established that the existing continuous compositor can advance drawn glyphs by 3, 4, 5, 6, 7 and 8 pixels. The 128-entry advance-table lookup is runtime-validated. Its implementation keeps A 8-bit, writes the 7-bit glyph index to `$7E:938A`, clears `$7E:938B`, loads 16-bit X from that word, then performs `LDA.l $ED7200,X`.

Two earlier table attempts remain rejected: one indexed the table unsafely and lost some glyphs; another changed accumulator width with `REP/SEP` in the character-end helper and caused severe rendering loss.

Earlier metric experiments established working narrow advances, but a broad intro-derived batch was visually rejected before complete lowercase framing because adjacent glyphs could lose the desired separator. Complete lowercase framing is now runtime-validated, so component 05's exact `ink_width + 1` rule is runtime-validated for lowercase `a-z`. The values are `a-h/k/m-q/s/u-z=7`, `i/l=3`, `j=4`, `r=6`, and `t=5`. Non-lowercase entries retain the conservative `min(8, rightmost_ink_column + 2)` baseline. No ROM/WRAM allocation changes are introduced.

### Framing diagnostics

The isolated lowercase `t` transform (2-pixel left shift), lowercase `a-h` batch (1-pixel left shift), and lowercase `m-s` batch (1-pixel left shift) are runtime-validated. The behavior-preserving factorization of the active `a-h`, `i/l`, and `m-s` selection is also runtime-validated.

The `u-z` extension and the final `j/k/t` integration are runtime-validated. Complete lowercase framing is selected by `$ED:71B0-$ED:71E7`, while the actual row transform stays in the validated `dialogue_font_row` path. Geometry is `a-h/k/m-s/u-z=1`, `i/l=3`, `j/t=2`. The lowercase width-table entries are runtime-validated. The outline boundary repair uses only `$7E:938C-$938D` as temporary state under the same `$C9` scope.

### Runtime-validated outline boundary repair

- ROM `$C0:1168-$C0:116B`: post-stock-outline hook.
- ROM `$ED:7280-$ED:72E9`: `$C9`-only boundary-repair helper.
- WRAM `$7E:938C-$938D`: temporary tile/row counters for the outline repair.

The hook is deliberately after stock `JSR $162C`. The rejected `$C0:1165` probe
replaced that call and suppressed most of the outline; it is not part of the
current code.

### Runtime-validated punctuation checkpoint

Handled punctuation uses one black pixel before and after the ink. Current
shifts / advances: `$BF-$C2` = `0 px / 4,4,7,4`; `$C3/$C4` = `0/1 px / 7,7`;
`$C6/$C7/$C9/$CA` = `0 px / 8`; `$C8/$CB/$CC` = `2/2/1 px / 5`.
Colon `$C5` is runtime-validated at `shift=1, advance=7`, yielding 2 px black framing on the left and 3 px on the right of its 2 px ink. `$CD` remains excluded.

### `$CD` deliberately excluded — stock/default only

`$CD` has no active special handling and must stay that way: no framing branch,
no dedicated metric, no punctuation-specific self-test, and no temporary test
text. It falls through to the stock/default conservative non-lowercase path.
The glyph appeared as an X-like symbol in runtime tests. A previous isolated 6 px
metric attempt coincided with severe rendering loss; removing `$CD` from that
test restored normal rendering. `$CD` is not needed for the current French
dialogue work, so do not modify it unless a future investigation is explicitly
dedicated to that glyph.

### Runtime-validated uppercase, colon and stock digits

Uppercase `A-Z` is runtime-validated at shift/advance `1/7` for `A-H/J-Z` and
`3/3` for `I`. Colon `$C5` is runtime-validated at `shift=1, advance=7`.
`$B5-$BE` are digits `0-9`; runtime inspection confirmed that their stock widths
are satisfactory, so they remain on the generic conservative path.

### Runtime-validated shared French charset

`$D4-$E5` is populated from the canonical `shared/french_charset` atlas. Component
06 independently writes the full glyph set and raises the DTE threshold from `$D3`
to `$E6`. Runtime-validated framing/advances are `$D4-$E3 = 1/7` and
`$E4/$E5 = 0/8`. The temporary 18-byte runtime diagnostic has been removed from
the cleaned checkpoint; no dialogue text is patched for charset exposure.

