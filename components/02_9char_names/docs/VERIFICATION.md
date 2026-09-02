# Verification — 02_9char_names

## Canonical hashes

Runtime-validated IPS SHA-256:

`31cdc4c829130194a54020c87c2d1bb56cc908372d2024aac1aaebb230196f9f`

Generated Name Entry resource SHA-256:

`c80dc4bc038eda52c046bee1cf1026fe32bd5646bc90dd25cf8dab6254a8f96f`

`build_patch.py` reproduces both values from the clean USA ROM and the editable
sources.

## Runtime validation

Validated in game:

- game boots normally;
- 9-character naming still works;
- four rows are visible inside the Name Entry frame;
- cursor starts on uppercase;
- cursor moves across exactly the four rows without overshooting;
- selected character matches the visible cursor row;
- French accent row renders correctly for `$D4-$E0`;
- previous bottom-right graphical corruption is absent;
- French help text renders correctly;
- accented characters can be entered in the player's name;
- accented player names subsequently render correctly when inserted in normal dialogue.

## Regression history captured by the final code

The final constants are deliberately documented because runtime tests showed
that superficially similar offsets have different responsibilities:

- `$A15A = $50/$60/$70/$80` controls four-row navigation.
- `$C7:5019 = $50` controls the opening row only.
- `$C7:50E8 = #$48` aligns character selection with the visually raised grid.
- The neighbouring `$74EA` pointers at `$C7:781C` must remain intact; restoring
  their USA values caused graphical corruption.
- `$E1-$E5` are not overwritten on this screen because doing so corrupts Name
  Entry graphics.
