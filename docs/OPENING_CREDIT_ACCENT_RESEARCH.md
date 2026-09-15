# Opening startup-credit accent research — `CHAUVIRÉ`

Date: 2026-09-15  
Status: **runtime-validated and promoted**

## Objective

Render the final `É` of:

`Traduction : E.CHAUVIRÉ`

without sacrificing the opening-font `Z` tile:

- the base credit row contains an ordinary `E`;
- the acute accent uses tile `$7D` on the tile row immediately above;
- opening-font tile `$7A` remains the stock `Z`;
- accent and base row follow the same fade-in/fade-out frame-for-frame;
- no stale accent remains after the fifth credit.

This is now the promoted implementation.

## Preserved opening architecture

The validated storage/loader architecture is unchanged:

- stock title resource loader/decompressor `$C1:0014`;
- literal-only arrangement stream at `$EE:A000-$BFFF`;
- opening renderer helper reserve `$EE:9000-$9FFF`;
- no allocation in `$EF`;
- five startup credits;
- 180-frame visible dwell;
- stock credit fade timing/state.

`intro_skip` and the dialogue corpus were not modified by this work.

## Renderer map

The startup-credit loop lives in the decompressed title-code resource around
CPU `$8DCD-$8E64` (logical title-code address space beginning at `$8000`).
The important sequence is:

- `$8E0A`: load current credit-list X offset;
- `$8E0F`: prepare the destination row;
- stock `$8820`: decode one 32-cell credit record into the tilemap buffer;
- `$C870`: submit the containing tilemap buffer for video transfer;
- `$8B5D`: update the fade color state once per fade step;
- 31-step fade-in;
- 180-frame dwell (French patch; stock was 240);
- 31-step fade-out;
- next credit.

The stock decoder writes one full tilemap row: 32 cells × 2 bytes = `$40`
bytes. It writes the tile-number byte while preserving the existing attribute
byte.

The tilemap base is kept in `$02`. The visible credit row is addressed as:

`tilemap_base + $0440`

The immediately preceding tile row is therefore:

`tilemap_base + $0400`

or exactly `$40` bytes earlier.

## Validated two-row rendering

The promoted credit list stores each logical credit as two records:

1. an overlay record for the row above, containing blanks except `$7D` over any
   accented `E`;
2. the normal text record, where accented `E` is encoded as ordinary `E`.

The title-code call site that previously invoked `$8820` directly is redirected
to a small wrapper in existing zero padding at decompressed title-code offset
`$3CED` / CPU `$BCED`.

The wrapper:

1. computes `main_row - $0040`;
2. calls stock `$8820` for the overlay record;
3. restores the normal row;
4. calls stock `$8820` for the text record;
5. returns to the unmodified credit loop.

A final blank overlay record followed by the normal `$00` list sentinel clears
the accent row after the fifth credit without creating a sixth visible credit.

No additional ROM bank or persistent WRAM allocation is required.

## Fade reverse engineering

The historical two-row experiment had already proved that the accent could be
drawn in the correct position, but the accent remained visually outside the
credit fade.

The decisive discovery is that the startup-credit fade is spatially restricted
by HDMA tables in the decompressed title arrangement. These tables drive CGRAM
registers `$2121/$2122` during the credit sequence.

Relevant arrangement offsets:

- `$0D63`: CGADD HDMA table;
- `$0D6C`, `$0D79`, `$0D86`: color/CGRAM HDMA tables.

In the stock/current pre-fix form, the vertical segmentation is:

`120 + 15 + 8 + 1 = 144 scanlines`

The fade-controlled segment is only the 8-scanline third segment. That is
exactly one tile row: the normal startup-credit row.

The overlay accent is one tile row (8 scanlines) above it, so it belonged to the
preceding segment and therefore did not share the animated CGRAM state. This
explains the historical runtime symptom even when the accent tile itself was
correctly positioned.

The promoted fix changes only the segment counts:

`120 + 7 + 16 + 1 = 144 scanlines`

Thus:

- the total vertical coverage remains exactly 144 scanlines;
- the lower boundary of the fade band does not move;
- the fade band simply starts 8 scanlines earlier;
- the normal credit row and the overlay row are now inside the same fade band;
- `$8B5D`, the fade timing, and the per-frame fade state remain unchanged.

This is why the accent now follows the credit fade frame-for-frame without a
parallel timer or a second fade implementation.

## Historical false lead corrected

During research, an intermediate hypothesis blamed the old candidate's
`STA $FFF9,Y` indexed write for leaving the accent in another bank. That
hypothesis was incorrect and is **not** part of the promoted explanation.

The final, runtime-confirmed cause is the HDMA scanline coverage described
above. The old accent was geometrically correct but lived outside the 8-line
CGRAM fade band.

## Font behavior

Opening-font tile `$7A` is restored to the stock `Z` artwork.

The prologue accent artwork remains unchanged:

- `$7D`: acute;
- `$7E`: grave;
- `$7F`: circumflex.

The startup credit reuses `$7D` only as artwork; it does not reuse the prologue's
record format or rendering helper. Credit rendering remains its own two-record
path around stock `$8820`.

## Runtime validation

Validation proceeded in two explicit stages.

### Stage A — geometry only

Promoted baseline was changed only enough to restore the historical two-row
rendering:

- stock `Z` restored in `$7A`;
- base `E` on the credit row;
- `$7D` acute on the row above;
- final overlay cleanup.

Runtime result: **validated**. Accent position and appearance were correct; fade
remained absent, reproducing the historical symptom.

### Stage B — fade band only

Relative to validated Stage A, only the four credit-specific HDMA tables were
changed from `15/8` to `7/16` scanline segmentation. Title-code, font geometry,
credit timing and other components were otherwise unchanged.

Runtime result: **validated by the user**. The accent now follows the fade-in and
fade-out correctly and the visual result is considered perfect.

## Regression constraints

Future changes must preserve all of the following unless independently
revalidated:

- `$7A` remains stock `Z`;
- credit `É` remains base `E` + `$7D` overlay;
- wrapper remains in existing decompressed-title-code padding at `$BCED`;
- fade band remains 16 scanlines with unchanged lower boundary;
- `$8B5D` and the 31-step fade loops remain stock;
- 180-frame French credit dwell remains unchanged;
- arrangement remains at `$EE:A000` through stock `$C1:0014`;
- helper remains in `$EE:9000-$9FFF`;
- `$EF` remains unused by `french_opening`;
- no dialogue or `intro_skip` behavior is coupled to this implementation.
