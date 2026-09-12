# Repository tools

`tools/` contains command-line entry points for extraction, review, audit and validation. Reusable code required by component builders belongs in `shared/`, not here.

## Layout

- `dialogue/` — Android dialogue generation/report materialization, simulator preview, Japanese dialogue extraction and dialogue-specific validation/audits.
- `text/` — clean-ROM text extraction/round-trip checks, Android `$CA` resource report materialization and text-source/layout audits.

The file name describes the action (`extract_`, `import_`, `generate_`, `simulate`, `audit_`, `check_`). No compatibility wrappers are kept at the old flat `tools/*.py` paths: update callers/docs to the owning domain path instead.

## Library boundary

CLI modules may import `shared.*`. Component builders must never import `tools.*`.

The deterministic dialogue generation engine lives in `shared/dialogue/pipeline/`; `tools/dialogue/import_android.py` is only its materialization CLI. Likewise, reusable Android resource mapping lives in `shared/text/android_resources.py`; `tools/text/import_android_resources.py` only writes optional review outputs.

Generated JSON/CSV/HTML belongs under `reports/` (or an explicit temporary path) and must not become a build input.

## Root extraction cache

The root `assets/` directory is an ignored local cache. Builders and checks reuse validated
JSON when present; when a cache entry is missing, the corresponding document is extracted
from the clean USA ROM and persisted atomically for subsequent runs. A full repository rebuild
warms all eight caches; targeted builds remain lazy. `tools/text/extract.py` explicitly refreshes
or materializes the same cache for inspection/research.
