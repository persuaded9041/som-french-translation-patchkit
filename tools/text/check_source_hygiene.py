#!/usr/bin/env python3
"""Check that translation prose uses only the canonical root JSON architecture."""
from __future__ import annotations

from pathlib import Path
import ast
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
COMPONENTS = ROOT / "components"

# Binary/metadata assets that are intentionally not prose translation sources.
ALLOWED_COMPONENT_TEXTLIKE_FILES = {
    "components/default_mana_tree_original/assets/mana_tree_jp.bin",
    "components/default_name_entry_extended/assets/naming_characters.txt",
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
    "default_mana_tree_original",
    "default_name_entry_extended",
    "default_name_entry_prefill",
    "default_vwf_intro",
    "default_vwf_dialogues",
    "default_intro_skip",
}

# `name_entry_extended` legitimately reads the clean-USA interface source so it
# can reproduce the relocated English help with the functional 9-character
# limit. It still must never consume a translation JSON.
NO_ROOT_TEXT_COMPONENTS = NO_TRANSLATION_COMPONENTS - {"default_name_entry_extended"}


def fail(message: str) -> None:
    raise SystemExit(message)


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def recipe_section(filename: str, section: str) -> dict:
    document = json.loads((ROOT / "recipes" / "android" / filename).read_text(encoding="utf-8"))
    return document["sections"][section]



def check_dialogue_pipeline(problems: list[str]) -> None:
    """Guard the Android-derived dialogue provenance architecture."""
    generator_files = [ROOT / "tools" / "dialogue" / "import_android.py"] + sorted((ROOT / "shared" / "dialogue" / "pipeline").glob("*.py"))
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

    document = recipe_section("dialogues_formatting.json", "mapping_layout")
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

    reviewed_path = ROOT / "recipes" / "android" / "dialogues_reviewed_alignment.json"
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

    final_layout_doc = recipe_section("dialogues_review.json", "final_layout")
    allowed_top = {"format_version", "source", "description", "validated_against", "events"}
    extra_top = set(final_layout_doc) - allowed_top
    if extra_top:
        problems.append(f"final-layout recipes: unsupported top-level keys {sorted(extra_top)}")
    if final_layout_doc.get("format_version") != 1:
        problems.append("final-layout recipes use an unsupported format version")
    prose_re = re.compile(r"[A-Za-zÀ-ÿŒœ]")
    for event_id, event in final_layout_doc.get("events", {}).items():
        if set(event) != {"carriers"}:
            problems.append(f"final-layout ${event_id}: unsupported event payload keys {sorted(set(event) - {'carriers'})}")
        for text_id, carrier in event.get("carriers", {}).items():
            allowed_carrier = {"semantic_sha256", "semantic_part_count", "seps"}
            extra = set(carrier) - allowed_carrier
            if extra:
                problems.append(f"final-layout ${event_id}/{text_id}: unsupported keys {sorted(extra)}")
            semantic_hash = str(carrier.get("semantic_sha256", ""))
            if not re.fullmatch(r"[0-9a-f]{64}", semantic_hash):
                problems.append(f"final-layout ${event_id}/{text_id}: invalid semantic SHA-256")
            count = carrier.get("semantic_part_count")
            seps = carrier.get("seps", [])
            if not isinstance(count, int) or count < 1 or len(seps) != count + 1:
                problems.append(f"final-layout ${event_id}/{text_id}: invalid semantic count/separator shape")
            for sep in seps:
                if not isinstance(sep, str) or re.search(r"[^ \n\f\r]", sep):
                    problems.append(f"final-layout ${event_id}/{text_id}: non-layout separator {sep!r}")
                if isinstance(sep, str) and prose_re.search(sep):
                    problems.append(f"final-layout ${event_id}/{text_id}: prose in separator {sep!r}")

    final_structure_doc = recipe_section("dialogues_review.json", "final_structure")
    allowed_top = {"format_version", "source", "description", "validated_against", "events"}
    extra_top = set(final_structure_doc) - allowed_top
    if extra_top:
        problems.append(f"final-structure recipes: unsupported top-level keys {sorted(extra_top)}")
    if final_structure_doc.get("format_version") != 1:
        problems.append("final-structure recipes use an unsupported format version")
    allowed_operations = {
        "inline_omitted_player_name_with_clear",
        "add_leading_clear",
        "remove_leading_clear",
        "preserve_source_punctuation_carrier",
        "prepend_source_leading_punctuation",
    }
    for event_id, event in final_structure_doc.get("events", {}).items():
        if set(event) != {"carriers"}:
            problems.append(f"final-structure ${event_id}: unsupported event payload keys")
        for text_id, carrier in event.get("carriers", {}).items():
            if set(carrier) != {"operation"}:
                problems.append(f"final-structure ${event_id}/{text_id}: unsupported carrier payload keys")
                continue
            if carrier.get("operation") not in allowed_operations:
                problems.append(f"final-structure ${event_id}/{text_id}: invalid structural operation")

    post_layout_doc = recipe_section("dialogues_review.json", "post_structure_layout")
    extra_top = set(post_layout_doc) - allowed_top
    if extra_top:
        problems.append(f"post-structure layout recipes: unsupported top-level keys {sorted(extra_top)}")
    if post_layout_doc.get("format_version") != 1:
        problems.append("post-structure layout recipes use an unsupported format version")
    for event_id, event in post_layout_doc.get("events", {}).items():
        if set(event) != {"carriers"}:
            problems.append(f"post-structure layout ${event_id}: unsupported event payload keys")
        for text_id, carrier in event.get("carriers", {}).items():
            allowed_carrier = {"semantic_sha256", "semantic_part_count", "seps"}
            extra = set(carrier) - allowed_carrier
            if extra:
                problems.append(f"post-structure layout ${event_id}/{text_id}: unsupported keys {sorted(extra)}")
            semantic_hash = str(carrier.get("semantic_sha256", ""))
            if not re.fullmatch(r"[0-9a-f]{64}", semantic_hash):
                problems.append(f"post-structure layout ${event_id}/{text_id}: invalid semantic SHA-256")
            count = carrier.get("semantic_part_count")
            seps = carrier.get("seps", [])
            if not isinstance(count, int) or count < 1 or len(seps) != count + 1:
                problems.append(f"post-structure layout ${event_id}/{text_id}: invalid semantic count/separator shape")
            for sep in seps:
                if not isinstance(sep, str) or re.search(r"[^ \n\f\r]", sep):
                    problems.append(f"post-structure layout ${event_id}/{text_id}: non-layout separator {sep!r}")
                if isinstance(sep, str) and prose_re.search(sep):
                    problems.append(f"post-structure layout ${event_id}/{text_id}: prose in separator {sep!r}")

    search_doc = recipe_section("dialogues_formatting.json", "layout_search")
    allowed = {"strategy", "text_id", "boundary_before_id", "source_offset", "step", "semantic_payload_changed"}
    for event_id, operations in search_doc.get("events", {}).items():
        for operation in operations:
            extra = set(operation) - allowed
            if extra:
                problems.append(f"layout-search ${event_id}: unsupported payload keys {sorted(extra)}")
            if operation.get("semantic_payload_changed") is not False:
                problems.append(f"layout-search ${event_id}: recipe may not change semantic payload")



def check_component_hardcoded_prose(problems: list[str]) -> None:
    """Reject localized prose copied into component Python/ASM source.

    Translation payloads belong in JSON/data sources.  This deliberately scans
    only human prose values (multi-word `text` fields) so structural tokens,
    glyph repertoires and short fixed identifiers do not create false positives.
    Python comments are ignored by the AST; ASM comments are stripped before
    matching.
    """
    prose: set[str] = set()
    for path in sorted((ROOT / "translations").glob("*.json")):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            problems.append(f"cannot parse translation JSON {path.relative_to(ROOT)}: {exc}")
            continue

        def visit(value: object) -> None:
            if isinstance(value, dict):
                text = value.get("text")
                if isinstance(text, str):
                    candidate = text.strip()
                    if len(candidate) >= 8 and any(ch.isspace() for ch in candidate):
                        prose.add(candidate)
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        visit(document)

    for path in sorted(COMPONENTS.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            problems.append(f"cannot parse component Python {rel(path)}: {exc}")
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            for payload in prose:
                if payload in node.value:
                    problems.append(
                        f"localized prose hard-coded in {rel(path)}:{getattr(node, 'lineno', '?')}: {payload!r}"
                    )
                    break

    for path in sorted(COMPONENTS.rglob("*.asm")):
        executable = "\n".join(
            line.split(";", 1)[0] for line in path.read_text(encoding="utf-8").splitlines()
        )
        for payload in prose:
            if payload in executable:
                problems.append(f"localized prose hard-coded in ASM {rel(path)}: {payload!r}")


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

    french_resources_builder = (COMPONENTS / "french_resources" / "build_patch.py").read_text(encoding="utf-8")
    # The generated translation may be reused only through the fingerprint-validated
    # persistent cache. Direct reads would silently promote it back to canonical input.
    if "shared.text.resource_cache" not in french_resources_builder:
        problems.append("french_resources does not use the validated text-resource cache layer")
    for needle in (
        'PROJECT_ROOT / "translations" / "text_resources_french.json"',
        "text_resources_french.json').read",
        'text_resources_french.json").read',
    ):
        if needle in french_resources_builder:
            problems.append(
                "french_resources directly reads generated text_resources_french.json: " + needle
            )

    french_dialogue_builder = (COMPONENTS / "french_dialogues" / "build_patch.py").read_text(encoding="utf-8")
    for needle in (
        'TRANSLATION_FILE = PROJECT_ROOT / "translations" / "dialogues_french.json"',
        "default=TRANSLATION_FILE",
        "default=GENERATED_TRANSLATION_FILE",
    ):
        if needle in french_dialogue_builder:
            problems.append(
                "french_dialogues normal build depends on generated dialogues_french.json: " + needle
            )

    check_dialogue_pipeline(problems)

    check_component_hardcoded_prose(problems)

    # Regression/audit consumers must regenerate dialogue alignment/format data
    # from canonical inputs rather than read ignored generated snapshots.
    generated_dialogue_consumers = {
        ROOT / "tools" / "dialogue" / "check_regressions.py": (
            "dialogues_french.json", "dialogues_auto.json", "dialogues_format_mass.json",
            "dialogues_format_mass_excluded.csv", "dialogues_unmapped.csv",
        ),
        ROOT / "tools" / "dialogue" / "audit_charset.py": ("DEFAULT_MAPPING",),
    }
    for consumer, needles in generated_dialogue_consumers.items():
        text = consumer.read_text(encoding="utf-8")
        for needle in needles:
            if needle in text:
                problems.append(
                    f"{consumer.relative_to(ROOT)} still depends on generated dialogue snapshot marker {needle!r}"
                )

    if problems:
        print("Text-source hygiene FAILED:")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print("Text-source hygiene OK")
    print("  - root assets/*.json are optional ignored ROM-extraction caches, never required build inputs")
    print("  - no component CSV translation sources")
    print("  - no retired component-local prose BIN/CSV paths")
    print("  - upstream Android prose is isolated under sources/android/")
    print("  - default components own no translation-JSON dependencies")
    print("  - remaining component-local .bin/.txt assets are explicit non-prose data")
    print("  - dialogues_french.json is only a fingerprint-validated local cache, never canonical provenance")
    print("  - dialogue regression/charset checks regenerate ignored alignment/format snapshots in memory")
    print("  - french_dialogues reuses a valid dialogues_french.json cache or regenerates and persists it automatically")
    print("  - french_resources reuses a valid text_resources_french.json cache or regenerates and persists it automatically; mapping reports remain optional")
    print("  - dialogue alignment/layout recipes contain structural references only, never translated prose payloads")
    print("  - component Python/ASM contains no multi-word localized prose copied from translation JSON payloads")
    return 0


if __name__ == "__main__":
    sys.exit(main())
