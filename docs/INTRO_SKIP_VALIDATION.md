# Intro skip — runtime validation record

Date completed: 2026-09-15

This document records the proof ladder that replaced the former experimental
`intro_skip` implementation. The final promoted component is the 120-tick
continuous-R hold implementation in `components/default_intro_skip/`.

The dialogue corpus was frozen throughout this work and was not reopened.

## Final validated behavior

During translated event `$0400`, before the final `$1D 7F` Mode-7 transition,
R is read from the stock synchronized pad-1 state `$7E:0042` bit `$10`.

- one continuous hold starts a 16-bit countdown;
- release before zero cancels/reset the countdown to `$FFFF`;
- separated short presses do not accumulate;
- once zero is reached, the skip request remains sticky until a validated safe
  commit point consumes it;
- the final production constant is **120 normal-loop ticks**.

A completed hold exits through the private tail `$CA:FFC0`:

```text
51          TEXT_CLOSE
18 00       room $0000 / waterfall
2A F8       balance the intro $29 F8 context
11 06 00    JUMP event $0106
```

The eight normal narrative text/WAIT phases are covered. The final Mode-7 /
flyover phase beginning at `$CA:0E82 = 1D 7F` remains deliberately outside the
validated scope.

The runtime-proven autonomous `french_intro + vwf_intro + intro_skip` test patch
was regenerated directly from the validated 60-tick 3.5 path and differs only by
the two `003C -> 0078` timer immediates plus checksum. The standalone component
patch also contains a 16-byte aggregate dispatcher in a previously unused ED gap,
but its direct standalone hook does not execute that dispatcher. When
`vwf_dialogues` is present, the aggregate builder routes the shared `$C0:16EA`
hook through the dispatcher so dialogue parser mode 2 retains its existing
`$ED:7500` preflight. Both the standalone component and the resulting `all.ips`
were runtime-validated by the user.

## Proof ladder

| Step | Runtime result | Status |
| --- | --- | --- |
| 0.1 | deterministic first intro text statically became `R` | VALIDATED |
| 0.2 | French/VWF intro baseline restored | VALIDATED |
| 1.1 | runtime code changed a known future line to `R` | VALIDATED |
| 1.2 | the line became `R` only when R was held at the known point | VALIDATED |
| 1.3 | a brief earlier R press was latched and consumed later | VALIDATED |
| 2.1 | unconditional direct skip reached the waterfall | VALIDATED |
| 2.2 | skip after the first known text boundary reached the waterfall | VALIDATED |
| 2.3 initial harness | double first page, stray sparkle animation, then waterfall | REJECTED |
| 2.3b | artificial flag conditional skip without intro restart artifact | VALIDATED |
| 2.3c | `$1D01`-based mid-sentence trigger never fired | REJECTED |
| 2.3c2 | live parser-Y trigger skipped in the middle of a carrier | VALIDATED |
| 2.4 | R drove mid-text skip; completed-text WAIT not yet covered | PARTIAL / retained |
| 2.4b | direct C1 WAIT hook broke no-R path | REJECTED |
| 2.4c | revised direct C1 WAIT hook still broke no-R path | REJECTED |
| 2.4d | external normal-loop observation handled both mid-text and first WAIT | VALIDATED |
| 2.4e global v1 | boot glitch | REJECTED |
| 2.4e first-two v1 | boot glitch | REJECTED |
| 2.4e1 | two sequences, mid-text only | VALIDATED |
| 2.4e2 | added first WAIT of sequence 2 | VALIDATED |
| 2.4e3 | added second WAIT of sequence 2 | VALIDATED |
| 2.4e4 | structural generalization over all normal narrative phases | VALIDATED |
| 3.1 | deterministic structural marker changed later text to `Skip` | VALIDATED |
| 3.2 | 60 and 600 count variants visibly expired at different times | VALIDATED |
| 3.3 initial | skip occurred almost immediately | REJECTED |
| 3.3b | timer 600 drove delayed skip after explicit post-arm gating | VALIDATED |
| 3.4 | brief R press armed timer 600; timer continued after release | VALIDATED |
| 3.5 / 600 | continuous-hold semantics appeared correct but test was slow | VALIDATED provisionally |
| 3.5 / 60 | continuous hold skipped; release reset; short presses did not accumulate | VALIDATED |
| production component | same 3.5 logic, constant changed only from 60 to **120** | RUNTIME VALIDATED |
| production `all.ips` | aggregate build including the promoted component | RUNTIME VALIDATED |
| production autonomous FR+VWF+skip | regenerated directly from the runtime-proven 3.5 path with only `60 -> 120` | RUNTIME VALIDATED |

## Important deductions

1. `$7E:0042` bit `$10` is a runtime-proven R source for this intro.
2. `$C0:012C` is useful while text is active but does not run through all WAIT
   phases.
3. `$1D01` is not a live per-character cursor. `$C0:16EA` sees the parser's live
   `Y` and is the proven mid-carrier departure point.
4. Directly intercepting C1's timed-WAIT handler is unsafe in the tested forms.
   The validated design observes/prepares externally and leaves C1 stock.
5. The two early "global" boot glitches were allocation bugs, not proof that a
   structural global gate was impossible: expanded helpers had overflowed into
   the shared VWF routine at `$C7:43D0-$43E7`.
6. Relocating the extensible helpers into the owned `$ED:7400-$74FF` reserve
   removed that corruption and allowed structural coverage of all normal
   narrative phases without enumerating every sequence/WAIT.
7. Fresh WRAM zero cannot itself mean "timer expired". The first active text
   converts the initial `$0000` to the explicit inactive sentinel `$FFFF` before
   parser commits are allowed; this fixed the first 3.3 immediate-skip failure.

## Rejected pre-restart designs

Before the isolated proof ladder, three compound designs were tried and rejected
because pressing R produced no visible effect: `safe-global`, `buffered-input`
and `immediate-R`. They remain useful negative evidence only; none of their NMI
or multi-engine commit architecture is part of the promoted component.

## Promoted artifact hashes

- `patches/default_intro_skip.ips`: `b37d529eb25eae572212d6f7179461785e463dfef9055fd840e00f5754136c16`
- `patches/all.ips`: `253ffde42f6977e714e9d27351089a2fbf0400bf46293ca8ed8967e38aad6b6d`
- validated autonomous `french_intro + vwf_intro + intro_skip 120`: `f9f21e070d898f8ef8f05709a6ce8796dbc70a2b2faf2979e56f6c2517ed5997`

The clean USA ROM remains external and must not be redistributed.


## Final runtime packaging note

The user runtime-validated all three relevant production surfaces:

- standalone `intro_skip` component patch;
- aggregate `all.ips`;
- autonomous `french_intro + vwf_intro + intro_skip 120` test patch with
  SHA-256 `f9f21e070d898f8ef8f05709a6ce8796dbc70a2b2faf2979e56f6c2517ed5997`.

An earlier autonomous artifact with SHA-256
`979921e82ac42e894e7d95e21d2918957b01f8cf3e523ef696eb8f5096b6e030`
was runtime-rejected because it presented stock/non-VWF intro output. Do not use
that artifact as a reference. It is not included in the cleaned checkpoint.
