#!/usr/bin/env python3
"""Build standalone French $CA resource-name component."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shared.core.ips import make_ips
from shared.core.rom import update_checksum, validate_base_rom
from shared.text.resource_translation import normalize_for_snes
from shared.text.stock import encode_text_with_stock_dte
from shared.text.resources import (
    CA_BASE,
    FIRST_RESOURCE_POINTER,
    RESOURCE_COUNT,
    RESOURCE_POINTER_TABLE,
    load_document,
    serialize_table_and_blob,
)
from shared.dialogue.dte import (
    validate_stock as validate_dialogue_dte_stock,
    install as install_dialogue_dte_router,
    enable_extended_dialogue as enable_extended_dialogue_dte,
)
from tools.import_android_resources import build_mapping, build_translation, load_inputs as load_android_inputs
from shared.charset import (
    CHAR_TO_CODE,
    DIALOGUE_FRENCH_CHARS,
    glyph_bytes,
)

ASSET = PROJECT_ROOT / "assets" / "text_resources.json"
STOCK_BLOB_BYTES = 7315
FONT_BASE = 0x12DC00
GLYPH_FIRST = min(CHAR_TO_CODE[ch] for ch in DIALOGUE_FRENCH_CHARS)
DEFAULT_CATEGORIES = (
    "magic_name",
    "mana_spirit_name",
    "weapon_name",
    "helmet_name",
    "armor_name",
    "accessory_name",
    "item_name",
    "enemy_name",
    "location_name",
)


def load_translation_entries() -> dict[str, tuple[str, str]]:
    """Regenerate the reviewed Android-FR resource payload in memory.

    ``translations/text_resources_french.json`` and the Android mapping JSON are
    review artifacts emitted by ``tools/import_android_resources.py``.  The
    component deliberately does not consume either generated file as a build
    source.
    """
    source, layout, android_en, android_fr = load_android_inputs()
    doc = build_translation(build_mapping(source, layout, android_en, android_fr))
    result: dict[str, tuple[str, str]] = {}
    for group in doc["groups"]:
        category = group["group"].split(".")[-1]
        for entry in group["entries"]:
            result[entry["id"]] = (category, entry["text"])
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("rom", type=Path, help="clean unheadered Secret of Mana (USA) ROM")
    ap.add_argument("-o", "--output", type=Path, required=True)
    args = ap.parse_args()

    base = args.rom.read_bytes()
    validate_base_rom(base)
    document = load_document(ASSET)
    entries = load_translation_entries()

    translations: dict[str, str] = {}
    skipped: list[tuple[str, str]] = []
    for snes_id, (category, text) in entries.items():
        if category not in DEFAULT_CATEGORIES:
            continue
        normalized, _notes = normalize_for_snes(text)
        try:
            encode_text_with_stock_dte(base, normalized, upper_dte_threshold=0xE6)
        except ValueError as exc:
            skipped.append((snes_id, str(exc)))
            continue
        translations[snes_id] = normalized

    table, blob = serialize_table_and_blob(
        base,
        document,
        translations=translations,
        compress_translations=True,
    )
    if len(blob) > STOCK_BLOB_BYTES:
        raise SystemExit(
            f"Translated resource blob is {len(blob)} bytes, exceeding stock allocation {STOCK_BLOB_BYTES}"
        )

    rom = bytearray(base)

    # Standalone French glyph/DTE support. These writes are byte-identical to
    # the shared profile installed by `vwf_dialogues` / `french_dialogues`, so aggregate overlap is safe.
    validate_dialogue_dte_stock(base)
    install_dialogue_dte_router(rom)
    enable_extended_dialogue_dte(rom)
    french_glyphs = glyph_bytes(DIALOGUE_FRENCH_CHARS)
    glyph_start = FONT_BASE + (GLYPH_FIRST - 0x80) * 12
    rom[glyph_start:glyph_start + len(french_glyphs)] = french_glyphs

    table_start = RESOURCE_POINTER_TABLE
    table_end = table_start + RESOURCE_COUNT * 2
    blob_start = CA_BASE + FIRST_RESOURCE_POINTER
    blob_end = blob_start + len(blob)
    stock_blob_end = blob_start + STOCK_BLOB_BYTES
    if blob_end > stock_blob_end:
        raise AssertionError("resource write crossed stock allocation")
    rom[table_start:table_end] = table
    rom[blob_start:blob_end] = blob

    update_checksum(rom)
    patch = make_ips(base, bytes(rom))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(patch)

    print(f"Translated resources: {len(translations)}")
    print(f"Skipped for current profile: {len(skipped)}")
    print(f"Blob: {len(blob)} / {STOCK_BLOB_BYTES} bytes")
    print(f"IPS: {args.output}")


if __name__ == "__main__":
    main()
