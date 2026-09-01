# Presets

`all_five.ips` combines all five components and is byte-identical to the combined candidate runtime-validated by the user.

SHA-256: `cabf040a3d74b6995248eca1f3ca2c17a058c785044e1d6b297feda7c887f5e8`

Applying it to the required clean US ROM produces a 3 MiB ROM with SHA-256:

`0f7f6420491f62b92045a0dad33572137263300277466c5654715f628eb65284`

The preset can always be regenerated with:

```bash
python3 build.py "Secret of Mana (USA).sfc" all -o presets/all_five.ips
```
