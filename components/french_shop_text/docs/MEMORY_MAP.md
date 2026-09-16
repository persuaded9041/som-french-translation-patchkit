# french_shop_text memory map

| ROM | CPU/SNES | Purpose |
|---:|---:|---|
| `0x19FE20-0x19FEF3` | `$D9:FE20-$FEF3` | existing stock 212-byte shop/forge mini-event allocation; rebuilt French pool currently occupies `$FE20-$FED2` and leaves the unused stock tail untouched |
| `0x007AFB-0x007AFC` | `$C0:7AFB-$7AFC` | rebuilt pointer operand for source script `$D9:FE20` |
| `0x007B0E-0x007B0F` | `$C0:7B0E-$7B0F` | rebuilt pointer operand for source script `$D9:FE2D` |
| `0x007B13-0x007B14` | `$C0:7B13-$7B14` | rebuilt pointer operand for source script `$D9:FE49` |
| `0x007B7B-0x007B7C` | `$C0:7B7B-$7B7C` | rebuilt pointer operand for source script `$D9:FE65` |
| `0x007B85-0x007B86` | `$C0:7B85-$7B86` | rebuilt pointer operand for source script `$D9:FE96` |
| `0x007B8C-0x007B8D` | `$C0:7B8C-$7B8D` | rebuilt pointer operand for source script `$D9:FEB5` |
| `0x007B91-0x007B92` | `$C0:7B91-$7B92` | rebuilt pointer operand for source script `$D9:FED1` |
| `0x007C38-0x007C39` | `$C0:7C38-$7C39` | rebuilt pointer operand for source script `$D9:FE7E` |
| `0x007E44-0x007E45` | `$C0:7E44-$7E45` | rebuilt pointer operand for source script `$D9:FEEC` |

Standalone operation also installs the existing byte-identical shared
`dialogue_french` glyph span and context-sensitive event DTE router documented
in the root memory map. Those writes are shared infrastructure, not private new
allocations.
