# Round 85.13 — opening literal-stream architecture

## Goal

Keep the French opening fully regenerable while removing the disproportionate
host-side cost of optimally recompressing the modified title arrangement.

## Validated architecture

- The prologue and five startup credits are still generated from the canonical
  opening source/translation JSON and font asset.
- The modified arrangement is relocated to ROM `$EE:A000`.
- It is stored in the game's existing compression container, but every packet is
  literal (maximum 128 bytes per packet). Encoding is deterministic O(n).
- The stock title loader still calls `$C1:0014`, which expands the stream into
  WRAM `$7E:5000` exactly as before.
- The renderer helper remains at `$EE:9000`.
- `french_opening` deliberately uses no `$EF` allocation.

## Why not raw copying

A prototype stored the arrangement as raw bytes and replaced the stock
`$C1:0014` call with a direct 65C816 block copy. It worked when
`french_opening` was applied alone, but the full combined patch booted to a
black screen. Bisecting the components showed that removing
`mana_tree_original` made the combined build work again.

`mana_tree_original` hooks the stock resource-loading/decompression machinery.
Restoring the normal `$C1:0014` path while keeping the opening stream trivial
resolved the interaction. The user runtime-validated both:

- `french_opening + mana_tree_original`;
- the complete combined patch.

## Performance

Historical standalone build timings in the maintenance environment:

- original optimal compressor: ~14.7 s;
- optimized optimal compressor: ~3.3 s;
- literal-only arrangement stream: ~1.5-1.6 s.

The optimal compressor is still retained for the title-code and font blocks,
where it is fast enough and preserves their existing fixed-capacity storage.

## Maintenance rule

Do not hardcode opening prose or a prebuilt compressed blob. Editing the French
opening translation must continue to rebuild the arrangement from source. The
literal stream is merely a cheap serialization of that freshly generated
arrangement.
