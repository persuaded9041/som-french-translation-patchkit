# Japanese warp hexagram restoration

`default_uncensored_hexagram` restores the three Japanese 4bpp warp-circle tiles that were changed to a triangular motif in the USA and French releases. It is a default component, so it belongs to both the USA and localized aggregates.

## Editable source

`assets/uncensored_hexagram.png` is a canonical indexed 24×8 PNG containing the three tiles left to right. The builder re-encodes the PNG to the original SNES 4bpp layout and rejects any result that differs from the verified Japanese bytes.

The first tile writes to `$DD:B840-$B85F`; the other two write to `$DD:B900-$B93F`. The gap `$DD:B860-$B8FF` is not part of the graphic and remains untouched.

## Build

```bash
python3 build.py "Secret of Mana (USA).sfc" uncensored-hexagram
python3 build.py "Secret of Mana (USA).sfc" --combine --locale french
```

Runtime validation is complete: the Japanese six-pointed warp symbol is visible
in game. This component is the promoted baseline for the restoration.
