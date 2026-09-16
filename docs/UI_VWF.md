# UI VWF — `vwf_ui` extension contract

This document is the operational guide for extending `vwf_ui` beyond the runtime-validated
Watts Forge backend. It is intentionally separate from `FORGE_VWF_RESEARCH.md`, which records the
Forge-specific search history and rejected probes.

## Ownership

`vwf_ui` owns **non-dialogue interface VWF rendering and layout fixes**. It must remain
standalone on a clean USA ROM and may depend only on shared helpers/infrastructure. It does not
own French text resources. `french_resources` owns the reviewed French `$CA` name families.
`vwf_dialogues` owns ordinary event dialogue.

The low-level VWF hooks may be shared byte-identically, but ownership decisions must remain
separate. A shared renderer entry is not, by itself, proof that a UI family belongs to `vwf_ui`.

## Accepted Forge reference backend

The Forge row is the reference implementation:

- exact mini-event submit identity: `$00:19D0`;
- one-shot UI tag armed only at that submit, not at the earlier generic `WEAPON_NAME` helper;
- stock parser and stock decoded buffer retained;
- local logical line margin: **+3** while the exact tag is active;
- suffix geometry is decoded at safe logical anchors then compacted at render time so `→...`
  follows the actual VWF width of the current weapon name;
- shared low-level VWF renderer is enabled only for the tagged invocation;
- stock fallbacks explicitly clear `$7E:9385` so GAME SELECT and other fixed-width callers
  cannot inherit stale VWF state.

Runtime validation covers the long French Forge row, 19-character stress names, complete `GP`
suffix, standalone GAME SELECT, and ordinary Watts dialogue. Treat this backend as locked.

## Procedure for a new UI backend

1. **Inventory the visible field.** Record stock text, resource IDs/commands, dynamic suffixes,
   anchors, and the exact screen/action that reaches it.
2. **Find the builder before the renderer.** Prefer the routine that assembles the UI record or
   submits it to the event/menu engine. Do not start from a global renderer hook.
3. **Prove identity with a harmless visual probe.** Change one literal glyph or one resource ID
   only on the suspected path. A successful runtime probe is required before any VWF gate.
4. **Trace builder → submit → decoded row → renderer.** Distinguish CPU DB from event bank and
   do not assume the initial event pointer is still unchanged by renderer time.
5. **Arm a one-shot tag as late as possible but before parser/layout decisions that need it.**
   Exact submit sites are preferred over generic helpers or broad mode flags.
6. **Keep stock parser/buffer by default.** Increase logical capacity locally only when a real
   stock counter is proven to be the limiting factor. Do not route arbitrary UI through the
   dialogue private-38 buffer.
7. **Make geometry VWF-aware at render time.** Fixed absolute anchors often waste logical slots
   or collide with long translated names. Compact or reposition suffixes from measured VWF width.
8. **Consume and clear state.** The tag must be one-shot, and all non-owned/fallback calls must
   clear low-level VWF-active state before replaying stock behavior.
9. **Validate standalone first, aggregate second.** Test `vwf_ui` alone on a clean USA ROM,
   then rebuild/test `all.ips` with `french_resources` and the dialogue components present.

## Mandatory regressions

After each new backend, verify at minimum:

- the new UI family itself, including its longest translated/resource names;
- Watts Forge row remains correct;
- GAME SELECT remains fixed-width and unglitched;
- Watts ordinary dialogue is not captured by `vwf_ui`;
- ordinary `vwf_dialogues` dialogues remain unchanged in the aggregate build;
- resource-name translation from `french_resources` is still present in `all.ips`;
- any menu family sharing the same submit/renderer helpers is spot-checked.

## Second backend: top-level Ring Menu title

The Ring Menu investigation proved that its title banner reaches the same `$00:19D0` submit as
Forge through `C0:6943 -> D0:D397`, but represents a continuous title row rather than the Forge
`name + suffix` layout. Applying Forge's overlapping slot-20..31 compaction to these titles exactly
explained the observed corruption of long French labels.

Production isolation now classifies the exact shared submit by the already-existing Ring subsystem
mode byte: `$1847==0` arms a distinct Ring one-shot tag (`$A8`), `$1847==1/2` arms the shop
merchandise tag (`$AA`), and `$1847==3` arms the Forge tag (`$A7`). Ring titles keep the stock parser/buffer, render their decoded
row unchanged under VWF, and receive exactly +4 logical units: 29 stock fresh-line units +4 = the
33-byte stock buffer, allowing 32 visible characters plus the following control. The private
dialogue parser is not used.

Runtime validation proves the dedicated Ring backend end-to-end: `Caractéristiques des personnages`
and `Choix des fenêtres de dialogue` render completely without the former repeated-glyph corruption,
and the exact +4 boundary restores the final `e` of the 32-character
`Niveaux des armes et de la magie`. The Forge backend remains isolated behind its own tag and
retains its validated suffix compaction. Future UI families must use another narrow identity and
must not broaden mode 0 or 3.

## Third backend: shop merchandise row

Modes `$1847==1/2` use the same `$00:19D0` submit for the buy/sell merchandise
row. The dedicated `$AA` tag keeps the stock parser/decoded buffer and applies
VWF without Forge suffix compaction. Runtime validation proves the item name
path and the right-aligned price path in the aggregate build.

Currency content is **not** owned by `vwf_ui`. The real shop sources are:

- `$C7:7B6A` — total-money unit;
- `$D0:D894` — two-byte merchandise-price unit literal.

`french_resources` translates those fixed two-glyph literals from `GP` to `PO`
using `translations/french_resources_reviewed_literals.json`. `vwf_ui` only
consumes whatever two glyphs are already present: a standalone USA build shows
`GP`, while `all.ips` shows `PO`.

Validated merchandise presentation is geometric only:

- resync the price from 168 px to **164 px**;
- insert a **4 px** separator before the final two unit glyphs;
- do not grow or rewrite the source buffer.

## Fourth backend: type-2 MONEY total

The total-money window is structurally recognized as bank `$7E`, type 2, source
pointer in `$A1E0-$A1EB`, plus exact event-renderer return `$1152`, then receives
one-shot UI tag `$AB`. The live source remains the stock `$A1E0-$A1E9` buffer and
`$A1EA` is never written.

Validated presentation:

- VWF rendering only; no glyph translation;
- **3 px** separator before the final two unit glyphs;
- type-2 frame width `$C7:714C` widened from **9 to 11 cells**.

## Standalone dependency fix

Runtime isolation proved a hidden dependency in the shared chunk-commit helper:
converted chunks unconditionally called dialogue continuation `$ED:7990`.
`vwf_ui` standalone does not install that routine, so opening shop rows could
reset the game. `vwf_ui + vwf_dialogues` worked only because `vwf_dialogues`
provided the missing code.

The shared low-level active byte now has explicit identities:

- `$9385=$01` for `vwf_dialogues`;
- `$9385=$02` for `vwf_ui`.

Shared UI/dialogue hooks accept identities 1/2, but `$ED:7990` is called only
for identity 1. Intro values 3..8 remain excluded. Stock fallbacks clear the
identity. The fallback-scope helper must branch to its own `CLC/RTL`; the
validated offsets are `BEQ +6` and `BCS +2`. The incorrect `+8/+4` offsets
caused a black GAME SELECT while music continued.

This dependency fix and GAME SELECT correction are runtime-validated. Do not
make `vwf_ui` depend on `vwf_dialogues`, and do not put `GP -> PO` translation
logic back into the renderer.

## Current next defect: `Haubert magique`

Resource `$CA:9F8E` / ID `$09C` (`armor_name`, stock `Magical Armor`) translates
to `Haubert magique`. In the shop merchandise `$AA` path, runtime testing shows
its leftmost `H` missing while other items are correct. Treat this as a narrow
item-specific rendering defect. First compare the decoded row, private VWF copy,
starting X/slot and clipping behavior with a known-good item such as
`Noix magique`; do not broaden the backend or alter the validated currency
geometry as a first response.

## Later candidates

Item-acquisition/pickup UI or other equipment/status rows may be considered only
after the current shop defect is resolved. Do not create a generic "all
non-dialogue text" switch. Each family must remain independently gated.

## Known rejected patterns

Do not reuse these unchanged:

- broad Forge/menu-mode gates;
- global parser hooks for UI discovery;
- renderer-time matching against stale initial event pointers;
- private-38 buffer substitution for arbitrary UI mini-events;
- low-level VWF hooks left active after a tagged UI invocation;
- tags armed at generic `WEAPON_NAME` helpers when a more exact submit exists;
- renderer-side `GP -> PO` substitution;
- unconditional calls from shared UI chunk commit into dialogue-only `$ED:7990`.
