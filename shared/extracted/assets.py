"""Load deterministic clean-USA ROM extraction caches, creating them on demand.

The root ``assets/`` tree is a local cache, not a canonical project input.  A
matching JSON file is validated and reused when present.  When it is absent,
the canonical structure is extracted from the supplied clean USA ROM, written
to the cache path, and returned to the caller.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable

from shared.dialogue.codec import extract_default_document, load_document as load_dialogue_document, parse_event
from shared.text.battle import extract_document as extract_battle, load_document as load_battle
from shared.text.interface import extract_document as extract_interface, load_document as load_interface
from shared.text.intro_event import make_document as extract_intro_event, load_document as load_intro_event
from shared.text.menu import extract_document as extract_menu, load_document as load_menu
from shared.text.opening import extract_document as extract_opening, load_document as load_opening
from shared.text.resources import extract_document as extract_resources, load_document as load_resources
from shared.text.shop import extract_document as extract_shop, load_document as load_shop

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ASSET_DIR = ROOT / "assets"


def _path(path: Path | None, filename: str) -> Path:
    return path if path is not None else DEFAULT_ASSET_DIR / filename


def _write_json_atomic(path: Path, document: dict) -> None:
    """Persist a generated cache without exposing callers to a partial JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _load_or_extract(
    cache: Path,
    loader: Callable[[Path], dict],
    extractor: Callable[[], dict],
) -> dict:
    if cache.exists():
        return loader(cache)
    document = extractor()
    _write_json_atomic(cache, document)
    return document


def load_or_extract_dialogues(rom: bytes, path: Path | None = None) -> dict:
    cache = _path(path, "dialogues.json")
    return _load_or_extract(cache, load_dialogue_document, lambda: extract_default_document(rom))


def load_or_extract_resources(rom: bytes, path: Path | None = None) -> dict:
    cache = _path(path, "text_resources.json")
    return _load_or_extract(cache, load_resources, lambda: extract_resources(rom))


def load_or_extract_interface(rom: bytes, path: Path | None = None) -> dict:
    cache = _path(path, "interface_text.json")
    return _load_or_extract(cache, load_interface, lambda: extract_interface(rom))


def load_or_extract_menu(rom: bytes, path: Path | None = None) -> dict:
    cache = _path(path, "menu_text.json")
    return _load_or_extract(cache, load_menu, lambda: extract_menu(rom))


def load_or_extract_battle(rom: bytes, path: Path | None = None) -> dict:
    cache = _path(path, "battle_text.json")
    return _load_or_extract(cache, load_battle, lambda: extract_battle(rom))


def load_or_extract_shop(rom: bytes, path: Path | None = None) -> dict:
    cache = _path(path, "shop_text.json")
    return _load_or_extract(cache, load_shop, lambda: extract_shop(rom))


def load_or_extract_opening(rom: bytes, path: Path | None = None) -> dict:
    cache = _path(path, "opening_text.json")
    return _load_or_extract(cache, load_opening, lambda: extract_opening(rom))


def load_or_extract_intro_event(rom: bytes, path: Path | None = None) -> dict:
    cache = _path(path, "intro_event.json")
    return _load_or_extract(
        cache,
        load_intro_event,
        lambda: extract_intro_event(parse_event(rom, 0x0400)),
    )


def materialize_all_assets(rom: bytes, asset_dir: Path | None = None) -> dict[str, dict]:
    """Ensure the complete root extraction cache exists and return its documents.

    This is used by a full repository build to warm all deterministic caches in
    one pass. Targeted component builds continue to populate only the cache files
    they actually need through the individual ``load_or_extract_*`` helpers.
    """
    directory = asset_dir if asset_dir is not None else DEFAULT_ASSET_DIR
    return {
        "dialogues": load_or_extract_dialogues(rom, directory / "dialogues.json"),
        "resources": load_or_extract_resources(rom, directory / "text_resources.json"),
        "interface": load_or_extract_interface(rom, directory / "interface_text.json"),
        "menu": load_or_extract_menu(rom, directory / "menu_text.json"),
        "battle": load_or_extract_battle(rom, directory / "battle_text.json"),
        "shop": load_or_extract_shop(rom, directory / "shop_text.json"),
        "opening": load_or_extract_opening(rom, directory / "opening_text.json"),
        "intro": load_or_extract_intro_event(rom, directory / "intro_event.json"),
    }
