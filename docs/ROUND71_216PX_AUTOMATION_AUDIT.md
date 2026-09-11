# Round 71 — 216 px automatic-layout audit

This audit is diagnostic only. No manual French wording is introduced.
All candidate repairs preserve Android-FR semantic payload and change only
layout bytes, then require a completely clean independent simulation.

## Automatically recoverable with one carrier-boundary NEWLINE candidate

A deterministic search that tries one presentation-only NEWLINE at an existing
translated carrier boundary and accepts only a fully clean simulation already
finds clean candidates for:

- `$0020`
- `$0023`
- `$0040`
- `$015A`
- `$03ED`
- `$0429`
- `$04E9`

The search is generic: it does not contain event text or French literals. When
multiple equivalent candidates exist, token order plus append-before-prepend can
provide a deterministic tie-break.

## Automatically recoverable by more permissive three-page balancing

`$03DC / C9:ECD2 -> Android FR 2468+2469` reflows to seven legal lines under
216 px / 38 units. The current formatter rejects it only because it requires
both page transitions to fall after complete sentences. A deterministic
balanced 3-page layout exists (for example 2/3/2 or 3/2/2 lines) with every line
<=216 px. The generic rule can therefore allow a page boundary inside a sentence
when the sentence itself necessarily spans more than one physical page, while
still splitting only at word boundaries.

## Reviewed redistribution candidate

`$04E9` also becomes simulator-clean when historical hard NEWLINE layout hints
inside its reviewed Android-FR carriers are repacked before wrapping. Applying
that transformation blindly to every reviewed scene is unsafe, so it should be
a candidate generator rather than a global rewrite: produce the repacked layout,
simulate it, and keep it only if completely clean.

## Cases needing a stronger automatic page/layout search

The following remain after the simple one-boundary experiment and need a
multi-step deterministic candidate search over NEWLINE/page boundaries while
preserving carrier/control structure:

- `$010C`
- `$01DA`
- `$01F6`
- `$04E2`
- `$04E6`
- `$0592`
- `$059B`
- `$05F8`

Several combine width pressure with `UNPAUSED_SCROLL`; some also contain dynamic
PLAYER_NAME constraints. They should not receive prose edits.

## Locked `$04E1`

`$04E1` is not an identity problem. Its Round-67 Android-FR Thanatos
redistribution remains locked. The current Round-71 generated active set drops
it because the conservative partial path rejects its 216 px layout. The next
pipeline revision must recover this scene from Android FR / reviewed structural
metadata and reflow it automatically; it must not fall back to English and must
not reopen the accepted translation.

## Permanent exclusions

`$0269`, `$02DE`, `$0603` remain routing-audited orphan/inaccessible stock
content and are unrelated to the 216 px formatter work.
