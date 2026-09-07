"""Load sparse translation JSON files bound to canonical source assets by text ID."""
from __future__ import annotations

import json
from pathlib import Path

FORMAT_VERSION = 1


def source_entries(document: dict) -> list[dict]:
    """Recursively return all source dictionaries carrying both ``id`` and ``source``."""
    found: list[dict] = []

    def walk(value) -> None:
        if isinstance(value, dict):
            if isinstance(value.get("id"), str) and "source" in value:
                found.append(value)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(document)
    ids = [entry["id"] for entry in found]
    if len(ids) != len(set(ids)):
        duplicates = sorted({text_id for text_id in ids if ids.count(text_id) > 1})
        raise ValueError("Duplicate canonical text ID(s): " + ", ".join(duplicates))
    return found


def load_translation(path: Path, source_document: dict, *, source_asset: str) -> dict[str, str]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("format_version") != FORMAT_VERSION:
        raise ValueError(f"{path.name}: unsupported translation format")
    if document.get("language") != "fr":
        raise ValueError(f"{path.name}: expected language 'fr'")
    if document.get("source_asset") != source_asset:
        raise ValueError(
            f"{path.name}: source_asset must be {source_asset!r}, got {document.get('source_asset')!r}"
        )

    canonical = {entry["id"]: entry for entry in source_entries(source_document)}
    translations: dict[str, str] = {}
    groups = document.get("groups")
    if not isinstance(groups, list):
        raise ValueError(f"{path.name}: missing groups list")
    for group in groups:
        entries = group.get("entries")
        if not isinstance(entries, list):
            raise ValueError(f"{path.name}: group {group.get('group')!r} has no entries list")
        for entry in entries:
            text_id = entry.get("id")
            text = entry.get("text")
            if not isinstance(text_id, str) or not isinstance(text, str):
                raise ValueError(f"{path.name}: every translation entry needs string id/text")
            if text_id in translations:
                raise ValueError(f"{path.name}: duplicate translation ID {text_id}")
            if text_id not in canonical and not text_id.startswith("new:"):
                raise ValueError(f"{path.name}: translation ID {text_id} is absent from {source_asset}")
            translations[text_id] = text
    return translations



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
            if not isinstance(name, str) or not isinstance(args, str) or not isinstance(before_id, str):
                raise ValueError(f"Structural omission ${event_id}: malformed command spec")
            if before_id not in suppressed:
                raise ValueError(
                    f"Structural omission ${event_id}: command anchor {before_id} is not a suppressed semantic ID"
                )
            target_index = text_index[before_id]
            command_index = target_index - 1
            if command_index < 0:
                raise ValueError(f"Structural omission ${event_id}: no command before {before_id}")
            token = tokens[command_index]
            if token.get("type") != "command" or token.get("name") != name or token.get("args", "") != args:
                raise ValueError(
                    f"Structural omission ${event_id}: expected {name} {args!r} immediately before {before_id}"
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

def require(translations: dict[str, str], ids: list[str] | tuple[str, ...], *, context: str) -> list[str]:
    missing = [text_id for text_id in ids if text_id not in translations]
    if missing:
        raise ValueError(f"{context}: missing translation ID(s): " + ", ".join(missing))
    return [translations[text_id] for text_id in ids]
