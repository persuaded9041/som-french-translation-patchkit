#!/usr/bin/env python3
"""Build reusable component IPS files and combine USA/French aggregates."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

from shared.build.compatibility import apply_merge_rules, audit_overlaps
from shared.build.components import discover_components
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
        if not component.metadata.get("french", False)
    }
    changed = True
    while changed:
        changed = False
        for component_id, component in list(selected.items()):
            if any(required_id not in selected for required_id in component.metadata.get("requires", [])):
                del selected[component_id]
                changed = True
    return [component for component in components if component.id in selected]


def french_aggregate_components(components):
    """Return aggregate-enabled or explicitly French components."""
    return [
        component
        for component in components
        if component.metadata.get("aggregate_enabled", True)
        or component.metadata.get("french", False)
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
            "Rebuild reusable standalone component IPS files and optionally combine the stored "
            "USA-compatible component patches into all.ips, with optional French aggregates."
        )
    )
    parser.add_argument("rom", nargs="?", type=Path, help="clean unheadered Secret of Mana (USA) ROM")
    parser.add_argument(
        "components",
        nargs="*",
        help="component short names/IDs to rebuild; default: all aggregate-enabled components (unless --combine is used alone)",
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
        help="after rebuilding the requested components, combine all stored component IPS files into all.ips",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="combined IPS output path (default with --combine: <patch-dir>/all.ips)",
    )
    parser.add_argument("--patched-rom", type=Path, help="optional patched ROM output; requires --combine")
    parser.add_argument(
        "--cheats",
        action="store_true",
        help="also create all-cheats.ips from the USA-compatible aggregate",
    )
    parser.add_argument(
        "--french",
        action="store_true",
        help="also create all-fr.ips, and all-fr-cheats.ips when combined with --cheats",
    )
    parser.add_argument("--list", action="store_true", help="list discovered components and exit")
    args = parser.parse_args()

    if args.list:
        for component in components:
            status = "" if component.metadata.get("aggregate_enabled", True) else " [standalone-only]"
            if component.metadata.get("french", False):
                status += " [French]"
            print(f"{component.short_name:20} {component.id:26} {component.name}{status}")
        return
    if args.rom is None:
        parser.error("rom is required unless --list is used")
    if args.output and not args.combine:
        parser.error("--output is only meaningful together with --combine")
    if args.patched_rom and not args.combine:
        parser.error("--patched-rom requires --combine")
    if args.cheats and not args.combine:
        parser.error("--cheats requires --combine")
    if args.french and not args.combine:
        parser.error("--french requires --combine")

    args.rom = args.rom.resolve()
    patch_dir = args.patch_dir.resolve()
    base = args.rom.read_bytes()
    validate_base_rom(base)

    # `--combine` with no component arguments is intentionally combine-only:
    # it reuses every standalone IPS already stored in patch_dir without rebuilding anything.
    selected = [] if args.combine and not args.components else resolve_selection(args.components, components)
    if args.cheats:
        cheats_component = next(component for component in components if component.id == "default_cheats")
        if cheats_component not in selected:
            selected.append(cheats_component)
    if args.french:
        french_font = next(component for component in components if component.id == "french_font")
        if french_font not in selected:
            selected.append(french_font)

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

    if args.patched_rom:
        args.patched_rom.parent.mkdir(parents=True, exist_ok=True)
        args.patched_rom.write_bytes(normal_rom)

    print("\nCombined components:")
    for component in normal_components:
        print(f"  - {component.id}")
    print(f"Compatible identical overlapping bytes: {normal_identical}")
    print(f"Declared special/header overlapping bytes: {normal_declared}")
    print(f"Final ROM size: 0x{len(normal_rom):X}")
    print(f"Final checksum: ${normal_checksum:04X}")
    print(f"IPS: {output}")

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

    if args.french:
        french_components = french_aggregate_components(components)
        french_patch_data = load_component_patches(french_components, patch_dir)
        french_patch, french_rom, french_checksum, french_identical, french_declared = combine_patches(
            base, french_components, french_patch_data
        )
        french_output = patch_dir / "all-fr.ips"
        french_output.write_bytes(french_patch)
        print("\nCombined French components:")
        for component in french_components:
            print(f"  - {component.id}")
        print(f"Compatible identical overlapping bytes: {french_identical}")
        print(f"Declared special/header overlapping bytes: {french_declared}")
        print(f"Final ROM size: 0x{len(french_rom):X}")
        print(f"Final checksum: ${french_checksum:04X}")
        print(f"IPS: {french_output}")

        if args.cheats:
            french_cheat_components = [*french_components, cheats_component]
            french_cheat_data = load_component_patches(french_cheat_components, patch_dir)
            french_cheat_patch, french_cheat_rom, french_cheat_checksum, french_cheat_identical, french_cheat_declared = combine_patches(
                base, french_cheat_components, french_cheat_data
            )
            french_cheat_output = patch_dir / "all-fr-cheats.ips"
            french_cheat_output.write_bytes(french_cheat_patch)
            print("\nCombined French components with cheats:")
            for component in french_cheat_components:
                print(f"  - {component.id}")
            print(f"Compatible identical overlapping bytes: {french_cheat_identical}")
            print(f"Declared special/header overlapping bytes: {french_cheat_declared}")
            print(f"Final ROM size: 0x{len(french_cheat_rom):X}")
            print(f"Final checksum: ${french_cheat_checksum:04X}")
            print(f"IPS: {french_cheat_output}")


if __name__ == "__main__":
    main()
