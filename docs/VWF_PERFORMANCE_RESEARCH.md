# VWF performance research — Ring/UI

Status: **Stages 1, 2A, 2B, 2C-R1 and 3A runtime-validated**. The original Stage 2C is rejected.
Baseline: promoted source in this archive; general Ring/UI performance work is frozen at Stage 3A.

## Symptom

The top-level Ring Menu is visibly less fluid with `vwf_ui` than with the stock fixed-width renderer.
Static inspection shows that this is expected from the current architecture: the stock renderer performs a direct font-row load/store, whereas the VWF path adds multiple cross-bank helpers and a variable shift/merge compositor for every one of the 12 pixel rows of every rendered glyph.

## Main hot spots

### 1. Ring renders 38 private slots regardless of real title length

`components/vwf_ui/build_patch.py::make_ui_renderer()` clears a 38-byte private render buffer, copies the stock decoded row, then sets `$A176=$26` for Ring/Forge/D9/MONEY. Therefore padding `$80` spaces are rasterized like real characters even though the bitmap is already cleared.

The nine reviewed Ring titles contain 4..32 real glyphs (average 20). Baseline work is always 38 glyphs = 456 font-row passes. Real-count rendering would average 240 font-row passes, a 47.4% reduction in Ring glyph passes before any lower-level optimization.

Examples:

| title | real glyphs | useless padding glyphs | useless 12-row passes |
|---|---:|---:|---:|
| `Équipement` | 10 | 28 | 336 |
| `Réglages manette` | 16 | 22 | 264 |
| `Jeter` | 5 | 33 | 396 |
| `Tous` | 4 | 34 | 408 |
| 32-character titles | 32 | 6 | 72 |

Merchandise, battle banner and GAME FILE Mana already use `$938E` (true decoded count), proving that the generic renderer supports this mode.

### 2. Per-font-row call stack is expensive

For generic UI VWF, the stock `$C0:16A4` font-row load is replaced by a JSL helper. For every one of the 12 rows of every glyph the active path is roughly:

`C0 hook -> ED font-row helper -> ED scope helper -> C7 row renderer -> C7 framing selector -> C7 compositor -> returns`

The stock path at the same point is only `LDA.l $D2:DC00,X` followed by the existing `STA $9000,Y`.

The current shared compositor also recalculates `pixel_cursor & 7` for every row and performs variable `LSR` / `ASL` loops. The shift is actually constant across all 12 rows of a glyph, so much of this work is redundant.

### 3. Outline bitmap is scanned twice

The stock outline routine at `$C0:162C` already scans 32 cells × 12 rows. The VWF post-outline repair at `$ED:7280` then scans the same 32 × 12 source rows again solely to repair cross-cell left/right outline pixels. This second 384-row pass is added to every generic VWF render, including Ring titles.

### 4. Generic per-character helpers do work irrelevant to Ring

Ring titles use the generic character-start/end path, which still performs structural checks for shop anchors, MONEY kerning and dialogue-choice geometry. These are correctly gated, but the checks and helper calls still consume CPU time for every Ring character.

### 5. Other UI VWF paths have separate performance opportunities

- Status labels and weapon/magic skill names bypass some generic scope checks, but still call the shared framing/compositor 12 times per glyph.
- The magic lower panel is especially expensive: the stock six-pass lifecycle means each 480 px logical row is rasterized once for its left pass and again for its right pass. This is deliberately left untouched in the first Ring optimization because the panel is runtime-validated and has different geometry/lifecycle constraints.

## Optimization plan

### Stage 1 — Ring true decoded count (**runtime-validated**)

For selector 0 (Ring) only, set `$A176` from saved decoded count `$938E`, exactly like the already-validated merchandise/battle/GAME FILE families. No parser, text, width metric, suffix geometry, DMA geometry, outline code, or other UI family is changed.

Expected impact: eliminate 6..34 synthetic glyphs per Ring title (average 18), i.e. about 47% of Ring glyph rasterization calls on the current nine labels.

Runtime result: user confirmed the Ring is smoother and validated this step on 2026-09-20. This behavior is now the baseline and must be preserved.

### Stage 2 — generic no-behavior-change low-level cleanup

#### Stage 2A — inline the hot font-row scope test (**runtime-validated**)

The `$C0:16A4` font-row hook previously called `$ED:73B0` with `JSL` for every
one of the 12 rows of every glyph, then branched on carry. Stage 2A inlines the
exact same acceptance rule directly in `$ED:7100`:

- `$9385 == 1` -> dialogue VWF;
- `$9385 == 2` -> UI VWF;
- `$9385 == 0` or `>=3` -> stock path (including intro scratch values 3..8).

No renderer identity, glyph byte, metric, geometry, compositor operation or
outline behavior changes. Static 65816 instruction-cycle accounting saves about
18 CPU cycles per rendered font row on the active path, or about 216 cycles per
glyph. With the post-Stage-1 Ring average of ~20 real glyphs, this is roughly
4,320 cycles avoided per title before considering memory wait-state details.

Binary comparison against the runtime-validated Stage 1 aggregate ROM changes
only 19 bytes at `$ED:7100-$ED:7112`, plus checksum/complement bytes. Because
this helper is shared by `vwf_dialogues` and `vwf_ui`, both standalone patches
are rebuilt so their intentionally overlapping bytes remain identical.

#### Stage 2B — cache generic glyph phase once per character (**runtime-validated**)

The generic stock text loop now computes `pixel_cursor & 7` once at character
start, after all shop/MONEY/choice cursor resynchronization, and stores it in
`$9383`. The destination `Y = floor(pixel_cursor/8)*12` calculation is moved
byte-for-byte-equivalently into the private helper at `$ED:7A80`.

The hot font-row path at `$ED:7100` then calls a private fast renderer at
`$ED:7AB0`. This helper keeps the validated stock-font load and shared framing
selector, but inlines the existing shift/merge/spill compositor and reads the
cached phase instead of recalculating `cursor & 7` for every pixel row.

Crucially, `$C7:4560` and `$C7:4C90` are unchanged. Direct callers such as
`vwf_intro`, Status labels, weapon/magic names and the 3x480px magic panel
therefore retain the already validated generic compositor path. Stage 2B only
changes the generic C0 text loop used by dialogue and the Ring/Forge/shop/MONEY
UI families.

Static instruction accounting removes one compositor `JSL/RTL` pair and the
per-row `AND #$07 / STA $9383`, for roughly 20 cycles saved per pixel row. The
one-time character-start cache costs additional work, leaving an estimated net
saving a little above 200 CPU cycles per rendered glyph (~4,000+ cycles for a
20-glyph Ring title), before ROM/WRAM wait-state details.

Aggregate and standalone builds succeed. Compared with runtime-validated Stage
2A, differences are confined to the shared generic helpers at `$ED:7100`,
`$ED:7180+`, the new `$ED:7A80-$7AF1` fast reserve, and checksum bytes. The
user runtime-validated Stage 2B on 2026-09-20 and reported another visible
improvement in Ring fluidity.

#### Stage 2C — first candidate (**rejected at runtime**)

The first Stage-2C attempt packed current+spill into a 16-bit value and used
`JMP (abs,X)` to enter an unrolled LSR chain. It black-screened immediately
when opening the Ring. Root cause: on the 65816, absolute indexed indirect
`JMP (addr,X)` fetches its 16-bit pointer from **bank 0**, while the candidate
placed its table in `$ED:7Axx`. The CPU therefore consumed unrelated bank-0
data as a jump pointer. This candidate is rejected and must never be restored.

#### Stage 2C-R1 — safe packed/unrolled compositor (**runtime-validated**)

R1 restarts from the runtime-validated Stage 2B source. It preserves the same
packed 16-bit `(source<<8)>>phase` idea but removes `JMP (abs,X)` completely.
Source is kept in hidden B while the stock row counter is saved. A long-addressed
`LDA.l` reads only the low byte of a synthetic RTS target from an explicit `$ED`
table; the common target high byte is pushed separately. `REP #$20 / AND #$FF00`
then reconstructs `source<<8` before `RTS` enters the local 1..7 LSR chain.

The helper is 67 bytes inside the existing 80-byte `$ED:7AB0-$7AFF` reserve.
No new ROM/WRAM allocation is introduced. `$C7:44C0/$4560/$4C90` remain
byte-identical. Static source/phase equivalence is exhaustive for all 256 source
bytes and all 8 phases; aggregate ROM differences from Stage 2B are confined to
the fast helper and checksum. Runtime validation on the Ring was accepted by the
user on 2026-09-20.

### Stage 3 — outline fusion / bounded repair

#### Stage 3A — bounded post-outline repair (**runtime-validated**)

Keep the stock `$C0:162C` outline pass completely unchanged, but stop the
VWF-only post-outline repair from rescanning all 32 source cells unconditionally.

The generic renderer already computes the useful width as physical 8-pixel cells
in `$7E:938F`. Stage 3A makes that snapshot available before outline processing
for true-count renderers as well (notably the Stage-1 Ring path), without changing
the existing `$A1CE` line-break/progression decisions. The post-outline helper
then scans only:

`min(32, physical_cells + 1)`

The one-cell safety margin is intentional. Exhaustive inspection of all 128
runtime glyph codes after installing the canonical direct-French glyph span,
with the validated framing/advance policy, finds no framed ink beyond the
logical advance. Scanning one extra cell therefore adds a conservative guard
against future metric/glyph changes without depending on that exact equality.

For the nine current Ring labels the bounded repair covers 5..27 cells instead
of 32, averaging exactly 17 cells. This removes roughly 47% of the second
post-outline cell scan on an average Ring title while leaving the stock outline
routine and direct `$C7` VWF callers untouched.

Runtime validation was accepted by the user on 2026-09-20. General Ring/UI
performance work stops here by explicit decision: no Stage 3B is planned for the
current baseline. The stock outline pass remains unchanged because modifying its
output/DMA lifecycle would carry stronger stale-tile risks than the additive
post-outline repair.

Longer-term alternatives remain:

- a VWF-aware outline routine that performs stock outline generation and cross-cell repair in one pass; or
- a tightly bounded repair pass over only the cells actually touched by the VWF row.

This has strong upside but is more invasive than Stage 1/2.

### Deferred alternatives

More invasive Ring-specific renderers or changes to the stock outline pass are intentionally deferred. The separate magic lower-panel performance work was completed afterward and is documented in `docs/MAGIC_PANEL_PERFORMANCE_RESEARCH.md`.

## Validation state

- **Stage 1:** runtime-validated by the user on 2026-09-20; visible Ring fluidity improved.
- **Stage 2A:** runtime-validated by the user on 2026-09-20; perceived Ring fluidity improved again.
- **Stage 2B:** runtime-validated by the user on 2026-09-20; Ring fluidity improved again.
- **Stage 2C initial:** rejected; Ring black-screen caused by bank-0 semantics of `JMP (addr,X)`.
- **Stage 2C-R1:** runtime-validated by the user on 2026-09-20.
- **Stage 3A:** runtime-validated by the user on 2026-09-20; general Ring/UI optimization stops here.
- Stage 2C-R1/3A deliberately leave `$C7:44C0/$C7:4560/$C7:4C90` unchanged so direct VWF callers keep the validated path.
