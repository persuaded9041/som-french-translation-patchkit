# Validation state

The project baseline was runtime-tested successfully on 2026-09-01. The current
version changes only the Name Entry help text in component `02_9char_names`; the
9-character naming logic and the other four components remain unchanged.

The current French help-text build is statically verified and reproducible, but
its new text still requires runtime validation.

Standalone IPS SHA-256 values:

- Japanese Mana Tree: `424a15e1f08be4207054d99c83d0f69a5ec5cf2d9acf3160d7b35eeb35060027`
- 9-character names + French help text: `e793dc519b3239d714038a34c6bffdb6ff93f08becc8baac90f960107447817c`
- GAME SELECT: `ede4084d40087fbaeb6622edeb9e976e4a70477ff1ba06cc5bafd610fb5b86d2`
- French opening integration-safe: `ba9145ff516e48dfe838c1258bd9aa1841be6a2aa4c85e75af663f018313c14b`
- French intro VWF: `36d419d9ad83e98cbc0b34ff41f11ef2941992ac223dc1cfc4d8b21ccdf37758`

`verify.py` checks these hashes and audits overlaps without requiring a ROM.

## Shared charset refactor

The shared-charset refactor is source-only. Rebuilding GAME SELECT and intro VWF
from `shared/french_charset/` still produces their byte-identical runtime-validated
IPS files.
