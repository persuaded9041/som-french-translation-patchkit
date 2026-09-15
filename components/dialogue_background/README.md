# dialogue_background

Runtime-validated standalone component that replaces Secret of Mana's stock
checkerboard/dithered dialogue-window fill with a hardware semi-transparent
background.

## Validated behavior

The v1 implementation keeps the stock BG3 frame and text opaque, makes the
stock BG3 fill pixels genuinely transparent, and applies SNES color math to the
world visible behind them. Window 1 plus HDMA confines the effect to the live
animated frame geometry.

Runtime validation currently covers:

- a normal single dialogue window, including opening/closing animation;
- the inn reservation flow with the large dialogue frame and the asynchronous
  type-2 GP frame simultaneously visible;
- the stock order `dialogue opens -> GP opens -> dialogue closes -> GP closes`.

The multi-window fix uses an explicit geometry `OWNER`; it never assumes that
current `$A162` identifies the owner of live `$A165-$A168` animation bounds.
See `../../docs/DIALOGUE_TRANSPARENCY_RESEARCH.md` for the reverse engineering.

## Current visual model

- stock dither source `$D2:D480-$D2:D87F` -> transparent 2bpp pixels;
- BG3 text/frame remain opaque;
- BG1/BG2/backdrop use fixed-color `ADD + HALF` (`$2131=$63`);
- BG3 and OBJ are excluded from color math;
- Window 1 confines color math;
- HDMA channel 6 writes `WH0/WH1` per scanline;
- the current diagnostic/final-v1 fixed color is black.

The fully-open standard dialogue calibration is `X=15..240`, `Y=15..63`.
During animation, geometry is derived from stock live bounds `$7E:A165-$A168`.

## Standalone-only status

`component.json` deliberately sets `aggregate_enabled: false`.

This is a real, rebuildable component, but **it is not yet part of `all.ips`**.
The v1 patch preserves the exact runtime-proven Stage-11 allocations so its
functional patch remains byte-identical to the validated test candidate.
Known integration work is intentionally deferred:

- HDMA channel 6 coexistence with water/magic/fog/boss effects;
- preservation/composition of pre-existing color-math/window state;
- current WRAM `$7E:93D0-$93DF` overlaps `vwf_dialogues` interrupted-chunk
  continuation state, so `dialogue_background` and `vwf_dialogues` must **not**
  yet be combined;
- broader validation of shops/Neko, choices and other auxiliary windows.

Do not "fix" those allocations without a new runtime checkpoint: this v1 is
intentionally the promoted, byte-identical validated candidate.

## Build

Against the clean unheadered USA ROM:

```bash
python3 build.py '/path/to/Secret of Mana (USA).sfc' dialogue-background
```

or directly:

```bash
python3 components/dialogue_background/build_patch.py \
  '/path/to/Secret of Mana (USA).sfc' \
  -o patches/dialogue_background.ips
```

No dialogue text, segmentation or Android mapping is modified.
