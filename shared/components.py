"""Component metadata discovery for the patchkit."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class Component:
    id: str
    short_name: str
    name: str
    path: Path
    metadata: dict


def discover_components(root: Path) -> list[Component]:
    components: list[Component] = []
    for manifest in sorted((root / "components").glob("*/component.json")):
        metadata = json.loads(manifest.read_text(encoding="utf-8"))
        folder = manifest.parent.name
        if metadata.get("id") != folder:
            raise SystemExit(f"{manifest}: id must match directory name {folder!r}")
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
    orders = [component.metadata.get("build_order") for component in components]
    if any(not isinstance(order, int) for order in orders):
        raise SystemExit("Every component.json must define an integer build_order")
    if len(orders) != len(set(orders)):
        raise SystemExit("Duplicate component build_order in component.json")
    components.sort(key=lambda component: (component.metadata["build_order"], component.id))

    short_names = [component.short_name for component in components]
    if len(short_names) != len(set(short_names)):
        raise SystemExit("Duplicate component short_name in component.json")
    return components
