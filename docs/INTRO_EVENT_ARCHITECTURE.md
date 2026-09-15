# New-game introduction `$0400` — event-engine / assembly architecture

Date: 2026-09-15

This document records the static reverse-engineering of the Secret of Mana (USA)
new-game introduction and the exact engine path used by event `$0400`. It exists
so future work on `intro_skip`, `french_intro` or `vwf_intro` does not have to
rediscover the event-engine architecture from trial-and-error patches.

The reference for this analysis is the clean, unheadered USA ROM with SHA-256
`4c15013131351e694e05f22e38bb1b3e4031dedac77ec75abecebe8520d82d5f`.

## Status / evidence levels

Three evidence levels are used deliberately:

- **Static-proven**: follows directly from clean-ROM bytes / dispatch tables /
  code paths decoded below.
- **Runtime-validated**: behavior already observed in emulator testing and
  preserved by the current project documentation.
- **Interpretation / to confirm**: a functional name inferred from surrounding
  behavior but not yet proven by a dedicated runtime trace.

Do not promote an interpretation to a runtime fact without an emulator trace.
No build or patch generation is required to use this document.

## Important distinction: stock event span vs translated runtime window

The clean-USA stock event `$0400` is:

- start: `$CA:0C02`;
- physical stock end (exclusive): `$CA:0E44`;
- stock size: `$0242` bytes / 578 bytes.

The French rebuilt event is intentionally larger:

- start: `$CA:0C02`;
- validated translated end (exclusive): `$CA:0E8B`;
- validated translated runtime window: `$CA:0C02-$0E8A`.

`french_intro` relocates unchanged stock events `$0401-$040F` away from the
space consumed by the enlarged French `$0400`. `vwf_intro` and `intro_skip`
therefore gate against the **translated** exclusive end `$0E8B`, not against
the stock `$0E44` endpoint.

## 1. Event-engine architecture

### 1.1 C1 is the primary event interpreter

The primary event dispatcher is in bank `$C1`, beginning at `$C1:E8E0`.

The live event-script pointer used by this interpreter is stored in direct page:

| DP | Meaning |
| --- | --- |
| `$D0` | interpreter state / asynchronous state selector |
| `$D1-$D2` | 16-bit event-script pointer |
| `$D3` | event-script bank |
| `$D6-$D8` | saved return pointer/bank used by event CALL/RETURN |

At `$C1:E8E0`, the engine first checks `$D0`:

- normal/non-negative state: decode the next event opcode;
- negative state (`$80+`): dispatch to an asynchronous state handler.

For a normal opcode, the engine reads a 16-bit unit from `[$D1]` into `$04-$05`.
This makes the convention below important when reading handlers:

- `$04` = opcode byte;
- `$05` = first argument byte.

Opcodes below `$50` are handled by C1 event handlers. Opcodes `$50+` are
clamped to the shared text bridge and delegated to the C0 text engine.

### 1.2 Event command dispatch table

The command pointer table begins at `$C1:E922`. The opcodes directly relevant
to `$0400` resolve as follows:

| Opcode | Project name / role | C1 handler | Evidence |
| ---: | --- | --- | --- |
| `$04` | `OP_04` actor-state bit toggle | `$C1:EA26` | Static-proven |
| `$08` | `COMPLETE_ACTIONS` | `$C1:EA59` | Static-proven |
| `$10-$17` | JUMP event family | `$C1:EAF0` | Static-proven |
| `$18-$1B` | room-change family | `$C1:EB07` | Static-proven |
| `$1D` | mode / travel transition family | `$C1:EB2F` | Static-proven; `$1D 7F` runtime-known as flyover path |
| `$20-$27` | CALL event family | `$C1:EBF2` | Static-proven |
| `$28` | `WAIT` | `$C1:EC1A` | Static-proven |
| `$29` | increment event counter nibble | `$C1:EC46` | Static-proven |
| `$2A` | decrement event counter nibble | `$C1:EC7F` | Static-proven |
| `$2D` | effect family; `$06` = palette-to-white path | `$C1:ED35` | Static-proven |
| `$32` | actor movement/action scheduling | `$C1:EEEA` | Static-proven |
| `$34` | repeated/loop actor action helper | `$C1:EFD1` | Static-proven at field level; semantic label partly inferred |
| `$40` | `PLAY_SOUND` | `$C1:F0EC` | Static-proven |
| `$42` | counter-range branch/select | `$C1:F140` | Static-proven |
| `$50+` | bridge to C0 text engine | `$C1:F27A` | Static-proven |

### 1.3 The C0 text engine is a delegated subsystem, not the primary event engine

`$C1:F27A` is the bridge used whenever C1 encounters text opcode `$50+`.
It copies the event pointer into the C0 text-engine variables:

```text
$D1 -> $1D01
$D2 -> $1D02
$D3 -> $1D03
```

and then sets:

```text
$48 = $01
$D0 = $81
```

The normal game loop then runs the C0 text engine, whose relevant entry point is
`$C0:012C`.

When the C0 text engine has returned control (`$48 == 0`), asynchronous state
`$81` at `$C1:F2F5` copies the possibly advanced C0 pointer back:

```text
$1D01 -> $D1
$1D02 -> $D2
$1D03 -> $D3
$D0 = $01
```

This explains why the current `intro_skip` pointer redirection works despite
hooking `$C0:012C`: it changes the C0-side pointer while the script is delegated
to the text engine, then C1 imports that redirected pointer when state `$81`
completes.

It also means `$C0:012C` should not be described as the primary event
interpreter. It is a **text-engine execution point reached through C1 state
`$81`**.

### 1.4 Normal-room scheduler and event cadence

The normal room main loop begins at `$C0:B03F`. After setup it maintains a
5-phase counter in `$56`:

```text
$56 = 0 -> 1 -> 2 -> 3 -> 4 -> 0 ...
```

`$C2:C786` is called every normal room-loop frame. The C1 event interpreter,
however, is entered through `$C1:E8C7` only when all of the following are true:

```text
$D0 != 0
$56 == 3
$E2 bit 0 == 0
$FF == 0
$52 == 0
$E8 bit 2 == 0
```

The `$56 == 3` gate means ordinary event-state progress occurs **once every five
normal room-loop frames**. A single interpreter tick can still consume several
synchronous opcodes because many handlers branch straight back to `$C1:E8D3`;
an asynchronous handler instead returns to the game loop and resumes on a later
event tick.

Text ownership has a different cadence. `$C2:C786` runs every normal room-loop
frame and, while `$48 != 0`, calls the C0 text-engine entry path
`$C0:0003 -> $C0:0083 -> $C0:012C` every frame. Consequently a C0 text hook is
frame-responsive while C1 is in state `$81`, even though ordinary C1 event-state
updates are only serviced on one phase out of five.

## 2. Asynchronous event states

The asynchronous-state pointer table begins at `$C1:E902`.

| `$D0` | Handler | Function relevant here |
| ---: | --- | --- |
| `$80` | `$C1:F2E9` | wait for `$4E` to clear, then resume |
| `$81` | `$C1:F2F5` | wait for C0 text engine (`$48`) then resync `$1D01-$1D03` into `$D1-$D3` |
| `$82` | `$C1:F310` | timed `WAIT`: decrement `$4F` each pass |
| `$83` | `$C1:F31C` | zero-duration `WAIT` / input-dependent wait path |
| `$84` | `$C1:F341` | immediate resume helper |
| `$85` | `$C1:F348` | `COMPLETE_ACTIONS`: wait until relevant actor actions finish |
| `$86` | `$C1:F37B` | wait on `$E2` bit `$08`, then resume |
| `$87-$8F` | `$C1:F389` | common fallback/resume path (not required by stock `$0400`) |

The important architectural fact is that many event opcodes are **non-blocking**:
they configure state and return to the main game loop. Progress continues on
later frames through `$D0`.

### 2.1 `WAIT` (`$28`)

Handler: `$C1:EC1A`.

For a non-zero delay:

```text
$4F = delay
$D0 = $82
```

State `$82` decrements `$4F` once per event-engine pass and resumes when it
reaches zero. Because the normal-room event scheduler is serviced once every
five frames, the stock timed wait duration is statically determined as:

```text
WAIT xx = 5 * xx normal-room frames
```

For the waits used by stock `$0400`:

| Command | Counter | Normal-room frames | Approx. NTSC time |
| --- | ---: | ---: | ---: |
| `28 10` | 16 | 80 | ~1.3 s |
| `28 30` | 48 | 240 | ~4.0 s |
| `28 38` | 56 | 280 | ~4.7 s |
| `28 40` | 64 | 320 | ~5.3 s |

The seconds are only a presentation aid; the exact static contract is the
frame count above.

For `$28 00`, the handler enters `$D0 = $83` instead; this is a different
input/actor-state wait path and must not be treated as an ordinary timed wait.

### 2.2 `COMPLETE_ACTIONS` (`$08`)

Handler: `$C1:EA59`.

The command sets:

```text
$D0 = $85
```

and advances the script. State `$85` at `$C1:F348` scans actor structures. An
active actor with a non-zero action/status field at `$E042,X` keeps the event
suspended. Only when the relevant actions have completed does `$D0` return to
the normal execution state.

### 2.3 Text (`$50+`)

All text commands share the bridge `$C1:F27A`; C0 decides whether the live byte
is `TEXT_OPEN`, `TEXT_CLOSE`, `TEXT_CLEAR`, a text glyph/DTE unit, etc.

The C1 event script therefore remains suspended in state `$81` while C0 owns
the live text pointer.

## 3. Event-entry path into `$0400`

The only stock event that directly selects `$0400` is `$0100`.

Stock `$0100`:

```text
42 00 1F
11 FF
14 00
00
```

`$42` at `$C1:F140` is a counter-range selector. For this instance it examines
counter `$CF00` and chooses one of the following two 2-byte event-jump commands:

- `$11 FF` -> event `$01FF`;
- `$14 00` -> event `$0400`.

With `$CF00 == 0`, the selector advances over `$11 FF` and reaches `$14 00`,
therefore entering the new-game introduction. Values in the encoded accepted
range use `$01FF` instead.

`$01FF` itself is only:

```text
18 0E
00
```

so the alternate route is a direct room transition rather than the intro.

## 4. Exact stock `$0400` command timeline

The clean-USA event occupies `$CA:0C02-$0E43` inclusive. Text content is omitted
here on purpose; the source spans / IDs are enough to correlate with
`assets/intro_event.json` and the French translation pipeline.

| Address | Bytes / source span | Meaning |
| --- | --- | --- |
| `$CA:0C02` | `04` | toggle actor-state bit 7 for the three party actor structures |
| `$CA:0C03` | `29 F8` | increment low nibble of `$CFF8` |
| `$CA:0C05` | `40 01 2B 0C FF` | sound command |
| `$CA:0C0A` | `27 90` | CALL event `$0790` |
| `$CA:0C0C` | `50` | `TEXT_OPEN` |
| `$CA:0C0D-$0C4A` | text part 1 | source text carrier |
| `$CA:0C4B` | `28 30` | timed wait |
| `$CA:0C4D` | `51` | `TEXT_CLOSE` |
| `$CA:0C4E` | `18 CF` | load room `$00CF` |
| `$CA:0C50` | `32 00 C0` | actor action |
| `$CA:0C53` | `08` | wait for actions |
| `$CA:0C54` | `34 00 8B` | repeated/loop action |
| `$CA:0C57` | `08` | wait for actions |
| `$CA:0C58` | `50` | `TEXT_OPEN` |
| `$CA:0C59-$0CA4` | text part 2 | source text carrier |
| `$CA:0CA5` | `28 38` | timed wait |
| `$CA:0CA7` | `51` | `TEXT_CLOSE` |
| `$CA:0CA8` | `18 CE` | load room `$00CE` |
| `$CA:0CAA` | `32 00 00` | actor action |
| `$CA:0CAD` | `08` | wait for actions |
| `$CA:0CAE` | `34 00 8B` | repeated/loop action |
| `$CA:0CB1` | `08` | wait for actions |
| `$CA:0CB2` | `50` | `TEXT_OPEN` |
| `$CA:0CB3-$0CFD` | text part 3 | source text carrier |
| `$CA:0CFE` | `28 40` | timed wait |
| `$CA:0D00` | `51` | `TEXT_CLOSE` |
| `$CA:0D01` | `18 CD` | load room `$00CD` |
| `$CA:0D03` | `32 00 80` | actor action |
| `$CA:0D06` | `08` | wait for actions |
| `$CA:0D07` | `34 00 8B` | repeated/loop action |
| `$CA:0D0A` | `08` | wait for actions |
| `$CA:0D0B` | `50` | `TEXT_OPEN` |
| `$CA:0D0C-$0D4D` | text part 4 | source text carrier |
| `$CA:0D4E` | `28 38` | timed wait |
| `$CA:0D50` | `51` | `TEXT_CLOSE` |
| `$CA:0D51` | `18 CC` | load room `$00CC` |
| `$CA:0D53` | `32 00 40` | actor action |
| `$CA:0D56` | `08` | wait for actions |
| `$CA:0D57` | `34 00 8B` | repeated/loop action |
| `$CA:0D5A` | `08` | wait for actions |
| `$CA:0D5B` | `50` | `TEXT_OPEN` |
| `$CA:0D5C-$0DA3` | text part 5 | source text carrier |
| `$CA:0DA4` | `28 30` | timed wait |
| `$CA:0DA6` | `52` | `TEXT_CLEAR` |
| `$CA:0DA7` | `34 00 80` | repeated/loop action change |
| `$CA:0DAA` | `08` | wait for actions |
| `$CA:0DAB-$0DF5` | text part 6 | source text carrier |
| `$CA:0DF6` | `2D 06 FF FF` | start palette-to-white effect |
| `$CA:0DFA` | `28 30` | timed wait while effect progresses |
| `$CA:0DFC` | `52` | `TEXT_CLEAR` |
| `$CA:0DFD` | `27 88` | CALL event `$0788` |
| `$CA:0DFF-$0E1E` | text part 7 | source text carrier |
| `$CA:0E1F` | `28 10` | timed wait |
| `$CA:0E21-$0E37` | text part 8 | source text carrier |
| `$CA:0E38` | `28 30` | timed wait |
| `$CA:0E3A` | `51` | `TEXT_CLOSE` |
| `$CA:0E3B` | `1D 7F` | transition into the stock Mode-7/flyover path |
| `$CA:0E3D` | `18 00` | load room `$0000` / waterfall entry environment |
| `$CA:0E3F` | `2A F8` | decrement low nibble of `$CFF8` |
| `$CA:0E41` | `11 06` | JUMP event `$0106` |
| `$CA:0E43` | `00` | physical end marker (normally unreachable after JUMP) |

The French rebuild preserves the command skeleton while replacing / repaginating
text and extending the payload to the validated `$0E8B` endpoint.

## 5. Intro-specific sub-events

### `$0790`

Called by `$27 90` near the start of `$0400`:

```text
40 02 1E 0F 88
02
00
```

This is a sound command followed by `RETURN` and a physical terminator.

### `$0788`

Called by `$27 88` late in `$0400`:

```text
40 F2 00 00 00
02
00
```

Again, sound-only plus `RETURN`.

The `$20-$27` family is a genuine CALL mechanism: `$C1:EBF2` saves the return
pointer in `$D6-$D8` before resolving the called event. Opcode `$02` at
`$C1:E9EC` restores `$D1-$D3` from `$D6-$D8`.

## 6. Important command behavior

### 6.1 `$04` / `$05` — party invisibility/transparency toggle

Both opcodes use `$C1:EA26`. The handler XORs bit `$80` in:

```text
$E00E
$E20E
$E40E
```

then advances the event pointer. Public reverse-engineering names both commands
**Invisibility Toggle** and identifies `$E00E` as the character transparency
field; the clean-ROM write itself independently proves the shared bit-toggle
behavior.

`$0400` starts with `$04`; `$0106` later contains `$05`, using the same handler.
There is an additional important reset boundary: room initialization code around
`$C1:DD50` tests `$010E`, and when the loaded room is `$0000` it writes exactly
`$80` to `$E00E/$E20E/$E40E`. Therefore the stock `18 00` transition establishes
a known hidden/transparency state before `$0106`; the later `$05` toggles from
that known state. A direct-waterfall skip that keeps `18 00` does not have to
preserve an arbitrary pre-skip value of those three bit-7 flags.

### 6.2 `$29 F8` / `$2A F8` and `$CFF8`

For non-zero argument `$xx`, `$29 xx` increments the low nibble of `$CFxx`
with saturation at `$0F`. `$2A xx` decrements that low nibble with a floor at
zero while preserving the high nibble.

Therefore `$0400` explicitly brackets the intro with:

```text
29 F8   ; increment low nibble $CFF8
...
2A F8   ; decrement low nibble $CFF8
```

The C0 text engine directly reads `$CFF8` at multiple locations including
`$C0:0658`, `$C0:0676`, `$C0:07E0` and `$C0:0943`. The branches are not merely
cosmetic checks:

- at `$C0:0658/$0676`, C0 starts with `X=$0118`; when `$CFF8 != 0` it replaces
  that with `X=$0000` before calling `$C0:1BC0`, which updates the current
  `$7E:9Cxx` window/tilemap cell;
- at `$C0:07E0`, non-zero `$CFF8` takes a dedicated short path that writes
  `$A15E=$04` and updates per-window state instead of entering the ordinary
  row-processing path;
- at `$C0:0943`, non-zero `$CFF8` again selects a dedicated state update using
  the current window index rather than the ordinary table-driven branch.

So `$CFF8 != 0` is a real text-engine mode selector used throughout the intro,
not just a counter checked by the event script. The precise human-readable name
of every sub-path is intentionally left unspecified, but its balancing
increment/decrement must be preserved by any skip path.

### 6.3 Room family `$18-$1B`

`$18 xx` at `$C1:EB07` transforms the command into an internal room identifier
and branches into the shared resolver around `$C1:E77B`.

For room transitions, the resolver uses the room descriptor table beginning at
`$C8:3000`, writes the selected room to `$010E`, updates transition parameters
including `$DC/$DE/$DF`, and sets `$FF = $40` to hand execution to the room
transition machinery.

The intro-specific rooms `$CC-$CF` occur only in stock event `$0400` among the
2048 parsed stock events. Their descriptors are:

| Room | Descriptor bytes |
| ---: | --- |
| `$CC` | `$C8:3330 = B3 10 20 80` |
| `$CD` | `$C8:3334 = B2 10 10 80` |
| `$CE` | `$C8:3338 = B1 24 38 80` |
| `$CF` | `$C8:333C = B0 40 60 80` |
| `$00` | `$C8:3000 = 00 13 11 E0` |

This is not a lightweight background swap: it is a full room-transition path.

### 6.4 Room reinitialization and direct-page cleanup

The normal room setup path reaches `$C0:B03F`, which calls `$C0:BC9B`.
`$C0:BC9B` contains a 16-bit clear loop:

```asm
LDX #$00CE
LDA #$0000
.loop:
    STA $00,X
    DEX
    DEX
    BNE .loop
```

Because `STA` is 16-bit, this clears direct-page bytes `$02-$CF` while leaving
`$00-$01` and the event-engine state beginning at `$D0` intact.

This is a key architectural property: a room change performs a broad transient
state reset but deliberately preserves the event interpreter pointer/state.

### 6.5 `$2D 06 FF FF` palette effect

At `$C1:ED35`, subcommand `$06` calls `$C2:C806`, then configures the palette
effect state including:

```text
$2A   = $60
$010C = $FFFF
$010A = $0000
```

The actual effect progresses later through the frame loop (including code at
`$C2:C820`); the event opcode itself does not wait for completion. The following
`WAIT` in `$0400` provides time for the visual effect to progress.

### 6.6 `$1D 7F` and the Mode-7/flyover path

`$1D` uses `$C1:EB2F` and then the same shared transition resolver used by other
high-level event destinations. For parameter `$7F`, the handler derives the
internal destination `$0D3F` and configures transition flags.

The shared resolver reaches `$C0:BC01`, whose transition arm is short and
explicit:

```text
JSR $8B09
SEP #$20
LDA #$81
STA $FF
RTL
```

So this route deliberately arms the special transition state with `$FF=$81`.
The normal frame machinery later reaches `$C0:B5C1`; once the relevant PPU/NMI
condition in `$E2` is clear, that routine derives `$FE=$80` from the low bit of
the shifted `$FF`, clears `$FF`, writes `$F8=$44`, and jumps to `$C0:8038`.
`$C0:8038` resets the stack to `$01FF`, reconfigures PPU/timing state and enters
a distinct main loop used by the stock Mode-7/flyover sequence.

This path also performs a broad direct-page reset (for example through
`$C0:82C4`, again clearing `$02-$CF`) while preserving event state above that
range. The important distinction is therefore explicit in RAM: `$FF=$81` is
not just a visual-effect flag; it is the hand-off that takes the normal room
loop into the separate special-mode loop.

Runtime behavior of `$1D 7F` as the world-map flyover is already established by
existing project tests/documentation. The static analysis adds the important
fact that it is a **full engine-mode transition**, not just a visual animation
opcode.

The fixed route can now be resolved exactly. `$1D 7F` advances `$D1` past its
two command bytes *before* entering the shared destination resolver, so the live
event pointer already targets the following `18 00`. Parameter `$7F` is reduced
to internal destination `$0D3F`; its four-byte entry is:

```text
C6:7D7C = 70 F0 94 AF
```

The resolver interprets those bytes as:

```text
$FA   = $0700
$FC   = $0F00
$0110 = $AF94
```

The special-flight initializer at `$C0:8EA0` then expands `$0110` into target
coordinate words `$0940` and `$0AF0`, computes wrapped signed deltas from
`$FA/$FC`, stores half-deltas in `$84/$88`, clears `$86/$8A`, and arms
`$8E = $01FF`. Axis names are intentionally not guessed here; the numeric
coordinate path is static-proven.

The natural fixed-flight completion contract is also explicit. At `$C0:8D08`,
the special engine executes the equivalent of:

```text
REP #$20
A = $8E
A--
$8E = A
SEP #$20
if A != 0: continue flight
$F2 = $80
JMP $824E
```

Thus the ordinary route reaches `$C0:824E` with **both** the route coordinates
at their resolved destination and `$F2=$80`. This matters for an early skip:
`$C0:824E` first calls `$C0:81ED`, which derives normal-map state from the
coarse bytes of `$FA/$FC`. Jumping to `$824E` from an arbitrary mid-flight
coordinate would therefore not be equivalent to natural completion. A safe
early completion should normalize `$FA=$0940`, `$FC=$0AF0` and `$F2=$80`
before using the stock teardown.

The special engine does not lose the event context: its broad reset stops at
`$CF`, preserving `$D0+`, and the event pointer had already advanced to
`18 00`. Exit code in the Mode-7 path eventually jumps through `$C0:824E` back
to the normal room loop `$C0:B03F`, where C1 can resume the preserved event at
that next command.

### 6.7 `$18 00` after the flyover

The stock script later executes `$18 00`, returning through the normal room
loading machinery. That normal room path performs its own `$02-$CF` reset via
`$C0:BC9B`.

Therefore the stock sequence contains two broad transition/reset boundaries:

```text
1D 7F
  -> special Mode-7 transition/reset
  -> flyover engine mode
18 00
  -> normal room transition/reset
  -> waterfall environment
```

This matters for `intro_skip`: omitting `$1D 7F` does **not** omit the final
normal room-reset boundary, because `$18 00` still performs one.

### 6.8 Actor selector and `$31/$32/$34` action contracts

The action-family handlers share a consistent actor selector. For the first
argument after the opcode:

- `$00`: use `$D4`, the current event actor structure base;
- bit 7 set: use the alternate actor base in `$3A`;
- positive `$01+`: `(value - 1) * $0200`, so `$01 -> $E000`, `$02 -> $E200`,
  `$03 -> $E400`, `$04 -> $E600`, etc.

The structures are therefore spaced by `$0200` bytes. The exact narrative
identity of `$D4` during each intro tableau is still a runtime question, but the
selector mechanics are static-proven.

#### `$32 actor, dir/count` — Walk / directional action

Handler `$C1:EEEA` advances the event pointer by three bytes and programs the
selected actor. Public nomenclature calls this command **Walk**; the upper two
bits of the second argument select direction. The clean-ROM handler establishes
the following lower-level contract:

- low 6 bits -> `$E00A,X` countdown (zero is normalized to `1`);
- `$E067,X = 0`;
- `$E042,X = 1` while the action is pending;
- the upper 2 bits select `$E010,X` direction/state and choose which of
  `$E006,X/$E007,X` receives a movement component;
- when low 6 bits are zero, an internal mask is zero, so **both movement
  components are written as zero** even though `$E00A` becomes `1`.

The normal actor update around `$C0:EB85` decrements `$E00A,X`; when the counter
reaches zero it clears the associated action/movement fields including
`$E011,X`, `$E042,X`, `$E006,X`, `$E007,X` and `$E008,X`. This is the field that
state `$85` (`COMPLETE_ACTIONS`) later observes.

That makes the four stock intro commands especially clear:

```text
32 00 C0
32 00 00
32 00 80
32 00 40
```

All four have a zero low-6-bit count. They therefore perform a one-update
**orientation/direction setup with zero movement components**, cycling through
the four directional encodings. The following `08` is a genuine synchronization
barrier until the actor update clears `$E042`.

#### `$31 actor, action` — Action

`$31` enters shared helper `$C1:EEAF`, which first calls `$C1:CA6C` to clear
prior movement/action state and then writes:

```text
$E01C,X = $40
$E011,X = action id
$E030,X = $FF
$E042,X = $01
```

This is a pending finite action contract: `$E042` begins non-zero and therefore
can block `COMPLETE_ACTIONS`.

#### `$34 actor, action` — Loop Action

`$34` deliberately reuses the same helper, then changes the final contract:

```text
$E01C,X = $30
$E042,X = $00
```

Thus `Loop Action` is **not** equivalent to `$31 Action`; it schedules the action
ID but explicitly marks it non-blocking to the event barrier. The stock intro
uses `$34 00 8B` after each orientation setup and later `$34 00 80`. The exact
visual meaning of action IDs `$8B/$80` still needs a runtime sprite/animation
trace, but their event synchronization semantics are now static-proven.

The actor update around `$C0:F925` has a dedicated `$E01C == $30` path while an
event is active (`$D0 != 0`), which explains how the loop-action state can
persist without setting `$E042`.

### 6.9 `COMPLETE_ACTIONS` (`$08`) as an actor barrier

`$08` sets `$D0 = $85` and returns. State `$85` at `$C1:F348` scans actor
structures in `$0200`-byte steps. An actor is ignored if inactive (`$E000,X ==
0`) or negative/disabled; any relevant actor with `$E042,X != 0` keeps the event
suspended. When no blocker remains, state `$85` restores normal state `$D0=1`
and immediately resumes event decoding.

This makes `$E042` an exact **event-action pending/barrier field** for the parts
of the actor system used by these commands.

### 6.10 `GET_READY` (`$06`)

Handler `$C1:EA43` sets bit `$80` in `$F1` and calls `$C2:B053`. The helper
scans the three party actor structures `$E400`, `$E200`, `$E000`. If an active,
non-negative actor still has `$E060,X != 0`, it returns carry set and the event
retries the same opcode. Once all three are ready it clears the party movement
words `$E006/$E206/$E406`, `$E008/$E208/$E408`, clears
`$E01D/$E21D/$E41D`, and returns carry clear so the event advances.

`$0106` uses this immediately before its first `TEXT_OPEN`, so the waterfall
continuation contains its own synchronization/normalization barrier after room
`$00` has loaded. This is another reason the stock `18 00 -> 2A F8 -> 11 06`
tail is a much stronger transition boundary than simply jumping into an
arbitrary point of the waterfall scene.

## 7. Waterfall continuation `$0106`

The stock end of `$0400` jumps to event `$0106` with `$11 06`.

Its opening structure is:

```text
27 3D          CALL $073D
40 01 1C 4A 2F PLAY_SOUND
27 8D          CALL $078D
06             GET_READY
50             TEXT_OPEN
32 00 03       actor action
32 04 C8       actor action
08             COMPLETE_ACTIONS
32 00 C0       actor action
57 00          PLAYER_NAME(0)
...            waterfall dialogue / movement sequence
```

`$073D` and `$078D` are sound-only returning sub-events. `$0106` therefore
performs explicit scene preparation before the waterfall dialogue continues; it
is not merely a text continuation that assumes the final intro frame is still
live.

## 8. Failed `intro_skip` experiments — retained as negative evidence

The functional `intro_skip` experiments performed after this static map were **runtime-rejected** and are **not part of the promoted implementation**. They are recorded only so a future reprise does not repeat the same compound experiments.

Rejected variants:

- **safe-global candidate**: attempted a global R-hold timer plus C0/C1/Mode-7 commit points; pressing/holding R produced no visible effect.
- **buffered-input candidate**: changed only the early sampler from raw `$4218` to the game's synchronized `$7E:0042` pad buffer; pressing/holding R still produced no visible effect.
- **immediate-R diagnostic**: removed the timer entirely and latched a skip request on a single observed R frame; pressing R still produced no visible effect.

These failures meant the project could not treat that earlier input chain, request latch, or multi-engine skip-commit design as proven. The subsequent isolated proof ladder in `docs/INTRO_SKIP_RESTART_PLAN.md` was therefore executed to completion; the results are recorded in `docs/INTRO_SKIP_VALIDATION.md`.

The promoted implementation does **not** revive those rejected compound designs. It uses the independently proven `$7E:0042` R source, live parser-Y commit, external normal-loop/WAIT observation, and the validated waterfall tail described below.

### 8.1 Promoted runtime-validated implementation

Final behavior is a continuous R hold for **120 normal-loop ticks**. `$7E:938A-$938B` is a 16-bit state/countdown: `$FFFF` inactive, positive values counting down, `$0000` completed/pending commit. Any release before zero resets to `$FFFF`, so separate short presses never accumulate.

Validated hooks:

- `$C0:012C -> $ED:7488`: active-text initialization / R observation;
- standalone `$C0:16EA -> $CA:FFC8`: live parser-Y commit for a completed hold during text;
- `$C2:C786 -> $ED:7400`: normal-loop observation/decrement and timed-WAIT commit.

In a complete build, `vwf_dialogues` also needs `$C0:16EA` for parser mode 2.
The compatibility merge therefore routes the shared hook through `$ED:73C0`;
mode 2 continues to the unchanged dialogue preflight `$ED:7500`, all other modes
continue to `$CA:FFC8`.

The C1 timed-WAIT handler remains stock. A completed request during `$D0 == $82` only prepares `$D1-$D3 = $CA:FFC0` and `$4F = 1`, then stock C1 expires the WAIT naturally. During live text, the parser helper redirects `Y` to `$FFC0`. The private tail remains `51 18 00 2A F8 11 06 00`.

The implementation is gated to `$CA:0C02-$0E81`; `$CA:0E82 = 1D 7F` begins the separate final Mode-7/flyover path and remains outside the runtime proof.

A later key finding explains two boot-glitching global variants: their growing helper overran a small C7 slot and corrupted shared VWF code at `$C7:43D0-$43E7`. The final extensible helpers live entirely in the owned `$ED:7400-$74FF` reserve instead.

## 9. Intro text rendering / VRAM presentation path

This section matters for any future attempt to display an independent skip
prompt, counter or overlay during the intro. The stock intro does **not** expose
a second independent text layer.

### 9.1 C0 text sub-state pipeline

The C0 text state dispatcher around `$C0:111A` indexes a function table at
`$C0:1A0C` using `$A15D`. The early line-building states include:

1. parser/buffer initialization and decode through `$C0:16B8+`;
2. glyph rasterization at `$C0:1664`;
3. stock intermediate composition through `$C0:15B9`;
4. outline/framing work through `$C0:162C` and neighboring helpers;
5. preparation of a WRAM staging tile buffer and VRAM transfer metadata.

`vwf_intro` replaces only the intro-specific rasterizer behavior at
`$C0:1664`: it clears and repopulates the same stock compact bitmap at
`$7E:9000`, while the downstream stock presentation pipeline remains in use.

### 9.2 Single compact bitmap and staging buffer

The stock compact glyph bitmap begins at `$7E:9000`. The intro VWF renderer
explicitly clears `$0180` bytes there and renders its decoded line into that
same area. Stock routines around `$C0:15B9-$165F` then combine the compact
rows into the tile-oriented staging area beginning at `$7E:9400`, including
outline/framing planes.

This is a shared, destructive line-rendering pipeline. Calling the normal text
rasterizer again to draw a second independent label does not allocate another
text surface; it reuses/clears the same `$9000` source and the same `$9400`
staging path. This explains why experiments that tried to “duplicate” intro
text through the ordinary renderer can replace, append to, or corrupt the live
text instead of behaving like an overlay.

### 9.3 Exact WRAM-to-VRAM DMA path

C0 prepares the VRAM destination and byte count in `$1D06/$1D08`. At
`$C0:1200`, `$A181` is used as a four-step transfer index: it is masked to a
byte, doubled, and used to read one word from each of the destination/size
tables below. After the setup, `$A181` is incremented; when it reaches `4`, C0
resets `$A181` to zero and advances the higher-level text sub-state `$A15D` by
two. The four VRAM transfers are therefore an explicit sequential phase of one
text presentation cycle, not four unrelated destinations.

The table at `$C0:1A36` contains the four destination words:

```text
$65A0, $6700, $6980, $6B00
```

and `$C0:1A3E` contains corresponding transfer sizes:

```text
$00C0, $0100, $0100, $00C0
```

For the ordinary text-transfer path (`$1D05 != $07`), `$C0:1D24-$1D51` programs SNES DMA channel 7 (the `$1D05 == $07` path begins earlier at `$C0:1CE0` and performs a related multi-transfer sequence):

```text
$2116      <- $1D06       ; VRAM word address
$4370      <- $01         ; DMA mode
$4371      <- $18         ; B-bus $2118 (VRAM data)
$4372/4373 <- $9400       ; source address
$4374      <- $7E         ; source bank
$4375/4376 <- $1D08       ; transfer size
$420B      <- $80         ; start DMA channel 7
```

So the visible text graphics are ultimately uploaded from the **single
`$7E:9400` staging surface** to one of the stock text VRAM destinations. A true
independent persistent skip prompt therefore needs its own explicitly managed
visual resource: for example a separate VRAM/tilemap allocation or a sprite/OAM
path, or deliberate composition into a reserved portion of the existing surface.
Simply invoking the normal intro text renderer a second time is not an
independent-layer solution.

## 10. Practical invariants for any future intro modification

Before accepting a new intro-skip architecture, preserve or deliberately replace
all of the following:

1. C1 `$D1-$D3` and C0 `$1D01-$1D03` are two views of the event pointer; know
   which engine currently owns it.
2. Do not redirect blindly while C1 is in an asynchronous state (`$81-$86`)
   without understanding that state's completion contract.
3. `$CFF8` is incremented before the intro text phase and must be balanced before
   ordinary waterfall dialogue proceeds.
4. `WAIT`, palette effects, room changes and actor actions are asynchronous; an
   opcode completing does not imply its visual/gameplay effect has completed.
5. `COMPLETE_ACTIONS` is a real synchronization barrier and should not be
   silently discarded when preserving an intermediate intro phase.
6. `$1D 7F` changes the engine mode; omitting it is materially different from
   skipping a visual-only opcode.
7. `$18 00` performs a full normal room transition and broad transient-state
   cleanup before `$0106`.
8. The stock `$0400` endpoint `$0E44` and translated runtime endpoint `$0E8B`
   are different concepts; do not mix them in gates.
9. Do not choose an input-sampling strategy by assumption. First prove the stock
   controller value at a known execution point, then extend sampling scope only after that
   observation is runtime-validated.
10. Do not assume `$C0:012C` sees the beginning of event `$0400`; it does not on
    the normal stock command skeleton.

## 11. Exact C1 event-command dispatch appendix

For future reverse-engineering, the complete `$00-$50` pointer table has been
read directly from clean ROM at `$C1:E922`:

```text
00 E9C4   01 E9E7   02 E9EC   03 E9FB
04 EA26   05 EA26   06 EA43   07 EA4E
08 EA59   09 EA62   0A EA99   0B EAA3
0C EAAD   0D EAB4   0E EAC1   0F EAD6
10-17 EAF0
18-1B EB07   1C EB19   1D EB2F   1E EB50   1F EB63
20-27 EBF2
28 EC1A   29 EC46   2A EC7F   2B ECA0
2C ED01   2D ED35   2E EDD2   2F EDEF
30 EE8C   31 EEA9   32 EEEA   33 EFB8
34 EFD1   35 EFDF   36 EFE7   37 EFE7
38 EFFA   39 F010   3A F04B   3B F06F
3C F0C6   3D F0E9   3E F0EA   3F F0EB
40 F0EC   41 F10E   42 F140   43 F16F
44 F1CB   45 F1CC   46 F1CD   47 F1CE
48 F1CF   49-4E F1F1   4F F279   50+ F27A
```

This table is useful when a future intro experiment encounters an opcode that
was not part of the current `$0400` path.

## 12. Remaining reverse-engineering work

The static map is now close to the useful limit of ROM-only analysis. The major
unknowns left are observational rather than structural:

- exact **visual** identity of `$D4` and action IDs `$8B/$80` in each intro
  room `$CC-$CF`;
- frame-by-frame confirmation of actor sprite state while `$32/$34/$08` run;
- a runtime trace of the `$1D 7F` fixed-flight loop, including exact visible
  entry/exit frames and the relationship of `$FA/$FC` axes to screen/world axes;
- direct runtime recording of the first and last `$C0:012C` sample for every
  translated intro page/non-text interval;
- the exact tilemap/OAM strategy to use if a future skip UI must remain visible
  independently of the stock `$9000 -> $9400 -> VRAM` text graphics pipeline.

Those points are best answered with a debugger trace (Mesen 2 / bsnes-plus)
rather than by extending blind static disassembly. The control-flow, scheduler,
transition, actor-barrier, text-buffer and DMA architecture needed to design such
a trace is now documented above.

## 13. External nomenclature cross-checks

The address/control-flow claims in this document come from the clean-USA ROM.
Public reverse-engineering was used only to cross-check established human-readable
names such as `Invisibility Toggle`, `Get Ready`, `Complete Actions`, `Walk`,
`Action`, `Loop Action` and the upper-two-bit direction convention of `$32`:

- Super Famicom Development Wiki, “Seiken Densetsu 2 / Secret of Mana”:
  https://wiki.superfamicom.org/seiken-densetsu-2
- Data Crystal, Secret of Mana bank disassemblies (banks C0/C1):
  https://datacrystal.tcrf.net/wiki/Secret_of_Mana_%28SNES%29/Bank_Disassemblies/SoM-Bank00
  https://datacrystal.tcrf.net/wiki/Secret_of_Mana_%28SNES%29/Bank_Disassemblies/SoM-Bank01

For the remaining observational questions, the most useful debugger setup is an
execution trace/breakpoint set on `$C1:E8E0`, `$C1:F27A`, `$C1:F2F5`,
`$C0:012C`, `$C0:B03F`, `$C0:8038`, `$C0:8EA0` and `$C0:1CE0`, plus write
watchpoints on `$D0-$D3`, `$1D01-$1D08`, `$CFF8`, `$FF`, `$2A`, `$E042` for the
active intro actor, and the intro input scratch. That trace should be used to
answer visual/frame-order questions, not to rediscover the static contracts
already established here.
