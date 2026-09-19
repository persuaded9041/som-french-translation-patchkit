# Weapon / magic skill-row VWF research

Date: 2026-09-19

## Goal and frozen constraints

Target only the dynamic weapon/magic names in the native `Niv. armes` /
`Niv. magies` lists. Keep the runtime-validated fixed headings, stock placement
structures `$C7:754A/$7558`, validated compact progress helper
`$C7:4F00-$4F22`, Status backend `$ED:8700+`, and frozen dialogue paths
unchanged. `french_resources` remains the owner of localized weapon/magic names.

## Starting failure

The rejected candidate scoped the exact 8-row batch correctly but assumed the
decoded compact prefix started at `$7E:A1A4+0` (and additionally checked menu
IDs 5/6). Runtime showed no proportional names. The unknown was therefore the
actual decoded-row / bitmap boundary used at `$C0:2366`.

## Runtime proof sequence

### Probe 01 — blank complete scoped bitmap

During the exact `$7E:93CD=$5A` scope, clear the whole `$7E:9000-$917F` bitmap
before the stock converter. Runtime result: both levels and names disappear in
weapon and magic lists. **Proof:** the exact `$C7:5D9A` batch reaches
`$C0:2366` with the scope active, and `$7E:9000` contains the row bitmap.

### Probe 02 — preserve cells 0..3/4, blank assumed name cells

Assume the compact prefix begins at bitmap cell 0 and clear from cell 4 or 5.
Runtime result: levels and names still both disappear. **Refutation:** the
compact row is not anchored at decoded/bitmap cell 0.

### Probe 03 — scan decoded row for compact prefix

Within the exact batch scope, scan up to 28 decoded cells in `$7E:A1A4` for
`d:d ` or `d:dd `. Use the discovered end of that prefix as the bitmap clear
boundary. Runtime result: levels remain visible while weapon/magic names
disappear. **Proof:** the dynamic scan finds the true name-start cell and that
cell maps correctly to the fixed-font bitmap boundary.

### Probe 04 — dynamic boundary + name-only VWF

Reuse the exact probe-03 scan. Preserve everything before the discovered name
cell, clear only the old fixed-font name bitmap, set the VWF pixel cursor to
`name_cell * 8`, and render the already-decoded name using the validated ordinary
UI advance table/compositor. Runtime result: levels remain fixed and all eight
weapon/magic names render proportionally. **Validated.**

## Promoted architecture

- `$C7:664A/$665D -> JSR $4F00`: compact progress helper, byte-identical to the
  previously validated implementation.
- `$C7:65B0/$6615 -> JSR $4F30`: exact magic/weapon 8-row submits.
- `$C7:4F30-$4F3F`: set `$7E:93CD=$5A`, call stock `$C7:5D9A`, clear scope.
- At the time of probe 04, `$C0:2366 -> JML $ED:8C00` directly. After the separately validated magic-description work, the global hook now reaches `$ED:8E00` first; every non-magic exact-caller case immediately jumps to the byte-identical `$ED:8C00` helper.
- `$ED:8C00`: require exact scope, dynamically scan decoded `$A1A4` for
  `d:d ` / `d:dd `, derive true name source/bitmap cell, clear only the name
  bitmap, VWF-render only the name, then resume stock pair-packed 4bpp conversion.
- all rejects `JML $ED:8700`, preserving the validated Status classifier.

The promoted `$ED:8C00` helper is byte-identical to the runtime-validated probe
04 helper (`0x12C` bytes). The old fixed-cell and menu-ID 5/6 assumptions are
removed.
