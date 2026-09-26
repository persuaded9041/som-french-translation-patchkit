# French localized graphics

`french_gfx` owns graphical assets that are specific to the French localization. It deliberately does **not** own generic renderer logic or translated prose.

## Controller buttons

The first asset replaces the shared USA 16×16 controller-button graphic with the official French-release shape and restores the four PAL/Japanese SNES button colors:

- `X` — blue
- `A` — red
- `Y` — green
- `B` — yellow

The stock engine already chooses a distinct palette slot for X/A/Y/B. The USA version subsequently calls a regional override at `$C0:2116` which collapses those four slots into the two purple/lavender North-American controller colors. `french_gfx` skips only that USA-only call; it does not introduce a new per-screen button-selection mechanism.

The button shape is a shared UI resource at `$D2:D8F0-$D2:D92F` (four 8×8 2bpp tiles arranged TL/TR/BL/BR). Because the game loads and reuses this common graphic, the patch is intentionally global: screens using this stock graphical button resource receive the French button shape automatically. Literal text such as a font-rendered `A`, `B`, `X` or `Y` is outside this component.

## Other stock French graphics

`french_gfx` also replaces exact, independently guarded French-ROM resources:

- West direction marker: `W` → `O` at `$C7:FB20`.
- Two HP (`HP` → `PV`) and two MP (`MP` → `PM`) compressed menu-icon variants.
- The `LVL` → `NIV` level indicator.
- Both inn-sign variants: the split alternate tileset ranges at `$DD:1500-$DD:153F` and `$DD:1580-$DD:15BF`, plus the Potos sign at `$DF:5460-$DF:54DF`.

Every resource is sourced from a canonical indexed PNG and must re-encode byte-for-byte to the verified French resource. The icon PNGs preserve the native compressed format's raw index 7 as transparency, so re-encoding cannot silently change their compression representation. The alternate inn sign intentionally leaves `$DD:1540-$DD:157F` untouched.

## Editable sources

- `assets/controller_button.png` — canonical 16×16 indexed PNG. Pixel indices `0..3` map directly to the SNES 2bpp values; index 0 is transparent. The preview palette uses the French red A-button ramp, but the runtime color is selected independently by the game.
- `assets/controller_button_palettes.json` — the four exact French BGR15 ramps, in runtime order `X / A / Y / B`.
- `assets/direction_west_fr.png` — French 8×8 west-direction tile.
- `assets/hp_indicator_1_fr.png`, `hp_indicator_2_fr.png`, `mp_indicator_1_fr.png`, `mp_indicator_2_fr.png`, `level_indicator_fr.png` — 16×16 compressed menu-icon sources. Indices `0..7` are preserved verbatim; index `7` is the native transparent value.
- `assets/inn_sign_1_fr.png` — 16×16 alternate inn sign. Its first two tiles are written at `$DD:1500`; its last two at `$DD:1580`.
- `assets/inn_sign_2_fr.png` — 16×16 Potos inn sign at `$DF:5460`.
- `tools/extract_controller_button.py` — optional provenance helper that recreates the PNG from a clean `Secret of Mana (France) (Rev 1)` ROM with the expected SHA-256. The French ROM is never part of the repository.

`build_patch.py` converts every PNG to its native SNES storage layout during every build. No generated `.bin` copy is canonical.

## Build

From the repository root:

```bash
python3 components/french_gfx/build_patch.py "Secret of Mana (USA).sfc" \
  -o patches/french_gfx.ips
```

Or through the aggregate builder:

```bash
python3 build.py "Secret of Mana (USA).sfc" french_gfx
python3 build.py "Secret of Mana (USA).sfc" french_gfx --combine
```

The builder guards all three clean-USA source regions before patching them and updates the SNES checksum. It does not expand the ROM and reserves no free-space bank.

## Validation status

Binary validation is deterministic:

- the checked-in PNG re-encodes byte-for-byte to the official French `$D2:D8F0-$D2:D92F` graphic;
- the JSON serializes byte-for-byte to the official French `$D2:DBCC-$D2:DBE3` X/A/Y/B palette data;
- every other localized graphic is guarded against its clean-USA byte sequence and replaced byte-for-byte with its French counterpart;
- the only code change is `NOP NOP NOP` over the clean-USA `JSR $212F` at `$C0:2116`.

Runtime visual validation is complete. The controller buttons, direction marker,
PV/PM/NIV indicators, and both inn-sign variants were user-validated in game.
They are all promoted as the stable `french_gfx` baseline.
