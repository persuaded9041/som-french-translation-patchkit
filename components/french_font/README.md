# French global fixed font candidate

This standalone candidate replaces the complete `$80-$FF` fixed font at
`$12DC00` with the font extracted from the French ROM. The canonical project
glyphs `$D3-$E7` are stored directly in the PNG and validated against the shared
glyph atlas, so the existing accented and special glyphs remain unchanged. The
editable source is `shared/charset/french_font.png`,
an 832×12 PNG containing the direct 8×12 glyph atlas in `$80-$E7` order.
Codes `$E8-$FF` are dialogue/DTE codes or adjacent data and are deliberately
left untouched.

The font-aware aggregate build must recalculate VWF metrics from this same
effective font. The normal standalone VWF patches remain based on the USA
font. This component remains excluded from `all.ips` until runtime validation.
Test ordinary fixed-font screens and every VWF path, especially wrapping,
right-edge glyphs, choices, menus and the opening intro.
