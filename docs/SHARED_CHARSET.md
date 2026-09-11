# Shared French charset

`shared/french_charset/` is the canonical editable source for project-owned
direct glyph codes and artwork. The mapping is a patchkit convention, not a
claim about every stock Secret of Mana font slot.

## Canonical direct-glyph assignments

| Code | Character | Use |
|---|---|---|
| `$D3` | ♪ | dialogue profile |
| `$D4` | Ç | shared French |
| `$D5` | à | shared French |
| `$D6` | â | shared French |
| `$D7` | ç | shared French |
| `$D8` | é | shared French |
| `$D9` | è | shared French |
| `$DA` | ê | shared French |
| `$DB` | ë | shared French |
| `$DC` | î | shared French |
| `$DD` | ï | shared French |
| `$DE` | ô | shared French |
| `$DF` | ù | shared French |
| `$E0` | û | shared French |
| `$E1` | À | full/dialogue profiles |
| `$E2` | É | full/dialogue profiles |
| `$E3` | Î | full/dialogue profiles |
| `$E4` | Œ | full/dialogue profiles |
| `$E5` | œ | full/dialogue profiles |
| `$E6` | ° | dialogue profile only |
| `$E7` | ; | dialogue profile only |

The 18 French assignments `$D4-$E5` are unchanged. `♪`, `°` and `;` are drawn
in the same editable PNG. Their dialogue direct-code/DTE routing and compact VWF
spacing are runtime-validated.

## Profiles

### `basic_french`

Direct range `$D4-$E0`; threshold `$E1`. GAME SELECT uses this profile directly.
`french_name_entry_extended` keeps the same ordinary-text threshold and the same `$D4-$E0` French
range, and also installs the disjoint shared glyphs `$D3=♪`, `$E6=°`, `$E7=;`.
It preserves the stock graphics occupying `$E1-$E5` and switches to `$E8` for
the relocated bank-`$E4` Name Entry resource and the temporary `PLAYER_NAME`
source.

### `full_french`

Direct range `$D4-$E5`; threshold `$E6`. `french_intro` owns this exact profile
so the runtime-validated intro compression and 25 private DTE pairs remain
unchanged. `vwf_intro` consumes the resulting direct glyph codes but does not
install the charset or DTE threshold.

### `dialogue_french`

Direct range `$D3-$E7`; event-dialogue threshold `$E8`. Used by `vwf_dialogues`
and 08. The threshold is context-sensitive rather than global:

- translated intro / ordinary non-dialogue parser contexts: `$E6`;
- real event-engine dialogue: `$E8`;
- French extended Name Entry resource in reserved bank `$E4`: `$E8`.

`shared/dialogue_dte.py` owns that routing. It uses the established event-parser
caller discriminator and protects event `$0400`; GAME SELECT remains on the
base `$E6` path. This lets `$E6/$E7` mean `°`/`;` in dialogue while they remain
intro DTE codes during event `$0400`.

## Source files

- `charset.json` - character assignments and profiles.
- `french_glyphs.png` - editable 21-glyph 8×12 atlas, code order `$D3-$E7`.
- `charset.py` - mapping/profile/PNG conversion helpers.
- `../dialogue_dte.py` - context-sensitive dialogue DTE router.
- `../name_dte.py` - Name Entry / PLAYER_NAME router owned by `french_name_entry_extended`.

## Rules

1. Keep `$D4-$E5` assignments stable.
2. Reuse the canonical PNG rather than creating private copies of shared glyphs.
3. Do not force the dialogue `$E8` threshold onto the intro.
4. Add new direct codes only after checking parser context, stock raw-byte usage,
   renderer metrics and component overlap.
5. Keep standalone patches self-sufficient even when this requires identical
   font/router writes.
