# Android dialogue charset audit

This audit covers French prose reachable through the conservative Android
alignment in `mappings/android/dialogues_auto.json`. The structural decisions
were reviewed before whole-game formatting.

## Result

After Android layout whitespace and `%S(n,0)` placeholders are removed, the
original audit found nine unsupported Unicode characters. Their approved
handling is now:

| Character | Occurrences | Handling |
|---|---:|---|
| `"` | 54 | normalize contextually to stock `“` / `”` (`$C3/$C4`) |
| `♪` | 5 | new dialogue direct glyph `$D3` |
| `;` | 2 | new dialogue direct glyph `$E7` |
| `°` | 1 | new dialogue direct glyph `$E6` |
| `→` | 2 | preserve existing SNES structural right-arrow token `$D0` |
| `←` | 1 | preserve existing SNES structural left-arrow token `$CF` |
| `▽` | 2 | structural prompt marker; preserve existing `$CE` when present, otherwise drop Android-only marker |
| `[` / `]` | 1 pair | normalize the Android choice presentation to SNES `(` / `)` |

The `▽ Que faire ?` case is user-validated: import only `Que faire ?` and keep
the existing SNES `$CE` glyph token. No `▽` text glyph is allocated.

## Dialogue extension

The editable shared atlas contains:

- `$D3 = ♪`;
- `$D4-$E5` = the unchanged 18-character French range;
- `$E6 = °`;
- `$E7 = ;`.

Ordinary event dialogue therefore needs `$E8` as its upper DTE boundary. The
intro must **not** inherit that boundary: component 05 uses all 25 `$E6-$FF`
private DTE slots and is already runtime-validated. `shared/dialogue_dte.py`
solves this by routing only true event-engine dialogue to `$E8`, while event
`$0400` and non-dialogue parser callers keep `$E6`.

A clean-ROM scan of all 2,048 event scripts found no raw `$D3-$FF` bytes inside
ordinary stock text tokens, so this dialogue-only reinterpretation does not
collide with an observed stock event-text DTE byte.

## Validation status

The context-sensitive dialogue DTE route and the three direct glyphs are
runtime-validated. Their compact VWF advances are also validated (`♪` 7 px,
`°` 7 px, `;` 4 px). The PNG artwork can still be retouched later without
changing byte assignments, but any visual edit should be regression-tested in
06. Component 05 remains byte-for-byte unchanged by the dialogue-only `$E8`
route.
