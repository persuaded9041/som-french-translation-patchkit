# Versioning checkpoint — 2026-09-15
> **Superseded note (later 2026-09-15):** this is a historical checkpoint from
> before the startup-credit accent work was completed. The current promoted state
> is documented in `VERSIONING_CHECKPOINT_2026-09-15_OPENING_CREDIT_ACCENT.md`
> and `HANDOFF.md`.


## Promoted state

This checkpoint freezes the state after runtime validation of the final
120-tick `intro_skip` implementation and before reopening work on
`french_opening` startup-credit accents.

The provided archive is authoritative over GitHub for continuation.
The clean unheadered USA ROM is external and is not included.

## Runtime-validated intro-skip surfaces

- `patches/intro_skip.ips` — standalone component: runtime validated;
- `patches/all.ips` — complete aggregate build: runtime validated;
- autonomous `french_intro + vwf_intro + intro_skip 120` test stack: runtime
  validated, SHA-256
  `f9f21e070d898f8ef8f05709a6ce8796dbc70a2b2faf2979e56f6c2517ed5997`.

Rejected autonomous artifact SHA-256
`979921e82ac42e894e7d95e21d2918957b01f8cf3e523ef696eb8f5096b6e030`
is deliberately not included and must not be reused.

## Rebuild hashes

- `patches/intro_skip.ips`:
  `b37d529eb25eae572212d6f7179461785e463dfef9055fd840e00f5754136c16`
- `patches/french_opening.ips`:
  `e041bad47c0707c06140eb26598b1575bbe0c88bdc00889b76d24f21001bea82`
- `patches/all.ips`:
  `253ffde42f6977e714e9d27351089a2fbf0400bf46293ca8ed8967e38aad6b6d`

A targeted rebuild of `intro_skip` + `french_opening` followed by aggregate
recombination reproduced these hashes byte-for-byte. Source-hygiene validation
also passed.

## Cleanup decisions

- no ROM image is stored in the checkpoint;
- no experimental intro-skip step patches/build scripts are stored in the
  repository checkpoint;
- stale generic `docs/RESUME_PROMPT.md` from the old dialogue-review phase was
  removed to avoid conflicting restart instructions;
- `docs/NEXT_CHAT_PROMPT.md` now points only to the opening-credit accent study;
- `docs/OPENING_CREDIT_ACCENT_RESEARCH.md` records the next target and the
  historical fade-synchronization failure.

## Next target

Do not change implementation immediately. First reverse engineer the startup
credit renderer and fade path deeply enough to explain why a previously visible
accent row did not share the credit line's fade.

The desired eventual result is `Traduction : E.CHAUVIRÉ` with ordinary `E` on
the credit row, acute accent on the row above, restored opening-font `Z`, and
frame-perfect shared fade-in/fade-out.
