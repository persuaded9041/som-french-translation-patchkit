"""Compatibility rules shared by aggregate builds."""
from __future__ import annotations

from .ips import patch_write_map
from .rom import CHECKSUM_RANGE
from .french_charset.charset import profile_threshold
from .name_dte import NAME_DTE_BASE_CONFIG_FILE, NAME_DTE_HOOK, NAME_DTE_ROUTE_FILE

DTE_THRESHOLD_OFFSET = 0x0016F6


def _uses_dialogue_dte_router(component) -> bool:
    return bool(component.metadata.get("dialogue_dte_router"))


def _uses_name_dte_router(component) -> bool:
    return bool(component.metadata.get("name_dte_router"))


def _uses_any_dte_router(component) -> bool:
    return _uses_dialogue_dte_router(component) or _uses_name_dte_router(component)


def _threshold(component) -> int | None:
    profile = component.metadata.get("shared_charset_profile")
    return profile_threshold(profile) if profile else None




def _declared_override(left, right, offset: int) -> bool:
    """Return True for an explicitly declared dependency overlay byte."""
    for owner, other in ((left, right), (right, left)):
        for rule in owner.metadata.get("overrides", []):
            if not isinstance(rule, dict) or rule.get("component") != other.id:
                continue
            try:
                start = int(rule["start"], 0) if isinstance(rule["start"], str) else int(rule["start"])
                end = int(rule["end"], 0) if isinstance(rule["end"], str) else int(rule["end"])
            except (KeyError, TypeError, ValueError) as exc:
                raise SystemExit(f"{owner.id}: malformed overrides rule: {rule!r}") from exc
            if start <= offset < end:
                if other.id not in owner.metadata.get("requires", []):
                    raise SystemExit(
                        f"{owner.id}: override of {other.id} must also declare it in requires"
                    )
                return True
    return False

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
                if _declared_override(left, right, offset):
                    declared += 1
                    continue
                left_threshold = _threshold(left)
                right_threshold = _threshold(right)
                if offset == DTE_THRESHOLD_OFFSET:
                    # Legacy threshold/profile components (`french_name_entry_extended` / `french_menus` / `french_intro`) may overlap
                    # the context-sensitive JML installed by `vwf_dialogues` / `french_dialogues` at the old
                    # immediate operand. In a combined build the later router
                    # owns this byte; without a router the historical max-
                    # threshold merge rule remains unchanged.
                    if _uses_any_dte_router(left) or _uses_any_dte_router(right):
                        declared += 1
                        continue
                    if (
                        left_threshold is not None
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
    # `vwf_dialogues` / `french_dialogues` install the full event-dialogue router and are later than 02 in
    # component order, so their hook owns the shared parser site in aggregate
    # builds. Never rewrite one byte of that JML with a legacy threshold.
    if any(_uses_dialogue_dte_router(component) for component in components):
        return

    thresholds = [value for component in components if (value := _threshold(component)) is not None]

    # `french_name_entry_extended` installs a smaller Name Entry / PLAYER_NAME router. A later legacy
    # component (notably 05) still writes its immediate threshold byte while
    # its dependency overlay IPS is being applied, so restore the name router's four-byte JML here
    # and move the historical max-threshold merge into the router config byte.
    if any(_uses_name_dte_router(component) for component in components):
        rom[NAME_DTE_ROUTE_FILE:NAME_DTE_ROUTE_FILE + len(NAME_DTE_HOOK)] = NAME_DTE_HOOK
        if thresholds:
            rom[NAME_DTE_BASE_CONFIG_FILE] = max(thresholds)
        return

    # No router selected: preserve the established max-profile merge rule used
    # by the legacy threshold-only components.
    if thresholds:
        rom[DTE_THRESHOLD_OFFSET] = max(thresholds)
