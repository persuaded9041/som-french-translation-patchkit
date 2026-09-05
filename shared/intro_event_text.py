"""Helpers for the stock event-$0400 intro source asset.

The actual event parser remains component 08's proven codec.  This small module
only validates the root asset shape used to keep the one component-05-owned
text-bearing event visible in the repository-wide source inventory.
"""
from __future__ import annotations

import json
from pathlib import Path

from shared.rom import BASE_SHA256

FORMAT_VERSION = 3
EVENT_ID = "0400"
EXPECTED_TEXT_PARTS = 8


def make_document(event: dict) -> dict:
    if event.get("event_id") != EVENT_ID:
        raise ValueError("intro_event.json must be extracted from event $0400")
    entries = []
    for token in event.get("tokens", []):
        if token.get("type") not in ("text", "ending_text"):
            continue
        entries.append({"id": token["id"], "source": token["source"]})
    if len(entries) != EXPECTED_TEXT_PARTS:
        raise ValueError(
            f"Expected {EXPECTED_TEXT_PARTS} stock intro text parts, found {len(entries)}"
        )
    return {
        "format_version": FORMAT_VERSION,
        "description": (
            "Stock source text from event $0400. The event itself remains owned by "
            "05_intro_vwf_french and is intentionally excluded from component-08 dialogues.json."
        ),
        "source_rom_sha256": BASE_SHA256,
        "entries": entries,
    }


def load_document(path: Path) -> dict:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("format_version") != FORMAT_VERSION:
        raise ValueError("Unsupported intro-event text document format")
    if document.get("source_rom_sha256") != BASE_SHA256:
        raise ValueError("Intro-event text document targets a different base ROM")
    entries = document.get("entries")
    if not isinstance(entries, list) or len(entries) != EXPECTED_TEXT_PARTS:
        raise ValueError(f"intro_event.json must contain {EXPECTED_TEXT_PARTS} entries")
    return document
