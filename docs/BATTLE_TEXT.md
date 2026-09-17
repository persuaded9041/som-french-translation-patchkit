# Battle/status text

`assets/battle_text.json` contains the stock battle/status message pool in bank
`$C0`.

## Clean-USA layout

The engine has an **88-entry 16-bit pointer table** at `$C0:5DBB`. The table
ends exactly where the physical string pool begins at `$C0:5E6B`. The pool runs
to `$C0:6380` and contains **109 null-terminated records / 1302 bytes** including
terminators.

All 88 table pointers resolve to distinct record starts. The remaining **21
records** are addressed directly by battle code. Two of those records,
`$C0:637D={50}` and `$C0:637F={51}`, are the tiny event scripts used to display
the already-built battle banner; they are not prose. The extractor therefore
follows the physical pool rather than only the 88 indexed entries.

Rare embedded control bytes are represented explicitly in the JSON, e.g.
`Cave{2A}in`, `{50}` and `{51}`. `tools/text/check_roundtrip.py` validates both
the 176-byte pointer table and the complete 1302-byte physical pool against the
clean USA ROM.

## French mapping and reviewed surcharge

Production identity/provenance is in
`recipes/android/battle_text_mapping.json`. Android French payload is read from
`sources/android/systxt_fr.bin`; it is not copied into Python/ASM.

`translations/battle_text_reviewed_overrides.json` is the reviewed surcharge
file. It contains:

- two validated SNES fragment adaptations: `C0:6251` (`Lv.` -> `niv.`) and
  `C0:62F3` (`'s magic faded.` -> ` s'est rétabli !` after the stock dynamic
  subject);
- one validated standalone JP-derived adaptation: `C0:62E2` (`Recovery failed!` ->
  `Rétablissement échoué !`);
- eight manually reviewed JP-derived translations for records with no sufficiently solid Android equivalent.


## Production insertion (`french_resources`)

`french_resources` owns the localized **content** of this family. The stock C0
pool is too small for the reviewed Android-FR strings, so the 107 text records
(`$C0:5E6B-$637C`) are deterministically relocated to reserved expanded-ROM
space beginning at **`$EE:6000`**. The current relocated pool, including four
small Android-template prefix strings, is **1573 bytes** and is bounded by the
reserved `$EE:6000-$6FFF` range.

The builder:

- rewrites all 88 table pointers to the new `$EE` offsets;
- changes the battle-copy routine's fixed source bank from `$C0` to `$EE`;
- rewrites every direct `LDX #record` operand used by battle code;
- keeps `$C0:637D/$637F` in place as event scripts;
- uses four tiny helpers in reclaimed old-pool space for Android templates where
  French text must precede a dynamic number/item (`GP inside`, item obtained,
  inventory full, GP total);
- suppresses only the exact stock subject-name append in the elemental weakness
  routine because Android French already supplies the complete `Point faible : …`
  wording.

The current plan has **92 Android-derived mapped records + 11 reviewed SNES/JP
adaptations**, **0 pending manual translations**, **0 pending layout adaptations**
and **6 stock control/empty records**.

## TODO — dormant stock message calls

Do **not** fix these as part of translation work. Keep them as a separate future
runtime-bug task:

- the stock caller for `Recovery failed!` uses `JSL $C0:58AF`, but `$C0:58AF`
  is an `RTL`; the message routine begins at `$C0:58B0`;
- the stock caller for `'s magic faded.` similarly uses `JSL $C0:58B9`, while
  `$C0:58B9` is an `RTL` and the message routine begins at `$C0:58BA`.

The current French project deliberately translates the underlying strings but
**preserves the vanilla calls unchanged**. A future bug-fix pass should first
prove the intended gameplay conditions and non-regression in emulator before
considering `58AF -> 58B0` and `58B9 -> 58BA`.

## Presentation (`vwf_ui`)

`vwf_ui` owns no battle prose. It arms one-shot tag `$AC` only in the two exact
stock banner submit helpers that launch `$C0:637D` and `$C0:637F`.

Those exact invocations use shared parser mode **3** and a 49-byte private span
`$7E:9390-$93C0` (48 visible decoded bytes plus the following control). The
five bytes above the ordinary 44-byte private buffer are borrowed only during
the battle banner; dialogue-choice scratch is mutually exclusive. All other UI
families retain their existing parser behavior.

The renderer keeps the already-decoded battle private buffer, renders only its
true decoded count, and otherwise uses the same isolated UI VWF runtime. This
backend is intentionally narrow: no generic `$C0` event or global battle-mode
switch is introduced.

**Runtime status:** the content relocation, pointer rewrites, provenance and the
exact `$AC` VWF presentation backend are runtime-validated. Both `vwf_ui`
standalone and `french_resources + vwf_ui` were validated in emulator.

### Dynamic subject + suffix fix

The original `$AC` candidate exposed a renderer-continuity bug on messages such
as `IDGET se change en mog !` and `LINA rétrécit !`: only the dynamic subject
was visible. `french_resources` alone rendered the complete sentences, proving
that the relocated French pool and stock dynamic composition were correct.

Comparative tracing showed that the suffix was **not lost by `PLAYER_NAME`**.
The battle message is copied to `$7E:FF69`, `$1D03` is set to `$7E`, and shared
parser mode 3 decodes the complete subject + suffix directly into
`$7E:9390-$93C0`. The first divergence occurred later in the `$AC` renderer:
selector 5 incorrectly required `$1D03 == $C0`, rejected its own private parse,
and fell back to the stock renderer, which reads `$7E:A1A4` instead. The
observed name-only output was therefore stale/partial stock-buffer content, not
a missing French suffix.

The validated fix is deliberately minimal and presentation-only: the exact
battle renderer continuity gate now requires the live WRAM source bank
`$1D03 == $7E` (`$ED:7B83`, immediate byte `$C0 -> $7E`). No battle text,
pointer, relocation or dynamic-composition logic in `french_resources` is
changed.

Two earlier tag-lifetime probes are documented only as rejected history and are
not part of the production baseline: preserving `$AC` while `$1D00 & $08` was
active, and preserving `$AC` across successive battle renderer invocations.
Neither changed runtime behavior.
