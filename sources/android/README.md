# Android text sources

This directory stores the original French text resources used as upstream
translation sources. They are kept separate from both clean-USA ROM extraction
and generated translation JSONs:

```text
sources/android/   original Android French resources
assets/            canonical text extracted from the clean USA SNES ROM
translations/      generated/sparse French text bound to SNES position IDs
```

## `scrtxt_fr.bin`

`scrtxt_fr.bin` is the Android French script-text container supplied for the
translation project. Its SHA-256 is:

```text
cd837aaf53a7979d0e84910e8cda3bd67427f4a3cbddadc351811378d7e7d696
```

The file contains 3500 `(text_id, string_offset)` records followed by a UTF-8,
NUL-terminated string pool. The root importer understands this container format.

Only Android IDs 3445-3452 are mapped at present; they generate the eight
component-05 intro translations. Future work can extend the importer to other
Android script IDs without changing the binary reader.

Generate the currently supported translation family with:

```bash
python3 tools/import_android_text.py --only intro
```

Check that the committed JSON is synchronized without rewriting it:

```bash
python3 tools/import_android_text.py --only intro --check
```

Do not edit `scrtxt_fr.bin` as part of SNES translation work. Treat it as an
upstream source artifact. Editorial changes for the SNES project should only be
made deliberately after deciding whether they belong upstream or in the generated
translation/layout layer.
