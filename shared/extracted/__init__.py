"""Optional on-disk caches for deterministic clean-USA ROM extractions."""

from .assets import (
    DEFAULT_ASSET_DIR,
    load_or_extract_battle,
    load_or_extract_dialogues,
    load_or_extract_interface,
    load_or_extract_intro_event,
    load_or_extract_menu,
    load_or_extract_opening,
    load_or_extract_resources,
    load_or_extract_shop,
    materialize_all_assets,
)

__all__ = [name for name in globals() if name.startswith("load_or_extract_")] + ["DEFAULT_ASSET_DIR", "materialize_all_assets"]
