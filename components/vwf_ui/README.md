# vwf_ui — UI VWF

Standalone variable-width-font extensions for user-interface text paths that are
not owned by the intro or ordinary event dialogue. The component reuses the
shared VWF primitives but keeps each UI family behind an explicit one-shot
identity gate.

## Runtime-validated Forge backend

The Watts weapon-upgrade row remains the reference backend:

- `$D0:D3B0-$D3C4` builds the current `WEAPON_NAME` at `$7E:19D2-$19D3`;
- `$D0:D82F+` builds the `→ ... GP` suffix;
- the exact shared submit at `$D0:D3D2` reaches mini-event `$00:19D0`;
- when the Ring subsystem mode byte is `$1847 == 3`, the submit wrapper arms
  one-shot tag `$7E:93C1=$A7` (Forge);
- the stock parser/buffer stays in use and receives only the proven **+3**
  logical-unit margin;
- safe logical suffix anchors 20/25 are compacted at render time so the arrow
  follows the actual VWF width of the current weapon name.

This path was runtime-validated previously with long French weapon names, the
complete `GP` suffix, GAME SELECT fallback and ordinary Watts dialogue.

## Runtime-validated Ring Menu title backend

The top-level Ring Menu title banner shares the same `$00:19D0` submit but must
not use Forge suffix geometry. Runtime tracing established the chain:

`Ring Menu -> C0:6943 -> D0:D397 -> $00:19D0 -> stock parser -> C0:167D -> vwf_ui`

The former corruption of long labels was explained exactly: Forge's overlapping
slot-20..31 suffix move was being applied to a continuous Ring title. A space at
slot 20 propagated spaces and hid the final words; a non-space propagated that
glyph (`Choix des fenêtres deeeee...`).

The production isolation is now explicit at the shared submit site:

- `$1847 == 0` -> one-shot tag `$7E:93C1=$A8` (top-level Ring Menu title);
- `$1847 == 3` -> one-shot tag `$7E:93C1=$A7` (Forge);
- `$1847 == 1/2` or any unexpected value -> no UI tag, stock fallback.

The Ring renderer copies the stock decoded row unchanged and enters the shared
VWF backend without any Forge compaction. Its capacity is raised by exactly
**+4** units. The stock fresh-line remainder is 29, so this yields exactly 33
units: the complete stock `$7E:A1A4-$A1C4` buffer, sufficient for **32 visible
characters plus the following control**. The buffer is not enlarged and the
private 38-character dialogue parser is not used.

This exact +4 case is required by `Niveaux des armes et de la magie` (32 visible
characters). The corruption fix, the dedicated Ring/Forge tag isolation and the final
+4 boundary restoring the last `e` are all runtime-validated. Shorter Ring labels
continue through the same narrow mode-0 gate.

## State and fallbacks

The shared dispatcher at `$C0:167D` recognizes only the two explicit UI magic
values when the ROM config marker `$C7:4C87=$09` is installed. The renderer
consumes the tag immediately. All unowned calls replay stock behavior and clear
the shared low-level VWF-active state so unrelated UI callers cannot inherit it.

`vwf_ui` owns no translated prose. Ring label translations remain in
`french_resources`.

For the extension procedure and regression checklist, read `docs/UI_VWF.md`.

Build standalone:

```bash
python3 build.py "Secret of Mana (USA).sfc" vwf-ui
```
