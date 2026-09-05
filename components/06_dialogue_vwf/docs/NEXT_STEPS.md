# Dialogue VWF handoff / next steps

## Current checkpoint

The `$C9` continuous-cursor renderer, framing/metrics, outline-boundary repair,
shared French charset, and generic interrupted-chunk physical-cell conversion are
runtime-validated.

The interruption solution is data-driven: it measures the actual decoded VWF
chunk and commits `ceil(useful_width / 8)` before stock progression. It contains
no event-address, movement-command, or WAIT-command exceptions. The stock
progression path at `$C0:13A3` is unmodified.

Before changing the component, read:

- `README.md`;
- `docs/ARCHITECTURE.md`;
- `docs/MEMORY_MAP.md`;
- `docs/EVENT_INTERRUPTION_NOTES.md`;
- root `docs/COMPATIBILITY.md`, `docs/MEMORY_MAP.md` and `docs/SHARED_CHARSET.md`.

## Planned work

1. Audit whether dialogue rendering should remain scoped to `$C9` or can safely be
   broadened, including event-bank selection and WRAM scratch lifetime.
2. Once scope is stable, implement English dialogue extraction to an editable
   text format.
3. Implement deterministic reinsertion from that format.
4. Integrate the French dialogue translation later.

Behavior-preserving refactoring is welcome when it has a clear maintenance
benefit, but runtime-validated helpers should not be rewritten merely to save a
few bytes.

## Validation workflow

For each meaningful change:

1. build component 06 independently;
2. rebuild it and compare output for reproducibility;
3. build all components and audit collisions;
4. runtime-test any change that affects rendering or event flow;
5. update component-local documentation and remove temporary diagnostics before
   keeping the checkpoint.

The commercial ROM is a local build input only and must never be committed or
included in release archives.
