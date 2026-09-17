#!/usr/bin/env python3
"""Build standalone French resources, shop/forge responses, and fixed literals."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shared.core.asm import lo16
from shared.core.ips import make_ips
from shared.core.rom import ROM_SIZE_OFFSET, expand_rom, update_checksum, validate_base_rom
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
from shared.text.android_strings import read_string_table
from shared.text.shop import (
    D9_BASE,
    EXPECTED_BLOB_END as SHOP_EXPECTED_BLOB_END,
    EXPECTED_BLOB_START as SHOP_EXPECTED_BLOB_START,
    serialize_translated_pool,
)
from shared.text.translation_json import load_translation
from shared.text.battle import (
    BLOB_START as BATTLE_BLOB_START,
    POINTER_COUNT as BATTLE_POINTER_COUNT,
    POINTER_TABLE as BATTLE_POINTER_TABLE,
    _physical_records as battle_physical_records,
    verify_against_rom as verify_battle_against_rom,
)
from shared.text.battle_translation import build_translation_plan as build_battle_translation_plan
from shared.charset import (
    CHAR_TO_CODE,
    DIALOGUE_FRENCH_CHARS,
    glyph_bytes,
)

from shared.extracted.assets import (
    load_or_extract_battle,
    load_or_extract_resources,
    load_or_extract_shop,
)  # noqa: E402
ASSET = PROJECT_ROOT / "assets" / "text_resources.json"
BATTLE_ASSET = PROJECT_ROOT / "assets" / "battle_text.json"
STOCK_BLOB_BYTES = 7315
REVIEWED_OVERRIDES = PROJECT_ROOT / "translations" / "text_resources_reviewed_overrides.json"
REVIEWED_LITERAL_OVERRIDES = PROJECT_ROOT / "translations" / "french_resources_reviewed_literals.json"
SHOP_ASSET = PROJECT_ROOT / "assets" / "shop_text.json"
SHOP_DIRECT_TRANSLATION = PROJECT_ROOT / "translations" / "shop_text_french.json"
SHOP_REVIEWED_OVERRIDES = PROJECT_ROOT / "translations" / "shop_text_reviewed_overrides.json"
SHOP_ANDROID_RECIPE = PROJECT_ROOT / "recipes" / "android" / "shop_text_mapping.json"
SHOP_MAX_VISIBLE_CHARS = 28

# Battle/status text content is non-dialogue resource data and therefore lives
# in french_resources.  The stock C0 pool is too small for Android-FR, so the
# 107 text records are relocated to expanded bank $EE.  The two tiny event
# scripts at C0:637D/$637F stay in place: vwf_ui identifies those exact submits
# separately and owns presentation only.
ROM_TARGET_SIZE = 0x300000
BATTLE_RELOC_FILE = 0x2E6000
BATTLE_RELOC_CPU = 0xEE6000
BATTLE_RELOC_LIMIT = 0x2E7000
BATTLE_COPY_BANK_FILE = 0x005C2D
BATTLE_EXPECTED_COPY_BANK = 0xC0
BATTLE_RELOC_BANK = 0xEE
BATTLE_EVENT_SCRIPT_START = 0x00637D

# The old text pool is freed once every table/direct reference has been moved.
# Four tiny same-bank helpers live at its beginning and prepend the French
# Android template text before a stock dynamic number/item insertion.
BATTLE_HELPER_FILE = BATTLE_BLOB_START
BATTLE_HELPER_CPU = 0xC00000 | BATTLE_BLOB_START
BATTLE_HELPER_LIMIT = 0x005EF0
BATTLE_COPY_ROUTINE = 0x5C2A
BATTLE_WEAKNESS_NAME_CALL_FILE = 0x005A76
BATTLE_WEAKNESS_NAME_CALL = bytes.fromhex("20 06 5C")

BATTLE_REORDER_SITES = {
    "C0:6294": (0x0058C9, 0x5D08),
    "C0:62A0": (0x0058DB, 0x5CCF),
    "C0:62C6": (0x0058F1, 0x5CCF),
    "C0:62D7": (0x005A1C, 0x5CCF),
}

# Direct LDX #record operands outside the 88-entry table.  C0:62A2 is an empty
# unreferenced physical record; C0:637D/$637F are event scripts, not text.
BATTLE_DIRECT_REFERENCE_SITES = {
    "C0:6251": (0x005B10,),
    "C0:6256": (0x005B29, 0x005B6C, 0x005B99),
    "C0:6263": (0x005B38,),
    "C0:6265": (0x005B49,),
    "C0:6279": (0x005B7E,),
    "C0:628C": (0x0059AE,),
    "C0:6290": (0x0059DC,),
    "C0:6294": (0x0058D5,),
    "C0:62A0": (0x0058EB,),
    "C0:62A3": (0x00598A,),
    "C0:62B7": (0x005997,),
    "C0:62C6": (0x005901,),
    "C0:62D2": (0x005A09,),
    "C0:62D7": (0x005A31,),
    "C0:62E2": (0x0058B3,),
    "C0:62F3": (0x0058C1,),
    "C0:6303": (0x005BC4,),
    "C0:6310": (0x005BBA,),
}

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
    "system_message",
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



def load_reviewed_shop_overrides(source: dict) -> dict[str, str]:
    """Load the three explicitly reviewed SNES-specific D9 adaptations."""
    doc = json.loads(SHOP_REVIEWED_OVERRIDES.read_text(encoding="utf-8"))
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


def _android_shop_tables(namespace: str) -> tuple[dict[int, str], dict[int, str]]:
    if namespace not in {"systxt", "scrtxt"}:
        raise ValueError(f"Unsupported Android shop namespace {namespace!r}")
    en = read_string_table(PROJECT_ROOT / "sources" / "android" / f"{namespace}_en.bin")
    fr = read_string_table(PROJECT_ROOT / "sources" / "android" / f"{namespace}_fr.bin")
    if set(en) != set(fr):
        raise ValueError(f"Android {namespace} EN/FR ID sets differ")
    return en, fr


def validate_shop_provenance(
    source: dict,
    direct: dict[str, str],
    overrides: dict[str, str],
) -> None:
    """Keep the former french_shop_text provenance checks byte-for-byte equivalent."""
    recipe = json.loads(SHOP_ANDROID_RECIPE.read_text(encoding="utf-8"))
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
                tables[namespace] = _android_shop_tables(namespace)
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
                        f"{text_id}: direct Android EN identity changed: "
                        f"{en_values[0]!r} != {canonical[text_id]!r}"
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


def build_shop_payload(base: bytes) -> tuple[bytes, dict[int, int], dict[str, dict[str, int]], int, int]:
    """Build the promoted D9 shop/forge text now owned by french_resources."""
    source = load_or_extract_shop(base, SHOP_ASSET)
    direct = load_translation(SHOP_DIRECT_TRANSLATION, source, source_asset="shop_text.json")
    overrides = load_reviewed_shop_overrides(source)
    validate_shop_provenance(source, direct, overrides)

    translations = dict(direct)
    overlap = sorted(set(translations) & set(overrides))
    if overlap:
        raise ValueError("Direct/reviewed shop translation overlap: " + ", ".join(overlap))
    translations.update(overrides)

    canonical_ids = {entry["id"] for entry in source["records"]}
    if set(translations) != canonical_ids:
        missing = sorted(canonical_ids - set(translations))
        raise ValueError(
            "French resources component requires all nine reviewed shop records; missing: "
            + ", ".join(missing)
        )

    blob, references, stats = serialize_translated_pool(
        base,
        source,
        translations,
        max_visible_chars=SHOP_MAX_VISIBLE_CHARS,
    )
    return blob, references, stats, len(direct), len(overrides)


def _battle_relocated_payload(base: bytes, source: dict) -> tuple[bytes, dict[int, int], dict[str, int], dict]:
    """Build the relocated $EE battle/status string pool.

    Pending manual/layout records are deliberately kept in English, but they
    are re-encoded for the active $E8 DTE boundary so their visible stock text
    stays byte-semantically correct after relocation.  The two C0 event scripts
    are not copied at all.
    """
    verify_battle_against_rom(base, source)
    plan = build_battle_translation_plan(source)
    translated = plan["record_texts"]
    prefixes = plan["prefix_texts"]
    source_by_id = {entry["id"]: entry["source"] for entry in source["records"]}

    records = battle_physical_records(base)
    pool = bytearray()
    relocated: dict[int, int] = {}
    id_to_pointer: dict[str, int] = {}

    for offset, _raw in records:
        if offset >= BATTLE_EVENT_SCRIPT_START:
            continue
        text_id = f"C0:{offset:04X}"
        text = translated.get(text_id, source_by_id[text_id])
        pointer = (BATTLE_RELOC_CPU + len(pool)) & 0xFFFF
        relocated[offset] = pointer
        id_to_pointer[text_id] = pointer
        pool += encode_text_with_stock_dte(base, text, upper_dte_threshold=0xE8)
        pool.append(0x00)

    prefix_pointers: dict[str, int] = {}
    for text_id in BATTLE_REORDER_SITES:
        text = prefixes.get(text_id)
        if text is None:
            raise ValueError(f"{text_id}: missing reviewed Android runtime prefix")
        prefix_pointers[text_id] = (BATTLE_RELOC_CPU + len(pool)) & 0xFFFF
        pool += encode_text_with_stock_dte(base, text, upper_dte_threshold=0xE8)
        pool.append(0x00)

    if BATTLE_RELOC_FILE + len(pool) > BATTLE_RELOC_LIMIT:
        raise ValueError(
            f"Relocated battle-text pool exceeds reserved $EE:6000-$6FFF: {len(pool)} bytes"
        )

    # Every table pointer must target a relocated text record.
    for index in range(BATTLE_POINTER_COUNT):
        old = int.from_bytes(
            base[BATTLE_POINTER_TABLE + index * 2:BATTLE_POINTER_TABLE + index * 2 + 2],
            "little",
        )
        if old not in relocated:
            raise ValueError(f"Battle pointer-table target ${old:04X} was not relocated")

    # Every code-owned direct record must likewise exist in the new pool and
    # still match its clean-ROM immediate operand before we rewrite it.
    for text_id, sites in BATTLE_DIRECT_REFERENCE_SITES.items():
        old = int(text_id.split(":", 1)[1], 16)
        if old not in relocated:
            raise ValueError(f"{text_id}: direct record was not relocated")
        for site in sites:
            actual = int.from_bytes(base[site:site + 2], "little")
            if actual != old:
                raise ValueError(
                    f"{text_id}: clean-ROM direct reference mismatch at C0:${site:04X}: "
                    f"${actual:04X}"
                )

    return bytes(pool), relocated, prefix_pointers, plan["stats"]


def _battle_reorder_helpers(prefix_pointers: dict[str, int]) -> tuple[bytes, dict[str, int]]:
    """Build four 10-byte C0 helpers that preserve the stock dynamic inserts."""
    payload = bytearray()
    helper_pointers: dict[str, int] = {}
    for text_id, (_site, original_init) in BATTLE_REORDER_SITES.items():
        helper_cpu = BATTLE_HELPER_CPU + len(payload)
        helper_pointers[text_id] = helper_cpu & 0xFFFF
        prefix = prefix_pointers[text_id]
        payload += bytes((0x20, *lo16(original_init)))         # JSR original initializer
        payload += bytes((0xA2, *lo16(prefix)))                # LDX #French prefix
        payload += bytes((0x20, *lo16(BATTLE_COPY_ROUTINE)))   # JSR battle copy
        payload.append(0x60)                                   # RTS
    if BATTLE_HELPER_FILE + len(payload) > BATTLE_HELPER_LIMIT:
        raise ValueError("Battle template helpers exceed reclaimed C0 text-pool space")
    return bytes(payload), helper_pointers


def install_battle_text(rom: bytearray, base: bytes, source: dict) -> dict:
    """Install reviewed Android-FR battle/status content, leaving pending rows English."""
    if base[BATTLE_COPY_BANK_FILE] != BATTLE_EXPECTED_COPY_BANK:
        raise ValueError("Unexpected clean-ROM battle text source bank")
    if base[
        BATTLE_WEAKNESS_NAME_CALL_FILE:BATTLE_WEAKNESS_NAME_CALL_FILE + len(BATTLE_WEAKNESS_NAME_CALL)
    ] != BATTLE_WEAKNESS_NAME_CALL:
        raise ValueError("Unexpected clean-ROM weakness-name append call")

    pool, relocated, prefix_pointers, stats = _battle_relocated_payload(base, source)
    helpers, helper_pointers = _battle_reorder_helpers(prefix_pointers)

    rom[BATTLE_RELOC_FILE:BATTLE_RELOC_FILE + len(pool)] = pool

    # Pointer-table users now keep a 16-bit offset but read it from fixed bank $EE.
    for index in range(BATTLE_POINTER_COUNT):
        table_site = BATTLE_POINTER_TABLE + index * 2
        old = int.from_bytes(base[table_site:table_site + 2], "little")
        rom[table_site:table_site + 2] = relocated[old].to_bytes(2, "little")
    rom[BATTLE_COPY_BANK_FILE] = BATTLE_RELOC_BANK

    # Code-owned direct LDX #record references.
    for text_id, sites in BATTLE_DIRECT_REFERENCE_SITES.items():
        new_pointer = relocated[int(text_id.split(":", 1)[1], 16)]
        for site in sites:
            rom[site:site + 2] = new_pointer.to_bytes(2, "little")

    # Android weakness strings already include the complete French wording and
    # intentionally omit the subject name. Suppress only this exact stock name
    # append inside the weakness routine; all other dynamic-name builders remain stock.
    rom[
        BATTLE_WEAKNESS_NAME_CALL_FILE:BATTLE_WEAKNESS_NAME_CALL_FILE + len(BATTLE_WEAKNESS_NAME_CALL)
    ] = b"\xEA" * len(BATTLE_WEAKNESS_NAME_CALL)

    # Reclaimed old-pool helpers prepend French template text before the stock
    # dynamic value/item insertion, then the relocated record supplies suffix.
    rom[BATTLE_HELPER_FILE:BATTLE_HELPER_FILE + len(helpers)] = helpers
    for text_id, (site, original_init) in BATTLE_REORDER_SITES.items():
        expected = bytes((0x20, *lo16(original_init)))
        if base[site:site + 3] != expected:
            raise ValueError(f"{text_id}: unexpected clean-ROM template initializer")
        rom[site:site + 3] = bytes((0x20, *lo16(helper_pointers[text_id])))

    return {
        **stats,
        "relocated_records": len(relocated),
        "relocated_bytes": len(pool),
        "runtime_prefixes": len(prefix_pointers),
    }

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

    rom = expand_rom(base, ROM_TARGET_SIZE)

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

    # Battle/status content is another non-dialogue resource family owned here.
    # Translation prose comes from Android FR or reviewed JSON only; vwf_ui owns
    # the proportional presentation of the exact C0:637D/$637F banner submits.
    battle_source = load_or_extract_battle(base, BATTLE_ASSET)
    battle_stats = install_battle_text(rom, base, battle_source)

    # Currency text ownership: keep translation in french_resources and leave
    # vwf_ui responsible only for spacing/window geometry. Both shop sites are
    # fixed two-glyph literals, so standalone french_resources can safely
    # replace GP -> PO without touching renderer logic.
    literal_overrides = load_reviewed_literal_overrides(base)
    for offset, payload in literal_overrides.items():
        rom[offset:offset + len(payload)] = payload

    # Shop/forge response ownership was merged into french_resources. Preserve
    # the former standalone component's exact source/provenance/capacity checks
    # and write map, but do not install a second copy of the shared glyph/DTE
    # infrastructure: it is already installed above by this component.
    shop_blob, shop_references, shop_stats, shop_direct_count, shop_override_count = build_shop_payload(base)
    shop_pool_start = D9_BASE + SHOP_EXPECTED_BLOB_START
    rom[shop_pool_start:shop_pool_start + len(shop_blob)] = shop_blob
    for site, pointer in shop_references.items():
        if rom[site] != 0xA2:
            raise ValueError(f"Expected clean-ROM LDX at C0:${site:04X}")
        rom[site + 1:site + 3] = pointer.to_bytes(2, "little")

    rom[ROM_SIZE_OFFSET] = 0x0C
    update_checksum(rom)
    patch = make_ips(base, bytes(rom))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(patch)

    print("Resource translation cache reused: translations/text_resources_french.json" if cache_hit else "Resource translation regenerated and cached: translations/text_resources_french.json")
    print(f"Translated resources: {len(translations)}")
    print(f"Skipped for current profile: {len(skipped)}")
    print(f"Blob: {len(blob)} / {STOCK_BLOB_BYTES} bytes")
    print(f"Reviewed fixed literals: {len(literal_overrides)}")
    print(f"Battle/status relocated records: {battle_stats['relocated_records']}")
    print(f"Battle/status relocated pool: {battle_stats['relocated_bytes']} bytes")
    print(f"Battle/status Android mapped: {battle_stats['mapped_android']}")
    print(f"Battle/status reviewed overrides: {battle_stats['reviewed_overrides']}")
    print(f"Battle/status pending manual: {battle_stats['pending_manual']}")
    print(f"Battle/status pending layout: {battle_stats['pending_layout']}")
    shop_capacity = SHOP_EXPECTED_BLOB_END - SHOP_EXPECTED_BLOB_START
    shop_max_chars = max(item["visible_chars"] for item in shop_stats.values())
    print(f"Translated shop/forge responses: {len(shop_stats)}")
    print(f"Shop direct Android FR: {shop_direct_count}")
    print(f"Shop reviewed SNES adaptations: {shop_override_count}")
    print(
        f"Shop fixed-width maximum used: {shop_max_chars} / "
        f"{SHOP_MAX_VISIBLE_CHARS} visible characters"
    )
    print(
        f"D9 mini-event pool: {len(shop_blob)} / {shop_capacity} bytes "
        f"({shop_capacity - len(shop_blob)} bytes free)"
    )
    print(f"IPS: {args.output}")


if __name__ == "__main__":
    main()
