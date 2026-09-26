# Dialogue transparency — PPU / window reverse engineering

Status: **promoted as standalone component `dialogue_background`; runtime-validated for the focused ordinary + type-2 inn case; intentionally excluded from `all.ips` pending compatibility work and deferred for a later session**.

Reference for this work: the clean project archive supplied on 2026-09-15 and
`Secret of Mana (USA)` unheadered.  The dialogue text corpus is not touched.

## Goal

Replace the stock dithered dialogue-window fill with a hardware color-math
underlay while keeping BG3 text and frame opaque.

The runtime-proven visual model is:

- stock BG3 frame/text remain opaque;
- stock dither pixels are replaced by transparent pixels;
- color math is applied to the world pixels visible through that transparent
  BG3 area;
- Window 1 confines the effect spatially;
- HDMA changes Window-1 X bounds by scanline to obtain a true rectangle.

For the standard dialogue frame the validated fully-open mapping is:

- `X = 15..240`;
- `Y = 15..63`.

The dynamic mapping is derived from the stock live frame bounds:

- `$7E:A165` = current top row;
- `$7E:A166` = current left column;
- `$7E:A167` = current bottom row;
- `$7E:A168` = current right column.

With:

- `WH0 = left * 8 + 7`;
- `WH1 = right * 8`;
- leading scanlines = `top * 8 + 7`;
- active height = `(bottom - top) * 8 - 7`.

This was runtime-validated for one animated dialogue frame in Stage 7.

## Stock MONEY / inn reservation flow

The inn reservation case is important because it displays the ordinary dialogue
frame and a small GP frame at the same time.  The two frames are **not** opened
or closed synchronously.

Observed runtime order:

1. ordinary dialogue frame opens;
2. type-2 GP frame opens;
3. ordinary dialogue frame closes;
4. type-2 GP frame closes.

The stock command dispatch resolves the relevant commands to:

- `$50 -> C0:0229` — ordinary text open;
- `$51 -> C0:0611` — ordinary text close;
- `$5D -> C0:0F6C` — MONEY open;
- `$5E -> C0:0F59` — MONEY close;
- `$5F -> C0:0F87` — MONEY print.

### Context save — `C0:0F08`

`MONEY_OPEN` / `MONEY_PRINT` call `$0F08` before entering type 2.  When the
current type is not already 2, stock saves:

- current event/script pointer + 1 in `$A1D1`;
- current script bank in `$A1D3`;
- previous window type `$A162` in `$A188`.

`MONEY_OPEN` then installs `$A162 = 2`.

### Context restore — `C0:0F2C`

When leaving the temporary type-2 context, stock restores:

- `$A162 <- $A188`;
- nominal window parameters through `JSR $0D8B`;
- text context through `JSR $193F`;
- event pointer/bank from `$A1D1/$A1D3`.

**Crucial fact:** `$0F2C` does **not** restore `$A165-$A168`.

Those four bytes are global animation work variables, not a per-window
structure.  Therefore immediately after type-2 work has restored `$A162` to the
ordinary dialogue type, `$A165-$A168` can still describe the type-2 frame.

## Why Stages 8-10 failed

Stages 8-10 cached geometry according to the current `$A162` value in the event
worker epilogue.  That was invalid for the nested MONEY path.

The failing sequence was effectively:

1. ordinary open: `$A162 != 2`, live bounds -> `RECT0` (correct);
2. MONEY/type-2 open: `$A162 = 2`, live bounds -> `RECT2` (correct);
3. `$0F2C` restores ordinary `$A162`, but live bounds still belong to type 2;
4. event epilogue sees ordinary `$A162` and copies type-2 live bounds into
   `RECT0` (corruption).

This exactly matches runtime observations:

- ordinary frame alone: transparency works;
- both frames visible: transparency disappears;
- after ordinary closes, type-2 alone: transparency works again.

The dual-window HDMA table itself is therefore not the primary failure.  The
software ownership model was wrong.

## Promoted v1 ownership model (validated Stage 11)

`dialogue_background` v1 separates **window context** (`$A162`) from **ownership of the live
animation bounds**. This is the runtime-validated Stage-11 model promoted unchanged.

Temporary experimental WRAM:

- `$7E:93D0-$93D3` — cached ordinary rectangle;
- `$7E:93D4-$93D7` — cached type-2 rectangle;
- `$7E:93D8` — active mask (bit 0 ordinary, bit 2 type 2);
- `$7E:93D9` — `OWNER` (`0` ordinary, `2` type 2);
- `$7E:93E0...` — HDMA table.

Ownership transitions are tied to actual frame animation transitions, not to
script-context restoration:

### Opening owner — `C0:0A37`

The already-proven opening hook executes immediately after `JSR $0D8B` has
selected the real frame type and before the seed bounds are completed.
It:

- marks that frame active;
- sets `OWNER` from the actual `$A162` at opening time.

### Closing owner — `C0:0742`

The stock first-close-frame path is identifiable because `$A16D == 0` causes
`C0:06EA` to initialize closing geometry.  After `JSR $0D8B` and construction
of `$A165-$A168`, stock executes:

- `C0:0742 INC $A16C`;
- `C0:0745 INC $A16C`.

Stage 11 hooks exactly these two instructions, reproduces them, and then sets
`OWNER` from the real `$A162` of the frame whose close animation is starting.

This provides the required asynchronous sequence:

- ordinary open => owner 0;
- type-2 open => owner 2;
- `$0F2C` restore => owner remains 2, so `RECT0` is frozen;
- ordinary close starts => owner 0;
- ordinary cleanup => active bit 0 clears, type-2 rectangle remains frozen;
- type-2 close starts => owner 2;
- type-2 cleanup => active bit 2 clears.

The common event epilogue no longer asks `$A162` which slot should receive the
live bounds.  It uses `OWNER` and updates only the corresponding active slot.

## HDMA / PPU state used by the experiment

The promoted component remains intentionally standalone and is **not yet aggregate compatibility-safe**.

- Channel 6 is temporarily claimed for the experiment.
- ch6 mode 1 writes `WH0/WH1` (`$2126/$2127`) by scanline.
- `$2130` uses the color-window confinement already proven by earlier stages.
- `$2131 = $63` selects ADD+HALF for BG1/BG2/backdrop, excluding BG3 and OBJ.
- the fixed color is black in this diagnostic version.

The NMI-tail hook is after the game's ordinary VBlank DMA reuse of channel 6,
so the experiment reconfigures ch6 only after those DMA transfers.

## Deferred work

The inn case is now runtime-proven and promoted. The component remains aggregate-disabled; remaining integration work includes:

- generic handling of more than the focused ordinary + type-2 pair;
- formal HDMA-channel coexistence with maps/effects;
- save/restore/composition of pre-existing color math/window state;
- choosing the final panel fixed color rather than diagnostic black;
- validation across choices, shops/Neko, magic/water/fog/boss effects and menus;
- replacement of temporary WRAM/ROM allocations by documented aggregate-safe
  allocations.
