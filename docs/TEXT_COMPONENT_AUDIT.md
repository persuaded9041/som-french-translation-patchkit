# Component text-source audit

This audit records which patch components own user-visible text and verifies that
translation prose has a single source path: clean-USA extraction under `assets/`
and sparse language overrides under `translations/`.

The Name Entry split now keeps the generic engine in `name_entry_extended` while
`french_name_entry_extended` alone consumes the French Name Entry translation.

## Result by component

| Component | User-visible text owned by the component? | Canonical text path |
| --- | --- | --- |
| `mana_tree_original` | No | none |
| `name_entry_extended` | USA help only, no translation | clean USA ROM extracted at build time (functional 6→9 adaptation) |
| `french_name_entry_extended` | Yes | `assets/interface_text.json` + `translations/interface_text_french.json` |
| `name_entry_prefill` | Configured USA names, not translation prose | component-local `assets/name_entry_defaults.json` |
| `french_name_entry_prefill` | Configured French names, not translation prose pipeline | component-local `assets/name_entry_defaults_fr.json` |
| `french_menus` | Yes | `assets/interface_text.json`, `assets/menu_text.json` + matching French JSONs |
| `french_opening` | Yes | `assets/opening_text.json` + `translations/opening_text_french.json` |
| `french_intro` | Yes | `assets/intro_event.json` + `translations/intro_event_french.json` |
| `vwf_intro` | No | runtime VWF only |
| `vwf_dialogues` | No script text | none; renderer/charset only |
| `intro_skip` | No | none; event-command-only private script |
| `french_dialogues` | Yes | `assets/dialogues.json` + `translations/dialogues_french.json` |

## Runtime/non-prose components

`mana_tree_original` owns graphical/compressed data, not prose. `vwf_intro` and
`vwf_dialogues` are renderer/runtime components and load no translation JSON.
`intro_skip` owns only event commands. `name_entry_extended` owns functional
Name Entry geometry plus generic character rows; it reads the clean-USA help only
to reproduce the instructions with the functional 9-character limit.
`name_entry_prefill` owns explicit configured USA player-name values.
`french_name_entry_prefill` owns the corresponding explicitly authored French
default values and the small fourth-row token-decoder overlay needed by `Popoï`.
Neither component consults Android or the root prose-translation pipeline.

## Remaining component-local editable assets

- `components/mana_tree_original/assets/mana_tree_jp.bin`: graphics/resource data;
- `components/name_entry_extended/assets/naming_characters.txt`: generic naming-screen character repertoire, not prose translation;
- `components/french_name_entry_extended/assets/name_entry_extension.json`: French extension-row character repertoire, not prose;
- `components/name_entry_prefill/assets/name_entry_defaults.json`: explicit USA default player-name data;
- `components/french_name_entry_prefill/assets/name_entry_defaults_fr.json`: explicit French default player-name data;
- `components/french_opening/assets/opening_font.png`: title/opening font artwork;
- `components/french_intro/assets/text/intro_layout.json`: French intro layout metadata;
- `src/*.asm`: readable references for generated/runtime patch code.

`build_patch.py` remains canonical when a readable ASM mirrors generated code.

## Legacy-format check

`tools/check_text_source_hygiene.py` rejects component CSV files, retired prose
BIN/CSV paths and translation dependencies in components declared to own no
translation. Run it with:

```bash
python3 tools/check_text_source_hygiene.py
```

This complements `tools/check_text_roundtrip.py`, which validates ROM extraction,
IDs and translation bindings.
