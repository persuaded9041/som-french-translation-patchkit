"""Validated translated-dialogue structural edits.

These helpers resolve narrowly scoped command omissions/replacements and choice
position overrides against the canonical dialogue token stream.  They live in
``shared.dialogue`` rather than the generic translation-JSON binder because the
metadata is specific to event dialogue structure.
"""
from __future__ import annotations

import json
from pathlib import Path

def resolve_structural_omission_token_indexes(
    translation_document: dict,
    source_document: dict,
    *,
    translations: dict[str, str] | None = None,
) -> dict[str, frozenset[int]]:
    """Resolve tightly-scoped user-validated command omissions.

    Translation text normally cannot alter event structure. The only supported
    exception is an explicitly documented Android-adaptation omission whose
    command is identified by exact adjacency to a suppressed semantic text ID.
    The canonical source asset remains untouched; callers receive token indexes
    to omit only during translated serialization/simulation.
    """
    raw = translation_document.get("user_validated_structural_omissions", [])
    if not isinstance(raw, list):
        raise ValueError("user_validated_structural_omissions must be a list")

    events = {event.get("event_id"): event for event in source_document.get("events", [])}
    result: dict[str, set[int]] = {}
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError("Every structural omission entry must be an object")
        event_id = entry.get("event_id")
        if not isinstance(event_id, str) or event_id not in events:
            raise ValueError(f"Unknown structural-omission event ID: {event_id!r}")
        suppressed = entry.get("suppressed_semantic_ids")
        commands = entry.get("suppressed_commands")
        reason = entry.get("reason")
        if not isinstance(suppressed, list) or not suppressed or not all(isinstance(v, str) for v in suppressed):
            raise ValueError(f"Structural omission ${event_id}: suppressed_semantic_ids must be a non-empty string list")
        if not isinstance(commands, list) or not commands:
            raise ValueError(f"Structural omission ${event_id}: suppressed_commands must be a non-empty list")
        if not isinstance(reason, str) or not reason:
            raise ValueError(f"Structural omission ${event_id}: reason is required")

        event = events[event_id]
        tokens = event.get("tokens", [])
        text_index = {
            token.get("id"): index
            for index, token in enumerate(tokens)
            if token.get("type") in {"text", "ending_text"}
        }
        for text_id in suppressed:
            if text_id not in text_index:
                raise ValueError(f"Structural omission ${event_id}: unknown semantic ID {text_id}")
            if translations is not None and translations.get(text_id) != "":
                raise ValueError(
                    f"Structural omission ${event_id}: {text_id} must be explicitly suppressed to empty text"
                )

        indexes = result.setdefault(event_id, set())
        for command in commands:
            if not isinstance(command, dict):
                raise ValueError(f"Structural omission ${event_id}: command spec must be an object")
            name = command.get("name")
            args = command.get("args", "")
            before_id = command.get("immediately_before_text_id")
            after_id = command.get("immediately_after_text_id")
            if not isinstance(name, str) or not isinstance(args, str):
                raise ValueError(f"Structural omission ${event_id}: malformed command spec")
            anchors = [
                ("before", before_id) if isinstance(before_id, str) else None,
                ("after", after_id) if isinstance(after_id, str) else None,
            ]
            anchors = [anchor for anchor in anchors if anchor is not None]
            if len(anchors) != 1:
                raise ValueError(
                    f"Structural omission ${event_id}: command spec must use exactly one immediate text anchor"
                )
            relation, anchor_id = anchors[0]
            if anchor_id not in suppressed:
                raise ValueError(
                    f"Structural omission ${event_id}: command anchor {anchor_id} is not a suppressed semantic ID"
                )
            target_index = text_index[anchor_id]
            command_index = target_index - 1 if relation == "before" else target_index + 1
            if command_index < 0 or command_index >= len(tokens):
                raise ValueError(
                    f"Structural omission ${event_id}: no command immediately {relation} {anchor_id}"
                )
            token = tokens[command_index]
            if token.get("type") != "command" or token.get("name") != name or token.get("args", "") != args:
                raise ValueError(
                    f"Structural omission ${event_id}: expected {name} {args!r} immediately {relation} {anchor_id}"
                )
            if command_index in indexes:
                raise ValueError(f"Structural omission ${event_id}: duplicate command omission at token {command_index}")
            indexes.add(command_index)

    return {event_id: frozenset(indexes) for event_id, indexes in result.items()}


def load_structural_omission_token_indexes(
    path: Path,
    source_document: dict,
    *,
    translations: dict[str, str] | None = None,
) -> dict[str, frozenset[int]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    return resolve_structural_omission_token_indexes(
        document, source_document, translations=translations
    )



def resolve_structural_command_overrides(
    translation_document: dict,
    source_document: dict,
) -> dict[str, dict[int, tuple[str, str] | None]]:
    """Resolve exact user-reviewed translated-only command rewrites/omissions.

    Unlike structural omissions tied to an empty text carrier, these edits are
    for regional dialogue resegmentation where a visible carrier must keep its
    text while an adjacent stock command changes ownership. Every edit is
    anchored to an exact neighboring text ID and validates the clean-USA
    command before returning a translated-only replacement. ``None`` means omit
    that one command. Canonical/source serialization never uses these edits.
    """
    raw = translation_document.get("user_validated_structural_command_overrides", [])
    if not isinstance(raw, list):
        raise ValueError("user_validated_structural_command_overrides must be a list")
    events = {event.get("event_id"): event for event in source_document.get("events", [])}
    result: dict[str, dict[int, tuple[str, str] | None]] = {}
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError("Every structural command override entry must be an object")
        event_id = entry.get("event_id")
        commands = entry.get("commands")
        reason = entry.get("reason")
        if not isinstance(event_id, str) or event_id not in events:
            raise ValueError(f"Unknown structural-command-override event ID: {event_id!r}")
        if not isinstance(commands, list) or not commands:
            raise ValueError(f"Structural command override ${event_id}: commands must be a non-empty list")
        if not isinstance(reason, str) or not reason:
            raise ValueError(f"Structural command override ${event_id}: reason is required")
        tokens = events[event_id].get("tokens", [])
        text_index = {
            token.get("id"): index
            for index, token in enumerate(tokens)
            if token.get("type") in {"text", "ending_text"}
        }
        event_result = result.setdefault(event_id, {})
        for spec in commands:
            if not isinstance(spec, dict):
                raise ValueError(f"Structural command override ${event_id}: command spec must be an object")
            name = spec.get("name")
            args = spec.get("args", "")
            before_id = spec.get("immediately_before_text_id")
            after_id = spec.get("immediately_after_text_id")
            omit = spec.get("omit", False)
            translated_name = spec.get("translated_name", name)
            translated_args = spec.get("translated_args", args)
            if not isinstance(name, str) or not isinstance(args, str):
                raise ValueError(f"Structural command override ${event_id}: malformed source command")
            anchors = [
                ("before", before_id) if isinstance(before_id, str) else None,
                ("after", after_id) if isinstance(after_id, str) else None,
            ]
            anchors = [a for a in anchors if a is not None]
            if len(anchors) != 1:
                raise ValueError(f"Structural command override ${event_id}: exactly one immediate text anchor is required")
            relation, anchor_id = anchors[0]
            if anchor_id not in text_index:
                raise ValueError(f"Structural command override ${event_id}: unknown anchor {anchor_id}")
            target_index = text_index[anchor_id]
            command_index = target_index - 1 if relation == "before" else target_index + 1
            if not (0 <= command_index < len(tokens)):
                raise ValueError(f"Structural command override ${event_id}: missing command {relation} {anchor_id}")
            token = tokens[command_index]
            if token.get("type") != "command" or token.get("name") != name or token.get("args", "") != args:
                raise ValueError(
                    f"Structural command override ${event_id}: expected {name} {args!r} immediately {relation} {anchor_id}"
                )
            if command_index in event_result:
                raise ValueError(f"Structural command override ${event_id}: duplicate token index {command_index}")
            if omit:
                if spec.get("translated_name") is not None or spec.get("translated_args") is not None:
                    # Omission specs should be unambiguous; source fields are enough.
                    raise ValueError(f"Structural command override ${event_id}: omit spec cannot also replace command")
                event_result[command_index] = None
            else:
                if not isinstance(translated_name, str) or not isinstance(translated_args, str):
                    raise ValueError(f"Structural command override ${event_id}: translated command must be strings")
                if translated_name != name:
                    raise ValueError(f"Structural command override ${event_id}: command-name changes are not supported")
                if translated_args == args:
                    raise ValueError(f"Structural command override ${event_id}: replacement must change command args")
                event_result[command_index] = (translated_name, translated_args)
    return result


def load_structural_command_overrides(path: Path, source_document: dict) -> dict[str, dict[int, tuple[str, str] | None]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    return resolve_structural_command_overrides(document, source_document)

def resolve_choice_option_position_overrides(
    translation_document: dict,
    source_document: dict,
) -> dict[str, dict[int, int]]:
    """Resolve generated, tightly-scoped CHOICE_OPTION position overrides.

    The canonical source keeps every stock command byte unchanged.  A translated
    build may move only an existing CHOICE_OPTION to the right, and only when the
    generated translation metadata identifies the exact event/token/source
    coordinate.  This supports VWF labels whose decoded character count exceeds
    the stock cell span even though their rendered pixels still fit.
    """
    raw = translation_document.get("choice_option_position_overrides", [])
    if not isinstance(raw, list):
        raise ValueError("choice_option_position_overrides must be a list")

    events = {event.get("event_id"): event for event in source_document.get("events", [])}
    result: dict[str, dict[int, int]] = {}
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError("Every choice-option position override must be an object")
        event_id = entry.get("event_id")
        token_index = entry.get("token_index")
        source_position = entry.get("source_position")
        translated_position = entry.get("translated_position")
        strategy = entry.get("strategy")
        if not isinstance(event_id, str) or event_id not in events:
            raise ValueError(f"Unknown choice-option override event ID: {event_id!r}")
        if not isinstance(token_index, int):
            raise ValueError(f"Choice-option override ${event_id}: token_index must be an integer")
        if not isinstance(source_position, int) or not isinstance(translated_position, int):
            raise ValueError(f"Choice-option override ${event_id}: positions must be integers")
        if not isinstance(strategy, str) or not strategy:
            raise ValueError(f"Choice-option override ${event_id}: strategy is required")
        if not (0 <= source_position < 32 and 0 <= translated_position < 32):
            raise ValueError(f"Choice-option override ${event_id}: positions must stay within 0..31")
        if translated_position <= source_position:
            raise ValueError(f"Choice-option override ${event_id}: only rightward moves are supported")

        tokens = events[event_id].get("tokens", [])
        if token_index < 0 or token_index >= len(tokens):
            raise ValueError(f"Choice-option override ${event_id}: invalid token index {token_index}")
        token = tokens[token_index]
        if token.get("type") != "command" or token.get("name") != "CHOICE_OPTION":
            raise ValueError(f"Choice-option override ${event_id}: token {token_index} is not CHOICE_OPTION")
        args = token.get("args", "").split()
        if len(args) != 1 or int(args[0], 16) != source_position:
            raise ValueError(
                f"Choice-option override ${event_id}: token {token_index} source coordinate does not match ${source_position:02X}"
            )
        event_result = result.setdefault(event_id, {})
        if token_index in event_result:
            raise ValueError(f"Choice-option override ${event_id}: duplicate token index {token_index}")
        event_result[token_index] = translated_position

    return result


def load_choice_option_position_overrides(path: Path, source_document: dict) -> dict[str, dict[int, int]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    return resolve_choice_option_position_overrides(document, source_document)

