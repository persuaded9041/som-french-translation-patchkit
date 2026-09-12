# Shared library

`shared/` is the internal Python/ASM library used by component builders and repository tools. It contains reusable implementation only: no component owns code from another component and generated reports must not become shared inputs.

## Layout

- `core/` — low-level ROM/IPS and 65C816-emission primitives. This layer must stay independent of higher-level project domains.
- `build/` — component discovery, manifest validation and aggregate compatibility/merge rules.
- `charset/` — canonical French direct-glyph definition and artwork, with import-time schema/profile validation.
- `text/` — generic stock-text encoding, extracted text-resource formats and sparse translation-document binding.
- `dialogue/` — event/dialogue codec, structural translated-event rules, Android-FR formatting helpers, simulator, relocation, Japanese extraction and dialogue DTE routing.
- `vwf/` — shared VWF geometry, metrics and runtime helpers. Readable ASM mirrors live beside the Python modules they document.
- `name_entry/` — Name Entry-specific shared runtime helpers.

## Dependency direction

Prefer dependencies in this direction:

`core` -> domain packages (`text`, `dialogue`, `vwf`, `name_entry`, `charset`) -> `build` / component builders / tools.

Domain packages may share narrowly scoped helpers where required (for example dialogue code uses stock text and VWF metrics), but `core/` must stay independent of them. `build/compatibility.py` is intentionally outside `core/` because aggregate merge rules know about domain-specific layouts.

Dialogue-specific structural translation metadata belongs in `dialogue/structure.py`, not in the generic `text/translation_json.py` binder. Likewise, consumers outside a module should import public helper names rather than underscore-prefixed implementation details.

## Source policy

- Python modules are executable sources of generated helper bytes.
- `.asm` files under `dialogue/` and `vwf/` are readable mirrors/references unless a component explicitly documents otherwise; they are not parallel build inputs.
- `charset/charset.json` and `charset/french_glyphs.png` are canonical editable data.
- Do not add generated JSON/CSV/HTML reports here.
- Shared runtime modules should validate their reserved-address bounds even when the clean base ROM has no bytes in the expanded-bank region yet.

When moving or adding a helper, update consumers to import from its domain package rather than re-exporting compatibility aliases at the `shared` root. Keeping old aliases would recreate the flat namespace this layout is intended to remove.

## Round 85.33 folder audit

- `core/`: no structural change required; it remains domain-independent.
- `build/`: component manifests now validate names, build order, dependency lists, override ranges/reasons and router/profile field types before discovery succeeds.
- `charset/`: validates duplicate glyphs/codes, ordering, `first_code`, profiles and thresholds; atlas lookup is indexed once and PNG access is context-managed.
- `text/`: remains split by real ROM format; dialogue-only structural translation rules moved out to `dialogue/structure.py`. Duplicate-ID validation in the generic translation binder is linear-time.
- `dialogue/`: command-length decoding is centralized in `codec.command_length()` for the canonical parser, Japanese extractor and simulator. Helpers used by the external formatter now have public names rather than `_private` imports.
- `name_entry/`: runtime helper remains appropriately isolated; only stale component-number terminology was removed.
- `vwf/`: framing selectors now use the common `MiniAssembler` instead of a private branch-fixup mini-DSL. `renderer_runtime.py` is now the executable source of the renderer helpers shared by `vwf_dialogues` and `vwf_ui`, and validates every shared ED-bank payload against the next reserved allocation.
