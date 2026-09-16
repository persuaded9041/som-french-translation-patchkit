# Versioning checkpoint — 2026-09-16 — resource-translation handoff

This checkpoint freezes the runtime-validated UI/shop baseline before the next resource-translation pass.

## Promoted runtime state

- `Haubert magique` merchandise first-glyph fix: `$AA` renders only the real decoded count.
- Ring `$A8`, Forge `$A7`, D9 Shop `$A9`, merchandise `$AA`: fresh row starts at +1 px.
- MONEY `$AB`: 11-cell frame, 3-px currency separator, and type-2 close seed `$C7:7140=$09` matching the widened left bound.
- `french_shop_text` remains merged into `french_resources`; no standalone shop-text patch exists.
- `PO` remains content-owned by `french_resources`; `vwf_ui` remains presentation-only and standalone-safe.

## Cleanup performed

- removed ignored `build/`, `reports/`, Python bytecode and `__pycache__` artifacts from the versioning tree;
- refreshed `README.md`, `HANDOFF.md`, `NEXT_CHAT_PROMPT.md`, resource/VWF/compatibility/memory-map documentation;
- refreshed readable ASM mirrors so shared VWF installer/identity comments match the current Python-generated runtime;
- extended `tools/text/check_source_hygiene.py` with a localized-prose guard for component Python/ASM.

## Text-source audit

`tools/text/check_source_hygiene.py` passes. No multi-word localized gameplay prose from translation JSON payloads is hard-coded in component Python or executable ASM. Component-local Name Entry character/default-name JSON remains explicit data, not embedded builder prose.

No component builder contains a literal `encode_text("...")`/`encode_text_with_stock_dte("...")` gameplay payload.

## Validation

- all 2048 stock event scripts parse;
- dialogue source round-trip: 713 events / 87,487 bytes;
- 513/513 `$CA` resources and 7,315-byte source blob round-trip;
- shop/forge source: 9 records / 9 references / 212 bytes round-trip;
- global source IDs: 2,918 unique;
- dialogue regression guard: 701/701 completion, 3 validated exclusions, Android identity 1798/1838;
- Android resource mapping reproducible: 475 mapped / 34 excluded / 4 unresolved;
- resource layout audit reproducible: 302 inside stock envelope / 170 geometry review / 3 encoding-blocked;
- fresh full rebuild in a new patch directory reproduces `all.ips`, `vwf_ui.ips`, and `french_resources.ips` byte-for-byte.

## Promoted hashes

- `patches/all.ips`: `47744d9f094882e8b2a8c3916b9a675ecdd122330839ebbaa90e0279843c3bb4`
- `patches/vwf_ui.ips`: `b32ae20b1b3836facafae5f3a32a6a799c12bbcfc7814e5a0b404c491ac0c834`
- `patches/french_resources.ips`: `82908a8e0fd594d50fd9bdb5acc43965baf6b2dadc2079f349ba4f3ab3659d2d`
- `patches/french_dialogues.ips`: `dfc94882e4162052ccd7195839ef7ef7f5a89f1bec51847d905ca6b05ad2de31`
- rebuilt aggregate ROM: `a9e22f7dedffceb23ebc8d8093f14b57520cd35e3110904169a86a7eca76f9ff`
- final SNES checksum: `$C107`

## Next work

Continue only with additional non-dialogue resource translations. `weapon_description` (72 mapped) and `magic_description` (42 mapped) are already available as candidates, but require per-context geometry/runtime review before promotion. See `docs/HANDOFF.md` and `docs/NEXT_CHAT_PROMPT.md`.
