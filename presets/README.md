# Presets

`all_five.ips` combines all five current components, including the
runtime-validated four-row French Name Entry screen.

IPS SHA-256:

`ffd5ddcfc436dba874751211ba9386ae57aa055b73772e6d42e649dd3f7d60a1`

Applied to the required clean USA ROM, it produces a 3 MiB ROM with SHA-256:

`3044c9b4dd21fe9c0c356888b2e974b032c46f43d0662e56dafff2d4e10caac5`

Regenerate with:

```bash
python3 build.py "Secret of Mana (USA).sfc" all -o presets/all_five.ips
```
