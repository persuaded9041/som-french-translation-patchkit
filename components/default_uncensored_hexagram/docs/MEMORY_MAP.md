# default_uncensored_hexagram memory map

| File range | SNES range | Size | Purpose |
|---|---|---:|---|
| `0x1DB840-0x1DB85F` | `$DD:B840-$DD:B85F` | 32 | Japanese hexagram warp tile 1 |
| `0x1DB900-0x1DB93F` | `$DD:B900-$DD:B93F` | 64 | Japanese hexagram warp tiles 2–3 |

`0x1DB860-0x1DB8FF` is intentionally outside this component.

Runtime status: **validated**. The Japanese six-pointed warp symbol is visible
in game, with no changes to the intervening tiles.
