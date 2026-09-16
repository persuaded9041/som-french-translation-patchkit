# Versioning checkpoint — 2026-09-16 — Shop VWF / PO

Runtime-promoted state before investigating `Haubert magique`.

- Shop merchandise VWF `$AA`: validated.
- Shop D9 response VWF `$A9`: validated, stock parser limit retained.
- Type-2 MONEY VWF `$AB`: validated, 11-cell frame, 3 px unit separator.
- Merchandise price geometry: 164 px resync, 4 px unit separator.
- Currency translation is owned only by `french_resources` through
  `translations/french_resources_reviewed_literals.json`:
  `$C7:7B6A GP -> PO`, `$D0:D894 GP -> PO`.
- `vwf_ui` renderer identity is `$9385=$02`; dialogue is `$01`.
  Shared chunk commit calls `$ED:7990` only for dialogue identity, removing the
  former standalone Sell reset.
- GAME SELECT stock fallback uses the corrected scope branches and is runtime-valid.
- Frozen dialogue corpus unchanged.

Promoted SHA-256:

- `patches/vwf_ui.ips`: `37b840462d39e9653f1c11fe85d5a6db97df17daa75a13c636bff6c88da0c896`
- `patches/french_resources.ips`: `718af6e165e7892c7be69ec809195fc864dd41e2ebbb847dca7949a09d98c8b2`
- `patches/vwf_dialogues.ips`: `dc6f02debf93b2c79a74235a4e889f1b372fe047149d7ba525a0fb7c82ea4d50`
- `patches/french_shop_text.ips`: `b4530dfb6f9c25e7b28229448ef90f435858a351d27de843ea54507cd04b8271`
- `patches/all.ips`: `f4e37892d3946b54493c0c93c2b9d35571dfd51670970e31f0925aaccd52e61e`

Next defect: `$CA:9F8E` / `$09C` `Haubert magique` loses the leftmost `H` in
shop merchandise VWF while other items appear correct. See `docs/HANDOFF.md` and
`docs/NEXT_CHAT_PROMPT.md`.
