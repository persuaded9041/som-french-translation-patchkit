# french_resources memory map

All addresses are SNES CPU addresses unless noted otherwise.

| Range | Purpose |
|---|---|
| `$C0:16F5-$16F8` | shared direct-glyph/DTE decision hook |
| `$C7:4570-$45EE` | shared context-sensitive DTE router (127 bytes active in `$4570-$45EF` reserve) |
| `$C7:4C85` | shared dialogue/resource `$E8` DTE-profile marker |
| `$CA:0800-$0C01` | complete 513-entry resource pointer table (`513 * 2 = 1026` bytes) |
| `$CA:98E1-$B49F` | current rebuilt resource blob (7,103 bytes) |
| `$CA:98E1-$B573` | maximum permitted stock resource allocation (7,315 bytes) |
| `$D2:DFE4-$E0DF` | shared `dialogue_french` direct-glyph span `$D3-$E7` |

The component allocates no private WRAM and no relocated ROM bank. The DTE router,
profile marker and glyph span are installed byte-identically by the dialogue/resource
components where needed and are therefore intentional compatible overlaps.
