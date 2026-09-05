# French intro VWF

Adds the French new-game introduction with variable-width rendering, private DTE, accents and a private 44-byte parser buffer.

This component is standalone and targets only the clean unheadered US ROM.

## Build

```bash
python3 build_patch.py "Secret of Mana (USA).sfc" -o build/patch.ips
```


## Editable sources

- `assets/`: component-specific intro text/layout inputs used by the builder.
- `../../shared/french_charset/`: canonical French character mapping and 18-glyph atlas.
- `src/intro_vwf.asm`: readable 65C816 representation of the code/data emitted by Python.
- `../../shared/asm65816.py`: shared minimal label/branch emitter used by the Python builder.
- `../../shared/vwf_geometry.py`: shared renderer-neutral 8×12 glyph geometry helpers.
- `../../shared/vwf_metrics.py`: canonical validated framing/advance policy shared with component 06.
- `../../shared/vwf_framing.py`: shared runtime framing-selector source (`../../shared/vwf_framing.asm` is the readable 65816 reference).
- `../../shared/vwf_text_buffer.py`: shared private decoded-text buffer/parser bridge also installed byte-identically by component 06.
- `../../shared/vwf_compositor.py`: shared 8x12 shift/merge/spill primitive installed byte-identically by components 05 and 06.
- `../../shared/vwf_row_renderer.py`: shared stock-font row load + framing + composition helper.
- `../../shared/vwf_outline.py`: shared stock-outline `ROL -> ASL` preparation used by both VWF components.
- `docs/MEMORY_MAP.md`: component ROM/WRAM allocations and hooks.

## VWF sharing status

The 38-character private parser buffer, shared compositor, shared metrics/framing
policy and stock-font runtime path are runtime-validated for the intro and
dialogues. Component 05 no longer carries a private preframed glyph table: it
reads the stock `$D2:DC00` font and uses the shared framing policy.

The shared row renderer is runtime-validated: `shared/vwf_row_renderer.py` installs
a 13-byte helper at `$C7:4560` that performs stock-row load -> shared framing ->
shared compositor. Component 05 calls that helper from its existing 12-row loop
while preserving the validated surrounding renderer layout. Component 06 calls
the same helper only after its caller-gated dialogue scope check. Intro event
gating, DTE, width lookup, layout and WAIT handling remain local.

## Compatibility

This component consumes the shared full French charset profile (`$D4-$E5`) and therefore uses `$E6` as its direct/DTE boundary. GAME SELECT consumes the first 13 characters from the same canonical source.

For cross-component rules, see the package-level `docs/COMPATIBILITY.md`.
