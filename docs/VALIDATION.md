# Validation state

The user runtime-tested the combined corrected build successfully on 2026-09-01. The five component IPS files in this package are the byte-identical standalone checkpoints used by that successful combination.

Standalone IPS SHA-256 values:

- Japanese Mana Tree: `424a15e1f08be4207054d99c83d0f69a5ec5cf2d9acf3160d7b35eeb35060027`
- 9-character names: `dc20f8994d78968863311543212dde5c9c8ee9befa97d58f79dd834d8156e77f`
- GAME SELECT: `ede4084d40087fbaeb6622edeb9e976e4a70477ff1ba06cc5bafd610fb5b86d2`
- French opening integration-safe: `ba9145ff516e48dfe838c1258bd9aa1841be6a2aa4c85e75af663f018313c14b`
- French intro VWF: `36d419d9ad83e98cbc0b34ff41f11ef2941992ac223dc1cfc4d8b21ccdf37758`

`verify.py` checks these hashes and audits overlaps without requiring a ROM.
