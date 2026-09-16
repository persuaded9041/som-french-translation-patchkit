#!/usr/bin/env python3
"""Build standalone French $CA resource-name component."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shared.core.ips import make_ips
from shared.core.rom import update_checksum, validate_base_rom
from shared.text.resource_translation import normalize_for_snes
from shared.text.stock import decode_text_bytes, encode_text, encode_text_with_stock_dte
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
from shared.text.android_resources import build_mapping, build_translation, load_inputs as load_android_inputs
from shared.text.resource_cache import load as load_translation_cache, store as store_translation_cache
from shared.charset import (
    CHAR_TO_CODE,
    DIALOGUE_FRENCH_CHARS,
    glyph_bytes,
)

from shared.extracted.assets import load_or_extract_resources  # noqa: E402
ASSET = PROJECT_ROOT / "assets" / "text_resources.json"
STOCK_BLOB_BYTES = 7315
REVIEWED_OVERRIDES = PROJECT_ROOT / "translations" / "text_resources_reviewed_overrides.json"
REVIEWED_LITERAL_OVERRIDES = PROJECT_ROOT / "translations" / "french_resources_reviewed_literals.json"

# Non-$CA fixed literals deliberately owned by french_resources. Their French
# payload comes only from REVIEWED_LITERAL_OVERRIDES; Python stores addresses
# and expected source identity, never localized prose.
REVIEWED_LITERAL_SITES = {
    "C7:7B6A": 0x077B6A,  # stock MONEY total unit
    "D0:D894": 0x10D894,  # shop merchandise price unit immediate payload
}
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
    "menu_label",
    "enemy_name",
    "location_name",
)


def _translation_entries_from_document(doc: dict) -> dict[str, tuple[str, str]]:
    result: dict[str, tuple[str, str]] = {}
    for group in doc["groups"]:
        category = group["group"].split(".")[-1]
        for entry in group["entries"]:
            result[entry["id"]] = (category, entry["text"])
    return result


def load_translation_entries(base: bytes, source: dict) -> tuple[dict[str, tuple[str, str]], bool]:
    """Load a valid local cache or regenerate and persist it atomically."""
    cached = load_translation_cache(base, source)
    if cached is not None:
        return _translation_entries_from_document(cached), True

    loaded_source, layout, android_en, android_fr = load_android_inputs(base)
    if loaded_source != source:
        raise ValueError("resource extraction changed while generating French resource cache")
    doc = build_translation(build_mapping(source, layout, android_en, android_fr))
    store_translation_cache(doc, base, source)
    return _translation_entries_from_document(doc), False


def load_reviewed_overrides(source: dict) -> dict[str, tuple[str, str]]:
    """Load small, explicitly reviewed SNES UI adaptations layered over Android FR."""
    doc = json.loads(REVIEWED_OVERRIDES.read_text(encoding="utf-8"))
    if doc.get("format_version") != 1 or doc.get("language") != "fr":
        raise ValueError("Unsupported reviewed text-resource override format")
    by_id = {entry["id"]: entry for entry in source["resources"]}
    result: dict[str, tuple[str, str]] = {}
    for entry in doc.get("entries", []):
        snes_id = entry["id"]
        canonical = by_id.get(snes_id)
        if canonical is None:
            raise ValueError(f"Reviewed resource override has unknown source ID {snes_id}")
        if entry.get("resource_id") != canonical["resource_id"]:
            raise ValueError(f"{snes_id}: reviewed override resource_id mismatch")
        if entry.get("category") != canonical["category"]:
            raise ValueError(f"{snes_id}: reviewed override category mismatch")
        text = entry.get("text")
        if not isinstance(text, str):
            raise ValueError(f"{snes_id}: reviewed override text must be a string")
        result[snes_id] = (canonical["category"], text)
    return result



def load_reviewed_literal_overrides(base: bytes) -> dict[int, bytes]:
    """Load exact reviewed currency literals outside the $CA resource table."""
    doc = json.loads(REVIEWED_LITERAL_OVERRIDES.read_text(encoding="utf-8"))
    if doc.get("format_version") != 1 or doc.get("language") != "fr":
        raise ValueError("Unsupported reviewed french_resources literal override format")
    result: dict[int, bytes] = {}
    seen: set[str] = set()
    for entry in doc.get("entries", []):
        literal_id = entry.get("id")
        if literal_id in seen:
            raise ValueError(f"Duplicate french_resources literal override {literal_id}")
        seen.add(literal_id)
        if literal_id not in REVIEWED_LITERAL_SITES:
            raise ValueError(f"Unknown french_resources literal override {literal_id}")
        source = entry.get("source")
        text = entry.get("text")
        if not isinstance(source, str) or not isinstance(text, str):
            raise ValueError(f"{literal_id}: source/text must be strings")
        encoded_source = encode_text(source)
        encoded_text = encode_text(text)
        if len(encoded_source) != len(encoded_text):
            raise ValueError(f"{literal_id}: fixed literal translation must preserve byte length")
        offset = REVIEWED_LITERAL_SITES[literal_id]
        actual = base[offset:offset + len(encoded_source)]
        if actual != encoded_source:
            try:
                decoded = decode_text_bytes(base, actual)
            except Exception:
                decoded = actual.hex(" ")
            raise ValueError(
                f"{literal_id}: clean-ROM source mismatch: expected {source!r}, found {decoded!r}"
            )
        result[offset] = encoded_text
    missing = set(REVIEWED_LITERAL_SITES) - seen
    if missing:
        raise ValueError(f"Missing reviewed french_resources literal override(s): {sorted(missing)}")
    return result

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("rom", type=Path, help="clean unheadered Secret of Mana (USA) ROM")
    ap.add_argument("-o", "--output", type=Path, required=True)
    args = ap.parse_args()

    base = args.rom.read_bytes()
    validate_base_rom(base)
    document = load_or_extract_resources(base, ASSET)
    entries, cache_hit = load_translation_entries(base, document)
    entries.update(load_reviewed_overrides(document))

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

    # Currency text ownership: keep translation in french_resources and leave
    # vwf_ui responsible only for spacing/window geometry. Both shop sites are
    # fixed two-glyph literals, so standalone french_resources can safely
    # replace GP -> PO without touching renderer logic.
    literal_overrides = load_reviewed_literal_overrides(base)
    for offset, payload in literal_overrides.items():
        rom[offset:offset + len(payload)] = payload

    update_checksum(rom)
    patch = make_ips(base, bytes(rom))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(patch)

    print("Resource translation cache reused: translations/text_resources_french.json" if cache_hit else "Resource translation regenerated and cached: translations/text_resources_french.json")
    print(f"Translated resources: {len(translations)}")
    print(f"Skipped for current profile: {len(skipped)}")
    print(f"Blob: {len(blob)} / {STOCK_BLOB_BYTES} bytes")
    print(f"Reviewed fixed literals: {len(literal_overrides)}")
    print(f"IPS: {args.output}")


if __name__ == "__main__":
    main()
