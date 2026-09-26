# Test cheats

This is a standalone test component. It is deliberately excluded from the
normal `all.ips`; `--cheats` adds it to `all-cheats.ips` and
`all-fr-cheats.ips` when a French locale is selected.

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

Runtime validation is complete for the modified combat and movement paths. The
three party members deal exactly `999` damage with physical and magic attacks,
and receive exactly `1` damage from physical and magic enemy attacks. Healing,
poison, traps, reflected damage, status effects and scripted damage are outside
the modified paths and remain optional non-regression checks.

The hero and both AI allies retain immediate direction changes, show no running
animation, and walk at ordinary running speed. Stopping, diagonals, collisions
and map transitions are outside the modified movement literals.
