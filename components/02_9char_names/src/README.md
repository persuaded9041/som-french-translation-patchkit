# 65C816 source map

These files document the machine-code/data changes made by the component in
assembly form. `build_patch.py` remains the canonical executable builder; the
exact emitted byte payloads are centralized in `src/patch_data.py` so builds do
not depend on an external assembler.

The split is intentional:

- `core.asm`: name length, handler hooks and relocated resource pointer.
- `navigation.asm`: four-row Up/Down states and initial cursor position.
- `selection.asm`: selected-character lookup alignment and relocated resource read.
- `layout.asm`: four-row window geometry and layout pointer redirection.

All addresses are for the clean unheadered USA ROM.
