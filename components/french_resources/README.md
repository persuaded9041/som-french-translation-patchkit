# french_resources — French CA resource names

Reinserts the reviewed Android-FR mappings from `translations/text_resources_french.json`
into the canonical SNES `$CA` resource table (`assets/text_resources.json`).

The component owns name-family resources only: magic/spirit/weapon/equipment/item/enemy/location names.
It does **not** own dialogue text or UI VWF rendering. `vwf_ui` may therefore be installed independently.

The resource blob is rebuilt deterministically inside the original stock allocation; no relocation is used.
For standalone correctness on a clean USA ROM, the component installs the same shared French direct-glyph /
DTE routing profile used by the dialogue components.
