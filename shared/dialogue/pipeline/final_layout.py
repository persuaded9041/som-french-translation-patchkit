"""Apply user-validated final dialogue layout without storing translated prose.

The recipe stores only event/carrier IDs, a SHA-256 fingerprint of the semantic
(non-layout) carrier chunks, and the reviewed separators between those chunks.
Actual words always come from the canonical dialogue formatter (ultimately
Android FR and the already-reviewed structural recipes/manual supplements).
If the semantic payload drifts, generation fails loudly instead of replaying a
stale layout onto different prose.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
import re

from .common import ROOT, _load_recipe_document

DIALOGUE_FINAL_LAYOUT_RECIPES = ROOT / "recipes" / "android" / "dialogues_final_layout.json"
_LAYOUT_SEPARATOR_RE = re.compile(r"[ \n\f]+")


def _split_layout(text: str) -> tuple[list[str], list[str]]:
    """Return semantic chunks and the layout separators around/between them.

    Only ordinary spaces, explicit NEWLINE markup (``\n``), and generated page
    boundaries (``\f`` = WAIT $00 + TEXT_CLEAR in translation markup) are
    considered mutable layout. All other bytes/markup remain part of the
    semantic chunks and therefore participate in the fingerprint.
    """
    parts: list[str] = []
    match = _LAYOUT_SEPARATOR_RE.match(text)
    if match:
        seps = [match.group(0)]
        pos = match.end()
    else:
        seps = [""]
        pos = 0

    while pos < len(text):
        match = _LAYOUT_SEPARATOR_RE.search(text, pos)
        if match:
            part = text[pos:match.start()]
            if not part:
                raise ValueError(f"Final-layout parser found empty semantic chunk in {text!r}")
            parts.append(part)
            seps.append(match.group(0))
            pos = match.end()
        else:
            part = text[pos:]
            if not part:
                raise ValueError(f"Final-layout parser found empty semantic tail in {text!r}")
            parts.append(part)
            seps.append("")
            pos = len(text)

    if not parts or len(seps) != len(parts) + 1:
        raise ValueError(f"Final-layout parser could not decompose carrier {text!r}")
    return parts, seps


def _semantic_sha256(parts: list[str]) -> str:
    payload = json.dumps(parts, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@lru_cache(maxsize=1)
def _recipe_index() -> dict[str, dict[str, dict]]:
    document = _load_recipe_document(
        DIALOGUE_FINAL_LAYOUT_RECIPES,
        label="Dialogue final-layout recipes",
        expected={"format_version": 1},
    )
    events = document.get("events", {})
    if not isinstance(events, dict):
        raise ValueError("Dialogue final-layout recipes must contain an events object")

    result: dict[str, dict[str, dict]] = {}
    for event_id, event in events.items():
        carriers = event.get("carriers", {})
        if not isinstance(carriers, dict):
            raise ValueError(f"Final-layout ${event_id}: carriers must be an object")
        rendered: dict[str, dict] = {}
        for text_id, recipe in carriers.items():
            seps = recipe.get("seps")
            if not isinstance(seps, list) or not all(isinstance(value, str) for value in seps):
                raise ValueError(f"Final-layout ${event_id}/{text_id}: invalid separators")
            if any(re.search(r"[^ \n\f]", value) for value in seps):
                raise ValueError(f"Final-layout ${event_id}/{text_id}: separators contain non-layout data")
            semantic_count = int(recipe.get("semantic_part_count", -1))
            semantic_hash = str(recipe.get("semantic_sha256", ""))
            if semantic_count < 1 or len(seps) != semantic_count + 1:
                raise ValueError(f"Final-layout ${event_id}/{text_id}: separator/count mismatch")
            if not re.fullmatch(r"[0-9a-f]{64}", semantic_hash):
                raise ValueError(f"Final-layout ${event_id}/{text_id}: invalid semantic SHA-256")
            rendered[str(text_id)] = {
                "semantic_part_count": semantic_count,
                "semantic_sha256": semantic_hash,
                "seps": list(seps),
            }
        result[str(event_id)] = rendered
    return result


def apply_validated_final_layout(
    event_id: str,
    translations: dict[str, str],
) -> tuple[dict[str, str], list[dict]]:
    """Replay reviewed layout for one event after verifying semantic identity."""
    recipes = _recipe_index().get(str(event_id))
    if not recipes:
        return translations, []

    current = dict(translations)
    applied: list[dict] = []
    for text_id, recipe in recipes.items():
        if text_id not in current:
            raise ValueError(f"Final-layout ${event_id}/{text_id}: carrier missing from generated event")
        parts, old_seps = _split_layout(current[text_id])
        if len(parts) != recipe["semantic_part_count"]:
            raise ValueError(
                f"Final-layout ${event_id}/{text_id}: semantic part count drifted "
                f"({len(parts)} != {recipe['semantic_part_count']})"
            )
        actual_hash = _semantic_sha256(parts)
        if actual_hash != recipe["semantic_sha256"]:
            raise ValueError(
                f"Final-layout ${event_id}/{text_id}: semantic payload fingerprint drifted; "
                "refresh/review the layout recipe instead of applying it blindly"
            )
        seps = recipe["seps"]
        rebuilt = seps[0] + "".join(
            part + seps[index + 1] for index, part in enumerate(parts)
        )
        if rebuilt != current[text_id]:
            current[text_id] = rebuilt
            applied.append({
                "text_id": text_id,
                "semantic_sha256": actual_hash,
                "old_seps": old_seps,
                "new_seps": list(seps),
                "semantic_payload_changed": False,
            })
    return current, applied
