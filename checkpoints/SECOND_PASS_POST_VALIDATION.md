# Second exhaustive dialogue pass — post-cleanup non-regression validation

Date: 2026-09-14

This validation was run **after** the final second-pass checkpoint and after documentation cleanup. It uses the clean unheadered USA ROM only as a local build/test input; no ROM is included in the checkpoint archive.

## Result

**PASS.** All validated corrections are present and no non-target carrier changed.

- starting carriers: **1959**
- final carriers: **1959**
- validated targeted carrier changes: **46/46 present**
- non-target carriers: **1913/1913 byte-for-byte identical**
- carriers added: **0**
- carriers removed: **0**
- unexpected top-level source/semantic metadata changes: **0**

The 46 final carrier differences are exactly the approved lot-by-lot target set:

- lot 1: `C9:0A44`
- lot 2: `C9:27AE`, `C9:2B85`, `C9:3370`, `C9:3590`, `C9:359A`
- lot 3: `C9:3A39`, `C9:41C5`, `C9:46BE`
- lot 4: `C9:5B49`, `C9:5D30`, `C9:5EA9`, `C9:63A6`, `C9:70BF`, `C9:7107`
- lot 5: `C9:8256`, `C9:8846`, `C9:8892`, `C9:9456`, `C9:9737`
- lot 6: `C9:A1B3`, `C9:A30C`
- lot 7: `C9:B941`, `C9:BBEF`, `C9:BE80`, `C9:C158`, `C9:C2A9`, `C9:C390`
- lot 8: **no final carrier delta** (recipe/regression cleanup only)
- lot 9: `C9:DB77`, `C9:DBE4`, `C9:DDF1`, `C9:E32D`, `C9:E548`
- lot 10: `CA:1012`, `CA:11C9`
- lot 11: `CA:4ABC`, `CA:5C2F`, `CA:5D34`, `CA:60C0`, `CA:6676`
- lot 12: `CA:71E3`, `CA:7397`, `CA:73F5`, `CA:889F`, `CA:8E72`, `CA:986B`

## Structural differences

Compared with the exact second-pass starting translation document, structural metadata differs only in the reviewed events:

- command overrides: `$0108`, `$0112`, `$0212`;
- command insertions: `$0022`, `$028A`, `$04B6`, `$04E1`, `$04EA`.

No other top-level semantic/source metadata changed. Choice-option position overrides remain unchanged.

## Fresh canonical validation

A fresh `dialogue-format-mass` regeneration was run after cleanup and reproduced the promoted state. Then:

- dialogue regressions: PASS;
- manual supplements: v3 minimal, **17 carriers = 15 translations + 2 suppressions**;
- redistribution recipes: **302 active carriers**, 0 simulator-filtered, no translated prose stored;
- source hygiene: PASS;
- round-trip: **713 dialogue events / 87,487 bytes**;
- stock script parse: **2048/2048**;
- full simulation: **701 events, 0 errors, 0 warnings, 0 implicit wraps**;
- full simulation with `WWWWWWWWW`: **701 events, 0 errors, 0 warnings, 0 implicit wraps**;
- speaker-label newline audit: **0 findings**;
- rolling-scroll discovery audit: **0 candidates**.

The simulator still reports 3 informational WAIT-$00 third-line review risks globally; these are historical reviewed cases, not errors/warnings and not newly introduced candidates.

## Rebuild reproducibility

`french_dialogues.ips` was force-rebuilt twice from the same clean USA ROM and canonical inputs. The two outputs are byte-identical and also byte-identical to the promoted patch. `all.ips` was recombined twice and likewise matches the promoted patch.

Final SHA-256:

- `translations/dialogues_french.json`: `3e4cacd926e31d6dfe9f9021d1026c4f71dc68ccd88ce4481749e47764d2b7d9`
- `patches/french_dialogues.ips`: `dfc94882e4162052ccd7195839ef7ef7f5a89f1bec51847d905ca6b05ad2de31`
- `patches/all.ips`: `49eb639aa0117d603c5cd6c92ba617f6c853da68cead59c34cf970658e94fd23`

## Conclusion

All second-pass corrections are in place. There is **no carrier-level collateral change outside the validated target set**. The dialogue state is suitable as the clean promoted handoff for the next project phase.
