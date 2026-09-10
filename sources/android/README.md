# Android text sources

This directory stores original Android text resources used as upstream
translation sources. They are kept separate from clean-USA extraction,
cross-version mappings and generated French data:

```text
sources/android/   original Android resources
assets/            canonical text extracted from the clean USA SNES ROM
mappings/android/  reviewed SNES <-> Android correspondence metadata
translations/      generated/sparse French text bound to SNES position IDs
```

## `scrtxt_en.bin` / `scrtxt_fr.bin`

These are the original Android English/French script-text containers supplied
for the translation project. SHA-256:

```text
scrtxt_en.bin  4d4508560967b6ce4d6cf992f29e84e2775ed4accc74d87c3fd4269044b75ae5
scrtxt_fr.bin  cd837aaf53a7979d0e84910e8cda3bd67427f4a3cbddadc351811378d7e7d696
```

Each file contains:

- a little-endian `entry_count` and string-pool byte size;
- 3500 `(text_id, string_offset)` records;
- a UTF-8, NUL-terminated string pool.

The current files expose the same contiguous ID namespace `1..3500`. Records and
pool offsets are ascending and the strings are packed consecutively. See
`docs/ANDROID_TEXT_ALIGNMENT.md` for the detailed observations about empty slots,
local ordering and the current alignment policy.

The English file is a bridge for matching clean-USA SNES source text to Android
resources. French text is then recovered from the corresponding Android
localization unit. A localization unit can span following IDs that are empty in
English, so the importer must not assume a naïve one-ID/one-string relationship.


## `systxt_en.bin` / `systxt_fr.bin`

The supplied Android system-text pair is also preserved byte-for-byte for future
interface/menu alignment:

```text
systxt_en.bin  3bbbba9f37ed18de891d382939723e5ab0830138475e388a07c456eef46a8809
systxt_fr.bin  4312b8c9a18b4f98b7dc1b297febc33a0e2c31f50212c3df593dd991669c7d42
```

It uses the same header/table/NUL-pool container shape, but a separate contiguous
ID namespace: 1300 entries `100000..101299`. Its contents are predominantly
system/interface vocabulary rather than event dialogue. Since Round 46 the importer consumes it **only through explicit reviewed mappings** for the chest-message family; the generic dialogue search/index remains `scrtxt`-only. In particular, `systxt` 101254 supplies the English identity/template for money chests, while 101255/101256 are used only as French localization-correction evidence for already-proven `scrtxt` item identities because their `systxt_en` records are themselves French. The remaining namespace is retained as upstream material for later `interface_text`, `menu_text` and related alignment work.

## Current supported work

The validated intro mapping remains Android IDs `3445-3452` -> the eight
position-derived IDs in `assets/intro_event.json`:

```bash
python3 tools/import_android_text.py --only intro
python3 tools/import_android_text.py --only intro --check
```

The reviewed dialogue checkpoints and whole-game conservative alignment are also
reproducible:

```bash
python3 tools/import_android_text.py --only dialogue-auto
python3 tools/import_android_text.py --only dialogue-auto --check
```

The whole-game correspondence pass writes only `mappings/android/`. The first
SNES-layout checkpoint is a separate, deliberately narrow operation:

```bash
python3 tools/import_android_text.py --only dialogue-format-pilot \
  --rom "Secret of Mana (USA).sfc"
```

It currently generates only the three translated text tokens of event `$0107`
plus a formatting trace report. That pilot is runtime-validated; broader
generation remains intentionally staged and conservative.

Do not edit the Android binaries as part of SNES translation work. Treat them as
upstream source artifacts. Layout/reflow and reviewed cross-version mapping
belong in the mapping/import layers, not in these files.
