"""Load sparse translation JSON files bound to canonical source assets by text ID."""
from __future__ import annotations

import json
from pathlib import Path

FORMAT_VERSION = 1


def source_entries(document: dict) -> list[dict]:
    """Recursively return all source dictionaries carrying both ``id`` and ``source``."""
    found: list[dict] = []

    def walk(value) -> None:
        if isinstance(value, dict):
            if isinstance(value.get("id"), str) and "source" in value:
                found.append(value)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(document)
    ids = [entry["id"] for entry in found]
    if len(ids) != len(set(ids)):
        duplicates = sorted({text_id for text_id in ids if ids.count(text_id) > 1})
        raise ValueError("Duplicate canonical text ID(s): " + ", ".join(duplicates))
    return found


def load_translation(path: Path, source_document: dict, *, source_asset: str) -> dict[str, str]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("format_version") != FORMAT_VERSION:
        raise ValueError(f"{path.name}: unsupported translation format")
    if document.get("language") != "fr":
        raise ValueError(f"{path.name}: expected language 'fr'")
    if document.get("source_asset") != source_asset:
        raise ValueError(
            f"{path.name}: source_asset must be {source_asset!r}, got {document.get('source_asset')!r}"
        )

    canonical = {entry["id"]: entry for entry in source_entries(source_document)}
    translations: dict[str, str] = {}
    groups = document.get("groups")
    if not isinstance(groups, list):
        raise ValueError(f"{path.name}: missing groups list")
    for group in groups:
        entries = group.get("entries")
        if not isinstance(entries, list):
            raise ValueError(f"{path.name}: group {group.get('group')!r} has no entries list")
        for entry in entries:
            text_id = entry.get("id")
            text = entry.get("text")
            if not isinstance(text_id, str) or not isinstance(text, str):
                raise ValueError(f"{path.name}: every translation entry needs string id/text")
            if text_id in translations:
                raise ValueError(f"{path.name}: duplicate translation ID {text_id}")
            if text_id not in canonical and not text_id.startswith("new:"):
                raise ValueError(f"{path.name}: translation ID {text_id} is absent from {source_asset}")
            translations[text_id] = text
    return translations


def require(translations: dict[str, str], ids: list[str] | tuple[str, ...], *, context: str) -> list[str]:
    missing = [text_id for text_id in ids if text_id not in translations]
    if missing:
        raise ValueError(f"{context}: missing translation ID(s): " + ", ".join(missing))
    return [translations[text_id] for text_id in ids]
