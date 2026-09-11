#!/usr/bin/env python3
"""Check that translation prose uses only the canonical root JSON architecture."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
COMPONENTS = ROOT / "components"

# Binary/metadata assets that are intentionally not prose translation sources.
ALLOWED_COMPONENT_TEXTLIKE_FILES = {
    "components/mana_tree_original/assets/mana_tree_jp.bin",
    "components/name_entry_extended/assets/naming_characters.txt",
    "components/french_intro/assets/text/intro_layout.json",
}

# These names are retired only as component-local translation inputs.
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
    "mana_tree_original",
    "name_entry_extended",
    "name_entry_prefill",
    "vwf_intro",
    "vwf_dialogues",
    "intro_skip",
}

# `name_entry_extended` legitimately reads the clean-USA interface source so it
# can reproduce the relocated English help with the functional 9-character
# limit. It still must never consume a translation JSON.
NO_ROOT_TEXT_COMPONENTS = NO_TRANSLATION_COMPONENTS - {"name_entry_extended"}


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
        # Root canonical text assets are unnecessary for pure runtime/data
        # components, but the generic Name Entry intentionally reads its clean
        # USA help source while remaining translation-free.
        if component_id in NO_ROOT_TEXT_COMPONENTS and 'PROJECT_ROOT / "assets"' in text:
            problems.append(f"{component_id} unexpectedly depends on root text assets")

    if problems:
        print("Text-source hygiene FAILED:")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print("Text-source hygiene OK")
    print("  - no component CSV translation sources")
    print("  - no retired component-local prose BIN/CSV paths")
    print("  - upstream Android prose is isolated under sources/android/")
    print("  - `mana_tree_original` / `name_entry_extended` / `name_entry_prefill` / `vwf_intro` / `vwf_dialogues` / `intro_skip` own no translation-JSON dependencies")
    print("  - remaining component-local .bin/.txt assets are explicit non-prose data")
    return 0


if __name__ == "__main__":
    sys.exit(main())
