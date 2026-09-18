# French localized graphics

`french_gfx` owns graphical assets that are specific to the French localization. It deliberately does **not** own generic renderer logic or translated prose.

## Controller buttons — first promoted asset

The first asset replaces the shared USA 16×16 controller-button graphic with the official French-release shape and restores the four PAL/Japanese SNES button colors:

- `X` — blue
- `A` — red
- `Y` — green
- `B` — yellow

The stock engine already chooses a distinct palette slot for X/A/Y/B. The USA version subsequently calls a regional override at `$C0:2116` which collapses those four slots into the two purple/lavender North-American controller colors. `french_gfx` skips only that USA-only call; it does not introduce a new per-screen button-selection mechanism.

The button shape is a shared UI resource at `$D2:D8F0-$D2:D92F` (four 8×8 2bpp tiles arranged TL/TR/BL/BR). Because the game loads and reuses this common graphic, the patch is intentionally global: screens using this stock graphical button resource receive the French button shape automatically. Literal text such as a font-rendered `A`, `B`, `X` or `Y` is outside this component.

## Editable sources

- `assets/controller_button.png` — canonical 16×16 indexed PNG. Pixel indices `0..3` map directly to the SNES 2bpp values; index 0 is transparent. The preview palette uses the French red A-button ramp, but the runtime color is selected independently by the game.
- `assets/controller_button_palettes.json` — the four exact French BGR15 ramps, in runtime order `X / A / Y / B`.
- `tools/extract_controller_button.py` — optional provenance helper that recreates the PNG from a clean `Secret of Mana (France) (Rev 1)` ROM with the expected SHA-256. The French ROM is never part of the repository.

`build_patch.py` converts the PNG into the exact four SNES 2bpp tiles during every build. No generated `.bin` copy of the graphic is canonical.

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
- the only code change is `NOP NOP NOP` over the clean-USA `JSR $212F` at `$C0:2116`.

Runtime visual validation is complete. The shared button replacement was user-validated in game and is promoted as the first stable `french_gfx` feature.
