# french_resources memory map

All addresses are SNES CPU addresses unless noted otherwise.

| Range | Purpose |
|---|---|
| `$C0:16F5-$16F8` | shared direct-glyph/DTE decision hook |
| `$C0:7AFA-$7E45` (9 immediate operands only) | shop/forge `LDX #pointer` references retargeted to rebuilt D9 scripts |
| `$C7:4570-$45EE` | shared context-sensitive DTE router |
| `$C7:4C85` | shared dialogue/resource `$E8` DTE-profile marker |
| `$C7:7B6A-$7B6B` | total-money unit literal `GP -> PO` |
| `$CA:0800-$0C01` | complete 513-entry resource pointer table |
| `$CA:98E1-$B49F` | current rebuilt resource blob (7,103 bytes) |
| `$CA:98E1-$B573` | maximum permitted stock resource allocation (7,315 bytes) |
| `$D0:D894-$D895` | merchandise-price unit literal `GP -> PO` |
| `$D2:DFE4-$E0DF` | shared `dialogue_french` direct-glyph span `$D3-$E7` |
| `$D9:FE20-$FED2` | current rebuilt shop/forge mini-event pool (179 bytes) |
| `$D9:FE20-$FEF3` | maximum permitted stock shop/forge allocation (212 bytes) |

The component allocates no private WRAM and no relocated ROM bank. The DTE router, profile marker and glyph span are byte-identical to the shared dialogue installations and are therefore intentional compatible overlaps.
