"""Replay the user-validated layout delta after final structural speaker edits."""
from __future__ import annotations

from functools import lru_cache
import re

from .common import ROOT, _load_recipe_section
from .final_layout import _split_layout, _semantic_sha256

DIALOGUE_REVIEW_RECIPES = ROOT / "recipes" / "android" / "dialogues_review.json"


@lru_cache(maxsize=1)
def _recipe_index() -> dict[str, dict[str, dict]]:
    document = _load_recipe_section(
        DIALOGUE_REVIEW_RECIPES, "post_structure_layout",
        label="Dialogue post-structure layout recipes",
        expected={"format_version": 1},
    )
    events = document.get("events", {})
    if not isinstance(events, dict):
        raise ValueError("Dialogue post-structure layout recipes must contain an events object")
    result: dict[str, dict[str, dict]] = {}
    for event_id, event in events.items():
        if not isinstance(event, dict) or set(event) != {"carriers"}:
            raise ValueError(f"Post-structure layout ${event_id}: expected only carriers")
        carriers = event.get("carriers", {})
        if not isinstance(carriers, dict):
            raise ValueError(f"Post-structure layout ${event_id}: carriers must be an object")
        rendered: dict[str, dict] = {}
        for text_id, recipe in carriers.items():
            if not isinstance(recipe, dict):
                raise ValueError(f"Post-structure layout ${event_id}/{text_id}: recipe must be an object")
            if set(recipe) != {"semantic_sha256", "semantic_part_count", "seps"}:
                raise ValueError(f"Post-structure layout ${event_id}/{text_id}: unsupported recipe keys")
            seps = recipe.get("seps")
            if not isinstance(seps, list) or not all(isinstance(value, str) for value in seps):
                raise ValueError(f"Post-structure layout ${event_id}/{text_id}: invalid separators")
            if any(re.search(r"[^ \n\f]", value) for value in seps):
                raise ValueError(f"Post-structure layout ${event_id}/{text_id}: separators contain non-layout data")
            semantic_count = int(recipe.get("semantic_part_count", -1))
            semantic_hash = str(recipe.get("semantic_sha256", ""))
            if semantic_count < 1 or len(seps) != semantic_count + 1:
                raise ValueError(f"Post-structure layout ${event_id}/{text_id}: separator/count mismatch")
            if not re.fullmatch(r"[0-9a-f]{64}", semantic_hash):
                raise ValueError(f"Post-structure layout ${event_id}/{text_id}: invalid semantic SHA-256")
            rendered[str(text_id)] = {
                "semantic_part_count": semantic_count,
                "semantic_sha256": semantic_hash,
                "seps": list(seps),
            }
        result[str(event_id)] = rendered
    return result


def apply_validated_post_structure_layout(
    event_id: str,
    translations: dict[str, str],
) -> tuple[dict[str, str], list[dict]]:
    recipes = _recipe_index().get(str(event_id))
    if not recipes:
        return translations, []
    current = dict(translations)
    applied: list[dict] = []
    for text_id, recipe in recipes.items():
        if text_id not in current:
            raise ValueError(f"Post-structure layout ${event_id}/{text_id}: carrier missing")
        parts, old_seps = _split_layout(current[text_id])
        if len(parts) != recipe["semantic_part_count"]:
            raise ValueError(
                f"Post-structure layout ${event_id}/{text_id}: semantic part count drifted "
                f"({len(parts)} != {recipe['semantic_part_count']})"
            )
        actual_hash = _semantic_sha256(parts)
        if actual_hash != recipe["semantic_sha256"]:
            raise ValueError(
                f"Post-structure layout ${event_id}/{text_id}: semantic payload fingerprint drifted"
            )
        seps = recipe["seps"]
        rebuilt = seps[0] + "".join(part + seps[index + 1] for index, part in enumerate(parts))
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
