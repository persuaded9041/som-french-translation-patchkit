# Dialogue VWF handoff / next steps

## Current checkpoint

The continuous-cursor renderer, framing/metrics, caller-based stock event scope,
shared French charset and generic interrupted-chunk physical-cell conversion are
runtime-validated.

The core VWF is enabled only for the real event-engine call to the shared
`$C0:1664` renderer (caller `$C0:1150`, stacked return `$1152`) and only for stock
event banks `$C9/$CA`. GAME SELECT remains fixed-width. Component 05 still owns
translated intro event `$0400` because it intercepts that event before component
06's renderer-entry hook.

The interruption solution is data-driven: it measures the actual decoded VWF
chunk and commits `ceil(useful_width / 8)` before stock progression. It contains
no event-address, movement-command or WAIT-command exceptions. The stock
progression path at `$C0:13A3` is unmodified.

Before changing the component, read:

- `README.md`;
- `docs/ARCHITECTURE.md`;
- `docs/MEMORY_MAP.md`;
- `docs/EVENT_INTERRUPTION_NOTES.md`;
- root `docs/COMPATIBILITY.md`, `docs/MEMORY_MAP.md` and `docs/SHARED_CHARSET.md`.

## Planned work

1. Exercise representative `$CA` dialogues beyond the first validated scene,
   especially glyphs that touch 8-pixel boundaries.
2. Audit the post-outline repair, which is still intentionally `$C9`-only, and
   extend it to `$CA` only if a runtime case demonstrates the need and intro
   isolation can be preserved cleanly.
3. Once dialogue-render coverage is considered stable, implement English
   dialogue extraction to an editable text format.
4. Implement deterministic reinsertion from that format, then integrate the
   French dialogue translation.

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
