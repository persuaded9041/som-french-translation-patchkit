# Opening startup-credit accent research — `CHAUVIRÉ`

Date: 2026-09-15
Status: **next investigation; no implementation promoted yet**

## Objective

Replace the current startup-credit one-cell `É` workaround with a true two-row
rendering for the final letter of:

`Traduction : E.CHAUVIRÉ`

Target result:

- base row contains ordinary `E`;
- the acute accent is rendered in the tile row immediately above that `E`;
- the opening-font `Z` slot is restored to `Z`;
- the accent follows the startup-credit line's fade-in and fade-out exactly,
  frame-for-frame, without lingering, popping early/late, or using a separate
  visual intensity.

## Validated baseline to preserve

`french_opening` currently:

- keeps the stock fixed-width startup/title renderer;
- keeps the stock `$C1:0014` resource-loader/decompressor path;
- relocates the literal-only arrangement stream to `$EE:A000-$BFFF`;
- uses the helper reserve `$EE:9000-$9FFF` (active helper currently starts at
  `$EE:9000`);
- keeps `$EF` unused because the previous raw-copy experiment conflicted with
  `mana_tree_original` in the full build;
- appends five startup credits and uses a 180-frame visible dwell;
- encodes startup-credit `É` as opening-font tile `$7A`, replacing stock `Z`.

The scrolling prologue is a **different rendering case**: it already represents
`é/É`, `è/È`, and `ê/Ê` as a base E plus `$7D/$7E/$7F` accent tiles on the row
above. That proves the opening font has usable accent artwork, but it does not
prove the startup-credit fade path can use the same overlay mechanism.

## Historical runtime evidence

An earlier experimental implementation (not present as promoted code in this
checkpoint) successfully displayed the startup-credit acute accent on the row
above the credit. The unresolved defect was that this accent row did **not**
follow the credit line's fade-in/fade-out.

Treat this as important negative evidence:

- placement of a second-row accent is feasible;
- fade synchronization is the unsolved problem;
- merely writing the accent tile to the row above is insufficient.

Do not claim the old experiment's exact hook/address unless rediscovered from
code/history or independently re-derived.

## Current code surfaces

Primary implementation files:

- `components/french_opening/build_patch.py`
- `components/french_opening/src/opening_hook.asm`
- `components/french_opening/assets/opening_font.png`
- `translations/opening_text_french.json`

Current credit-specific builder functions/constants include:

- `CREDIT_E_ACUTE_TILE_CODE = 0x7A`;
- `encode_credit_text()`;
- `append_startup_credit_list()`;
- `patch_startup_credit_sequence()`;
- credit-list and dwell signatures in the decompressed title-code resource.

Current prologue accent machinery to study for comparison:

- `accents()`;
- `build_prologue()`;
- `$7D` acute / `$7E` grave / `$7F` circumflex convention.

## Required reverse engineering before implementation

The next investigation should produce an address-backed map for the startup
credits, not merely a high-level guess.

### 1. Credit loop

Recover the complete routine around the current credit-loop signature (described
in the builder as the CPU `$8DD0` area):

- record pointer/indexing;
- line centering/indent handling;
- text decoding;
- tilemap write location;
- per-credit state transitions;
- fade-in loop;
- 180-frame dwell;
- fade-out loop;
- row clearing / transition to the next credit.

Record both decompressed-title-code offsets and effective CPU addresses wherever
possible.

### 2. Tilemap/buffer ownership

Determine exactly:

- which WRAM buffer/tilemap row receives the credit text;
- which VRAM tilemap it ultimately updates;
- the row immediately above the credit;
- whether the renderer rewrites only the main row on every fade frame;
- whether a second row must be copied/marked dirty separately;
- whether attributes/palette bits differ by row or tile.

### 3. Fade mechanism

Prove what actually fades the credit. Possibilities to test rather than assume:

- palette/CGRAM mutation;
- palette-number or priority bits in tilemap entries;
- global screen brightness (`INIDISP`);
- a precomputed sequence of tile attributes/colors;
- selective buffer/VRAM updates;
- some combination of the above.

Identify the exact state variable(s) or subroutine(s) controlling fade intensity
and the exact frame at which they are applied.

### 4. Explain the historical failure

Once the fade path is mapped, provide the most likely concrete explanation for
why a separately written accent row could be visible yet fail to fade with the
credit. The explanation must point to observed code/data behavior, for example:

- accent used another palette/attribute;
- accent row was not rewritten during fade steps;
- accent bypassed the staging buffer that receives changing attributes;
- fade cleanup only touched the main row;
- or another proven mechanism.

### 5. Candidate architectures

Only after the above evidence, rank minimal implementations. Prefer designs that
reuse the stock fade state and update the accent in the same rendering phase as
the main credit. Avoid a parallel timer/fade implementation unless the stock
path cannot be shared.

A good design should ideally:

- restore tile `$7A` to the original `Z` artwork;
- encode startup-credit `É` as ordinary `E` plus metadata/marker rather than a
  replacement glyph;
- generate the accent tile entry using the **same palette/attribute/fade state**
  as the corresponding base-row tile;
- clear/update both rows together;
- keep all other credits byte/visually unchanged;
- preserve the validated five-credit duration and arrangement architecture.

## Validation plan for a future patch

When an implementation is eventually approved, validate incrementally:

1. `Z` restored and ordinary credits unchanged;
2. accent appears at the correct horizontal tile above the final `E`;
3. static full-bright credit looks correct;
4. accent and base row appear on the same fade-in frame/intensity;
5. accent and base row disappear on the same fade-out frame/intensity;
6. no stale accent remains for the next credit;
7. standalone `french_opening` works;
8. `french_opening + mana_tree_original` works;
9. full `all.ips` works.

Do not alter dialogue data or `intro_skip` as part of this investigation.
