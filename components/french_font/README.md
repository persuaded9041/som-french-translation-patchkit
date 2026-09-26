# French global fixed font

This standalone component replaces the complete `$80-$FF` fixed font at
`$12DC00` with the font extracted from the French ROM. The canonical project
glyphs `$D3-$E7` are stored directly in the PNG and validated against the shared
glyph atlas, so the existing accented and special glyphs remain unchanged. The
editable source is `shared/charset/french_font.png`,
an 832×12 PNG containing the direct 8×12 glyph atlas in `$80-$E7` order.
Codes `$E8-$FF` are dialogue/DTE codes or adjacent data and are deliberately
left untouched.

The font-aware aggregate build recalculates VWF metrics from this same effective
font. The normal standalone VWF patches remain based on the USA font. Runtime
validation is complete for ordinary fixed-font screens and the affected VWF
paths, including wrapping, right-edge glyphs, choices, menus and the opening
intro. The component is promoted in the French aggregate (`all-fr.ips`) while
remaining correctly excluded from the USA-only `all.ips`.
