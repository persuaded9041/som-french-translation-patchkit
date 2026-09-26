"""Helpers for emitting a component delta over declared dependencies."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile

from shared.core.ips import apply_ips, make_ips


def make_dependency_overlay(
    base: bytes,
    rom_path: Path,
    dependency_components: list[Path],
    component_patch: bytes,
) -> bytes:
    """Return ``component_patch`` as a delta over its dependency patches."""
    project_root = dependency_components[0].parent.parent
    with tempfile.TemporaryDirectory(prefix="som-dependency-overlay-") as temp:
        temp_path = Path(temp)
        dependency_rom = bytearray(base)
        for index, component in enumerate(dependency_components):
            patch_path = temp_path / f"dependency-{index}.ips"
            result = subprocess.run(
                [sys.executable, str(component / "build_patch.py"), str(rom_path), "-o", str(patch_path)],
                cwd=component,
                env={"PYTHONPATH": str(project_root)},
                check=False,
                capture_output=True,
                text=True,
            )
            if result.returncode:
                raise SystemExit((result.stdout + "\n" + result.stderr).strip())
            apply_ips(dependency_rom, patch_path.read_bytes())

        target_rom = bytearray(dependency_rom)
        apply_ips(target_rom, component_patch)
        return make_ips(bytes(dependency_rom), bytes(target_rom))
