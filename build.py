#!/usr/bin/env python3
"""Build reusable component IPS files and safely combine them into all.ips."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

from shared.compatibility import apply_merge_rules, audit_overlaps
from shared.components import discover_components
from shared.ips import apply_ips, make_ips
from shared.rom import update_checksum, validate_base_rom

ROOT = Path(__file__).resolve().parent
DEFAULT_PATCH_DIR = ROOT / "patches"


def resolve_selection(values: list[str], components):
    aliases = {component.short_name: component for component in components}
    aliases.update({component.id: component for component in components})
    if not values or values == ["all"]:
        return components
    if "all" in values:
        raise SystemExit("Component 'all' must be used alone")
    selected = []
    for value in values:
        component = aliases.get(value)
        if component is None:
            raise SystemExit(f"Unknown component: {value}")
        if component not in selected:
            selected.append(component)
    selected_ids = {component.id for component in selected}
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
            "component patches into all.ips."
        )
    )
    parser.add_argument("rom", nargs="?", type=Path, help="clean unheadered Secret of Mana (USA) ROM")
    parser.add_argument(
        "components",
        nargs="*",
        help="component short names/IDs to rebuild; default: all (unless --combine is used alone)",
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
    parser.add_argument("--list", action="store_true", help="list discovered components and exit")
    args = parser.parse_args()

    if args.list:
        for component in components:
            print(f"{component.short_name:12} {component.id:26} {component.name}")
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

    # `--combine` with no component arguments is intentionally combine-only:
    # it reuses every standalone IPS already stored in patch_dir without rebuilding anything.
    selected = [] if args.combine and not args.components else resolve_selection(args.components, components)

    if selected:
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
        print("Use --combine to create all.ips from the complete set of stored component patches.")
        return

    patch_data = load_component_patches(components, patch_dir)
    patch, rom, checksum, identical, declared = combine_patches(base, components, patch_data)
    output = (args.output or (patch_dir / "all.ips")).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(patch)

    if args.patched_rom:
        args.patched_rom.parent.mkdir(parents=True, exist_ok=True)
        args.patched_rom.write_bytes(rom)

    print("\nCombined components:")
    for component in components:
        print(f"  - {component.id}")
    print(f"Compatible identical overlapping bytes: {identical}")
    print(f"Declared special/header overlapping bytes: {declared}")
    print(f"Final ROM size: 0x{len(rom):X}")
    print(f"Final checksum: ${checksum:04X}")
    print(f"IPS: {output}")


if __name__ == "__main__":
    main()
