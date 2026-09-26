"""Build a language-profile overlay from one profile-aware default builder."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile

from shared.core.ips import make_ips


def build_profile_overlay(default_component: Path, rom_path: Path, output_path: Path) -> None:
    """Build the French full patch and emit only its delta over the default patch."""
    project_root = default_component.parent.parent
    with tempfile.TemporaryDirectory(prefix="som-vwf-profile-") as temp:
        temp_dir = Path(temp)
        default_patch = temp_dir / "default.ips"
        french_patch = temp_dir / "french.ips"
        env = os.environ.copy()
        env["PYTHONPATH"] = str(project_root) + os.pathsep + env.get("PYTHONPATH", "")

        for profile, destination in ((None, default_patch), ("french", french_patch)):
            child_env = env.copy()
            if profile is None:
                child_env.pop("SOM_VWF_PROFILE", None)
            else:
                child_env["SOM_VWF_PROFILE"] = profile
            result = subprocess.run(
                [sys.executable, str(default_component / "build_patch.py"), str(rom_path), "-o", str(destination)],
                cwd=default_component,
                env=child_env,
                text=True,
                capture_output=True,
            )
            if result.returncode:
                raise SystemExit((result.stdout + "\n" + result.stderr).strip())

        base = rom_path.read_bytes()
        default_rom = bytearray(base)
        french_rom = bytearray(base)
        from shared.core.ips import apply_ips

        apply_ips(default_rom, default_patch.read_bytes())
        apply_ips(french_rom, french_patch.read_bytes())
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(make_ips(bytes(default_rom), bytes(french_rom)))
