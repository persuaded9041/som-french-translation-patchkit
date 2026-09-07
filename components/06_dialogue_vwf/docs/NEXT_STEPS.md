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

Choice rows now use the same VWF path as ordinary dialogue. Runtime validation on the Potos
`$0331` path confirms that resynchronizing the cumulative pixel cursor at stock option starts
from `$A1D7[]` keeps the magenta selection aligned. The terminal boundary appended by
`CHOICE_END` is also scanned, keeping a preserved closing `)` outside the final highlighted
span. GAME SELECT remains normal.

Component 08 owns the remaining decoded-row geometry issue. It may move only a later
`CHOICE_OPTION` right to the minimum cell required to prevent the preceding official-French
label from being overwritten by the parser's absolute reset. The Potos diagnostic using
`Temple de l'Eau / Pandora` runtime-validates `$03/$11 -> $03/$12`. Do not add a private
choice renderer, rewrite `$A1D7[]` at runtime, or hook the magenta routine unless a future
case proves this minimal shared geometry insufficient.

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
