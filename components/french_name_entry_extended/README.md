# French extended Name Entry overlay

French localization layer for `name_entry_extended`. It keeps the validated
four-row Name Entry behavior while leaving the generic 9-character engine in
the base component.

## Dependency and ownership

This component **requires `name_entry_extended`**. It owns only:

- the four-row `$50/$60/$70/$80` navigation/layout override;
- the extra row `Çàâçéèêëîïôùû♪°;`;
- French Name Entry help from `translations/interface_text_french.json`;
- the French/name-only glyph writes needed by that row;
- the Name Entry / `PLAYER_NAME` DTE router.

The generic component continues to own the 9-character limit, the first three
rows, the relocated `$E4:4000` resource base and the character lookup. No
private WRAM is allocated here.

## Canonical inputs

- `assets/name_entry_extension.json` — extra-row repertoire;
- `translations/interface_text_french.json` — localized help prose;
- `shared/french_charset/` — canonical shared glyph artwork/codes;
- `shared/name_dte.py` — executable Name Entry / `PLAYER_NAME` DTE router;
- `src/patch_data.py` — static four-row navigation/layout payloads.

`src/*.asm` is the readable 65C816/data representation used for maintenance;
it is not a second build-input path.

## Resource overlay

The dependent resource starts at `$E4:40B4`, where the generic English help
begins. It writes the fourth row followed by French help. The localized useful
payload currently reaches `$E4:4188`, beyond the generic resource payload
(currently ending at `$E4:415C`), so composition cannot leave stale English
help behind. `$E4:4000-$41FF` remains reserved for the complete Name Entry
stack.

The builder also zero-fills the rest of that window in its in-memory ROM image.
Because standalone IPS files are authored against clean expanded-ROM zeros,
those trailing zero bytes are naturally omitted from the IPS; they are not a
generated-data dependency.

## DTE routing

The router at `$C0:16F5` sends only the relocated Name Entry resource (bank
`$E4`) and the stock `PLAYER_NAME` scratch source (`$7E:A22F` range) through
the `$E8` direct-glyph boundary. Ordinary event sources keep the component's
base `$E1` threshold. In aggregate builds, `shared/compatibility.py` either
merges that base threshold or lets the full dialogue DTE router supersede this
smaller hook.

## Build

```bash
python3 build.py "Secret of Mana (USA).sfc" name-entry-fr
```

The IPS is authored against the clean USA ROM, like every component patch; the
root builder automatically selects and applies `name_entry_extended` first.
See `docs/MEMORY_MAP.md` for exact addresses.
