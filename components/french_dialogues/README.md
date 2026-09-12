# french_dialogues

`french_dialogues` owns translated **event-script data** and deterministic
reinsertion/relocation. It does not own the VWF runtime; `vwf_dialogues` renders
ordinary event dialogue, while `french_intro` / `vwf_intro` retain ownership of
intro event `$0400`.

## Canonical inputs

The normal standalone build regenerates the French dialogue translation **in
memory**. It does not require `translations/dialogues_french.json` to exist.
Canonical inputs are:

- `assets/dialogues.json` — optional materialized cache of clean-USA source events;
- `sources/android/scrtxt_en.bin` — Android-English identity layer;
- `sources/android/scrtxt_fr.bin` — Android-French localized prose;
- reviewed structural recipe files under `recipes/android/`;
- `translations/dialogues_manual_supplements.json` — only reviewed material that
  genuinely does not derive from Android FR;
- the clean USA ROM — source bytes plus VWF/layout metrics for formatter gating.

`translations/dialogues_french.json` is a **generated review/build artifact**.
The canonical command

```bash
python3 tools/dialogue/import_android.py --only dialogue-format-mass \
  --rom "Secret of Mana (USA).sfc"
```

regenerates it from the inputs above. The component builder calls the same
`make_dialogue_format_mass()` pipeline directly in memory, so deleting the
artifact does not break a normal standalone build.

`--translation <file.json>` remains available on `build_patch.py` only as an
explicit diagnostic/testing override. It is not the default source path.

## Current corpus

The audited Round-85 corpus contains:

- 713 text-bearing stock events in `assets/dialogues.json`;
- 701 accepted playable French events, 0 PARTIEL;
- 1815 accepted semantic source IDs;
- 1947 sparse generated translation entries;
- 3 excluded routing-audited unused/orphan events: `$0269`, `$02DE`, `$0603`;
- independent simulation: 0 errors, 0 warnings, 0 implicit runtime wraps.

Ordinary dialogue lines retain the validated `<= 38` decoded-glyph and
`<= 216 px` contracts. `WAIT != NEWLINE`.

## Reinsertion

Every source event is reparsed from the clean USA ROM. Untranslated text keeps
its exact stock bytes, including stock DTE choices. Translated text is encoded
deterministically with the shared dialogue charset and structural metadata from
the generated translation document.

If a rebuilt event fits its original pointer span, it stays in place and any
unused tail is padded with `END` bytes. If it grows, it is packed
Deterministically into the reserved expanded-ROM pool and redirected through the
shared sparse resolver:

- hook: `$C1:E794-$E799`;
- sparse 2048-entry pointer table: `$E8:0000-$17FF`;
- resolver helper reserve: `$E8:1800-$1FFF` (83 active bytes at `$E8:1800-$1852`);
- relocated event pool: `$E8:2000-$EC:FFFF`.

A zero sparse-table entry falls back to the live stock `$C9/$CA` pointer path.
That preserves the intro pair's `$0400-$040F` pointer ownership. Relocated events
never cross a 64 KiB bank boundary.

The relocation architecture was runtime-validated by forcing unchanged event
`$0107` to `$E8:2000`; the force probe is not part of normal builds.

## Shared text infrastructure

When at least one translated token exists, standalone `french_dialogues`
installs the same shared dialogue text infrastructure used by the other dialogue
components:

- DTE router: `$C7:4570-$45EE`;
- shared dialogue-DTE marker: `$C7:4C85`;
- `dialogue_french` glyph span: `$D2:DFE4-$E0DF` (`$D3-$E7`).

The runtime renderer itself remains owned by `vwf_dialogues`.

## Structural recipes and manual supplements

Reviewed scene redistributions and layout decisions live in prose-free recipe
files under `recipes/android/`. They store identities, Android token references,
SNES carriers and structural/layout operations, never copied French prose.

`translations/dialogues_manual_supplements.json` is the only manual input for
genuine non-Android material or reviewed suppressions. Its v3 schema is intentionally
minimal: translated entries contain only `id` + `text`, while validated deletions
contain only `id` + `suppress: true`. Event/source metadata and policy reasons are
derived from canonical assets and exact allow-lists. Manual supplements never create
Android identity. `$035F/C9:D1B8` remains exactly `Dryade`.

Detailed formatter policy and validation history belong in:

- `docs/DIALOGUE_FORMAT.md`;
- `docs/DIALOGUE_SIMULATOR.md`;
- `docs/JAPANESE_DIALOGUE_EXTRACTION.md`.

## Build and validation

Build the standalone component:

```bash
python3 build.py "Secret of Mana (USA).sfc" french-dialogues
```

Or invoke the component directly:

```bash
python3 components/french_dialogues/build_patch.py \
  "Secret of Mana (USA).sfc" -o /tmp/french_dialogues.ips
```

Useful checks after dialogue-pipeline changes:

```bash
python3 tools/dialogue/check_regressions.py --rom "Secret of Mana (USA).sfc"
python3 tools/dialogue/check_redistribution_recipes.py
python3 tools/dialogue/check_manual_supplements.py
python3 tools/text/check_source_hygiene.py
python3 tools/text/check_roundtrip.py "Secret of Mana (USA).sfc" --scan-all-events
```

Generated dialogue/alignment/report artifacts are absent from a clean checkout by design.
Rebuild the component normally; the IPS
must remain byte-identical.

## Intentional limits

- `$0400` is excluded because `french_intro` owns its translated payload.
- Event `$03FF` uses its validated three-byte stock terminal span.
- Event `$07FF` uses the first following `$CA` resource pointer as its exact upper
  boundary.
- Unknown command layouts fail rather than being guessed.
- Dialogue DTE recompression remains intentionally deferred.
