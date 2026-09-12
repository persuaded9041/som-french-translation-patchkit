# Watts forge weapon-line VWF research — clean checkpoint

This document records the September 2026 investigation into the long French weapon-name
problem in Watts' weapon-upgrade screen. It exists specifically to prevent future work
from repeating rejected hooks or trusting invalid diagnostic patches.

## Runtime problem

The Android-FR name insertion experiment is broadly usable in game, but a long weapon
name such as `Fendeuse de dragon` overflows the fixed-width weapon-upgrade line shown by
Watts. In the Matango/Mushroom Kingdom Watts sequence, the current weapon name can continue
onto a second physical row instead of remaining on the intended single upgrade row.

The production Round-72 dialogue VWF must **not** be changed merely to solve this menu.
The canonical dialogue checkpoint remains 701/701 complete, 0 PARTIEL, 0 errors,
0 warnings, 0 implicit wraps.

## Current safe baseline

The safe repository state for further work is the resource-insertion-study checkpoint:

- Android `systxt` -> SNES `$CA` mapping is deterministic;
- 475/513 resources map, with 4 unresolved and 34 deliberately excluded;
- the production `french_resources` component inserts 349 translated names and leaves
  three `n°` enemies stock because `°=$E6` conflicts with the current non-event DTE boundary;
- the user runtime-tested the names experiment and reported that it works **mostly**;
- the known blocker is the Watts weapon-upgrade line for long names;
- the rejected experiments below remain historical; the later exact-submit Forge backend is
  production-owned by `vwf_ui` and documented in `docs/UI_VWF.md`.

The `capacity24` experiment restored normal Watts introduction text but **did not enable
VWF** in the weapon-upgrade line. Treat it as historical diagnostics only, not as an
accepted runtime change.

## Runtime facts actually validated

These observations are useful and may be relied on when resuming the investigation.

### 1. The visible right arrow uses the stock `$D0` font glyph

A diagnostic patch replaced the bitmap of glyph `$D0` (`→`) with the following stock
arrow glyph. The arrow in the Watts upgrade row changed accordingly. This proves that
this field uses the same stock font glyph data. It does **not**, by itself, identify the
specific text-renderer invocation.

### 2. The upgrade row reaches shared renderer `$C0:1664` from caller `$C0:1150`

The first caller probe was invalid (see rejected paths below). A later **stable entry
probe** captured the JSR return once at renderer entry before renderer-local stack
activity. On the real Watts upgrade line the user observed `←`, which encoded caller
`$C0:1150` / return `$1152`.

Therefore the line does pass through the same shared renderer entry used by event text,
but existing Round-72 VWF gating still does not activate for it.

### 3. The renderer enters with data bank `$7E`

A separate entry-time DB probe changed only the `$D0` arrow according to the data bank.
The user observed `←`, which encoded **DB = `$7E`**.

This is a strong discriminator: the upgrade line is a dynamic WRAM-backed text path,
not an ordinary static `$C9/$CA` dialogue line.

### 4. Static code trace: dynamic WRAM mini-script path

Static reverse engineering found a path in bank `$C0` that prepares/uses a WRAM event
buffer around `$7E:FF69`, with `$1D03` selecting `$7E`, then invokes the event engine.
A source record is copied from WRAM before execution. This matches the runtime DB result
and is a promising lead, but the exact routine that assembles

`[current weapon name]  →  [next weapon name / ...]`

has **not yet been isolated and runtime-proven**. Do not promote guessed addresses or
pointer timing to validated facts until a targeted probe proves them.

## Rejected approaches — do not retry unchanged

### A. Enable dialogue VWF for bank `$D9`

Reason tried: Watts has shop/forge response mini-events in bank `$D9`.

Runtime result: **no effect on the weapon-upgrade line**.

Conclusion: `$D9` contains response/event text after menu actions, not the line renderer
we need. Do not broaden `vwf_dialogues` to `$D9` for this problem.

### B. Treat `OP_0F` / forge mode as sufficient and hook the presumed menu caller

A hook around the presumed third caller (`$C0:CB3C`) / forge-mode path was attempted.

Runtime result: Watts' introduction was contaminated, including repeated weapon-name text,
while the actual upgrade line still had no VWF.

Conclusion: forge-mode state alone is too broad and the presumed caller was not a safe
identity for the target row.

### C. `$7F`-buffer correction of the same menu-caller hypothesis

A second variant corrected an assumed WRAM bank mismatch and kept temporary data in `$7F`.

Runtime result: still no VWF on the actual weapon-upgrade line.

Conclusion: correcting WRAM bank use did not make the underlying caller hypothesis valid.

### D. Raise the forge parser capacity to 24 characters

Reason tried: `Fendeuse de dragon` is longer than stock names, and an early hypothesis
was that a pre-render character cap forced the extra row.

Runtime result: Watts' introduction returned to normal, but **the upgrade text remained
fixed-width with no VWF**.

Conclusion: useful as evidence that capacity alone is not the solution. Do not mistake
this for a VWF fix.

### E. Search the decoded row for `$D0` and enable VWF when the arrow is present

Reason tried: the arrow is visually distinctive and appears in the target row.

Runtime result: no VWF on the target row.

Conclusion: the expected decoded buffer/state was not the right place or time to identify
the row.

### F. First caller probe based on per-scanline stack inspection

This diagnostic was invalid in **two separate ways** during the investigation:

1. one delivered `caller probe` IPS was accidentally byte-identical to the `capacity24`
   test, so it did not contain the announced instrumentation at all;
2. a subsequent raster-level version inspected stack-derived caller state separately for
   each of the 12 glyph rows. The user observed a mixture of `←`, `↑` and corrupted lines
   inside one arrow, proving that the method itself was unstable.

Conclusion: never identify the caller from renderer-local stack layout inside every
font-row call. If caller identity is needed, capture it once at renderer entry. The later
stable-entry probe is the valid result.

### G. Gate VWF on `caller $C0:1150 + forge mode`

Runtime result: Watts' introductory text glitched badly, while the upgrade line still
showed no VWF.

Conclusion: the introduction can share those broad conditions; they are not specific
enough to identify the upgrade row.

### H. Gate at renderer time on `$7E:FF69`

Runtime result: introduction was normal, but the target line remained unchanged.

Conclusion: by renderer time the event pointer/state had already advanced; matching the
initial mini-script address there is too late.

### I. Hook the global parser to tag `$7E:FF69`

Runtime result: **the game glitched immediately at startup**.

Conclusion: modifying the global parser entry for a menu-specific experiment is too risky.
Do not reintroduce this architecture.

### J. Tag from presumed exact NOP site around `$C0:588E`

Reason tried: avoid the global parser and tag only the presumed dynamic-record copy path.

Runtime result: the target upgrade line still had no VWF, and the final characters of
Watts' introductory dialogue stopped rendering correctly.

Conclusion: this site/tag timing is not a validated identity for the upgrade row and also
leaks into normal text state. Remove it completely from canonical code.

## Invalid / withdrawn address claim

An earlier note referred to `$C0:D85D`; this came from an incorrect ROM-address mapping
conversion and was withdrawn. Do not use `$C0:D85D` as a forge-text landmark.

A later `$C0:585D`/WRAM-copy hypothesis is useful only as a static lead; it remains
unproven as the exact assembler of the visible `weapon X → weapon Y/...` row.

## Historical pre-solution investigation plan (superseded)

Do **not** add another broad VWF gate yet. First isolate the builder of the exact upgrade
row.

Recommended sequence:

1. Start from the clean resource-insertion-study checkpoint, not any forge-VWF archive.
2. Keep `vwf_dialogues` byte-identical to the validated Round-72 version.
3. Instrument the dynamic WRAM record **before** it is passed to the event engine.
4. Find the code that writes the two weapon identifiers / name references and the `$D0`
   arrow into that record.
5. Prove that identity with a harmless one-shot visual probe that changes only the target
   row, never the global parser or renderer.
6. Once the builder is known, choose between:
   - emitting a dedicated marker/control byte that the existing VWF can recognize safely;
   - rendering only the name fields with a dedicated menu VWF compositor;
   - or changing the layout itself if the target row has stricter geometry than expected.
7. Preserve the normal Watts introduction and all 701 validated dialogues as hard
   regression tests.

The next implementation should not depend solely on `forge mode`, `$D9`, `$FF69` at
renderer time, `$C0:CB3C`, or searching a presumed decoded buffer for `$D0`; all of those
were already tested and rejected in that form.

## Round 74 accepted solution — `vwf_ui`

The investigation is complete for the Watts Forge row. The accepted solution is
productionized as standalone component `vwf_ui`; it does not depend on `vwf_dialogues`
and keeps ordinary dialogue ownership separate.

### Runtime proofs accumulated after the Round-73 clean research checkpoint

1. **Forge suffix builder proven** — changing only the literal arrow byte in the
   `$D0:D82F+` branch changed the visible row arrow from `→` to `←`.
2. **Current-name writer proven** — replacing only `$D0:D3C4 STA $19D3` with
   `STZ $19D3` forced all current weapon names to resource ID 0 (`Gant d'aura`).
3. **Builder → renderer continuity proven** — a probe from the current-name path reached
   renderer `$C0:167D`. The successful continuity probe uses `$1D03=$00`; this is the
   event bank for the low-WRAM mirror. CPU DB=`$7E` is a separate runtime fact.
4. **Local VWF proven** — the current weapon name renders proportionally.
5. **Dynamic suffix compaction proven** — after preserving the full name in the stock
   decoded row, `→...` can be shifted to one decoded space after the real name end.
6. **Logical capacity proven** — the final `P` of `GP` was a logical-budget problem,
   not a pixel-width problem. +1 fixed the observed case; the production component uses
   **+3**, stress-tested successfully with a temporary 19-character weapon name.
7. **Standalone targeting proven** — arming the UI tag at the earlier weapon-name helper
   leaked into Watts' ordinary dialogue. The final tag is armed only at the exact submit
   of Forge mini-event `$00:19D0`. With that targeting and an explicit `$9385` clear on
   stock dispatcher fallbacks, standalone `vwf_ui` was runtime-validated on a clean
   USA ROM: Forge names use VWF, GAME SELECT remains stock/non-glitched, and Watts'
   ordinary dialogue remains stock/non-VWF.

### Final architecture

- the exact Forge-row submit sequence (X=`$19D0`, bank `$00`, immediately before
  `$D0:D5D7`) is redirected through a tiny wrapper that arms a one-shot UI tag and then
  reproduces the original submit; the earlier `WEAPON_NAME` helper is untouched;
- Forge `TEXT_X` arguments move from logical slots 16/21 to safe slots 20/25. This is
  decoder geometry only; final visual position is not fixed there;
- the stock parser and stock decoded buffer remain in use;
- the common capacity helper adds +3 only when `vwf_ui` config and the exact
  one-shot submit tag are both active;
- the `vwf_ui` renderer copies the already-decoded stock row, finds the true end of
  the current weapon name, compacts the complete suffix leftward, and draws it with the
  shared VWF framing/compositor/metrics;
- the shared dispatcher consumes the UI tag and clears `$7E:9385` on every stock
  fallback, so fixed-width callers such as GAME SELECT cannot inherit stale VWF state;
- `vwf_ui` has its own renderer and is standalone. A shared renderer dispatcher lets
  `vwf_dialogues` and `vwf_ui` coexist without one depending on the other.

The temporary longest-name override used for stress testing is not included in production.
Resource translation remains a separate text-resource concern.

### Rejected paths from the continuation

Do not retry these unchanged:

- tagging the later `$D0:D836` suffix path and expecting it to identify the current-name
  renderer invocation;
- requiring event bank `$7E` at renderer time (event bank is `$00`; DB=`$7E` is a
  different CPU register fact);
- routing the Forge mini-event through `vwf_dialogues`'s private 38-character parser buffer;
- changing only the price logical slot from 25 to 24;
- capacity changes gated by `$1D01 == $19D0`;
- a +1 capacity change armed from a tag that did not yet exist at capacity init;
- an autonomous UI renderer that did not share the validated low-level VWF hooks;
- leaving `$9385` set after an UI render (GAME SELECT corruption);
- arming the one-shot tag at the earlier current-weapon helper (Watts dialogue became VWF).

The successful identity is the **exact submit of `$00:19D0`**, with the stock parser/buffer
kept intact and only render-time compaction plus a local +3 logical margin.


## Round 75 final status

The Forge investigation is closed. The final standalone `vwf_ui` backend is runtime-validated
on a clean USA ROM and in the aggregate build: weapon names render in VWF, the full dynamic
`→...` / price suffix remains on one line under the +3 logical margin, GAME SELECT remains stock,
and Watts' ordinary dialogue remains owned by the stock/dialogue path rather than `vwf_ui`.

Do not reopen the rejected Forge probes when extending UI VWF elsewhere. New work belongs in
separate narrow backends under `vwf_ui` and should follow `docs/UI_VWF.md`.
