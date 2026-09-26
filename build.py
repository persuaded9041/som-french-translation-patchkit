#!/usr/bin/env python3
"""Build reusable component IPS files and optional default/locale aggregates."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

from shared.build.compatibility import apply_merge_rules, audit_overlaps
from shared.build.components import component_locale, discover_components
from shared.core.ips import apply_ips, make_ips
from shared.core.rom import update_checksum, validate_base_rom
from shared.extracted import materialize_all_assets

ROOT = Path(__file__).resolve().parent
DEFAULT_PATCH_DIR = ROOT / "patches"


def aggregate_components(components):
    """Components currently admitted to the validated aggregate/all.ips set."""
    return [component for component in components if component.metadata.get("aggregate_enabled", True)]


def us_aggregate_components(components):
    """Return aggregate components that are valid for the USA-only build."""
    selected = {
        component.id: component
        for component in aggregate_components(components)
        if component_locale(component) is None
    }
    changed = True
    while changed:
        changed = False
        for component_id, component in list(selected.items()):
            if any(required_id not in selected for required_id in component.metadata.get("requires", [])):
                del selected[component_id]
                changed = True
    return [component for component in components if component.id in selected]


def locale_aggregate_components(components, locale: str):
    """Return the default aggregate plus components for one named locale."""
    return [
        component
        for component in components
        if (
            component_locale(component) is None
            and component.metadata.get("aggregate_enabled", True)
        )
        or component_locale(component) == locale
    ]


def resolve_selection(values: list[str], components):
    aliases = {component.short_name: component for component in components}
    aliases.update({component.id: component for component in components})
    if not values or values == ["all"]:
        return aggregate_components(components)
    if "all" in values:
        raise SystemExit("Component 'all' must be used alone")
    selected = []
    for value in values:
        component = aliases.get(value)
        if component is None:
            raise SystemExit(f"Unknown component: {value}")
        if component not in selected:
            selected.append(component)

    by_id = {component.id: component for component in components}
    selected_ids = {component.id for component in selected}

    # Selecting a dependent component also rebuilds its declared prerequisites.
    # Patches are still authored against the clean USA ROM; `requires` expresses
    # application/aggregate order, not source-byte inheritance.
    pending = list(selected_ids)
    while pending:
        component_id = pending.pop()
        for required_id in by_id[component_id].metadata.get("requires", []):
            if required_id not in selected_ids:
                selected_ids.add(required_id)
                pending.append(required_id)
    return [component for component in components if component.id in selected_ids]


def component_patch_path(patch_dir: Path, component) -> Path:
    return patch_dir / f"{component.id}.ips"


def build_component(component, rom_path: Path, output_path: Path) -> bytes:
    command = [sys.executable, str(component.path / "build_patch.py"), str(rom_path), "-o", str(output_path)]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run(command, cwd=component.path, env=env, text=True, capture_output=True)
    if result.returncode:
        details = (result.stdout + "\n" + result.stderr).strip()
        raise SystemExit(f"Builder failed for {component.id}:\n{details}")
    if not output_path.is_file():
        raise SystemExit(f"Builder for {component.id} did not create {output_path}")
    return output_path.read_bytes()


def load_component_patches(components, patch_dir: Path) -> dict[str, bytes]:
    missing = [component_patch_path(patch_dir, component) for component in components if not component_patch_path(patch_dir, component).is_file()]
    if missing:
        lines = ["Cannot build all.ips: missing standalone component patch(es):"]
        lines.extend(f"  - {path}" for path in missing)
        lines.append("Rebuild the missing components first, or run with 'all --combine'.")
        raise SystemExit("\n".join(lines))
    return {component.id: component_patch_path(patch_dir, component).read_bytes() for component in components}


def combine_patches(base: bytes, components, patch_data: dict[str, bytes]) -> tuple[bytes, bytearray, int, int, int]:
    identical, declared = audit_overlaps(components, patch_data)
    rom = bytearray(base)
    for component in components:
        rom = apply_ips(rom, patch_data[component.id])
    apply_merge_rules(rom, components)
    checksum = update_checksum(rom)
    return make_ips(base, bytes(rom)), rom, checksum, identical, declared


def main() -> None:
    components = discover_components(ROOT)
    parser = argparse.ArgumentParser(
        description=(
            "Build default component IPS files, optionally add locale/cheat IPS files, "
            "and combine stored patches into aggregate IPS files."
        )
    )
    parser.add_argument("rom", nargs="?", type=Path, help="clean unheadered Secret of Mana (USA) ROM")
    parser.add_argument(
        "components",
        nargs="*",
        help="component short names/IDs to rebuild; default: USA-compatible default components",
    )
    parser.add_argument(
        "--patch-dir",
        type=Path,
        default=DEFAULT_PATCH_DIR,
        help="directory containing reusable component IPS files (default: patches/)",
    )
    parser.add_argument(
        "--combine",
        action="store_true",
        help="also create all.ips, plus one all-<locale>.ips per --locale",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="combined IPS output path (default with --combine: <patch-dir>/all.ips)",
    )
    parser.add_argument(
        "--patched-rom",
        type=Path,
        help="optional ROM for the selected aggregate; requires --combine and at most one --locale",
    )
    parser.add_argument(
        "--cheats",
        action="store_true",
        help="also build default_cheats.ips; with --combine create cheat aggregates",
    )
    parser.add_argument(
        "--french",
        action="store_true",
        help="legacy alias for --locale french (writes all-fr.ips)",
    )
    parser.add_argument(
        "--locale",
        action="append",
        metavar="LANGUAGE",
        help="also build <language>_* IPS files; with --combine create all-<language>.ips; repeatable",
    )
    parser.add_argument("--list", action="store_true", help="list discovered components and exit")
    args = parser.parse_args()

    if args.list:
        for component in components:
            status = "" if component.metadata.get("aggregate_enabled", True) else " [standalone-only]"
            if locale := component_locale(component):
                status += f" [{locale}]"
            print(f"{component.short_name:20} {component.id:26} {component.name}{status}")
        return
    if args.rom is None:
        parser.error("rom is required unless --list is used")
    if args.output and not args.combine:
        parser.error("--output is only meaningful together with --combine")
    if args.patched_rom and not args.combine:
        parser.error("--patched-rom requires --combine")
    args.rom = args.rom.resolve()
    patch_dir = args.patch_dir.resolve()
    base = args.rom.read_bytes()
    validate_base_rom(base)

    # With no explicit components, normal builds produce only the reusable
    # USA-compatible default patches. Combine builds reuse stored patches but
    # reconstruct any missing default prerequisite before producing all.ips.
    selected = (
        resolve_selection(args.components, components)
        if args.components
        else ([] if args.combine else us_aggregate_components(components))
    )
    locales = list(dict.fromkeys([*(args.locale or []), *( ["french"] if args.french else [])]))
    if args.patched_rom and len(locales) > 1:
        parser.error("--patched-rom is ambiguous with multiple --locale values")
    known_locales = {locale for component in components if (locale := component_locale(component))}
    unknown_locales = sorted(set(locales) - known_locales)
    if unknown_locales:
        raise SystemExit(f"Unknown locale component prefix(es): {', '.join(unknown_locales)}")
    for locale in locales:
        for locale_component in locale_aggregate_components(components, locale):
            if locale_component not in selected:
                selected.append(locale_component)
    if args.cheats:
        cheats_component = next(component for component in components if component.id == "default_cheats")
        if cheats_component not in selected:
            selected.append(cheats_component)
    if args.combine:
        for component in us_aggregate_components(components):
            if not component_patch_path(patch_dir, component).is_file() and component not in selected:
                selected.append(component)

    # Builders run in manifest build order even when missing patches were
    # appended after explicit components or locale selections.
    selected_ids = {component.id for component in selected}
    selected = [component for component in components if component.id in selected_ids]

    if selected:
        # A full rebuild warms the complete deterministic root extraction cache
        # once. Targeted builds stay lazy and only create assets they consume.
        if len(selected) == len(aggregate_components(components)) and set(c.id for c in selected) == set(c.id for c in aggregate_components(components)):
            materialize_all_assets(base)

        patch_dir.mkdir(parents=True, exist_ok=True)
        built_data: dict[str, bytes] = {}
        for component in selected:
            output_path = component_patch_path(patch_dir, component)
            built_data[component.id] = build_component(component, args.rom, output_path)
            print(f"Built: {output_path}")

        # Catch collisions immediately when several components are rebuilt together.
        if len(selected) > 1:
            identical, declared = audit_overlaps(selected, built_data)
            print(f"Selected-component identical overlapping bytes: {identical}")
            print(f"Selected-component declared overlapping bytes: {declared}")

    if not args.combine:
        if selected:
            print("\nRebuilt components:")
            for component in selected:
                print(f"  - {component.id}")
        print("Use --combine to create all.ips from the stored USA-compatible component patches.")
        return

    normal_components = us_aggregate_components(components)
    normal_patch_data = load_component_patches(normal_components, patch_dir)
    normal_patch, normal_rom, normal_checksum, normal_identical, normal_declared = combine_patches(
        base, normal_components, normal_patch_data
    )
    output = (args.output or (patch_dir / "all.ips")).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(normal_patch)

    print("\nCombined components:")
    for component in normal_components:
        print(f"  - {component.id}")
    print(f"Compatible identical overlapping bytes: {normal_identical}")
    print(f"Declared special/header overlapping bytes: {normal_declared}")
    print(f"Final ROM size: 0x{len(normal_rom):X}")
    print(f"Final checksum: ${normal_checksum:04X}")
    print(f"IPS: {output}")

    patched_rom_data = normal_rom

    if args.cheats:
        cheat_components = [*normal_components]
        cheats_component = next(component for component in components if component.id == "default_cheats")
        cheat_components.append(cheats_component)
        cheat_patch_data = load_component_patches(cheat_components, patch_dir)
        cheat_patch, cheat_rom, cheat_checksum, cheat_identical, cheat_declared = combine_patches(
            base, cheat_components, cheat_patch_data
        )
        cheat_output = (patch_dir / "all-cheats.ips").resolve()
        cheat_output.write_bytes(cheat_patch)
        print("\nCombined components with cheats:")
        for component in cheat_components:
            print(f"  - {component.id}")
        print(f"Compatible identical overlapping bytes: {cheat_identical}")
        print(f"Declared special/header overlapping bytes: {cheat_declared}")
        print(f"Final ROM size: 0x{len(cheat_rom):X}")
        print(f"Final checksum: ${cheat_checksum:04X}")
        print(f"IPS: {cheat_output}")
        if not locales:
            patched_rom_data = cheat_rom

    for locale in locales:
        locale_components = locale_aggregate_components(components, locale)
        locale_patch_data = load_component_patches(locale_components, patch_dir)
        locale_patch, locale_rom, locale_checksum, locale_identical, locale_declared = combine_patches(
            base, locale_components, locale_patch_data
        )
        output_suffix = "fr" if locale == "french" else locale
        locale_output = patch_dir / f"all-{output_suffix}.ips"
        locale_output.write_bytes(locale_patch)
        print(f"\nCombined {locale} components:")
        for component in locale_components:
            print(f"  - {component.id}")
        print(f"Compatible identical overlapping bytes: {locale_identical}")
        print(f"Declared special/header overlapping bytes: {locale_declared}")
        print(f"Final ROM size: 0x{len(locale_rom):X}")
        print(f"Final checksum: ${locale_checksum:04X}")
        print(f"IPS: {locale_output}")
        patched_rom_data = locale_rom

        if args.cheats:
            locale_cheat_components = [*locale_components, cheats_component]
            locale_cheat_data = load_component_patches(locale_cheat_components, patch_dir)
            locale_cheat_patch, locale_cheat_rom, locale_cheat_checksum, locale_cheat_identical, locale_cheat_declared = combine_patches(
                base, locale_cheat_components, locale_cheat_data
            )
            locale_cheat_output = patch_dir / f"all-{output_suffix}-cheats.ips"
            locale_cheat_output.write_bytes(locale_cheat_patch)
            print(f"\nCombined {locale} components with cheats:")
            for component in locale_cheat_components:
                print(f"  - {component.id}")
            print(f"Compatible identical overlapping bytes: {locale_cheat_identical}")
            print(f"Declared special/header overlapping bytes: {locale_cheat_declared}")
            print(f"Final ROM size: 0x{len(locale_cheat_rom):X}")
            print(f"Final checksum: ${locale_cheat_checksum:04X}")
            print(f"IPS: {locale_cheat_output}")
            patched_rom_data = locale_cheat_rom

    if args.patched_rom:
        args.patched_rom.parent.mkdir(parents=True, exist_ok=True)
        args.patched_rom.write_bytes(patched_rom_data)
        print(f"ROM: {args.patched_rom}")


if __name__ == "__main__":
    main()
