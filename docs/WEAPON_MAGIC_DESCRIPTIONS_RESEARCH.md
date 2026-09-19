# Weapon / magic description research — 2026-09-19

This document records the runtime proof sequence that led to the promoted
French description architecture in `french_resources` + `vwf_ui`.

## Weapon descriptions — validated stock geometry

The Android mapping already contained 72 weapon descriptions, but the original
recipe incorrectly treated their Android IDs as one contiguous 72-entry range.
Android actually inserts one separator after each family of nine weapons. The
correct mapping is therefore eight 9-entry groups with the eight separators
skipped. Once corrected, the SNES/Android empty/non-empty pattern matches 72/72.

Runtime probing established the native SNES description layout:

- descriptions are stored as fixed 30-character segments separated by `$7F`;
- the first two 30-cell segments form the first visible row, the next two form
  the second visible row, and the fifth segment forms the third;
- a continuing segment must be exactly 30 characters wide. Trying to wrap at
  words creates visible horizontal gaps; removing `$7F` entirely causes
  overflow and lost glyphs;
- the correct French insertion therefore collapses Android presentation
  whitespace to one logical sentence, prepends the stock one-cell inset, then
  slices it at exact 30-character boundaries. A word may be split across a
  segment boundary, exactly as in the USA/FRA ROMs.

The final weapon-description implementation is source-owned by
`french_resources`; 60 non-empty descriptions use Android FR wording and 12
blank records preserve their stock blank payload byte-for-byte.

## Magic descriptions — stock path and geometry

The 42 stock descriptions are selected from the `$CA` resource family whose
first pointer is resource `$197`. The lower panel path is built around:

- `$C7:64A1+`: stock availability filtering;
- `$C7:649E -> JSR $6BCF`: lower-panel preparation;
- `$C7:6501 -> JSR $6AB7`: exact description-copy call; at this point `$A1D0`
  is the description index stock just selected;
- `$C7:650E -> JSR $6512`: six-pass text submission;
- inside `$C7:6512`, the six passes are submitted through `$C7:5D9A` and the
  standard `$C0:2ADB/$2AEA/$2ADF` path.

The French official ROM confirms that the stock lower-panel description is not
three independent long rows. Each spell line is physically two horizontal
segments and the French official translation keeps the same narrow stock
geometry.

## Probe sequence

### Probe 01 / 01b / 01c / 01d — identify the exact lower-panel path

A destructive blank-bitmap probe proved that the lower descriptions pass through
`$C0:2366`. Early scopes were too broad and also affected weapon descriptions or
one frame fragment. The path was eventually isolated to the magic-only call at
`$C7:650E` while preserving stock menu lifecycle.

The disappearing border fragment was an artifact of destructive bitmap clearing;
it was not used as the basis of the final architecture.

### Probe 02 / 03 — reject long prose in stock `13+24` geometry

Injecting full Android FR into the stock two-segment layout produced either large
horizontal gaps or lost text. A concise stock-geometry candidate worked, proving
the stock model, but it required unnecessary wording reductions and was not kept.

### Probe 04 / 04b / 04c — first full-width experiments

A first 3-line VWF prototype glitched GAME SELECT because a global bitmap hook
was gated by a WRAM byte that was not a sufficiently strong identity. Probe 04b
fixed this by using the exact stacked return address of a cloned magic-only
`JSL $C0:2ADB`; GAME SELECT returned to normal.

A direct-DMA rewrite in 04c caused menu animation/exit lockups and was rejected.
Conclusion: keep the entire stock six-pass wait/DMA/tail lifecycle.

### Probe 04d — map the six stock passes

The six passes were labeled at runtime. The screenshot proved the physical grid:

- visible row 1 = passes 0 + 1;
- visible row 2 = passes 2 + 3;
- visible row 3 = passes 4 + 5.

### Probe 04e / 04f — prove 480px paired rows

04e initially assumed one pass was 15 cells and produced a large central gap.
`$A191=$03C0` proves a single pass is 960 bytes = 30 SNES 4bpp tiles = 240 px.
Therefore a pair is 60 cells = 480 px.

04f rendered one logical VWF row across the stock 64-cell `$7E:9000-$92FF`
source bitmap, then sliced cells 0..29 for the even pass and cells 30..59 for
the odd pass. Runtime validation showed three long, continuous lines with no gap
at the midpoint and no menu regression.

## Dynamic identity: capture stock IDs, do not re-identify text

An early dynamic candidate attempted to recognize the displayed spell name and
also aliased one scratch byte with the left/right-half flag. It repeated rows and
reintroduced a central gap. This approach is rejected.

The robust solution captures stock's own resource identity at the exact
`$C7:6501` copy call:

- `$A1D0` is captured in stock emission order into three private IDs;
- Lumina uses raw stock indices 42..47 and stock subtracts 6 before accessing the
  shared special resources, so the capture mirrors this mapping to 36..41;
- before each rebuild the three capture IDs are reset to `$FF` and the capture
  count to 0;
- the stock availability condition remains authoritative. Locked elementals emit
  no IDs, so their rows remain blank;
- when a partially populated elemental such as Dryad emits only two spells, the
  missing `$FF` row is explicitly blanked instead of falling back to stale stock
  bitmap content.

Runtime validation covered normal elementals, Lumina, locked elementals and
Dryad's missing third row.

## Final promoted architecture

### Content ownership — `french_resources`

`french_resources` owns 42 fixed-size records at `$ED:9200-$9F1F`. Each record
is 80 bytes: one direct-glyph length byte plus the complete Android-FR
`Nom : description` payload. Android layout whitespace is collapsed to ordinary
spaces only; no description wording is shortened.

A marker `MFV1` at `$ED:9F20-$9F23` proves the localization table is present.
The widest validated row is 445 px; the build enforces a 472 px safety ceiling
within the 480 px logical row.

### Presentation ownership — `vwf_ui`

`vwf_ui` owns only presentation and stock identity capture:

- `$C7:649E`, `$6501`, `$650E` are wrapped but replay their stock work;
- a clone at `$C7:4F40-$4FB4` preserves the exact six-pass stock submit/DMA
  lifecycle;
- `$C0:2366` first reaches `$ED:8E00`; only the exact cloned caller can enter the
  magic lower-panel path;
- without the `MFV1` marker, even the exact caller falls back to the stock
  converter, so standalone `vwf_ui` remains content-neutral;
- non-magic callers fall through to the already validated skill-row VWF helper
  `$ED:8C00`, then Status `$ED:8700` as before;
- each logical row is rasterized across up to 60 cells / 480 px and then sliced
  into the two stock 30-cell passes after VWF composition.

No experimental Ombre row bypass is retained in production. The earlier blank
Ombre slot was correctly explained by the save state's unlock condition.

## Next untranslated text

The default instructional/help text shown in the `Niv. armes / Niv. magies`
screen is still English and is deliberately left for the next translation pass.
The next session should identify the original Japanese text, check whether an
Android FR counterpart exists, then adapt it to the SNES target after tracing its
actual renderer/geometry. Do not infer wording from the current English text
alone.
