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

The known event-interruption spacing issue in the first dialogue remains
**intentionally unresolved**. The clean component contains no diagnostic or
resume experiment for it.

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

`$CD` is deliberately excluded from special handling. Do not add a framing rule,
dedicated metric, self-test or diagnostic text for it unless a future task is
explicitly dedicated to that glyph.

## Documentation

Component-specific technical information lives here rather than in the global
project documents:

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — validated renderer design,
  invariants and rejected implementation patterns;
- [`docs/MEMORY_MAP.md`](docs/MEMORY_MAP.md) — ROM/WRAM hooks and private scratch;
- [`docs/EVENT_INTERRUPTION_NOTES.md`](docs/EVENT_INTERRUPTION_NOTES.md) — complete
  deferred `Wait ... up!` / event-boundary investigation, including the
  **Secret of Mana: Relocalized** v1.7 comparison;
- [`docs/NEXT_STEPS.md`](docs/NEXT_STEPS.md) — clean handoff and planned work.

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
