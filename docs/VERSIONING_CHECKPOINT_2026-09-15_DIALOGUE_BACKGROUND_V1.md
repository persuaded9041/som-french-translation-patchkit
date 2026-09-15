# Versioning checkpoint — `dialogue_background` v1 — 2026-09-15

## Promotion

The runtime-proven Stage-11 dialogue transparency candidate is promoted to the
semantic, unnumbered component:

- `components/dialogue_background/`
- standalone patch: `patches/dialogue_background.ips`
- short name: `dialogue-background`

The promoted component is **functionally byte-identical** to the runtime-tested
Stage-11 IPS. No dialogue text, segmentation, Android mapping, opening,
`intro_skip`, or VWF behavior is intentionally changed by this promotion.

## Runtime validation inherited from Stage 11

Validated on the clean unheadered USA ROM:

- one ordinary animated dialogue frame;
- stock opening/closing geometry tracking;
- inn reservation flow with the ordinary dialogue frame plus the asynchronous
  type-2 GP frame;
- sequence `ordinary opens -> GP opens -> ordinary closes -> GP closes`;
- both frames keep independent semi-transparent backgrounds while coexisting.

The successful state model is documented in
`docs/DIALOGUE_TRANSPARENCY_RESEARCH.md`: `$A165-$A168` are global live animation
bounds, so geometry ownership is tracked explicitly and is **not** inferred
from restored `$A162` context.

## Build/integration status

The manifest sets:

```json
"aggregate_enabled": false
```

This keeps `dialogue_background` a normal targeted/rebuildable component while
excluding it from `all` / `--combine` until integration is runtime-proven.

Known blockers before aggregate promotion:

- temporary WRAM `$7E:93D0-$93F1` overlaps `vwf_dialogues` continuation state at
  `$7E:93D0-$93DF`;
- HDMA channel 6 coexistence with game effects is not yet proven;
- pre-existing color-math/window state is not yet composed/restored generally.

The v1 allocations are intentionally **not moved during promotion**, because the
objective is to preserve the exact runtime-validated candidate.

## Reproducibility checks

- direct component builder and root targeted builder produce the same IPS;
- promoted `dialogue_background.ips` is byte-identical to the validated Stage-11 IPS;
- SHA-256: `32ad0eb245a8f12fdf5d00987ee21bd7f9ec06851b59c2622f3d4c64a0883253`;
- aggregate `all.ips` remains byte-identical when recombined because
  `dialogue_background` is aggregate-disabled.

The old staged experimental source directory is removed after promotion;
historical reasoning is retained in `docs/DIALOGUE_TRANSPARENCY_RESEARCH.md`.
