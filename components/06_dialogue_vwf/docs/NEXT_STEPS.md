# Next steps

Component 06 is runtime-validated for stock `$C9/$CA` event dialogue and for
component-08 relocated event banks `$E8-$EC` under the same caller gate. The
forced `$0107` relocation probe has been removed; component 08 now relocates
only translated events that genuinely outgrow their stock span.

The shared 44-byte parser buffer, continuous pixel cursor, validated framing and
metrics, interrupted-chunk physical-cell progression, right-edge preflight and
post-outline repair are the current stable base. The stock glyph-addressing block
`$C0:168A-$16B0` remains intentionally intact.

## Interactive-choice checkpoint

Choice rows use the ordinary dialogue VWF renderer. The earlier stock-anchor synchronization and `CHOICE_END` terminal-boundary handling remain the fallback for decorated rows.

A generic measured-end path is now runtime-validated for undecorated two-option rows. Logical `$A1D7[]` coordinates remain untouched for parser/storage; component 06 records the actual VWF endpoint and derives separate cell-aligned visual/highlight boundaries. The first option starts at `max(logical_first, $03) - 2`, so only the private visual/highlight boundary moves left. The second normally starts one full cell after the rounded measured endpoint; when that rounded endpoint has reached cell `$11`, the extra cell is omitted to protect the right edge. The terminal boundary is rounded up from the final VWF end. The magenta geometry hook consumes only these private bounds after they are complete.

Runtime-validated wide cases: `$00CE`, `$00CF`, `$00D0`, `$00D1`, `$0202`. In the final two-cell-left geometry `$00D0` uses the normal separator and terminal cell `$1B`; the generic late-first-option separator-omission branch remains separately runtime-validated from the earlier right-edge stress checkpoint. Runtime-validated fallback controls: ordinary Potos `Acheter / Vendre` and `Oui / Non` retain the decorated stock-anchor path. Do not reintroduce a special `CHOICE_BEGIN` renderer.

The `$0331` Potos carrier has stock logical anchors `$05/$0A`; they must not be left unchanged when a long diagnostic label is injected. `$5A $0A` is an absolute decoded-buffer reset and will overwrite the tail of the first label. The validated `$00D0` reproduction used logical `$03/$14`: `$14` is the minimum slot after the 17 decoded characters of `Désert de Kakkara`. These logical test anchors are independent of the private measured-end visual placement.

One cosmetic follow-up remains:

1. Short decorated choices visually lack about one extra blank cell before the closing `)`. Treat this as separate from the now-validated wide-choice geometry.

## Deferred renderer work

The clipping-safety wrap is validated, but a word can still be split when the
remaining physical width ends inside it. A future optional improvement is
word-aware pre-wrap: break before a whole word when it does not fit in the
remaining pixels but does fit on a fresh line. Do not weaken the existing
pre-consumption clipping checks or split/rewind dynamic temporary sources or DTE
tokens to implement it.

The earlier WAIT/event-interruption spacing investigation remains intentionally
deferred; see `EVENT_INTERRUPTION_NOTES.md` before revisiting it.

### Minor position-dependent outline/compositor artifact

The runtime-validated `$0107` Android-format pilot exposed a small visual artifact
that is deliberately **not** being fixed during text-source work: the final `e`
of `cascade` can look slightly displaced when the glyph straddles an 8-pixel cell
boundary. Text advance, wrapping and event progression are correct. Keep this
word as a future regression case when revisiting the compositor/post-outline
repair. A useful diagnostic is to compare the same glyph at each `X mod 8`
position, especially positions where its right edge spills into the next cell.
Do not change the currently validated metrics merely to hide this isolated
artifact.

### Extended dialogue glyph checkpoint

The dialogue-only direct-code routing for `♪=$D3`, `°=$E6` and `;=$E7` is
runtime-validated: the corrected router reuses component 06's already-selected
shared parser mode (mode 2 -> dialogue `$E8`, mode 1 -> intro `$E6`), so `$E6`
and `$E7` no longer expand as DTE in real dialogue. Component 05 still rebuilds
byte-for-byte identical.

The compact VWF metrics are also runtime-validated with the explicit probe
`Lala ♪ Lala ♪`, `Sujet n°1 est X.` and `C'est vrai; je sais.`: `°` uses
ordinary punctuation geometry (1 px before/after its 5 px ink, advance 7), `;`
uses the same 1 px punctuation bearing around 2 px ink (advance 4), and `♪` uses
advance 7 with its canonical PNG framing. Treat these metrics as the current
validated checkpoint.

## Build discipline

Do not refactor the validated VWF path merely for text-source work. Runtime-
affecting changes still require the modified component to be rebuilt and tested
standalone, then combined with stored IPS files for unchanged components. The
commercial ROM is a local build input only and must never be committed or
redistributed.
