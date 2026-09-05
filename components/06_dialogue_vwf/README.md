# 06 — Dialogue VWF

Development component for proportional rendering of normal in-game event text.

The current checkpoint is deliberately limited to event-text bank `$C9`. It keeps
Secret of Mana's stock character-to-glyph lookup and replaces only the placement
and composition needed for a continuous pixel cursor.

## Current status

Runtime-validated:

- `$001D03 == $C9` development scope;
- stock `$C0:168A-$C0:16B0` glyph lookup / `×12` addressing / `$D2:DC00` reads;
- continuous pixel cursor with no forced 8 px realignment;
- cross-cell merge + spill composition;
- 128-entry advance table at `$ED:7200-$ED:727F`;
- actual glyph advances from 3 through 8 px;
- lowercase, uppercase, punctuation and French direct-glyph framing/metrics;
- post-stock outline-boundary repair;
- standalone installation of the canonical shared French charset `$D4-$E5` with
  direct/DTE threshold `$E6`.

Generic event-interruption handling is also runtime-validated. For any `$C9`
chunk interrupted before a normal line break, the renderer snapshots the
cumulative VWF width exactly when the useful decoded characters end, converts
that width to physical 8 px cells, and commits that cell count through `$A1CE`
before stock progression. No event address, `$32` movement command or `$08` wait
opcode is special-cased.

Runtime validation covers both `" Wait "` = 30 px -> 4 cells -> `up!` and a
dynamic-name `"A:Hey! "` = 44 px -> 6 cells -> `Guys!` boundary, confirming that
the mechanism follows the actual decoded buffer rather than literal script bytes.
See `docs/EVENT_INTERRUPTION_NOTES.md`.

## Charset / metrics checkpoint

Validated lowercase framing:

- `a-h`, `k`, `m-s`, `u-z`: shift left 1 px;
- `i`, `l`: shift left 3 px;
- `j`, `t`: shift left 2 px.

Validated lowercase advances:

- `a-h/k/m-q/s/u-z = 7`;
- `i/l = 3`;
- `j = 4`;
- `r = 6`;
- `t = 5`;
- space = 4.

Other validated glyph groups:

- uppercase `A-H/J-Z = shift 1 / advance 7`, `I = shift 3 / advance 3`;
- `$B5-$BE` are `0-9`; their stock/generic widths are satisfactory and remain
  intentionally unspecialized;
- `. , / '` (`$BF-$C2`): shifts `0/0/0/0`, advances `4/4/7/4`;
- paired quotes `$C3/$C4`: shifts `0/1`, advances `7/7`;
- `:` `$C5`: shift `1`, advance `7`;
- `- % & ?` (`$C6/$C7/$C9/$CA`): shift `0`, advance `8`;
- `! ( )` (`$C8/$CB/$CC`): shifts `2/2/1`, advances `5/5/5`;
- French `$D4-$E3`: shift `1`, advance `7`;
- French `$E4/$E5` (`Œ/œ`): shift `0`, advance `8`.

`$CD` is deliberately excluded from special handling and remains on the generic
conservative path.

## Documentation

Component-specific technical information lives here rather than in the global
project documents:

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — validated renderer design and invariants;
- [`docs/MEMORY_MAP.md`](docs/MEMORY_MAP.md) — ROM/WRAM hooks and private scratch;
- [`docs/EVENT_INTERRUPTION_NOTES.md`](docs/EVENT_INTERRUPTION_NOTES.md) — stock event/text hand-off and the generic interrupted-chunk solution;
- [`docs/NEXT_STEPS.md`](docs/NEXT_STEPS.md) — current handoff and planned work.

Cross-component charset and collision policy remains in the root `docs/` folder.

## Build

From the repository root:

```bash
python3 components/06_dialogue_vwf/build_patch.py "Secret of Mana (USA).sfc" \
  -o build/06_dialogue_vwf.ips
```

Or build it together with every component:

```bash
python3 build.py "Secret of Mana (USA).sfc" all -o build/all.ips
```

The commercial ROM is a local build input only and must never be committed or
included in release archives.
