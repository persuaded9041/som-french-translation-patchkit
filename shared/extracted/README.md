# Extracted clean-ROM cache

`shared/extracted/` is the resolver layer for deterministic data extracted from
the clean USA ROM.

The repository does **not** version the root `assets/` directory. Production
code should call the `load_or_extract_*()` helpers from this package:

1. if the requested `assets/*.json` cache exists, it is validated and reused;
2. otherwise the document is extracted from the supplied clean USA ROM;
3. the generated JSON is written atomically under `assets/` and returned.

This makes the first build self-contained while making subsequent builds faster.
The cache can be deleted at any time; it contains no canonical project data.

`tools/text/extract.py` remains the explicit CLI for refreshing or materializing
all extraction JSONs on demand.
