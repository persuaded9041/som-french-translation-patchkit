"""Component metadata discovery for the patchkit."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Component:
    id: str
    short_name: str
    name: str
    path: Path
    metadata: dict[str, Any]


def _as_offset(value: object, *, component_id: str, field: str) -> int:
    try:
        return int(value, 0) if isinstance(value, str) else int(value)
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"{component_id}: {field} must be an integer/0x-prefixed offset") from exc


def _validate_manifest(folder: str, metadata: object, manifest: Path) -> dict[str, Any]:
    if not isinstance(metadata, dict):
        raise SystemExit(f"{manifest}: component manifest must be a JSON object")
    if metadata.get("id") != folder:
        raise SystemExit(f"{manifest}: id must match directory name {folder!r}")
    for key in ("short_name", "name"):
        if not isinstance(metadata.get(key), str) or not metadata[key]:
            raise SystemExit(f"{manifest}: {key} must be a non-empty string")
    if not isinstance(metadata.get("build_order"), int):
        raise SystemExit(f"{manifest}: build_order must be an integer")

    requires = metadata.get("requires", [])
    if not isinstance(requires, list) or any(not isinstance(item, str) for item in requires):
        raise SystemExit(f"{folder}: requires must be a list of component IDs")
    if len(requires) != len(set(requires)):
        raise SystemExit(f"{folder}: requires contains duplicate component IDs")

    overrides = metadata.get("overrides", [])
    if not isinstance(overrides, list):
        raise SystemExit(f"{folder}: overrides must be a list")
    for rule in overrides:
        if not isinstance(rule, dict) or not isinstance(rule.get("component"), str):
            raise SystemExit(f"{folder}: malformed override rule: {rule!r}")
        start = _as_offset(rule.get("start"), component_id=folder, field="override start")
        end = _as_offset(rule.get("end"), component_id=folder, field="override end")
        if not 0 <= start < end:
            raise SystemExit(f"{folder}: override range must satisfy 0 <= start < end: {rule!r}")
        if not isinstance(rule.get("reason"), str) or not rule["reason"]:
            raise SystemExit(f"{folder}: override rule needs a non-empty reason: {rule!r}")

    for flag in ("dialogue_dte_router", "name_dte_router", "aggregate_enabled", "french"):
        if flag in metadata and not isinstance(metadata[flag], bool):
            raise SystemExit(f"{folder}: {flag} must be boolean")
    if "shared_charset_profile" in metadata and not isinstance(metadata["shared_charset_profile"], str):
        raise SystemExit(f"{folder}: shared_charset_profile must be a string")
    return metadata


def discover_components(root: Path) -> list[Component]:
    components: list[Component] = []
    for manifest in sorted((root / "components").glob("*/component.json")):
        folder = manifest.parent.name
        metadata = _validate_manifest(
            folder,
            json.loads(manifest.read_text(encoding="utf-8")),
            manifest,
        )
        components.append(
            Component(
                id=folder,
                short_name=metadata["short_name"],
                name=metadata["name"],
                path=manifest.parent,
                metadata=metadata,
            )
        )
    if not components:
        raise SystemExit("No components found under components/*/component.json")

    # Public component IDs are semantic and intentionally unnumbered. Preserve the
    # established aggregate patch order explicitly through manifest build_order so
    # renaming/reorganizing component folders cannot silently change merge precedence.
    orders = [component.metadata["build_order"] for component in components]
    if len(orders) != len(set(orders)):
        raise SystemExit("Duplicate component build_order in component.json")
    components.sort(key=lambda component: (component.metadata["build_order"], component.id))

    short_names = [component.short_name for component in components]
    if len(short_names) != len(set(short_names)):
        raise SystemExit("Duplicate component short_name in component.json")

    by_id = {component.id: component for component in components}
    for component in components:
        for required_id in component.metadata.get("requires", []):
            required = by_id.get(required_id)
            if required is None:
                raise SystemExit(f"{component.id}: unknown required component {required_id!r}")
            if required.metadata["build_order"] >= component.metadata["build_order"]:
                raise SystemExit(
                    f"{component.id}: dependency {required_id!r} must have a lower build_order"
                )
            if component.metadata.get("aggregate_enabled", True) and not required.metadata.get("aggregate_enabled", True):
                raise SystemExit(
                    f"{component.id}: aggregate-enabled component cannot require aggregate-disabled "
                    f"component {required_id!r}"
                )
        for rule in component.metadata.get("overrides", []):
            overridden_id = rule["component"]
            if overridden_id not in by_id:
                raise SystemExit(f"{component.id}: override references unknown component {overridden_id!r}")
            if overridden_id not in component.metadata.get("requires", []):
                raise SystemExit(
                    f"{component.id}: override of {overridden_id!r} must also declare it in requires"
                )
    return components
