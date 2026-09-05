# Interface text extraction

`assets/interface_text.json` contains stock help/status rows referenced by the
24-bit pointer table at ROM `$0033B5` / SNES `$C0:33B5`. These strings are
neither event scripts nor entries in the 513-resource `$CA` table.

The previous five-block interpretation was incomplete: the clean USA table has
**nine** consecutive valid HiROM text pointers. The first five target `$C0`, the
next four target `$C7`, and the following three bytes do not form a valid text
pointer. This is the structural end used by the extractor.

| Entry | Target | Group | Rows |
| ---: | --- | --- | ---: |
| 0 | `$C0:33F0` | `game_select.welcome` | 4 |
| 1 | `$C0:348D` | `game_file.save_help` | 2 |
| 2 | `$C0:34F9` | `window_settings.help` | 3 |
| 3 | `$C0:3583` | `name_entry.help` | 3 |
| 4 | `$C0:3620` | `action_settings.help` | 3 |
| 5 | `$C7:784C` | `weapon_skill.help` | 3 |
| 6 | `$C7:78D4` | `magic_skill.help` | 3 |
| 7 | `$C7:795F` | `controller_edit.help` | 4 |
| 8 | `$C7:7A28` | `status.labels` | 2 |

Each block is `$00`-terminated and uses `$7F` as a display-line separator.
Blank rows used only as layout spacing are omitted from the JSON. The stock
Name Entry rows also carry one leading `$80` layout margin; that framing byte is
not part of their extracted source strings.

Every visible row has a globally unique ROM-position `id`. No redundant semantic per-row key is stored. Existing component 02/03 French rows live in `translations/interface_text_french.json` and are bound directly by those IDs.

Regenerate only this family with:

```bash
python3 tools/extract_text.py "Secret of Mana (USA).sfc" --only interface
```
