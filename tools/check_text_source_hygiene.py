#!/usr/bin/env python3
"""Check that translation prose uses only the canonical root JSON architecture."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
COMPONENTS = ROOT / "components"

# Binary/metadata assets that are intentionally not prose translation sources.
ALLOWED_COMPONENT_TEXTLIKE_FILES = {
    "components/01_japanese_mana_tree/assets/mana_tree_jp.bin",
    "components/02_9char_names/assets/naming_characters.txt",
    "components/05_intro_vwf_french/assets/text/intro_layout.json",
}

RETIRED_NAMES = {
    "game_select_text.csv",
    "game_file_text.csv",
    "name_help.csv",
    "naming_help.csv",
    "scrtxt_fr.bin",
    "scrtxt.bin",
}

# These components intentionally own no translatable prose.
NO_TRANSLATION_COMPONENTS = {
    "01_japanese_mana_tree",
    "06_dialogue_vwf",
    "07_intro_skip",
}


def fail(message: str) -> None:
    raise SystemExit(message)


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def main() -> None:
    problems: list[str] = []

    for path in COMPONENTS.rglob("*"):
        if not path.is_file():
            continue
        relative = rel(path)
        lower_name = path.name.lower()

        if path.suffix.lower() == ".csv":
            problems.append(f"legacy component CSV: {relative}")
        if lower_name in RETIRED_NAMES:
            problems.append(f"retired text-source filename: {relative}")
        if path.suffix.lower() in {".bin", ".txt"} and relative not in ALLOWED_COMPONENT_TEXTLIKE_FILES:
            problems.append(f"unexpected component-local .bin/.txt source: {relative}")

    legacy_needles = tuple(sorted(RETIRED_NAMES | {"fixed_text.json", "shared/fixed_text.py"}))
    for path in COMPONENTS.glob("*/build_patch.py"):
        text = path.read_text(encoding="utf-8")
        for needle in legacy_needles:
            if needle in text:
                problems.append(f"legacy reference {needle!r} in {rel(path)}")

    for component_id in sorted(NO_TRANSLATION_COMPONENTS):
        builder = COMPONENTS / component_id / "build_patch.py"
        text = builder.read_text(encoding="utf-8")
        if "translation_json" in text or "translations/" in text or 'PROJECT_ROOT / "translations"' in text:
            problems.append(f"{component_id} unexpectedly depends on translation JSON")
        # Root canonical text assets are also unnecessary for these components.
        if 'PROJECT_ROOT / "assets"' in text:
            problems.append(f"{component_id} unexpectedly depends on root text assets")

    if problems:
        print("Text-source hygiene FAILED:")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print("Text-source hygiene OK")
    print("  - no component CSV translation sources")
    print("  - no retired prose BIN/CSV paths")
    print("  - components 01/06/07 own no translation-JSON dependencies")
    print("  - remaining component-local .bin/.txt assets are explicit non-prose data")
    return 0


if __name__ == "__main__":
    sys.exit(main())
