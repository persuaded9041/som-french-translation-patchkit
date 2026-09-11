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

## Next candidates

### 1. Ring Menu

Runtime observation after the Round-75 Forge work: Ring Menu text already renders with VWF. This
is likely an effect of a shared path, but the exact ownership/submit chain has not yet been proven.
Do **not** add another gate merely to "enable" Ring Menu VWF. First inventory which labels/names are
built dynamically versus read directly from `$CA` resources, trace the exact builder/submit path,
and explain why the current narrow `vwf_ui` infrastructure already reaches it. Only add a new
one-shot gate if a specific Ring Menu field is proven to need one. Long equipment/item names remain
useful stress cases.

### 2. Item-acquisition / pickup UI

Find the path used when item/resource names are shown after pickup. Record whether quantities,
icons, punctuation, or status text are placed with absolute cell anchors. Prove the builder with
a local resource-ID or glyph probe before attempting VWF.

### Later candidates

Equipment/status/shop rows may be considered after the first two families are understood. Do not
create a generic "all non-dialogue text" switch. Each family should remain independently gated
and independently disableable inside `vwf_ui`.

## Known rejected patterns

Do not reuse these unchanged:

- broad Forge/menu-mode gates;
- global parser hooks for UI discovery;
- renderer-time matching against stale initial event pointers;
- private-38 buffer substitution for arbitrary UI mini-events;
- low-level VWF hooks left active after a tagged UI invocation;
- tags armed at generic `WEAPON_NAME` helpers when a more exact submit exists.
