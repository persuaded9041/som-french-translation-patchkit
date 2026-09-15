# Intro skip — restart plan by isolated runtime proofs

Date: 2026-09-15

**Status: COMPLETE / historical proof plan.** The restart was executed through Step 3.5 with explicit runtime validation after each accepted sub-step. The promoted implementation is documented in `components/intro_skip/README.md`; the complete result log is `docs/INTRO_SKIP_VALIDATION.md`.

This plan remains authoritative as the record of how the component was reproven from the clean pre-experiment implementation: one mechanism at a time, with no advancement until the user had runtime-tested and explicitly validated the current sub-step.

The assembly map to use is `docs/INTRO_EVENT_ARCHITECTURE.md`.

## Why the restart is necessary

Three compound candidates were runtime-rejected:

1. `safe-global`: global R-hold timer + C0/C1/Mode-7 commit points — no visible response to R.
2. `buffered-input`: same design but reading synchronized `$7E:0042` instead of raw `$4218` — no visible response to R.
3. `immediate-R`: timer removed, one observed R frame latched a skip request — no visible response to R.

These failures do **not** prove which individual link failed. They prove only
that the composed chain was not validated end-to-end. The restart therefore
separates display, runtime execution, controller observation, skipping and timing.

## Rules for every sub-step

- Use the clean, unheadered Secret of Mana (USA) ROM as the test base.
- Deliver one autonomous IPS for that sub-step.
- Change only the minimum bytes needed to prove the new hypothesis.
- Keep a byte/address diff against the previous validated sub-step.
- Never silently reuse an unvalidated hook from a rejected candidate.
- Do not advance after a static proof alone: the user must validate the visible/runtime result.
- If a sub-step fails, investigate that sub-step only; do not compensate by adding another mechanism.
- Preserve the reference ROM outside deliverables; never redistribute it.

## Step 0 — prove the observation surface

### 0.1 Static text replacement

Replace one known, deterministic intro text payload with a minimal visible marker
such as `R`, with **no runtime condition and no new assembly hook**.

Proof criterion: the expected intro text visibly becomes `R` in emulator.

Purpose: prove that the test IPS is applied to the expected ROM and that the
chosen text/payload path is the one actually displayed.

### 0.2 Restore baseline text

Restore the original translated text before beginning runtime experiments.

Proof criterion: the exact previous intro text is visible again.

## Step 1 — prove R input without skipping

### 1.1 Runtime code can alter a known future text

At a point known to execute, make runtime code force the next known intro text to
become `R`, still with **no controller condition**.

Proof criterion: the marker appears only because the runtime routine executed.

### 1.2 Read R at one known execution point

Use the stock controller state at a point whose execution and refresh order are
understood. If R is down at that exact point, make the next known text become `R`;
otherwise keep the normal text.

No timer, no latch, no NMI-only observation, no skip.

Proof criterion: the same test produces different visible text depending only on
whether R is held at that known point.

### 1.3 Prove a latched R observation

After 1.2 is validated, allow an R press before the chosen text to set a one-bit
flag, then consume that flag by making the next known text become `R`.

Proof criterion: a brief press before the text is visibly remembered.

Only after 1.3 is validated is an R-driven skip allowed to be attempted.

## Step 2 — prove intro skipping without timing

### 2.1 Unconditional direct skip

On new-game intro entry, skip directly to the waterfall using the smallest
stock-compatible path. Do not read R and do not use a timer.

Because this branch may occur before `$29 F8`, do not blindly reuse a tail that
contains `$2A F8`; balance `$CFF8` according to the actual point of departure.

Proof criterion: starting a new game reaches the waterfall reliably, with the
waterfall scene/dialogue behaving normally.

### 2.2 Skip after one known event boundary

Let `$0400` run normally to a precisely identified command/event boundary, then
unconditionally take the validated skip path.

Proof criterion: the intro always skips at that exact boundary and nowhere else.

### 2.3 Conditional skip from an artificial flag

Drive the already-validated 2.2 skip path from a simple flag set by known code,
still without controller input.

Proof criterion: flag clear = no skip; flag set = skip.

### 2.4 Connect validated R input to validated skip

Use only the R mechanism validated in Step 1 to set the flag validated in 2.3.

Proof criterion: R causes the skip; no R does not.

## Step 3 — prove timing independently, then compose it

### 3.1 Deterministic event marker

After one known event boundary, make a future text display `Skip`.

Proof criterion: marker appears at the expected structural boundary.

### 3.2 Calculated delay marker

Start a counter at that known boundary and display `Skip` only after a calculated
delay. Use two deliberately different delay values in separate test patches if
needed to prove the counter is real rather than coincidentally aligned with the
next event.

Proof criterion: visible delay changes according to the configured count.

### 3.3 Timer drives the validated skip

Replace the visual marker with the skip mechanism already validated in Step 2.

Proof criterion: no R involved; the intro skips after the calculated delay.

### 3.4 R starts the timer

Use the R observation mechanism already validated in Step 1 to start the timer.

Proof criterion: R starts a known-duration countdown that ends in the validated skip.

### 3.5 Hold-to-skip semantics

Finally, require R to remain held for the full configured duration; release must
cancel/reset the pending timer.

Proof criterion: one continuous hold skips; shorter separated presses do not
accumulate.

## Completion result

The ladder succeeded. The final production implementation requires a continuous R hold for **120 normal-loop ticks**, cancels on release, does not accumulate short presses, and commits only through the validated live-parser or timed-WAIT paths. It covers the eight normal narrative phases before `$CA:0E82 = 1D 7F`. The final Mode-7/flyover path remains deferred.

## Explicitly deferred ideas

The proof ladder is complete; these remain separate future investigations and are **not** part of the promoted component:

- an independent persistent `Skip` overlay drawn over already-visible intro text;
- a new NMI input subsystem;
- a global C0/C1/Mode-7 request/commit architecture;
- mid-transition forced exits;

The text renderer uses a shared destructive `$7E:9000 -> $7E:9400 -> VRAM`
pipeline, so a true overlay is a separate rendering problem and is not needed to
prove controller input or skip behavior.
