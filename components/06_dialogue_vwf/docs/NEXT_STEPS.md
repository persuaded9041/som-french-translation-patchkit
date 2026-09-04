# Dialogue VWF handoff / next steps

## Start from the archive actually supplied

Before modifying the component, inspect the current archive rather than relying
on an older conversation. Read at minimum:

- root `README.md`, `docs/COMPATIBILITY.md`, `docs/MEMORY_MAP.md` and
  `docs/SHARED_CHARSET.md`;
- `build.py` and every `component.json`;
- component `05_intro_vwf_french` where comparison is useful;
- all files under `components/06_dialogue_vwf/`.

Never download, redistribute or archive the commercial ROM. A clean unheadered
US ROM is only a local build input.

## Clean checkpoint

The useful charset calibration is complete and runtime-validated. The current
component contains the original dialogue text and no active diagnostic.

Preserve the architecture and address invariants in `ARCHITECTURE.md` and the
allocations in `MEMORY_MAP.md`.

For hard-to-reach glyph tests, the user permits temporary replacement of the
first dialogue bytes at ROM `0x0928CC-0x0928D0`:

```text
B1 81 89 94 80   = "Wait "
```

The following `$32` byte must never be changed, and `Wait ` must always be
restored in a cleaned checkpoint.

## Deferred event-interruption issue

The large stock-position gap before `up!` after the first dialogue is still
unresolved. A substantial investigation, including reverse-engineering of
**Secret of Mana: Relocalized v1.7**, is preserved in
`EVENT_INTERRUPTION_NOTES.md`.

Do not carry any of those probes into normal development. Resume that research
only when explicitly requested, and start with tracing/understanding rather than
another blind state mutation.

## Planned work after the deferred issue

1. Audit broadening the dialogue scope beyond `$C9`, especially event-bank
   selection and WRAM scratch lifetime.
2. Once scope is stable, implement English dialogue extraction to CSV.
3. Implement reinsertion from CSV.
4. Translate dialogue to French later.

Behavior-preserving refactoring is welcome when it has a clear maintenance
benefit, but runtime-validated helpers should not be rewritten merely to save a
few bytes.

## Validation workflow

For each meaningful change:

1. build component 06 independently;
2. rebuild it a second time and compare output for reproducibility;
3. build all six components together and audit collisions;
4. runtime-test the candidate;
5. after validation, remove diagnostics and update component-local docs;
6. deliver only the complete project ZIP and one combined IPS.
