#!/usr/bin/env python3
"""Check that translation prose uses only the canonical root JSON architecture."""
from __future__ import annotations

from pathlib import Path
import json
import re
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



def check_dialogue_pipeline(problems: list[str]) -> None:
    """Guard the Android-derived dialogue provenance architecture."""
    generator_files = [ROOT / "tools" / "import_android_text.py"] + sorted((ROOT / "tools" / "dialogue_pipeline").glob("*.py"))
    forbidden_reads = (
        "DEFAULT_DIALOGUE_FORMAT_MASS_OUTPUT.read",
        "dialogues_french.json\").read",
        "dialogues_french.json').read",
    )
    for generator_file in generator_files:
        text = generator_file.read_text(encoding="utf-8")
        for needle in forbidden_reads:
            if needle in text:
                problems.append(
                    f"dialogue generator reads its own generated output in {generator_file.relative_to(ROOT)}: {needle}"
                )

    recipe_path = ROOT / "mappings" / "android" / "dialogues_mapping_layout_recipes.json"
    document = json.loads(recipe_path.read_text(encoding="utf-8"))
    if document.get("source") != "sources/android/scrtxt_fr.bin":
        problems.append("mapping-layout recipes do not declare Android FR as their source")
    prose_re = re.compile(r"[A-Za-zÀ-ÿŒœ]")
    for recipe in document.get("recipes", []):
        event_id = recipe.get("event_id", "?")
        for text_id, carrier in recipe.get("carriers", {}).items():
            parts = carrier.get("parts", [])
            seps = carrier.get("seps", [])
            if len(seps) != len(parts) + 1:
                problems.append(f"mapping-layout ${event_id}/{text_id}: invalid separator count")
            for sep in seps:
                if prose_re.search(str(sep)):
                    problems.append(f"mapping-layout ${event_id}/{text_id}: prose in separator {sep!r}")
            for part in parts:
                if not isinstance(part, list) or not part:
                    problems.append(f"mapping-layout ${event_id}/{text_id}: invalid part {part!r}")
                    continue
                if part[0] == "x" and (len(part) != 2 or prose_re.search(str(part[1]))):
                    problems.append(f"mapping-layout ${event_id}/{text_id}: prose literal {part!r}")
                elif part[0] not in {"a", "p", "x"}:
                    problems.append(f"mapping-layout ${event_id}/{text_id}: unknown part {part!r}")

    reviewed_path = ROOT / "mappings" / "android" / "dialogues_reviewed_alignment_recipes.json"
    reviewed_doc = json.loads(reviewed_path.read_text(encoding="utf-8"))
    if reviewed_doc.get("format") != "dialogues-reviewed-alignment-recipes-v1":
        problems.append("reviewed-alignment recipes use an unsupported format")
    allowed_review_keys = {
        "event_id", "parts", "android_ids", "confidence", "provenance",
        "relation", "note", "android_namespace", "localization_systxt_id",
    }
    forbidden_payload_keys = {"text", "translation", "translation_fr", "french", "french_text"}
    for record in reviewed_doc.get("records", []):
        event_id = record.get("event_id", "?")
        extra = set(record) - allowed_review_keys
        if extra:
            problems.append(f"reviewed-alignment ${event_id}: unsupported keys {sorted(extra)}")
        if forbidden_payload_keys.intersection(record):
            problems.append(f"reviewed-alignment ${event_id}: translated payload field is forbidden")
        for part in record.get("parts", []):
            if isinstance(part, str):
                if not re.fullmatch(r"(?:C9|CA):[0-9A-F]{4}", part):
                    problems.append(f"reviewed-alignment ${event_id}: invalid SNES carrier {part!r}")
            elif isinstance(part, dict):
                if set(part) != {"command", "index"} or part.get("command") != "player_name" or part.get("index") not in {0, 1, 2}:
                    problems.append(f"reviewed-alignment ${event_id}: invalid structural command {part!r}")
            else:
                problems.append(f"reviewed-alignment ${event_id}: invalid part {part!r}")

    search_path = ROOT / "mappings" / "android" / "dialogues_layout_search_recipes.json"
    search_doc = json.loads(search_path.read_text(encoding="utf-8"))
    allowed = {"strategy", "text_id", "boundary_before_id", "source_offset", "step", "semantic_payload_changed"}
    for event_id, operations in search_doc.get("events", {}).items():
        for operation in operations:
            extra = set(operation) - allowed
            if extra:
                problems.append(f"layout-search ${event_id}: unsupported payload keys {sorted(extra)}")
            if operation.get("semantic_payload_changed") is not False:
                problems.append(f"layout-search ${event_id}: recipe may not change semantic payload")


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

    check_dialogue_pipeline(problems)

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
    print("  - dialogue generation never consumes dialogues_french.json as an input")
    print("  - dialogue alignment/layout recipes contain structural references only, never translated prose payloads")
    return 0


if __name__ == "__main__":
    sys.exit(main())
