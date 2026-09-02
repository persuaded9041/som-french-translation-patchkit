# Presets

`all_five.ips` combines all five components, including the new French Name Entry
help text.

SHA-256: `1122ad524cc77a512bde6af55db69aba643b5c2c10f29493a06c7f6ec0bf95d0`

Applying it to the required clean US ROM produces a 3 MiB ROM with SHA-256:

`e97a832795a665dc50aea2672700067d87e1bd0fa1da5d11be73d6fe499232b0`

The previous combined build was runtime-validated. This preset differs only by
the translated Name Entry help resource (and resulting checksum) and therefore
requires runtime validation of that screen.

The preset can always be regenerated with:

```bash
python3 build.py "Secret of Mana (USA).sfc" all -o presets/all_five.ips
```
