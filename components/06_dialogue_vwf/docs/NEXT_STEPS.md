# Next steps

Component 06 is runtime-validated for stock `$C9/$CA` event dialogue and for
component-08 relocated event banks `$E8-$EC` under the same caller gate. The
forced `$0107` relocation probe has been removed; component 08 now relocates
only translated events that genuinely outgrow their stock span.

The shared 44-byte parser buffer, continuous pixel cursor, validated framing and
metrics, interrupted-chunk physical-cell progression, right-edge preflight and
post-outline repair are the current stable base. The stock glyph-addressing block
`$C0:168A-$16B0` remains intentionally intact.

## Deferred renderer work

The clipping-safety wrap is validated, but a word can still be split when the
remaining physical width ends inside it. A future optional improvement is
word-aware pre-wrap: break before a whole word when it does not fit in the
remaining pixels but does fit on a fresh line. Do not weaken the existing
pre-consumption clipping checks or split/rewind dynamic temporary sources or DTE
tokens to implement it.

The earlier WAIT/event-interruption spacing investigation remains intentionally
deferred; see `EVENT_INTERRUPTION_NOTES.md` before revisiting it.

## Build discipline

Do not refactor the validated VWF path merely for text-source work. Runtime-
affecting changes still require the modified component to be rebuilt and tested
standalone, then combined with stored IPS files for unchanged components. The
commercial ROM is a local build input only and must never be committed or
redistributed.
