# Shared library

`shared/` is the internal Python/ASM library used by component builders and repository tools. It contains reusable implementation only: no component owns code from another component and generated reports must not become shared inputs.

## Layout

- `core/` — low-level ROM/IPS and 65C816-emission primitives. This layer should not depend on higher-level project domains.
- `build/` — component discovery and aggregate compatibility/merge rules.
- `charset/` — canonical French direct-glyph definition and artwork.
- `text/` — stock text encoding plus extracted text-resource formats and translation-document binding.
- `dialogue/` — event/dialogue codec, Android-FR formatting helpers, simulator, relocation, Japanese extraction and dialogue DTE routing.
- `vwf/` — shared VWF geometry, metrics and runtime helpers. Readable ASM mirrors live beside the Python modules they document.
- `name_entry/` — Name Entry-specific shared runtime helpers.

## Dependency direction

Prefer dependencies in this direction:

`core` -> domain packages (`text`, `dialogue`, `vwf`, `name_entry`, `charset`) -> `build` / component builders / tools.

Domain packages may share narrowly scoped helpers where required (for example dialogue code uses stock text and VWF metrics), but `core/` must stay independent of them. `build/compatibility.py` is intentionally outside `core/` because aggregate merge rules know about domain-specific layouts.

## Source policy

- Python modules are executable sources of generated helper bytes.
- `.asm` files under `dialogue/` and `vwf/` are readable mirrors/references unless a component explicitly documents otherwise; they are not parallel build inputs.
- `charset/charset.json` and `charset/french_glyphs.png` are canonical editable data.
- Do not add generated JSON/CSV/HTML reports here.

When moving or adding a helper, update consumers to import from its domain package rather than re-exporting compatibility aliases at the `shared` root. Keeping old aliases would recreate the flat namespace this layout is intended to remove.
