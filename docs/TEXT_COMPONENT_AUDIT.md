# Component text-source audit

This audit records which patch components own user-visible text and verifies that
translation prose has a single source path: clean-USA extraction under `assets/`
and sparse language overrides under `translations/`.

It was performed after the repository-wide ROM text inventory and the migration
of `name_entry_extended`, `french_menus`, `french_opening`, `french_intro`, and `french_dialogues` to the root JSON model.

## Result by component

| Component | User-visible text owned by the component? | Canonical text path |
| --- | --- | --- |
| `mana_tree_original` | No | none |
| `name_entry_extended` | Yes | `assets/interface_text.json` + `translations/interface_text_french.json` |
| `french_menus` | Yes | `assets/interface_text.json`, `assets/menu_text.json` + matching French JSONs |
| `french_opening` | Yes | `assets/opening_text.json` + `translations/opening_text_french.json` |
| `french_intro` | Yes | `assets/intro_event.json` + `translations/intro_event_french.json` |
| `vwf_intro` | No | runtime VWF only |
| `vwf_dialogues` | No script text | none; renderer/charset only |
| `intro_skip` | No | none; event-command-only private script |
| `french_dialogues` | Yes | `assets/dialogues.json` + `translations/dialogues_french.json` |

## Runtime/non-prose components

### Mana Tree restoration

`mana_tree_original` owns a graphical/compressed Mana Tree resource, not a text
resource. `components/mana_tree_original/assets/mana_tree_jp.bin` is therefore
intentionally component-local and is not a legacy translation BIN. The builder
never encodes or writes user-visible prose.

### Intro VWF

`vwf_intro` is now a renderer/runtime component only. It owns the intro VWF
window, private parser bridge, metrics/framing/compositor path and WAIT cursor
repair, but loads no root text asset or translation JSON.

### Dialogue VWF

`vwf_dialogues` is a renderer/runtime component. It installs the dialogue VWF,
framing/metrics, shared French glyph support, parser preflight, interruption
handling and outline repair. It does not own event-script text and does not load
any translation JSON. Dialogue strings are owned by `french_dialogues` through
`assets/dialogues.json` / `translations/dialogues_french.json`.

The French charset constants imported by `vwf_dialogues` describe glyph codes and
artwork, not translated prose, so they correctly remain in `shared/french_charset/`.

### Intro skip

`intro_skip` adds a private event script at `$CA:FFC0`, but that script contains
only event commands:

```text
51 18 00 2A F8 11 06 00
```

It contains no text opcode or string payload, so there is nothing to extract or
translate. The component therefore remains independent from the root text JSONs.

## Remaining component-local editable assets

The post-migration audit found no component-local CSV translation source and no
translated prose BIN. The remaining component-local editable data is deliberate:

- `components/mana_tree_original/assets/mana_tree_jp.bin`: graphics/resource data;
- `components/name_entry_extended/assets/naming_characters.txt`: editable naming-screen
  character repertoire/layout, not prose translation;
- `components/french_opening/assets/opening_font.png`: title/opening font artwork;
- `components/french_intro/assets/text/intro_layout.json`: French intro page
  layout metadata (word counts/page structure), not source or translated prose;
- `src/*.asm`: readable references for generated/runtime patch code.

`build_patch.py` remains canonical when a readable ASM mirrors generated code.

## Legacy-format check

`tools/check_text_source_hygiene.py` enforces the repository-level part of this
audit. It rejects component CSV files, known retired CSV/BIN text filenames and
legacy builder references. It also verifies that `mana_tree_original` / `vwf_intro` / `vwf_dialogues` / `intro_skip` have not
accidentally gained dependencies on root translation JSONs.

Run it with:

```bash
python3 tools/check_text_source_hygiene.py
```

This is complementary to `tools/check_text_roundtrip.py`: the round-trip checker
validates ROM extraction/IDs/translation bindings, while the hygiene checker
validates that components do not reintroduce parallel text-source formats.
