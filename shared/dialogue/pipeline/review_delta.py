"""Replay the final user-validated Round-85 review delta without localized prose.

This layer is intentionally late. It can only rearrange already-generated carrier
content, append payloads by Android-FR ID, alter punctuation/control/layout, or
replay reviewed layout fingerprints. Recipe data must never contain translated
prose.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache

from .common import ROOT, _load_recipe_document, normalize_android_prose
from .final_layout import _split_layout, _semantic_sha256

RECIPE = ROOT / "recipes" / "android" / "dialogues_round85_review.json"

@lru_cache(maxsize=1)
def load_round85_review_recipe() -> dict:
    doc = _load_recipe_document(RECIPE, label="Round-85 reviewed dialogue delta", expected={"format_version": 1})
    forbidden = re.compile(r"[A-Za-zÀ-ÿ]{3,}")
    # Operations/layout are structural only. Reasons/strategy labels and IDs are metadata.
    for event_id, event in doc.get("events", {}).items():
        for op in event.get("operations", []):
            if "text" in op or "prose" in op:
                raise ValueError(f"Round-85 review ${event_id}: localized prose key forbidden")
            if op.get("operation") == "prepend_punctuation":
                value = op.get("value", "")
                if re.search(r"[^\s:;,.!?…'\"()\-–—]", value):
                    raise ValueError(f"Round-85 review ${event_id}: unsafe punctuation payload")
        for text_id, spec in event.get("layout", {}).items():
            seps = spec.get("seps", [])
            if any(re.search(r"[^ \n\f]", value) for value in seps):
                raise ValueError(f"Round-85 review ${event_id}/{text_id}: non-layout separator")
    return doc


def reviewed_structural_command_overrides() -> list[dict]:
    return list(load_round85_review_recipe().get("structural_command_overrides", []))


def reviewed_choice_option_position_overrides() -> list[dict]:
    return list(load_round85_review_recipe().get("choice_option_position_overrides", []))

def reviewed_appended_entry_order() -> list[str]:
    return list(load_round85_review_recipe().get("appended_entry_order", []))


def _apply_operation(current: dict[str, str], op: dict, french: dict[int, str]) -> None:
    kind = op["operation"]
    text_id = op.get("text_id")
    if kind == "set_empty":
        current[text_id] = ""
        return
    if kind == "set_layout_literal":
        value = op.get("value", "")
        if re.search(r"[^ \n\f]", value):
            raise ValueError("set_layout_literal may contain layout only")
        current[text_id] = value
        return
    if kind == "strip_trailing_choice_decoration":
        before = current[text_id]
        after = re.sub(r"\s*\)\s*$", "", before)
        if after == before:
            raise ValueError(f"{text_id}: expected trailing choice decoration")
        current[text_id] = after
        return
    if kind == "replace_terminal_open_quote_with_close":
        before = current[text_id]
        if not before.endswith("“"):
            raise ValueError(f"{text_id}: expected terminal opening quote")
        current[text_id] = before[:-1] + "”"
        return
    if kind == "remove_leading_clear":
        before = current[text_id]
        if not before.startswith("\v"):
            raise ValueError(f"{text_id}: expected leading clear")
        current[text_id] = before[1:]
        return
    if kind == "add_leading_clear":
        before = current[text_id]
        if before.startswith("\v"):
            raise ValueError(f"{text_id}: leading clear already present")
        current[text_id] = "\v" + before
        return
    if kind == "prepend_punctuation":
        current[text_id] = op["value"] + current[text_id].lstrip()
        return
    if kind == "collapse_duplicate_percent":
        before = current[text_id]
        after = before.replace("%%", "%")
        if after == before:
            raise ValueError(f"{text_id}: expected duplicated percent")
        current[text_id] = after
        return
    if kind == "append_android":
        before = current.get(text_id)
        if before is None:
            raise ValueError(f"{text_id}: append target missing")
        units = []
        for android_id in op["android_ids"]:
            unit = normalize_android_prose(french[int(android_id)]).replace("_", "").strip()
            if unit:
                units.append(unit)
        payload = op.get("android_separator", " ").join(units)
        current[text_id] = before.rstrip() + op.get("separator", " ") + payload
        return
    if kind == "merge_carrier":
        source_id = op["source_id"]
        if text_id not in current or source_id not in current:
            raise ValueError(f"merge carrier missing {text_id}/{source_id}")
        current[text_id] = current[text_id].rstrip() + op.get("separator", "") + current[source_id].lstrip()
        if op.get("clear_source", True):
            current[source_id] = ""
        return
    if kind == "split_trailing_word_punctuation":
        source_id = op["source_id"]
        before = current[source_id]
        match = re.search(r"(?:^|\s)([^\s!?]+)\s*([!?])\s*$", before)
        if not match:
            raise ValueError(f"{source_id}: no trailing word+punctuation pair")
        current[source_id] = before[:match.start()].rstrip()
        current[op["word_target_id"]] = match.group(1)
        current[op["punct_target_id"]] = match.group(2)
        return
    if kind == "extract_numbered_choice_lines":
        source_id = op["source_id"]
        lines = current[source_id].splitlines()
        targets = op["targets"]
        if len(lines) < len(targets):
            raise ValueError(f"{source_id}: not enough numbered lines")
        for idx, target_id in enumerate(targets):
            match = re.match(r"^\s*\d+\s*:\s*(.*?)\s*(?:\))?\s*$", lines[idx])
            if not match or not match.group(1):
                raise ValueError(f"{source_id}: malformed numbered choice line {lines[idx]!r}")
            current[target_id] = match.group(1)
        if op.get("clear_source", True):
            current[source_id] = ""
        return
    raise ValueError(f"Unsupported Round-85 review operation {kind!r}")


def apply_round85_review_delta(event_id: str, translations: dict[str, str], french: dict[int, str]) -> tuple[dict[str, str], list[dict]]:
    spec = load_round85_review_recipe().get("events", {}).get(str(event_id))
    if not spec:
        return translations, []
    current = dict(translations)
    repairs = []
    for op in spec.get("operations", []):
        before = dict(current)
        _apply_operation(current, op, french)
        if current != before:
            repairs.append({"operation": op["operation"], "text_id": op.get("text_id"), "localized_prose_hardcoded": False})
    for text_id, layout in spec.get("layout", {}).items():
        if text_id not in current:
            raise ValueError(f"Round-85 review ${event_id}/{text_id}: layout carrier missing")
        if current[text_id] == "":
            if layout.get("semantic_part_count", 0) != 0:
                raise ValueError(f"Round-85 review ${event_id}/{text_id}: empty carrier/layout mismatch")
            value = layout.get("empty_layout", "")
            if re.search(r"[^ \n\f]", value):
                raise ValueError(f"Round-85 review ${event_id}/{text_id}: invalid empty layout")
            if current[text_id] != value:
                current[text_id] = value
                repairs.append({"operation": "layout", "text_id": text_id, "localized_prose_hardcoded": False})
            continue
        parts, old_seps = _split_layout(current[text_id])
        if len(parts) != layout["semantic_part_count"] or _semantic_sha256(parts) != layout["semantic_sha256"]:
            raise ValueError(f"Round-85 review ${event_id}/{text_id}: semantic payload fingerprint drifted")
        seps = layout["seps"]
        rebuilt = seps[0] + "".join(part + seps[i + 1] for i, part in enumerate(parts))
        if rebuilt != current[text_id]:
            current[text_id] = rebuilt
            repairs.append({"operation": "layout", "text_id": text_id, "old_seps": old_seps, "new_seps": seps, "localized_prose_hardcoded": False})
    return current, repairs
