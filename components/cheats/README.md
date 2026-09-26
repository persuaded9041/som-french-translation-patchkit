# Combat test cheats

This is a standalone, candidate-only test component. It is deliberately
excluded from `all.ips` so the runtime-validated French aggregate remains
unchanged.

The movement-speed experiment that set the dash bit in `$C0:D5ED` is rejected:
that field drives the dash/action state and causes blinking instead of changing
the walking velocity. It is intentionally absent from the builder. A future
movement candidate must modify the common velocity calculation itself.

The clean USA ROM's final-damage paths store the pending HP damage in
the target character structure at `$E1F1`. The first three structures are the
party members (`$E000`, `$E200`, `$E400`); enemy structures begin at `$E600`.
The patch replaces only the two stock physical six-byte additions and the
separate C8 magic-damage six-byte addition immediately before their final
stores. The relocated helper at C7:4E80 returns `1` for a party target and
`999` for an enemy target, leaving the stores, animations and surrounding
status logic in place.

This is statically traced but not runtime-validated. The intended test scope
is combat attacks from all three party members, including physical and magic
damage, against ordinary enemies and bosses. Also verify that enemy attacks
against each party member show and apply exactly 1 damage. Healing, poison,
traps, reflected damage, status effects and scripted damage must be checked
explicitly.
