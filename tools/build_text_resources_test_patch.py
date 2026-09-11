#!/usr/bin/env python3
"""Build an autonomous clean-USA experimental IPS for CA resource review.

Research/test utility only.  It applies the repository's current ``patches/all.ips``
then replaces selected CA resources with the generated Android-FR translations.
The resource blob must remain no larger than the original stock allocation; this
utility never overwrites the data following the stock blob and never relocates it.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.ips import apply_ips, make_ips  # noqa: E402
from shared.rom import update_checksum, validate_base_rom  # noqa: E402
from shared.text_resource_translation import normalize_for_snes  # noqa: E402
from shared.stock_text import encode_text_with_stock_dte  # noqa: E402
from shared.text_resources import (  # noqa: E402
    CA_BASE,
    FIRST_RESOURCE_POINTER,
    RESOURCE_COUNT,
    RESOURCE_POINTER_TABLE,
    load_document,
    serialize_table_and_blob,
)

ASSET = ROOT / "assets" / "text_resources.json"
TRANSLATION = ROOT / "translations" / "text_resources_french.json"
ALL_PATCH = ROOT / "patches" / "all.ips"
STOCK_BLOB_BYTES = 7315
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
    doc = json.loads(TRANSLATION.read_text(encoding="utf-8"))
    result: dict[str, tuple[str, str]] = {}
    for group in doc["groups"]:
        category = group["group"].split(".")[-1]
        for entry in group["entries"]:
            result[entry["id"]] = (category, entry["text"])
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("rom", type=Path, help="clean unheadered Secret of Mana (USA) ROM")
    ap.add_argument("-o", "--output", type=Path, required=True, help="experimental IPS output")
    ap.add_argument(
        "--categories",
        nargs="+",
        default=list(DEFAULT_CATEGORIES),
        help="resource categories to translate (default: all name families)",
    )
    args = ap.parse_args()

    base = args.rom.read_bytes()
    validate_base_rom(base)
    if not ALL_PATCH.is_file():
        raise SystemExit(f"Missing current aggregate patch: {ALL_PATCH}")

    document = load_document(ASSET)
    available_categories = {r["category"] for r in document["resources"]}
    unknown = sorted(set(args.categories) - available_categories)
    if unknown:
        raise SystemExit(f"Unknown resource categories: {', '.join(unknown)}")

    entries = load_translation_entries()
    translations: dict[str, str] = {}
    normalization_count = 0
    skipped_profile: list[tuple[str, str]] = []
    for snes_id, (category, text) in entries.items():
        if category not in args.categories:
            continue
        normalized, notes = normalize_for_snes(text)
        normalization_count += bool(notes)
        try:
            encode_text_with_stock_dte(base, normalized, upper_dte_threshold=0xE6)
        except ValueError as exc:
            skipped_profile.append((snes_id, str(exc)))
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
            f"Selected translation blob is {len(blob)} bytes, exceeding the stock allocation "
            f"of {STOCK_BLOB_BYTES}; relocation is deliberately not supported by this test utility"
        )

    patched = bytearray(apply_ips(bytearray(base), ALL_PATCH.read_bytes()))
    table_start = RESOURCE_POINTER_TABLE
    table_end = table_start + RESOURCE_COUNT * 2
    blob_start = CA_BASE + FIRST_RESOURCE_POINTER
    blob_end = blob_start + len(blob)
    stock_blob_end = blob_start + STOCK_BLOB_BYTES

    patched[table_start:table_end] = table
    patched[blob_start:blob_end] = blob
    # Preserve bytes after the new logical end exactly as they were in the aggregate
    # build.  They are unreachable stale stock-resource bytes until stock_blob_end;
    # critically, no write crosses the original allocation boundary.
    if blob_end > stock_blob_end:
        raise AssertionError("resource write crossed stock allocation")

    update_checksum(patched)
    patch = make_ips(base, bytes(patched))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(patch)

    print(f"Translated resources: {len(translations)}")
    print(f"Categories: {', '.join(args.categories)}")
    print(f"Representation-only normalizations: {normalization_count}")
    print(f"Skipped for current $E6 runtime profile: {len(skipped_profile)}")
    for snes_id, reason in skipped_profile:
        print(f"  - {snes_id}: {reason}")
    print(f"Blob: {len(blob)} / {STOCK_BLOB_BYTES} bytes ({len(blob)-STOCK_BLOB_BYTES:+d})")
    print(f"Logical end: CA:{FIRST_RESOURCE_POINTER + len(blob):04X}")
    print(f"Autonomous clean-USA IPS: {args.output}")


if __name__ == "__main__":
    main()
