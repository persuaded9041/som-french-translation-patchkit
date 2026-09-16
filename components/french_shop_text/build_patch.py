#!/usr/bin/env python3
"""Build standalone French D9 shop/forge response-text component."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shared.charset import CHAR_TO_CODE, DIALOGUE_FRENCH_CHARS, glyph_bytes
from shared.core.ips import make_ips
from shared.core.rom import update_checksum, validate_base_rom
from shared.dialogue.dte import (
    enable_extended_dialogue as enable_extended_dialogue_dte,
    install as install_dialogue_dte_router,
    validate_stock as validate_dialogue_dte_stock,
)
from shared.extracted.assets import load_or_extract_shop
from shared.text.android_strings import read_string_table
from shared.text.shop import (
    D9_BASE,
    EXPECTED_BLOB_END,
    EXPECTED_BLOB_START,
    serialize_translated_pool,
)
from shared.text.translation_json import load_translation

ASSET = PROJECT_ROOT / "assets" / "shop_text.json"
DIRECT_TRANSLATION = PROJECT_ROOT / "translations" / "shop_text_french.json"
REVIEWED_OVERRIDES = PROJECT_ROOT / "translations" / "shop_text_reviewed_overrides.json"
ANDROID_RECIPE = PROJECT_ROOT / "recipes" / "android" / "shop_text_mapping.json"
FONT_BASE = 0x12DC00
GLYPH_FIRST = min(CHAR_TO_CODE[ch] for ch in DIALOGUE_FRENCH_CHARS)
MAX_VISIBLE_CHARS = 28


def _load_reviewed_overrides(source: dict) -> dict[str, str]:
    doc = json.loads(REVIEWED_OVERRIDES.read_text(encoding="utf-8"))
    if doc.get("format_version") != 1 or doc.get("language") != "fr":
        raise ValueError("Unsupported reviewed shop-text override format")
    if doc.get("source_asset") != "shop_text.json":
        raise ValueError("shop_text_reviewed_overrides.json source_asset mismatch")

    canonical = {entry["id"] for entry in source["records"]}
    out: dict[str, str] = {}
    for entry in doc.get("entries", []):
        text_id = entry.get("id")
        text = entry.get("text")
        if not isinstance(text_id, str) or text_id not in canonical:
            raise ValueError(f"Reviewed shop override has unknown source ID {text_id!r}")
        if not isinstance(text, str):
            raise ValueError(f"{text_id}: reviewed shop override text must be a string")
        if text_id in out:
            raise ValueError(f"Duplicate reviewed shop override {text_id}")
        out[text_id] = text
    return out


def _android_tables(namespace: str) -> tuple[dict[int, str], dict[int, str]]:
    if namespace not in {"systxt", "scrtxt"}:
        raise ValueError(f"Unsupported Android shop namespace {namespace!r}")
    en = read_string_table(PROJECT_ROOT / "sources" / "android" / f"{namespace}_en.bin")
    fr = read_string_table(PROJECT_ROOT / "sources" / "android" / f"{namespace}_fr.bin")
    if set(en) != set(fr):
        raise ValueError(f"Android {namespace} EN/FR ID sets differ")
    return en, fr


def _validate_provenance(
    source: dict,
    direct: dict[str, str],
    overrides: dict[str, str],
) -> dict[str, dict]:
    recipe = json.loads(ANDROID_RECIPE.read_text(encoding="utf-8"))
    if recipe.get("format_version") != 1 or recipe.get("source_asset") != "shop_text.json":
        raise ValueError("Unsupported shop-text Android mapping recipe")

    canonical = {entry["id"]: entry["source"] for entry in source["records"]}
    records = recipe.get("records")
    if not isinstance(records, list):
        raise ValueError("shop_text_mapping.json has no records list")
    by_id: dict[str, dict] = {}
    tables: dict[str, tuple[dict[int, str], dict[int, str]]] = {}

    for record in records:
        text_id = record.get("snes_id")
        status = record.get("status")
        if text_id not in canonical or text_id in by_id:
            raise ValueError(f"Invalid/duplicate shop mapping source ID {text_id!r}")
        if status not in {"direct", "adaptation_basis", "reviewed_without_android_equivalent"}:
            raise ValueError(f"{text_id}: unsupported shop mapping status {status!r}")

        namespace = record.get("android_namespace")
        ids = record.get("android_ids")
        if not isinstance(ids, list) or any(not isinstance(value, int) for value in ids):
            raise ValueError(f"{text_id}: android_ids must be an integer list")

        if status == "reviewed_without_android_equivalent":
            if namespace is not None or ids:
                raise ValueError(f"{text_id}: no-equivalent record must not bind Android IDs")
            if text_id not in overrides or text_id in direct:
                raise ValueError(f"{text_id}: no-equivalent record must come from reviewed overrides only")
        else:
            if not isinstance(namespace, str) or not ids:
                raise ValueError(f"{text_id}: mapped record needs Android namespace/IDs")
            if namespace not in tables:
                tables[namespace] = _android_tables(namespace)
            en, fr = tables[namespace]
            try:
                en_values = [en[value].strip() for value in ids]
                fr_values = [fr[value].strip() for value in ids]
            except KeyError as exc:
                raise ValueError(f"{text_id}: Android ID {exc.args[0]} missing in {namespace}") from exc
            if len(set(en_values)) != 1 or len(set(fr_values)) != 1:
                raise ValueError(f"{text_id}: reviewed duplicate Android IDs no longer agree")

            if status == "direct":
                if en_values[0] != canonical[text_id]:
                    raise ValueError(
                        f"{text_id}: direct Android EN identity changed: {en_values[0]!r} != {canonical[text_id]!r}"
                    )
                if text_id not in direct or text_id in overrides:
                    raise ValueError(f"{text_id}: direct record must come from shop_text_french.json only")
                if direct[text_id] != fr_values[0]:
                    raise ValueError(
                        f"{text_id}: direct French payload differs from Android FR: "
                        f"{direct[text_id]!r} != {fr_values[0]!r}"
                    )
            else:
                if text_id not in overrides or text_id in direct:
                    raise ValueError(f"{text_id}: adaptation record must come from reviewed overrides only")

        by_id[text_id] = record

    if set(by_id) != set(canonical):
        missing = sorted(set(canonical) - set(by_id))
        extra = sorted(set(by_id) - set(canonical))
        raise ValueError(f"shop mapping recipe/source mismatch: missing={missing}, extra={extra}")
    return by_id


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("rom", type=Path, help="clean unheadered Secret of Mana (USA) ROM")
    ap.add_argument("-o", "--output", type=Path, required=True)
    args = ap.parse_args()

    base = args.rom.read_bytes()
    validate_base_rom(base)
    source = load_or_extract_shop(base, ASSET)

    direct = load_translation(DIRECT_TRANSLATION, source, source_asset="shop_text.json")
    overrides = _load_reviewed_overrides(source)
    _validate_provenance(source, direct, overrides)

    translations = dict(direct)
    overlap = sorted(set(translations) & set(overrides))
    if overlap:
        raise ValueError("Direct/reviewed shop translation overlap: " + ", ".join(overlap))
    translations.update(overrides)

    canonical_ids = {entry["id"] for entry in source["records"]}
    if set(translations) != canonical_ids:
        missing = sorted(canonical_ids - set(translations))
        raise ValueError("French shop component requires all nine reviewed records; missing: " + ", ".join(missing))

    blob, references, stats = serialize_translated_pool(
        base,
        source,
        translations,
        max_visible_chars=MAX_VISIBLE_CHARS,
    )

    rom = bytearray(base)

    # Standalone D9 event text needs the same event-context direct-glyph/DTE
    # boundary used by ordinary French dialogue, but it deliberately keeps the
    # stock fixed-width renderer because vwf_dialogues does not own bank D9.
    validate_dialogue_dte_stock(base)
    install_dialogue_dte_router(rom)
    enable_extended_dialogue_dte(rom)
    french_glyphs = glyph_bytes(DIALOGUE_FRENCH_CHARS)
    glyph_start = FONT_BASE + (GLYPH_FIRST - 0x80) * 12
    rom[glyph_start:glyph_start + len(french_glyphs)] = french_glyphs

    pool_start = D9_BASE + EXPECTED_BLOB_START
    rom[pool_start:pool_start + len(blob)] = blob
    for site, pointer in references.items():
        if rom[site] != 0xA2:
            raise ValueError(f"Expected clean-ROM LDX at C0:${site:04X}")
        rom[site + 1:site + 3] = pointer.to_bytes(2, "little")

    update_checksum(rom)
    patch = make_ips(base, bytes(rom))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(patch)

    capacity = EXPECTED_BLOB_END - EXPECTED_BLOB_START
    max_chars = max(item["visible_chars"] for item in stats.values())
    print(f"Translated shop/forge responses: {len(translations)}")
    print(f"Direct Android FR: {len(direct)}")
    print(f"Reviewed SNES adaptations: {len(overrides)}")
    print(f"Stock fixed-width maximum used: {max_chars} / {MAX_VISIBLE_CHARS} visible characters")
    print(f"D9 mini-event pool: {len(blob)} / {capacity} bytes ({capacity - len(blob)} bytes free)")
    print(f"IPS: {args.output}")


if __name__ == "__main__":
    main()
