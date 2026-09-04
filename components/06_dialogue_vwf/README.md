# 06 — Dialogue VWF

Development component for proportional rendering of normal in-game event text.

## Runtime-validated foundation

The following points are proven in game and must be preserved:

- `$C0:167D` supports a neutral jump to extended ROM and back; relocating the whole stock renderer is rejected because it glitched at runtime.
- `$C0:13A3` is genuinely executed during progressive text display and `$A1D0` participates in progression. The current build keeps stock `+1/+1` progression.
- `$001D03 == $C9` is stable at this stage and safely scopes the current dialogue work without affecting the `$CA` post-new-game intro. It is **not** yet the final definition of all dialogues.
- Individual glyph rows can be intercepted safely.
- A glyph can spill across two 12-byte cells without corruption.
- Successive glyphs can share cells using a cumulative pixel X position.
- Returning from a custom cumulative compositor to the stock renderer **mid-line is rejected**: runtime testing produced extra glitched characters.
- A fully custom line renderer is also rejected for now: even after fixing its exit-state contract, runtime testing selected/rendered incorrect glyph data.

## Validated architecture

The stock `$C0:168A-$C0:16B0` path remains responsible for character decode, `$80`-based glyph indexing, `×12` addressing and the 12-row reads from `$D2:DC00`. Component 06 only changes where the already-selected glyph rows are composed.

A fixed-8 version of this architecture rendered perfectly at runtime. The later continuous-cursor diagnostics then validated narrow `i` / `l` glyphs and long chains of following 8-pixel glyphs without the artificial gaps produced by earlier realignment probes.

Do **not** reimplement the code-to-glyph lookup and do **not** relocate the whole stock renderer.

## Runtime-validated checkpoint — table-driven advances

The table lookup and renderer architecture below are the cleaned runtime-safe checkpoint. The source contains no WAIT/event-resume diagnostic code.

For bank `$C9` only, the original validated table checkpoint used:

- space `$80`: 4 px advance;
- lowercase `i` `$89`: 3 px advance;
- lowercase `l` `$8C`: 3 px advance;
- every other decoded glyph: 8 px advance.

The 128-entry advance table at `$ED:7200-$ED:727F` and its zero-extended WRAM index through `$7E:938A-$938B` are now runtime-validated. The lookup keeps A in 8-bit mode and does not disturb the stock row-loop accumulator state.

`$C0:16A4` intercepts only the already-selected stock font row. The helper composes that row at `pixel_cursor & 7`, merges it with any existing pixels in the current tile, and spills the right side into the following 12-byte tile cell. `Y` is derived from `floor(pixel_cursor / 8) * 12` for every glyph, with no forced tile-boundary realignment.

The stock lowercase rows are now framed before composition according to their validated left bearings. This framing is separate from the advance table: the current metrics remain deliberately conservative until they are tightened against the framed glyph geometry.

### Latest runtime result

This continuous-cursor version is runtime-validated for the current limited width set across several dialogue lines. Words containing narrow `i` / `l` and subsequent wide glyphs render continuously without the earlier diagnostic gaps. Controlled micro-diagnostics also validated drawn-glyph advances of **3, 4, 5, 6, 7 and 8 pixels**. A first 7-pixel failure was not reproducible after a clean rebuild and is treated as a bad diagnostic build, not a renderer limitation.

One known exception remains: the stock dialogue containing `Wait up!` still shows a large gap before `up!`. Comparison with the unpatched ROM shows `up!` starting at the same stock X position. This has been isolated as an event-interruption/resume issue rather than a general spill/cursor failure and is intentionally deferred.

See [`docs/EVENT_INTERRUPTION_NOTES.md`](docs/EVENT_INTERRUPTION_NOTES.md) for the complete investigation and rejected experiments. None of those diagnostics remain in the production source.

## Runtime-validated metric baseline — guaranteed one-pixel separator

The broad intro-derived metric batch was runtime-stable, but visually rejected because some adjacent glyphs no longer had a clearly visible black pixel between them. This did **not** indicate a compositor failure; it exposed a metric/framing mismatch.

Component `05_intro_vwf_french` gets its clean spacing by first left-compacting every bitmap and then using `ink_width + 1` as the advance. Component 06 does not yet compact ordinary glyphs, so copying the same numeric advance onto a stock bitmap that still has its original left bearing can consume the intended separator.

The conservative metric baseline used before complete lowercase framing uses the generated advance table. For every ordinary unshifted stock glyph, the advance is now derived from the bitmap **as actually rendered**: `rightmost_ink_column + 2`, capped at 8 px. That guarantees one full black pixel after the glyph whenever a narrower-than-8 advance is possible. Space remains 4 px. Lowercase `i/l` remain special for now: their already validated helper compacts their two-pixel ink to columns 0..1 and keeps a 3-pixel advance, so column 2 is the separator.

This is deliberately conservative. Most stock Latin glyphs end at column 6, so without general bitmap compaction they return to an 8-pixel advance. `r` becomes 7 px, `t` becomes 7 px, and common punctuation such as `.`, `,` and `'` becomes 4 px. The purpose of this checkpoint is to restore the separator invariant before introducing a general bitmap-framing layer.

The zero-extended index through `$7E:938A-$938B` remains the runtime-validated lookup method. Two earlier table experiments stay rejected: an unsafe X index caused selective glyph loss, and a `REP/SEP` variant caused severe rendering loss by disturbing the stock accumulator state.

## Runtime-validated micro-diagnostic — lowercase `t` framing

The rejected general `left_shift[128]` experiment corrupted dialogue rendering and is not present in this source. A later isolated diagnostic proved that bitmap framing itself is not limited to `i/l`: lowercase `t` (`$94`) rendered correctly when its stock rows were shifted left by 2 pixels, matching its ink bounds at columns 2..5, while its conservative 7-pixel advance was left unchanged.

That isolated `t` transform was later integrated successfully into the complete lowercase framing checkpoint described below.

## Runtime-validated framing batch — lowercase `a`-`h`

Lowercase `a` through `h` (`$81-$88`) are runtime-validated when their stock rows are shifted left by exactly 1 pixel. All eight glyphs have a one-pixel stock left bearing, and the batch rendered cleanly across complete dialogue lines. Their advances remain conservative in this framing-only checkpoint, so this validation isolates bitmap framing from metric tightening.

## Runtime-validated framing batch — lowercase `m`-`s`

Lowercase `m` through `s` (`$8D-$93`) are now runtime-validated with the same 1-pixel left framing as `a`-`h`. Their existing conservative advances remain unchanged. Combined dialogue lines containing the validated `a-h`, `i/l`, and `m-s` transforms render cleanly.

## Runtime-validated checkpoint — complete lowercase framing through a factored selector

The factorized framing selection, the `u-z` extension, and the final integration of `j/k/t` are runtime-validated. The current source completes lowercase `a-z` framing while keeping the already validated `dialogue_char_start` helper fixed at `$ED:7180`. To avoid overflowing `dialogue_font_row`, only the framing-decision tree is moved to a tiny helper at `$ED:71B0`; the selected row is still transformed at the same runtime-validated point in `dialogue_font_row`.

The geometry is `a-h/k/m-s/u-z = 1 px`, `i/l = 3 px`, and `j/t = 2 px`. Character advances remain on the conservative one-pixel-separator baseline, so framing is now validated independently from the next metric-tightening step. No generic `left_shift` table and no new WRAM state are used.

## Important implementation pitfall

An earlier continuous-cursor candidate corrupted GAME SELECT because a non-`$C9` `BNE` used a stale hard-coded displacement after its helper was shortened. It landed on the `INX` in the middle of the stock `LDA $A1A4,X / INX` replay.

The helper resolves branch labels programmatically. Preserve this approach: 65816 relative branches in generated helpers must not rely on manually maintained offsets when the helper layout can change.

## Rejected / superseded experiments

- Relocating the entire stock renderer outside bank `$C0`: runtime glitch/crash.
- Transplanting the Relocalized/FuSoYa VWF engine directly: incompatible with its wider relocalized-script environment; intro glitched.
- Fully custom complete-line renderer: first crashed, then selected the wrong glyphs even after fixing its exit-state contract.
- Custom→stock handoff in the middle of a line: produced glitched characters.
- Using `$001D01` event-pointer range as an intro filter at `$C0:13A3`: not stable at that late stage. `$001D03` bank is stable for the diagnostic scope.
- Forced tile-boundary realignment after narrow glyphs: useful as a diagnostic, but intentionally created visible spaces and is removed.
- WAIT / event `$32` resume bridges: no successful spacing correction; progression-hook variants also glitched the `$CA` intro. Removed from source and documented separately.

Relocalized/FuSoYa remains useful as an architectural reverse-engineering reference, while component `05_intro_vwf_french` remains the best proven reference for the bitmap shift/spill primitive.


### Framing-selection factorization checkpoint

The factorized `dialogue_font_row` selection and complete lowercase framing are runtime-validated through the separate selector helper at `$ED:71B0`: `a-h/k/m-s/u-z = 1 px`, `i/l = 3 px`, `j/t = 2 px`. `dialogue_char_start` stays at its validated `$ED:7180` location. The later lowercase metric tightening described below is also runtime-validated.

## Runtime-validated lowercase metrics

The complete lowercase metric tightening is runtime-validated with the already
validated framing: `a-h/k/m-q/s/u-z=7`, `i/l=3`, `j=4`, `r=6`, `t=5`. These
values follow `advance = framed ink width + 1 black pixel`. Framing, compositor,
stock lookup and `dialogue_char_start` at `$ED:7180` remain unchanged.

## Runtime-validated checkpoint — post-stock-outline boundary repair

Some lowercase glyphs show a position-dependent incomplete black border even
though the same glyph is complete at another sub-tile X position. The stock
outline routine at `$C0:162C` expands each 8-bit source row left/right inside a
single cell; pixels shifted beyond bit 7/0 are not naturally transferred to the
adjacent cell.

The validated repair preserves the entire stock outline pass and hooks only
after its `JSR $162C` returns, at `$C0:1168`. For `$C9`, helper `$ED:7280` adds
the missing horizontal edge contribution to the previous/next output tile when
the source bitmap touches a cell boundary, then replays the stock tail.

A rejected first probe hooked `$C0:1165`, accidentally replacing the stock
`JSR $162C`; runtime testing showed that this suppressed almost the entire black
outline. That probe is removed completely and must not be reused.

## Runtime-validated punctuation checkpoint

Handled punctuation now uses a visual spacing policy distinct from lowercase:
**one black pixel before the ink and one black pixel after it**. This was
runtime-validated after the earlier compact version was judged too close to the
preceding text.

Current validated framing / advances:

- `$BF-$C2` (`.`, `,`, `/`, apostrophe): shifts `0/0/0/0`, advances `4/4/7/4`;
- `$C3/$C4` (paired quotes): shifts `0/1`, advances `7/7`;
- `$C6/$C7/$C9/$CA` (`-`, `%`, `&`, `?`): shift `0`, advance `8`;
- `$C8/$CB/$CC` (`!`, `(`, `)`): shifts `2/2/1`, advances `5/5/5`.

Colon `$C5` is runtime-validated: stock ink is 2 px wide at columns 3-4; `shift=1` plus `advance=7` leaves 2 black pixels before the ink and 3 after it. `$CD` remains deliberately excluded from all active special handling and falls through to the generic conservative path.

The punctuation selector entry remains at `$ED:71E8`. Its batch-2 trampoline is
**pinned at `$ED:71F4`** and guarded by a build-time assertion. A rejected build
shortened the selector by one byte, moved that JML to `$ED:71F3`, and left an
existing dispatch entering at `$ED:71F4` in the middle of the instruction; the
ROM then failed to start. Do not remove or relocate that fixed trampoline without
updating every dispatch path.

## `$CD` exclusion — do not touch

`$CD` has no dedicated framing, metric, self-test or runtime-test path. It must
remain on the stock/default conservative path unless a future investigation is
explicitly dedicated to it. In runtime tests the glyph appeared as an X-like
symbol rather than a normal `#`. Tightening it to 6 px coincided with severe
rendering loss, and excluding it restored normal dialogue rendering. It is not
needed for the current French dialogue work, so there is no reason to risk it.

## Runtime test convenience

For hard-to-reach future glyph batches, event `$0106` provides a convenient
5-byte diagnostic slot immediately before command `$32`: ROM `0x0928CC-0x0928D0`
contains `B1 81 89 94 80` (`Wait `) in the clean US ROM. A temporary candidate
may replace exactly those five bytes to display test glyphs, but the checkpoint
source must restore `Wait ` afterward and must never modify the following `$32`.

## Runtime-validated uppercase A-Z

Uppercase `A-Z` is runtime-validated. Stock bitmap analysis found a homogeneous geometry: `A-H/J-Z` have a 1 px left bearing and 6 px ink width, while `I` alone has a 3 px left bearing and 2 px ink width. The validated settings are therefore `shift=1, advance=7` for `A-H/J-Z` and `shift=3, advance=3` for `I`.

The fixed batch-2 JML remains exactly at `$ED:71F4`. Uppercase handling stays in the later selector at `$ED:72F0`. `$B5-$BE` are the digits `0-9`; they were checked in runtime, render correctly at their stock width, and receive no dedicated VWF framing or metric. `$CD` remains untouched.

## Runtime-validated colon `$C5`

The stock colon has a 3 px left bearing and 2 px ink (`columns 3-4`). The final
runtime-validated setting is `shift=1, advance=7`, producing framed ink at
columns 2-3 with 2 black pixels on the left and 3 on the right. The temporary
`:::::` diagnostic has been removed and the original `Wait ` bytes are restored.

## Stock digits `$B5-$BE`

`$B5-$BE` are `0-9`. They were exposed in runtime and render correctly without
width changes. Keep them on the generic conservative path: no dedicated framing,
metric or diagnostic is needed. Unlike `$CD`, this is not a danger/frozen range;
it is simply already satisfactory stock.

## Runtime-validated shared French charset `$D4-$E5`

Component 06 consumes the canonical full French charset from
`shared/french_charset`: `Ç à â ç é è ê ë î ï ô ù û À É Î Œ œ`. It installs
the canonical 18-glyph atlas itself and raises the direct/DTE boundary to `$E6`,
so component 06 remains independently buildable rather than relying on component 05.

Runtime-validated framing / advances:

- `$D4-$E3` (`Ç à â ç é è ê ë î ï ô ù û À É Î`): `shift=1, advance=7`;
- `$E4/$E5` (`Œ/œ`): `shift=0, advance=8`.

The temporary 18-glyph diagnostic has been removed. The cleaned checkpoint does
not patch dialogue text for testing.

## Next work

The useful current charset is now calibrated and runtime-validated. The next
phase should preserve this checkpoint and proceed conservatively:

1. consider only behavior-preserving factorization/generalization that has a
   clear maintainability benefit;
2. broaden dialogue scope beyond `$C9` only after reviewing the relevant event
   banks and scratch-state assumptions;
3. only after renderer scope is stable, implement dialogue CSV
   extraction/reinsertion;
4. keep `$B5-$BE` stock and `$CD` excluded from special handling.

Do not resume the separate `Wait   up!` event-interruption spacing investigation
at the start of the next phase. See `docs/EVENT_INTERRUPTION_NOTES.md`.
