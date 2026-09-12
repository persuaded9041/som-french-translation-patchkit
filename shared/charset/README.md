# Shared French character set

This directory is the single editable source for project-owned direct glyphs used
by French text components.

`charset.json` defines the canonical character-to-byte mapping and named
profiles. `french_glyphs.png` is an editable 21-glyph 8×12 atlas ordered by code
from `$D3` through `$E7`; `charset.py` validates and converts it for builders.

Profiles:

- `basic_french`: `$D4-$E0` (13 French glyphs), threshold `$E1`.
- `full_french`: `$D4-$E5` (18 French glyphs), threshold `$E6`. This remains
  `french_intro`'s runtime-validated intro profile.
- `dialogue_french`: `$D3-$E7`, with `$D3=♪`, `$D4-$E5` unchanged French
  glyphs, `$E6=°`, `$E7=;`, and an event-dialogue DTE threshold of `$E8`.

The dialogue profile does **not** move the translated intro's DTE boundary.
`vwf_dialogues` / `french_dialogues` install `shared/dialogue/dte.py`, which selects `$E8` only for
real event-engine dialogue while the intro and non-dialogue parser callers retain
`$E6`. In combined `vwf_dialogues` builds it reuses the shared parser mode already selected
by the VWF buffer initializer, avoiding a second fragile context inference in the
middle of decoding. `french_intro` therefore keeps all 25 of its private
`$E6-$FF` DTE pairs.

Current consumers:

- `french_name_entry_extended`: `basic_french` plus the shared disjoint `$D3/$E6/$E7` name glyphs and `shared/name_entry/dte.py` for the relocated Name Entry resource and temporary `PLAYER_NAME` parsing.
- `french_menus`: `basic_french`.
- `french_intro`: `full_french`.
- `vwf_intro`: runtime consumer only; no charset threshold ownership.
- `vwf_dialogues`: `dialogue_french`.
- `french_dialogues`: `dialogue_french` when translated event text is present.

Name Entry still leaves `$E1-$E5` untouched because they are used by graphics
on that screen, but it can safely use `$D3`, `$E6` and `$E7`. Its standalone
router raises the boundary to `$E8` for the relocated bank-`$E4` naming resource
and the temporary PLAYER_NAME source; ordinary event decoding keeps `$E1`. Standalone components may
install identical glyph bytes because each must work independently; the artwork
itself remains centralized here.
