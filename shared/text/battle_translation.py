"""Reviewed Android-FR translation plan for the C0 battle/status text pool.

Identity/provenance lives in ``recipes/android/battle_text_mapping.json``.
French payload is read from the original Android ``systxt_fr.bin`` table at
build time.  Only explicit SNES-specific adaptations or pending manual entries
live in ``translations/battle_text_reviewed_overrides.json``.
"""
from __future__ import annotations

import json
from pathlib import Path

from shared.text.android_strings import read_string_table

ROOT = Path(__file__).resolve().parents[2]
MAPPING = ROOT / "recipes" / "android" / "battle_text_mapping.json"
OVERRIDES = ROOT / "translations" / "battle_text_reviewed_overrides.json"
ANDROID_EN = ROOT / "sources" / "android" / "systxt_en.bin"
ANDROID_FR = ROOT / "sources" / "android" / "systxt_fr.bin"

FORMAT_VERSION = 1


def _load_recipe(source: dict) -> list[dict]:
    doc = json.loads(MAPPING.read_text(encoding="utf-8"))
    if doc.get("format_version") != FORMAT_VERSION:
        raise ValueError("Unsupported battle-text Android mapping format")
    if doc.get("source_asset") != "battle_text.json":
        raise ValueError("battle-text mapping source_asset mismatch")
    if doc.get("android_namespace") != "systxt":
        raise ValueError("battle-text mapping must use Android systxt")

    records = doc.get("records")
    if not isinstance(records, list):
        raise ValueError("battle-text mapping has no records list")
    source_ids = [entry["id"] for entry in source["records"]]
    recipe_ids = [entry.get("snes_id") for entry in records]
    if recipe_ids != source_ids:
        raise ValueError("battle-text mapping must cover all 109 source records in source order")
    if len(set(recipe_ids)) != len(recipe_ids):
        raise ValueError("battle-text mapping contains duplicate source IDs")
    return records


def _load_overrides(source: dict) -> dict[str, dict]:
    doc = json.loads(OVERRIDES.read_text(encoding="utf-8"))
    if doc.get("format_version") != FORMAT_VERSION or doc.get("language") != "fr":
        raise ValueError("Unsupported battle-text reviewed override format")
    if doc.get("source_asset") != "battle_text.json":
        raise ValueError("battle-text reviewed override source_asset mismatch")

    canonical = {entry["id"]: entry["source"] for entry in source["records"]}
    out: dict[str, dict] = {}
    for entry in doc.get("entries", []):
        text_id = entry.get("id")
        if text_id not in canonical:
            raise ValueError(f"Unknown battle-text reviewed override ID {text_id!r}")
        if text_id in out:
            raise ValueError(f"Duplicate battle-text reviewed override {text_id}")
        if entry.get("source") != canonical[text_id]:
            raise ValueError(f"{text_id}: reviewed override source identity changed")
        status = entry.get("status")
        if status not in {"translated", "needs_manual_translation", "needs_layout_adaptation"}:
            raise ValueError(f"{text_id}: unsupported reviewed override status {status!r}")
        text = entry.get("text")
        if status == "translated":
            if not isinstance(text, str):
                raise ValueError(f"{text_id}: translated override requires string text")
        elif text is not None:
            raise ValueError(f"{text_id}: pending override must keep text null")
        out[text_id] = entry
    return out


def _one_value(table: dict[int, str], ids: list[int], *, label: str, text_id: str) -> str:
    values: list[str] = []
    for android_id in ids:
        if android_id not in table:
            raise ValueError(f"{text_id}: Android {label} ID {android_id} is missing")
        values.append(table[android_id])
    unique = set(values)
    if len(unique) != 1:
        raise ValueError(f"{text_id}: mapped Android {label} duplicates no longer agree")
    return values[0]


def _split_one_placeholder(template: str, *, text_id: str) -> tuple[str, str]:
    placeholders = [token for token in ("$0s", "$0d") if token in template]
    if len(placeholders) != 1 or template.count(placeholders[0]) != 1:
        raise ValueError(f"{text_id}: runtime-reorder template must contain exactly one supported placeholder")
    return tuple(template.split(placeholders[0], 1))  # type: ignore[return-value]


def build_translation_plan(source: dict) -> dict:
    """Return translated record payloads plus synthetic runtime prefixes.

    ``record_texts`` maps canonical C0 record IDs to the exact string that can
    replace that record under the existing SNES battle-string composition.
    ``prefix_texts`` contains the four Android template prefixes that require a
    tiny runtime prepend before the stock dynamic number/item insertion.
    Pending entries are intentionally absent and therefore remain clean-USA.
    """
    recipe = _load_recipe(source)
    overrides = _load_overrides(source)
    android_en = read_string_table(ANDROID_EN)
    android_fr = read_string_table(ANDROID_FR)
    if set(android_en) != set(android_fr):
        raise ValueError("Android systxt EN/FR ID sets differ")

    canonical = {entry["id"]: entry["source"] for entry in source["records"]}
    record_texts: dict[str, str] = {}
    prefix_texts: dict[str, str] = {}
    stats = {
        "mapped_android": 0,
        "reviewed_overrides": 0,
        "pending_manual": 0,
        "pending_layout": 0,
        "stock_control": 0,
    }

    for rec in recipe:
        text_id = rec["snes_id"]
        strategy = rec.get("strategy")
        status = rec.get("status")
        identity = rec.get("identity")
        override = overrides.get(text_id)

        if status == "needs_manual_translation":
            if override is None or override.get("status") != "needs_manual_translation":
                raise ValueError(f"{text_id}: missing explicit needs_manual_translation override entry")
            stats["pending_manual"] += 1
            continue
        if status == "needs_layout_adaptation":
            if override is None or override.get("status") != "needs_layout_adaptation":
                raise ValueError(f"{text_id}: missing explicit needs_layout_adaptation override entry")
            stats["pending_layout"] += 1
            continue
        if status == "stock_control":
            stats["stock_control"] += 1
            continue
        if status != "mapped":
            raise ValueError(f"{text_id}: unsupported mapping status {status!r}")

        if strategy == "reviewed_override":
            if override is None or override.get("status") != "translated":
                raise ValueError(f"{text_id}: missing translated reviewed override")
            record_texts[text_id] = override["text"]
            stats["reviewed_overrides"] += 1
            continue

        ids = rec.get("android_ids")
        if not isinstance(ids, list) or not ids or not all(isinstance(value, int) for value in ids):
            raise ValueError(f"{text_id}: mapped record requires Android IDs")
        en = _one_value(android_en, ids, label="EN", text_id=text_id)
        fr = _one_value(android_fr, ids, label="FR", text_id=text_id)

        # Exact-identity records get a cheap drift guard. Reviewed/template/
        # ordered relationships are intentionally not forced back to exact EN.
        if identity == "direct_exact" and en != canonical[text_id]:
            raise ValueError(
                f"{text_id}: direct Android EN identity changed: {en!r} != {canonical[text_id]!r}"
            )

        if strategy == "direct":
            record_texts[text_id] = fr.rstrip()
        elif strategy == "suffix":
            if fr.count("$0s") != 1:
                raise ValueError(f"{text_id}: suffix template no longer contains one $0s placeholder")
            prefix, suffix = fr.split("$0s", 1)
            if prefix:
                raise ValueError(f"{text_id}: suffix template gained French text before $0s")
            record_texts[text_id] = suffix.rstrip()
        elif strategy == "no_name":
            if "$0s" in fr or "$0d" in fr or "$1d" in fr:
                raise ValueError(f"{text_id}: no-name translation unexpectedly contains a placeholder")
            record_texts[text_id] = fr.rstrip()
        elif strategy == "between_subject_and_number":
            if fr.count("$0s") != 1 or fr.count("$1d") != 1:
                raise ValueError(f"{text_id}: level template placeholder shape changed")
            before_number, after_number = fr.split("$0s", 1)[1].split("$1d", 1)
            if after_number.strip() != "!":
                raise ValueError(f"{text_id}: level template suffix changed unexpectedly")
            record_texts[text_id] = before_number
        elif strategy == "after_number":
            if fr.count("$1d") != 1:
                raise ValueError(f"{text_id}: level template no longer contains one $1d")
            record_texts[text_id] = fr.split("$1d", 1)[1].rstrip()
        elif strategy == "template_reorder":
            prefix, suffix = _split_one_placeholder(fr, text_id=text_id)
            prefix_texts[text_id] = prefix
            record_texts[text_id] = suffix.rstrip()
        else:
            raise ValueError(f"{text_id}: unsupported battle translation strategy {strategy!r}")
        stats["mapped_android"] += 1

    # Every reviewed pending/translated override must be owned by one mapping row.
    recipe_ids = {rec["snes_id"] for rec in recipe}
    extra = set(overrides) - recipe_ids
    if extra:
        raise ValueError(f"Battle reviewed overrides not present in mapping: {sorted(extra)}")

    return {
        "record_texts": record_texts,
        "prefix_texts": prefix_texts,
        "stats": stats,
    }
