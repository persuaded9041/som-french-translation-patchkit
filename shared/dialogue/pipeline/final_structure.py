"""Apply user-validated final dialogue structural payload edits without prose.

Round 85.55 exposed a small class of speaker-boundary defects that cannot be
represented by spaces/newlines alone: a stock PLAYER_NAME may need to move into
the translated carrier after a reviewed page break, a clear-only marker may
move between the event stream and a carrier, or a punctuation-only stock
carrier may need to remain visible.  The recipe stores only carrier IDs and a
small enum of structural operations.  No French words are stored here.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache

from .common import ROOT, _load_recipe_document
from shared.dialogue.codec import TRANSLATION_CLEAR

DIALOGUE_FINAL_STRUCTURE_RECIPES = ROOT / "recipes" / "android" / "dialogues_final_structure.json"
_ALLOWED_OPERATIONS = {
    "inline_omitted_player_name_with_clear",
    "add_leading_clear",
    "remove_leading_clear",
    "preserve_source_punctuation_carrier",
    "prepend_source_leading_punctuation",
}
_PUNCTUATION_ONLY_RE = re.compile(r"^[\s:;,.!?…'\"()\-–—]+$")
_LEADING_PUNCTUATION_RE = re.compile(r"^([\s:;,.!?…'\"()\-–—]+)")


@lru_cache(maxsize=1)
def _recipe_index() -> dict[str, dict[str, str]]:
    document = _load_recipe_document(
        DIALOGUE_FINAL_STRUCTURE_RECIPES,
        label="Dialogue final-structure recipes",
        expected={"format_version": 1},
    )
    events = document.get("events", {})
    if not isinstance(events, dict):
        raise ValueError("Dialogue final-structure recipes must contain an events object")
    result: dict[str, dict[str, str]] = {}
    for event_id, event in events.items():
        if not isinstance(event, dict) or set(event) != {"carriers"}:
            raise ValueError(f"Final-structure ${event_id}: expected only carriers")
        carriers = event.get("carriers")
        if not isinstance(carriers, dict):
            raise ValueError(f"Final-structure ${event_id}: carriers must be an object")
        rendered: dict[str, str] = {}
        for text_id, spec in carriers.items():
            if not isinstance(spec, dict) or set(spec) != {"operation"}:
                raise ValueError(f"Final-structure ${event_id}/{text_id}: invalid recipe payload")
            operation = spec.get("operation")
            if operation not in _ALLOWED_OPERATIONS:
                raise ValueError(f"Final-structure ${event_id}/{text_id}: unsupported operation {operation!r}")
            rendered[str(text_id)] = str(operation)
        result[str(event_id)] = rendered
    return result


def _text_token_index(event: dict, text_id: str) -> int:
    indexes = [
        index for index, token in enumerate(event.get("tokens", []))
        if token.get("type") in {"text", "ending_text"} and token.get("id") == text_id
    ]
    if len(indexes) != 1:
        raise ValueError(f"Final-structure ${event.get('event_id')}/{text_id}: carrier not unique in source event")
    return indexes[0]


def _source_text(event: dict, text_id: str) -> str:
    token = event["tokens"][_text_token_index(event, text_id)]
    source = token.get("source")
    if not isinstance(source, str):
        raise ValueError(f"Final-structure ${event.get('event_id')}/{text_id}: source text missing")
    return source


def apply_validated_final_structure(
    event: dict,
    translations: dict[str, str],
    *,
    structural_command_overrides: dict[int, tuple[str, str] | None] | None = None,
) -> tuple[dict[str, str], list[dict]]:
    """Replay reviewed structural-only speaker/punctuation edits for one event."""
    event_id = str(event.get("event_id"))
    recipes = _recipe_index().get(event_id)
    if not recipes:
        return translations, []

    current = dict(translations)
    overrides = dict(structural_command_overrides or {})
    repairs: list[dict] = []
    tokens = event.get("tokens", [])

    for text_id, operation in recipes.items():
        before = current.get(text_id)

        if operation == "inline_omitted_player_name_with_clear":
            if before is None:
                raise ValueError(f"Final-structure ${event_id}/{text_id}: translated carrier missing")
            index = _text_token_index(event, text_id)
            if index <= 0:
                raise ValueError(f"Final-structure ${event_id}/{text_id}: no preceding command")
            command = tokens[index - 1]
            if command.get("type") != "command" or command.get("name") != "PLAYER_NAME":
                raise ValueError(f"Final-structure ${event_id}/{text_id}: preceding command is not PLAYER_NAME")
            if overrides.get(index - 1, "__missing__") is not None:
                raise ValueError(
                    f"Final-structure ${event_id}/{text_id}: preceding PLAYER_NAME must be omitted by reviewed override"
                )
            args = command.get("args", "")
            try:
                player_index = int(args, 16)
            except ValueError as exc:
                raise ValueError(f"Final-structure ${event_id}/{text_id}: malformed PLAYER_NAME args {args!r}") from exc
            if player_index not in {0, 1, 2}:
                raise ValueError(f"Final-structure ${event_id}/{text_id}: unsupported PLAYER_NAME index {player_index}")
            if "%S(" in before:
                raise ValueError(f"Final-structure ${event_id}/{text_id}: carrier already contains a dynamic player placeholder")
            after = f"{TRANSLATION_CLEAR}%S({player_index},0){before}"

        elif operation == "add_leading_clear":
            if before is None:
                raise ValueError(f"Final-structure ${event_id}/{text_id}: translated carrier missing")
            if before.startswith(TRANSLATION_CLEAR):
                raise ValueError(f"Final-structure ${event_id}/{text_id}: leading clear already present")
            after = TRANSLATION_CLEAR + before

        elif operation == "remove_leading_clear":
            if before is None or not before.startswith(TRANSLATION_CLEAR):
                raise ValueError(f"Final-structure ${event_id}/{text_id}: expected a leading clear marker")
            after = before[len(TRANSLATION_CLEAR):]

        elif operation == "preserve_source_punctuation_carrier":
            source = _source_text(event, text_id)
            if not source or not _PUNCTUATION_ONLY_RE.fullmatch(source):
                raise ValueError(
                    f"Final-structure ${event_id}/{text_id}: source carrier is not punctuation-only: {source!r}"
                )
            if before not in {None, "", source}:
                raise ValueError(
                    f"Final-structure ${event_id}/{text_id}: refusing to overwrite non-empty translated prose"
                )
            after = source.strip()

        elif operation == "prepend_source_leading_punctuation":
            if before is None:
                raise ValueError(f"Final-structure ${event_id}/{text_id}: translated carrier missing")
            source = _source_text(event, text_id)
            match = _LEADING_PUNCTUATION_RE.match(source)
            if not match:
                raise ValueError(f"Final-structure ${event_id}/{text_id}: source has no leading punctuation")
            punctuation = match.group(1).strip()
            if not punctuation or not _PUNCTUATION_ONLY_RE.fullmatch(punctuation):
                raise ValueError(f"Final-structure ${event_id}/{text_id}: unsafe source punctuation {punctuation!r}")
            if before.lstrip().startswith(punctuation):
                raise ValueError(f"Final-structure ${event_id}/{text_id}: source punctuation already present")
            after = punctuation + " " + before.lstrip()

        else:  # pragma: no cover - guarded during recipe load
            raise AssertionError(operation)

        if after != before:
            current[text_id] = after
            repairs.append({
                "text_id": text_id,
                "operation": operation,
                "semantic_payload_changed": operation not in {"add_leading_clear", "remove_leading_clear"},
                "translated_prose_hardcoded": False,
            })

    return current, repairs
