#!/usr/bin/env python3
"""Build one or more independent components, audit compatibility, and emit one IPS."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from shared.compatibility import apply_merge_rules, audit_overlaps
from shared.components import discover_components
from shared.ips import apply_ips, make_ips
from shared.rom import update_checksum, validate_base_rom

ROOT = Path(__file__).resolve().parent


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


def main() -> None:
    components = discover_components(ROOT)
    parser = argparse.ArgumentParser(
        description="Rebuild and safely combine independent Secret of Mana French-project components."
    )
    parser.add_argument("rom", nargs="?", type=Path, help="clean unheadered Secret of Mana (USA) ROM")
    parser.add_argument("components", nargs="*", help="component short names/IDs; default: all")
    parser.add_argument("-o", "--output", type=Path, default=ROOT / "build" / "all.ips", help="combined IPS output")
    parser.add_argument("--patched-rom", type=Path, help="optional patched ROM output")
    parser.add_argument("--list", action="store_true", help="list discovered components and exit")
    args = parser.parse_args()

    if args.list:
        for component in components:
            print(f"{component.short_name:12} {component.id:26} {component.name}")
        return
    if args.rom is None:
        parser.error("rom is required unless --list is used")

    base = args.rom.read_bytes()
    validate_base_rom(base)
    selected = resolve_selection(args.components, components)

    with tempfile.TemporaryDirectory(prefix="som_patchkit_") as temp_dir:
        temp = Path(temp_dir)
        patch_data = {
            component.id: build_component(component, args.rom, temp / f"{component.id}.ips")
            for component in selected
        }
        identical, declared = audit_overlaps(selected, patch_data)

        rom = bytearray(base)
        for component in selected:
            rom = apply_ips(rom, patch_data[component.id])
        apply_merge_rules(rom, selected)
        checksum = update_checksum(rom)
        patch = make_ips(base, bytes(rom))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(patch)
    if args.patched_rom:
        args.patched_rom.parent.mkdir(parents=True, exist_ok=True)
        args.patched_rom.write_bytes(rom)

    print("Components:")
    for component in selected:
        print(f"  - {component.id}")
    print(f"Compatible identical overlapping bytes: {identical}")
    print(f"Declared special/header overlapping bytes: {declared}")
    print(f"Final ROM size: 0x{len(rom):X}")
    print(f"Final checksum: ${checksum:04X}")
    print(f"IPS: {args.output}")

if __name__ == "__main__":
    main()
