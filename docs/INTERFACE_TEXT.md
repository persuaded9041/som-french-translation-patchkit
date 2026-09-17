# Interface text extraction

`assets/interface_text.json` contains stock help/status rows referenced by the
24-bit pointer table at ROM `$0033B5` / SNES `$C0:33B5`. These strings are
neither event scripts nor entries in the 513-resource `$CA` table.

The clean USA table has **nine** consecutive valid HiROM text pointers. The
first five target `$C0`, the next four target `$C7`, and the following three
bytes do not form a valid text pointer. This is the structural end used by the
extractor.

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

## Promoted help rows

The following interface/help rows are now promoted and runtime-validated:

- GAME FILE save help:
  - `$C0:348D` -> `Sauvegarder sur un fichier utilisé efface ses données.`
  - second row -> `Pressez “Attaque” pour sauver, “Retour” pour annuler.`
- Name Entry:
  - `Choisissez un caractère avec la croix directionnelle.`
  - `Appuyez sur B pour valider. Le nom peut faire`
  - `9 lettres maximum. Appuyez sur Start pour continuer.`
  Physical `B`/`Start` are intentional here: this screen is used while creating a
  new game, before the player can remap controls.
- Action Settings fixed-font help:
  - `$C0:3620` -> `Choisissez le type d'action. Validez avec “Attaque”.`
  - `$C0:3654` -> `Jusqu'où charger la jauge ? Validez avec “Attaque”.`

The Action help path remains fixed-font. Its redraw loop is 29 columns / 58
logical 4-px characters. `$C0:368F` (`0 1 2 3 4 5 6 7 8`) remains structural
and byte-identical. Do not reintroduce VWF on this page.

## Reviewed status labels

`translations/interface_text_french.json` contains the ten reviewed
characteristic labels (`Force`, `Agilité`, `Endurance`, `Intelligence`, etc.).
They have been checked against the available 80 px VWF envelope, but are still
**translation-only** until their Status rendering path is promoted.

Every visible row has a globally unique ROM-position `id`. Existing
`french_name_entry_extended` / `french_menus` French rows live in
`translations/interface_text_french.json` and are bound directly by those IDs.

Regenerate only this family with:

```bash
python3 tools/text/extract.py "Secret of Mana (USA).sfc" --only interface
```
