# vwf_ui — UI VWF

Standalone variable-width-font extensions for user-interface text paths that are
not owned by the intro (`05`) or ordinary event dialogue (`06`).  The component
may use the shared VWF helpers, but it has no dependency on another component.

## Runtime-validated path: Watts forge row

The first backend targets the Watts weapon-upgrade row.  Research established the
exact chain rather than using a broad menu/renderer gate:

- `$D0:D3B0-$D3C4` builds the current `WEAPON_NAME` at `$7E:19D2-$19D3`;
- `$D0:D82F+` is the Forge-mode suffix builder and writes the literal `→`;
- the tag is armed only at the exact submit of the Forge row `$00:19D0`
  (the stock caller has X=`$19D0` immediately before `$D0:D5D7`); it is not
  armed at the earlier `WEAPON_NAME` helper;
- the shared renderer dispatcher gives that one tagged invocation to `vwf_ui`,
  consumes the tag, and clears the low-level VWF-active flag on all stock fallbacks;
- the stock decoded row is kept on the stock parser/buffer path, copied only at
  render time, and rendered with shared VWF framing/metrics;
- the stock fixed-column suffix anchors are moved to safe logical slots 20/25,
  then compacted at render time so `→...` follows the actual VWF width of the
  weapon name with one decoded space;
- the stock logical line budget is raised by **+3** only while the exact UI tag
  is armed.  The +3 margin was stress-tested with 19-character French weapon
  names and keeps the full `GP` suffix on the same line.

The final component contains no temporary weapon-name override.  Resource/name
translation remains owned by the text-resource pipeline.  The standalone component
was runtime-validated on a clean USA ROM: the Forge weapon row uses VWF, GAME SELECT
remains stock/non-glitched, and Watts' ordinary dialogue remains stock/non-VWF.

## Intended future scope

Additional proven UI paths may be added here, especially Ring Menu text and
item-acquisition / pickup UI. Each new backend must be isolated and runtime-proven
before it is added to production. Reuse the shared VWF primitives, but give each
UI family its own narrow identity gate, one-shot state where possible, and explicit
stock fallback. Do **not** turn this component into a global non-dialogue VWF switch.

For the current extension procedure and regression checklist, read `docs/UI_VWF.md`.

Build standalone:

```bash
python3 build.py "Secret of Mana (USA).sfc" ui-vwf
```
