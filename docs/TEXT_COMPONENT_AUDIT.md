# Component text-source audit

This audit records which patch components own user-visible text and verifies that
translation prose has a single source path: clean-USA extraction under `assets/`
and sparse language overrides under `translations/`.

It was performed after the repository-wide ROM text inventory and the migration
of components 02-05/08 to the root JSON model.

## Result by component

| Component | User-visible text owned by the component? | Canonical text path |
| --- | --- | --- |
| `01_japanese_mana_tree` | No | none |
| `02_9char_names` | Yes | `assets/interface_text.json` + `translations/interface_text_french.json` |
| `03_game_select` | Yes | `assets/interface_text.json`, `assets/menu_text.json` + matching French JSONs |
| `04_french_opening` | Yes | `assets/opening_text.json` + `translations/opening_text_french.json` |
| `05_intro_vwf_french` | Yes | `assets/intro_event.json` + `translations/intro_event_french.json` |
| `06_dialogue_vwf` | No script text | none; renderer/charset only |
| `07_intro_skip` | No | none; event-command-only private script |
| `08_dialogue_text` | Yes | `assets/dialogues.json` + `translations/dialogues_french.json` |

## Components 01, 06 and 07

### 01 - Japanese Mana Tree restoration

Component 01 owns a graphical/compressed Mana Tree resource, not a text
resource. `components/01_japanese_mana_tree/assets/mana_tree_jp.bin` is therefore
intentionally component-local and is not a legacy translation BIN. The builder
never encodes or writes user-visible prose.

### 06 - Dialogue VWF

Component 06 is a renderer/runtime component. It installs the dialogue VWF,
framing/metrics, shared French glyph support, parser preflight, interruption
handling and outline repair. It does not own event-script text and does not load
any translation JSON. Dialogue strings are owned by component 08 through
`assets/dialogues.json` / `translations/dialogues_french.json`.

The French charset constants imported by component 06 describe glyph codes and
artwork, not translated prose, so they correctly remain in `shared/french_charset/`.

### 07 - Intro skip

Component 07 adds a private event script at `$CA:FFC0`, but that script contains
only event commands:

```text
51 18 00 2A F8 11 06 00
```

It contains no text opcode or string payload, so there is nothing to extract or
translate. The component therefore remains independent from the root text JSONs.

## Remaining component-local editable assets

The post-migration audit found no component-local CSV translation source and no
translated prose BIN. The remaining component-local editable data is deliberate:

- `components/01_japanese_mana_tree/assets/mana_tree_jp.bin`: graphics/resource data;
- `components/02_9char_names/assets/naming_characters.txt`: editable naming-screen
  character repertoire/layout, not prose translation;
- `components/04_french_opening/assets/opening_font.png`: title/opening font artwork;
- `components/05_intro_vwf_french/assets/text/intro_layout.json`: French intro page
  layout metadata (word counts/page structure), not source or translated prose;
- `src/*.asm`: readable references for generated/runtime patch code.

`build_patch.py` remains canonical when a readable ASM mirrors generated code.

## Legacy-format check

`tools/check_text_source_hygiene.py` enforces the repository-level part of this
audit. It rejects component CSV files, known retired CSV/BIN text filenames and
legacy builder references. It also verifies that components 01/06/07 have not
accidentally gained dependencies on root translation JSONs.

Run it with:

```bash
python3 tools/check_text_source_hygiene.py
```

This is complementary to `tools/check_text_roundtrip.py`: the round-trip checker
validates ROM extraction/IDs/translation bindings, while the hygiene checker
validates that components do not reintroduce parallel text-source formats.
