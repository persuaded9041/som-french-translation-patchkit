# Test cheats

This is a standalone, candidate-only test component. It is deliberately
excluded from `all.ips` so the runtime-validated French aggregate remains
unchanged.

The rejected movement experiment set the dash bit in `$C0:D5ED`; that field
drives the dash/action state and caused blinking. The current movement cheat
does not use that path. It changes only the four direction-magnitude literals
in `$C1:B710`, changing stock magnitude `2` to `4` and preserving the negative
direction marker (`$82` to `$84`).

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

For movement, test the hero and both AI allies in all four directions. Confirm
that direction can be changed immediately, no running animation appears, and
the walking speed matches ordinary running. Also check stopping, diagonals,
collisions and map transitions.
