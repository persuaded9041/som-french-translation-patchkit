"""Compatibility rules shared by aggregate builds."""
from __future__ import annotations

from .ips import patch_write_map
from .rom import CHECKSUM_RANGE

DTE_THRESHOLD_OFFSET = 0x0016F6


def _threshold(component) -> int | None:
    value = component.metadata.get("direct_glyph_threshold")
    if value is None:
        return None
    return int(value, 0) if isinstance(value, str) else int(value)


def audit_overlaps(components, patch_data: dict[str, bytes]) -> tuple[int, int]:
    """Reject differing writes unless metadata declares a mergeable DTE threshold."""
    maps = {component.id: patch_write_map(patch_data[component.id])[0] for component in components}
    errors: list[tuple[str, str, int, int, int]] = []
    identical = declared = 0
    for index, left in enumerate(components):
        for right in components[index + 1:]:
            common = set(maps[left.id]) & set(maps[right.id])
            for offset in common:
                if offset in CHECKSUM_RANGE:
                    declared += 1
                    continue
                left_value = maps[left.id][offset]
                right_value = maps[right.id][offset]
                if left_value == right_value:
                    identical += 1
                    continue
                left_threshold = _threshold(left)
                right_threshold = _threshold(right)
                if (
                    offset == DTE_THRESHOLD_OFFSET
                    and left_threshold is not None
                    and right_threshold is not None
                    and left_value == left_threshold
                    and right_value == right_threshold
                ):
                    declared += 1
                    continue
                errors.append((left.id, right.id, offset, left_value, right_value))
    if errors:
        lines = ["Undeclared patch collision(s):"]
        for left, right, offset, left_value, right_value in errors[:20]:
            lines.append(
                f"  {left} / {right} @ 0x{offset:06X}: "
                f"${left_value:02X} vs ${right_value:02X}"
            )
        raise SystemExit("\n".join(lines))
    return identical, declared


def apply_merge_rules(rom: bytearray, components) -> None:
    thresholds = [value for component in components if (value := _threshold(component)) is not None]
    if thresholds:
        rom[DTE_THRESHOLD_OFFSET] = max(thresholds)
