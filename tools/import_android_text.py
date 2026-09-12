#!/usr/bin/env python3
"""Import or analyze French translations from original Android text resources.

The Android ``scrtxt`` reader is generic, while dialogue generation is intentionally
limited to established SNES/Android identities plus structural recipes. Translated
prose is always read from the Android resources at generation time; recipe files may
store IDs, token references, punctuation and layout operations, but never translated
prose. ``dialogue-format-mass`` is the canonical dialogue generator and simulator gate.
"""
from __future__ import annotations

import argparse
import csv
from difflib import SequenceMatcher
import hashlib
from functools import lru_cache
from itertools import combinations
import json
import math
from pathlib import Path
import re
import struct
import sys
import unicodedata

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shared.intro_event_text import load_document as load_intro_source  # noqa: E402
from shared.dialogue_translation import (  # noqa: E402
    DIALOGUE_PAGE_LINES,
    DIALOGUE_WRAP_CHARS,
    DIALOGUE_WRAP_PIXELS,
    format_mapping as format_dialogue_mapping,
    format_mapping_across_existing_wait_boundaries,
    format_mapping_across_existing_timed_wait_boundary,
    format_mapping_across_existing_action_boundary,
    event_text_index,
    normalize_android_french,
    _sentence_boundary_positions,
    _markup_width,
    semantic_wrap_markup,
    make_dialogue_advances,
    player_placeholder_width,
    MAX_PLAYER_NAME_CHARS,
    make_translation_document as make_dialogue_translation_document,
)
from shared.dialogue_codec import (  # noqa: E402
    TRANSLATION_CLEAR, TRANSLATION_TRAILING_PAGE_BREAK_ALLOWLIST, parse_event,
)
from shared.translation_json import (  # noqa: E402
    resolve_structural_omission_token_indexes,
    resolve_structural_command_overrides,
)
from shared.rom import validate_base_rom  # noqa: E402

DEFAULT_SCRTXT_EN = ROOT / "sources" / "android" / "scrtxt_en.bin"
DEFAULT_SCRTXT_FR = ROOT / "sources" / "android" / "scrtxt_fr.bin"
DEFAULT_SYSTXT_EN = ROOT / "sources" / "android" / "systxt_en.bin"
DEFAULT_SYSTXT_FR = ROOT / "sources" / "android" / "systxt_fr.bin"
DEFAULT_INTRO_OUTPUT = ROOT / "translations" / "intro_event_french.json"
DIALOGUE_REDISTRIBUTION_RECIPES = ROOT / "mappings" / "android" / "dialogues_redistribution_recipes.json"
DIALOGUE_MAPPING_LAYOUT_RECIPES = ROOT / "mappings" / "android" / "dialogues_mapping_layout_recipes.json"
DIALOGUE_LAYOUT_SEARCH_RECIPES = ROOT / "mappings" / "android" / "dialogues_layout_search_recipes.json"
DIALOGUE_CHOICE_LAYOUT_RECIPES = ROOT / "mappings" / "android" / "dialogues_choice_layout_recipes.json"
DIALOGUE_COVERAGE_REPAIR_RECIPES = ROOT / "mappings" / "android" / "dialogues_coverage_repair_recipes.json"
DIALOGUE_REVIEWED_ALIGNMENT_RECIPES = ROOT / "mappings" / "android" / "dialogues_reviewed_alignment_recipes.json"
DIALOGUE_SOURCE = ROOT / "assets" / "dialogues.json"
DIALOGUE_MANUAL_SUPPLEMENTS = ROOT / "translations" / "dialogues_manual_supplements.json"



def _load_recipe_document(path: Path, *, label: str, expected: dict) -> dict:
    """Load a structural recipe document and validate its schema markers."""
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError(f"{label}: recipe root must be an object")
    for key, value in expected.items():
        if document.get(key) != value:
            raise ValueError(f"{label}: expected {key}={value!r}")
    return document

INTRO_ANDROID_IDS = tuple(range(3445, 3453))
INTRO_TARGET_IDS = (
    "CA:0C0D",
    "CA:0C59",
    "CA:0CB3",
    "CA:0D0C",
    "CA:0D5C",
    "CA:0DAB",
    "CA:0DFF",
    "CA:0E21",
)


# ---- Android text decoding and structural recipe rendering -----------------

def read_scrtxt(path: Path) -> dict[int, str]:
    """Read an Android scrtxt binary into ``android_id -> UTF-8 text``."""
    data = path.read_bytes()
    if len(data) < 8:
        raise ValueError(f"{path}: file is too small to be a scrtxt binary")

    entry_count, pool_size = struct.unpack_from("<II", data, 0)
    table_end = 8 + entry_count * 8
    if table_end > len(data):
        raise ValueError(f"{path}: entry table extends beyond end of file")
    if table_end + pool_size != len(data):
        raise ValueError(
            f"{path}: declared pool size does not match file size "
            f"({pool_size} bytes declared, {len(data) - table_end} available)"
        )

    pool = data[table_end:]
    result: dict[int, str] = {}
    for index in range(entry_count):
        text_id, offset = struct.unpack_from("<II", data, 8 + index * 8)
        if text_id in result:
            raise ValueError(f"{path}: duplicate Android text ID {text_id}")
        if offset >= len(pool):
            raise ValueError(f"{path}: text ID {text_id} has invalid offset {offset:#x}")
        end = pool.find(b"\x00", offset)
        if end < 0:
            raise ValueError(f"{path}: text ID {text_id} is not NUL-terminated")
        try:
            result[text_id] = pool[offset:end].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"{path}: text ID {text_id} is not valid UTF-8") from exc
    return result


_REDISTRIBUTION_TOKEN_RE = re.compile(r"%S\(\d+,0\)|[\wÀ-ÿŒœ’'-]+|[^\w\s]", re.UNICODE)


def _redistribution_tokens(text: str) -> list[str]:
    """Tokenize Android prose for index-based redistribution recipes.

    Recipes store only Android ID/token references plus layout punctuation and
    whitespace. They never store translated prose: the words are read from
    scrtxt_fr.bin on every deterministic generation.
    """
    return _REDISTRIBUTION_TOKEN_RE.findall(text.replace("_", " "))


def _android_token_cache(french: dict[int, str], android_ids, *, context: str) -> dict[int, list[str]]:
    cache: dict[int, list[str]] = {}
    for android_id in sorted({int(value) for value in android_ids}):
        if android_id not in french:
            raise ValueError(f"{context}: missing Android FR ID {android_id}")
        cache[android_id] = _redistribution_tokens(french[android_id])
    return cache


def _render_android_token_recipe(
    *,
    parts: list,
    seps: list,
    token_cache: dict[int, list[str]],
    context: str,
    declared_android_ids: set[int] | None = None,
    allow_transforms: bool = False,
) -> str:
    """Render one prose-free carrier recipe from Android-token references."""
    if len(seps) != len(parts) + 1:
        raise ValueError(f"{context}: invalid separator count")
    chunks = [str(seps[0])]
    for index, part in enumerate(parts):
        if not isinstance(part, list) or not part:
            raise ValueError(f"{context}: invalid part {part!r}")
        kind = part[0]
        if kind == "a":
            max_len = 4 if allow_transforms else 3
            if len(part) not in ({3, 4} if allow_transforms else {3}):
                raise ValueError(f"{context}: invalid Android token ref {part!r}")
            android_id, token_index = int(part[1]), int(part[2])
            if declared_android_ids is not None and android_id not in declared_android_ids:
                raise ValueError(f"{context}: undeclared Android ID {android_id}")
            tokens = token_cache.get(android_id)
            if tokens is None:
                raise ValueError(f"{context}: missing Android token cache for {android_id}")
            if not 0 <= token_index < len(tokens):
                raise ValueError(f"{context}: token index out of range {part!r}")
            token = tokens[token_index]
            if len(part) == 4:
                transform = part[3]
                if transform == "capitalize":
                    token = token[:1].upper() + token[1:]
                elif transform == "lower_first":
                    token = token[:1].lower() + token[1:]
                else:
                    raise ValueError(f"{context}: unknown transform {transform!r}")
        elif kind == "p":
            if len(part) != 2 or int(part[1]) not in {0, 1, 2}:
                raise ValueError(f"{context}: invalid PLAYER_NAME ref {part!r}")
            token = f"%S({int(part[1])},0)"
        elif kind == "x":
            if len(part) != 2 or re.search(r"[A-Za-zÀ-ÿŒœ]", str(part[1])):
                raise ValueError(f"{context}: literal prose forbidden {part!r}")
            token = str(part[1])
        else:
            raise ValueError(f"{context}: unknown part kind {kind!r}")
        chunks.append(token)
        chunks.append(str(seps[index + 1]))
    return "".join(chunks)


def _load_dialogue_redistribution_recipes(french: dict[int, str]) -> tuple[dict[str, dict[str, str]], dict[str, dict]]:
    document = _load_recipe_document(
        DIALOGUE_REDISTRIBUTION_RECIPES,
        label="Dialogue redistribution recipes",
        expected={"format_version": 1, "source": "sources/android/scrtxt_fr.bin"},
    )

    rendered: dict[str, dict[str, str]] = {}
    event_meta: dict[str, dict] = {}

    for event_id, event_recipe in document.get("events", {}).items():
        android_ids = [int(x) for x in event_recipe.get("android_ids", [])]
        token_cache = _android_token_cache(french, android_ids, context=f"Redistribution ${event_id}")
        declared_android_ids = set(android_ids)

        values: dict[str, str] = {}
        for sid, recipe in event_recipe.get("carriers", {}).items():
            values[sid] = _render_android_token_recipe(
                parts=recipe.get("parts", []),
                seps=recipe.get("seps", []),
                token_cache=token_cache,
                context=f"Redistribution ${event_id}/{sid}",
                declared_android_ids=declared_android_ids,
            )
        rendered[event_id] = values
        event_meta[event_id] = {"android_ids": android_ids, "round": int(event_recipe.get("round", 0) or 0)}
    return rendered, event_meta


@lru_cache(maxsize=1)
def _mapping_layout_recipe_index() -> dict[tuple[str, tuple[str, ...], tuple[int, ...], str], dict]:
    """Load mapping-local layout recipes without materializing translated prose.

    The JSON stores only Android-FR token references, SNES carrier identities,
    punctuation/layout separators and optional case transforms. Actual words are
    always read from ``scrtxt_fr.bin`` at generation time.
    """
    document = _load_recipe_document(
        DIALOGUE_MAPPING_LAYOUT_RECIPES,
        label="Dialogue mapping-layout recipes",
        expected={"format_version": 1, "source": "sources/android/scrtxt_fr.bin"},
    )
    out = {}
    for recipe in document.get("recipes", []):
        key = (
            str(recipe.get("event_id")),
            tuple(str(x) for x in recipe.get("snes_ids", [])),
            tuple(int(x) for x in recipe.get("android_ids", [])),
            str(recipe.get("relation", "")),
        )
        if key in out:
            raise ValueError(f"Duplicate mapping-layout recipe {key}")
        out[key] = recipe
    return out


def _render_mapping_layout_recipe(mapping: dict, french: dict[int, str]) -> tuple[dict[str, str], dict] | None:
    key = (
        str(mapping.get("event_id")),
        tuple(str(x) for x in mapping.get("snes_ids", [])),
        tuple(int(x) for x in mapping.get("android_ids", [])),
        str(mapping.get("relation", "")),
    )
    recipe = _mapping_layout_recipe_index().get(key)
    if recipe is None:
        return None

    values: dict[str, str] = {}
    provenance_ids = sorted({
        int(part[1])
        for carrier in recipe.get("carriers", {}).values()
        for part in carrier.get("parts", [])
        if isinstance(part, list) and part and part[0] == "a"
    })
    token_cache = _android_token_cache(french, provenance_ids, context=f"Mapping-layout recipe {key}")

    for text_id, carrier in recipe.get("carriers", {}).items():
        values[str(text_id)] = _render_android_token_recipe(
            parts=carrier.get("parts", []),
            seps=carrier.get("seps", []),
            token_cache=token_cache,
            context=f"Mapping-layout recipe {key}/{text_id}",
            allow_transforms=True,
        )

    return values, {
        "event_id": key[0],
        "snes_ids": list(key[1]),
        "android_ids": list(key[2]),
        "confidence": mapping.get("confidence"),
        "source_display": mapping.get("source_display", ""),
        "android_english_display": mapping.get("android_english_display", ""),
        "android_french_raw": mapping.get("french_display", ""),
        "mapping_layout_recipe": True,
        "mapping_layout_relation": key[3],
        "android_fr_provenance_ids": provenance_ids,
        "formatted_entries": [{"id": text_id, "text": text} for text_id, text in values.items()],
    }


def _load_dialogue_coverage_repair_recipes(
    french: dict[int, str], source_document: dict
) -> dict[str, list[dict]]:
    """Load source-derived Android-FR coverage repairs.

    These recipes may only splice complete Android-FR units into canonical SNES
    text carriers. They contain no translated prose: only event/carrier IDs,
    Android IDs, structural separators, and append/replace mode.
    """
    document = _load_recipe_document(
        DIALOGUE_COVERAGE_REPAIR_RECIPES,
        label="Dialogue coverage-repair recipes",
        expected={"format_version": 1, "source": "sources/android/scrtxt_fr.bin"},
    )
    by_event = {event["event_id"]: event for event in source_document.get("events", [])}
    result: dict[str, list[dict]] = {}
    seen: set[tuple[str, str]] = set()
    for recipe in document.get("repairs", []):
        event_id = str(recipe.get("event_id", "")).upper()
        carrier_id = str(recipe.get("carrier_id", "")).upper()
        mode = recipe.get("mode")
        android_ids = [int(x) for x in recipe.get("android_ids", [])]
        clear_carrier_ids = [str(x).upper() for x in recipe.get("clear_carrier_ids", [])]
        separator = str(recipe.get("separator", ""))
        android_separator = str(recipe.get("android_separator", " "))
        if mode not in {"append", "replace"}:
            raise ValueError(f"Coverage repair ${event_id}/{carrier_id}: unsupported mode {mode!r}")
        if not event_id or not carrier_id or not android_ids:
            raise ValueError(f"Coverage repair has incomplete identity: {recipe!r}")
        if (event_id, carrier_id) in seen:
            raise ValueError(f"Duplicate coverage repair ${event_id}/{carrier_id}")
        seen.add((event_id, carrier_id))
        if any(ch not in " \n\f\v\t" for ch in separator):
            raise ValueError(f"Coverage repair ${event_id}/{carrier_id}: separator may contain layout whitespace only")
        if any(ch not in " \n\f\v\t" for ch in android_separator):
            raise ValueError(f"Coverage repair ${event_id}/{carrier_id}: android_separator may contain layout whitespace only")
        event = by_event.get(event_id)
        if event is None:
            raise ValueError(f"Coverage repair references unknown event ${event_id}")
        carriers = {
            token.get("id") for token in event.get("tokens", [])
            if token.get("type") in {"text", "ending_text"}
        }
        if carrier_id not in carriers:
            raise ValueError(f"Coverage repair ${event_id}: unknown carrier {carrier_id}")
        unknown_clear = sorted(set(clear_carrier_ids) - carriers)
        if unknown_clear:
            raise ValueError(f"Coverage repair ${event_id}: unknown clear carrier(s) {unknown_clear}")
        missing_android = [android_id for android_id in android_ids if android_id not in french]
        if missing_android:
            raise ValueError(f"Coverage repair ${event_id}/{carrier_id}: missing Android FR IDs {missing_android}")
        result.setdefault(event_id, []).append({
            "event_id": event_id,
            "carrier_id": carrier_id,
            "mode": mode,
            "android_ids": android_ids,
            "clear_carrier_ids": clear_carrier_ids,
            "separator": separator,
            "android_separator": android_separator,
            "strip_player_name": bool(recipe.get("strip_player_name", False)),
            "newline_after_colon": bool(recipe.get("newline_after_colon", False)),
            "wrap_android_units": bool(recipe.get("wrap_android_units", False)),
        })
    return result


def _apply_dialogue_coverage_repairs(
    event_id: str, translations: dict[str, str], repairs_by_event: dict[str, list[dict]],
    french: dict[int, str], advances: dict[str, int],
) -> list[dict]:
    reports: list[dict] = []
    for recipe in repairs_by_event.get(event_id, []):
        carrier_id = recipe["carrier_id"]
        payload_units: list[str] = []
        for android_id in recipe["android_ids"]:
            unit = normalize_android_prose(french[android_id]).replace("_", "").strip()
            if not unit:
                continue
            if recipe.get("wrap_android_units"):
                unit, _widths, _chars, _units = semantic_wrap_markup(unit, advances)
            payload_units.append(unit)
        payload = recipe.get("android_separator", " ").join(payload_units)
        if recipe.get("strip_player_name"):
            payload = re.sub(r"^%S\(\d+,0\)\s*", "", payload).lstrip()
        if recipe.get("newline_after_colon") and ": " in payload:
            payload = payload.replace(": ", ":\n", 1)
        if not payload:
            raise ValueError(f"Coverage repair ${event_id}/{carrier_id}: empty Android FR payload")
        if recipe["mode"] == "append":
            if carrier_id not in translations:
                raise ValueError(f"Coverage repair ${event_id}/{carrier_id}: append carrier is not translated")
            translations[carrier_id] = translations[carrier_id].rstrip() + recipe["separator"] + payload
        else:
            translations[carrier_id] = payload
        for clear_id in recipe.get("clear_carrier_ids", []):
            translations[clear_id] = ""
        reports.append({
            "event_id": event_id,
            "snes_ids": [carrier_id],
            "android_ids": recipe["android_ids"],
            "confidence": "coverage_audit_confirmed_android_fr_repair",
            "coverage_repair": True,
            "coverage_repair_mode": recipe["mode"],
            "formatted_entries": ([{"id": carrier_id, "text": translations[carrier_id]}] + [
                {"id": clear_id, "text": ""} for clear_id in recipe.get("clear_carrier_ids", [])
            ]),
        })
    return reports

def _load_reviewed_choice_layout_recipes(source_document: dict) -> dict[str, dict]:
    """Load structural-only reviewed choice presentation decisions.

    These recipes deliberately contain no localized prose.  They only pin the
    exact canonical SNES event/carrier pair whose outer stock parentheses were
    reviewed away during Round 72.  Source-shape validation prevents a stale
    recipe from silently applying after extraction changes.
    """
    document = _load_recipe_document(
        DIALOGUE_CHOICE_LAYOUT_RECIPES,
        label="Dialogue choice-layout recipes",
        expected={"format_version": 1},
    )

    events = {event["event_id"]: event for event in source_document.get("events", [])}
    recipes: dict[str, dict] = {}
    for recipe in document.get("recipes", []):
        event_id = str(recipe.get("event_id", "")).upper()
        if not event_id or event_id in recipes:
            raise ValueError(f"Duplicate/invalid reviewed choice-layout event {event_id!r}")
        if recipe.get("strategy") != "strip_outer_choice_decoration":
            raise ValueError(f"Unsupported reviewed choice-layout strategy for ${event_id}")
        event = events.get(event_id)
        if event is None:
            raise ValueError(f"Reviewed choice-layout recipe references unknown event ${event_id}")
        token_ids = {
            token.get("id") for token in event.get("tokens", [])
            if token.get("type") in {"text", "ending_text"}
        }
        opening_id = recipe.get("opening_text_id")
        closing_id = recipe.get("closing_text_id")
        if opening_id not in token_ids or closing_id not in token_ids:
            raise ValueError(
                f"Reviewed choice-layout recipe ${event_id} carrier IDs no longer match source"
            )
        recipes[event_id] = {
            "event_id": event_id,
            "strategy": recipe["strategy"],
            "opening_text_id": opening_id,
            "closing_text_id": closing_id,
        }
    return recipes


def require_parallel_scrtxt(english: dict[int, str], french: dict[int, str]) -> None:
    """Require English/French containers to expose the same Android ID namespace."""
    if set(english) != set(french):
        missing_fr = sorted(set(english) - set(french))
        missing_en = sorted(set(french) - set(english))
        details = []
        if missing_fr:
            details.append("missing in French: " + ", ".join(map(str, missing_fr[:10])))
        if missing_en:
            details.append("missing in English: " + ", ".join(map(str, missing_en[:10])))
        raise ValueError("Android scrtxt ID sets differ (" + "; ".join(details) + ")")


def normalize_android_prose(text: str) -> str:
    """Remove source-layout whitespace while preserving the translated prose."""
    return " ".join(text.replace("\r", " ").replace("\n", " ").split())


def make_intro_translation(scrtxt: dict[int, str]) -> dict:
    source = load_intro_source(ROOT / "assets" / "intro_event.json")
    source_ids = tuple(entry["id"] for entry in source["entries"])
    if source_ids != INTRO_TARGET_IDS:
        raise ValueError(
            "assets/intro_event.json IDs/order no longer match the validated Android intro mapping"
        )

    missing = [text_id for text_id in INTRO_ANDROID_IDS if text_id not in scrtxt]
    if missing:
        raise ValueError("Missing Android intro text ID(s): " + ", ".join(map(str, missing)))

    entries = [
        {
            "id": target_id,
            "text": normalize_android_prose(scrtxt[android_id]),
        }
        for android_id, target_id in zip(INTRO_ANDROID_IDS, INTRO_TARGET_IDS, strict=True)
    ]
    return {
        "format_version": 1,
        "language": "fr",
        "source_asset": "intro_event.json",
        "groups": [
            {
                "group": "intro.event_0400",
                "entries": entries,
            }
        ],
    }


@lru_cache(maxsize=None)
def normalize_alignment_text(text: str) -> str:
    """Normalize English text for cross-version comparison, not for translation output."""
    text = re.sub(r"%S\([^)]*\)", " playername ", text, flags=re.IGNORECASE)
    text = text.replace("_", " ")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.casefold()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def load_dialogue_text_entries(path: Path = DIALOGUE_SOURCE) -> dict[str, dict]:
    document = json.loads(path.read_text(encoding="utf-8"))
    result: dict[str, dict] = {}
    for event in document.get("events", []):
        event_id = event.get("event_id")
        for token_index, token in enumerate(event.get("tokens", [])):
            if token.get("type") != "text":
                continue
            text_id = token.get("id")
            source = token.get("source")
            if not isinstance(text_id, str) or not isinstance(source, str):
                raise ValueError(f"{path}: malformed dialogue text token in event {event_id}")
            if text_id in result:
                raise ValueError(f"{path}: duplicate dialogue text ID {text_id}")
            result[text_id] = {
                "event_id": event_id,
                "token_index": token_index,
                "source": source,
            }
    return result



def english_anchor_interval(anchor_id: int, english: dict[int, str]) -> list[int]:
    """Return an English non-empty ID plus following empty slots up to the next anchor."""
    if anchor_id not in english or not english[anchor_id]:
        raise ValueError(f"Android English ID {anchor_id} is not a non-empty anchor")
    ids = [anchor_id]
    next_id = anchor_id + 1
    while next_id in english and english[next_id] == "":
        ids.append(next_id)
        next_id += 1
    return ids


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_snes_review_parts(parts: tuple, source: dict[str, dict], *, event_id: str) -> tuple[list[str], str]:
    """Render canonical SNES source parts plus explicit dynamic-name placeholders."""
    snes_ids: list[str] = []
    chunks: list[str] = []
    for part in parts:
        if isinstance(part, str):
            if part not in source:
                raise ValueError(f"Dialogue review source ID {part} is absent from assets/dialogues.json")
            if source[part]["event_id"] != event_id:
                raise ValueError(
                    f"Dialogue review source ID {part} moved from event {event_id} "
                    f"to {source[part]['event_id']}"
                )
            snes_ids.append(part)
            chunks.append(source[part]["source"])
        elif (
            isinstance(part, tuple)
            and len(part) == 2
            and part[0] == "player_name"
            and isinstance(part[1], int)
        ):
            chunks.append(f"%S({part[1]},0)")
        else:
            raise ValueError(f"Unsupported dialogue review SNES part: {part!r}")
    return snes_ids, "".join(chunks)


def android_anchor_units(anchor_ids: tuple[int, ...], english: dict[int, str]) -> list[int]:
    """Expand one or more English anchors to include their localization slots."""
    result: list[int] = []
    for anchor_id in anchor_ids:
        for text_id in english_anchor_interval(anchor_id, english):
            if text_id not in result:
                result.append(text_id)
    return result



# ---- Conservative whole-dialogue Android alignment -------------------------

DEFAULT_DIALOGUE_AUTO_OUTPUT = ROOT / "mappings" / "android" / "dialogues_auto.json"
DEFAULT_DIALOGUE_UNMAPPED_CSV = ROOT / "mappings" / "android" / "dialogues_unmapped.csv"
DEFAULT_DIALOGUE_FORMAT_MASS_OUTPUT = ROOT / "translations" / "dialogues_french.json"
DEFAULT_DIALOGUE_FORMAT_MASS_REPORT = ROOT / "mappings" / "android" / "dialogues_format_mass.json"
DEFAULT_DIALOGUE_FORMAT_MASS_EXCLUDED_CSV = ROOT / "mappings" / "android" / "dialogues_format_mass_excluded.csv"
# These two stress-test sources were explicitly reviewed and have no confident
# standalone Android-English equivalent. Automatic passes must never force them.
DIALOGUE_FORCED_UNMAPPED = {
    "C9:902F": "Round-5 validated unmatched case: nearby Android text compresses/redistributes the explanation; no confident standalone English anchor.",
    "CA:437D": "Round-5 validated unmatched case: the nearby Android exclamation is semantically different.",
    "C9:2179": "Round-47 trigger-proven Cannon route with no unique Android equivalent: $00EE is used by map triggers $0049/$011C, but Android reorganizes the Cannon network and has no provenance-safe standalone counterpart for SNES 'All aboard for Pandora!'. Do not recycle another Pandora response.",
    "C9:2208": "Round-47 trigger-proven Cannon route with no unique Android equivalent: $00F1 is used by map trigger $0121, but Android has no provenance-safe standalone counterpart for SNES 'For Pandora!'. Do not recycle another Pandora response.",
    "C9:2268": "Round-47 trigger-proven Cannon route with no unique Android equivalent: $00F3 is used by map trigger $011F, while Android contains multiple Ice Country Cannon responses belonging to other scene blocks. Do not force one by destination text alone.",
    "C9:A49C": "Round-47 unreferenced duplicate audit: $0269 has no incoming OP_10..27 event reference, no map trigger and no map-object event reference in the canonical routing tables. The actually used Truffle line $0276 is called from $04E3 and already owns Android 1400. Keep $0269 as an orphan stock duplicate instead of forcing reuse of 1400.",
    "C9:C4FB": "Round-47 unreferenced stock audit: $02DE has no incoming OP_10..27 event reference, no map trigger and no map-object event reference, unlike the surrounding live Tasnica NPC scripts. No Android-English identity is established; do not force a loose medicine-line candidate.",
    "CA:85FC": "Round-47 unreferenced sign audit: $0603 ('Topaz Falls') is the only $0600-$0609 sign event with no incoming event reference, map trigger or map-object reference in the canonical routing tables, and Android scrtxt/systxt contains no Topaz Falls anchor. Preserve it as an orphan stock sign rather than inventing an identity.",
}

# A stronger omission proof: an already accepted neighboring mapping explicitly
# documents that Android EN drops this standalone SNES fragment rather than
# translating/resegmenting it elsewhere.  Keep the carrier unmapped, but this
# status may admit a conservative PARTIEL event around it.
DIALOGUE_VALIDATED_ANDROID_OMISSIONS = {
    "C9:1057": (
        "Round-47 sprite-naming branch omission: $0041 conditionally transfers to $0042 after Android-aligned naming response 625, and both paths rejoin at the already aligned join message 628. Android 623-628 contains no counterpart for the alternate SNES 'Well, let's go!' line."
    ),
    "C9:916F": (
        "Round-47 Water Palace trigger omission: map $0053 directly selects $0207 on the same trigger pair that selects $0206 ('That's impossible!' -> Android 837). The Water Palace Android scene has no standalone counterpart for SNES 'Proof that Mana is fading!'; superficially similar Android 2310 belongs to Mandala and 890 is already the distinct $04E9 dialogue."
    ),
    "C9:9193": (
        "Round-47 Water Palace trigger omission: map $004B directly selects $0208 in the same stateful trigger set as $020A (Android 938-942). The corresponding Android Water Palace material omits the boy's standalone reflection that everyone is angry because he pulled the Sword; the Potos elder line about pulling the Sword is a different scene."
    ),
    "C9:9F88": (
        "Round-47 Wind Palace branch omission: $04E2 conditionally branches to $024F before its already aligned Grandpa/Sylphid sequence. Android 1274-1308 covers the same Wind Palace aftermath but contains no standalone counterpart for SNES 'The Empire sent monsters into the palace!'."
    ),
    "C9:CAA6": (
        "Round-47 Tasnica diary omission: non-text event $02FB conditionally transfers to optional diary event $02FC immediately before the already aligned Tasnica spy aftermath. Android 2578-2605 contains the king/spy sequence but omits this diary interaction entirely."
    ),
    "C9:CAC2": (
        "Round-47 Tasnica diary omission: this is the diary body in optional event $02FC reached from $02FB; Android's corresponding Tasnica spy block 2578-2605 has no diary text."
    ),
    "C9:CB0C": (
        "Round-47 Tasnica diary omission: this '(Text suddenly stops)' carrier belongs to optional event $02FC, absent from Android's corresponding Tasnica spy block 2578-2605."
    ),
    "C9:CB28": (
        "Round-47 Tasnica diary omission: the player's 'What does this mean?' closes optional event $02FC, which is absent from Android's corresponding Tasnica spy block 2578-2605."
    ),
    "C9:C56C": (
        "Round-48 Tasnica live-NPC omission: map $001A object #0 at ROM $089538 (raw 3C 0E 8C 16 50 B7 E1 C2) directly selects event $02E1 under the same $3C state family as live Tasnica NPCs $02E2-$02E7. Android 2539-2577 covers the corresponding Tasnica castle NPC block and anchors all surrounding live scripts, but contains no counterpart for SNES 'We'll smash the Empire!'. Keep it unmapped rather than borrowing another Empire line."
    ),
    "C9:30F5": (
        "Round-2 validated omission: Android 62 covers only the following player line; "
        "its accepted mapping explicitly records that the standalone SNES 'ELLIOTT:You!' fragment is absent."
    ),
    "CA:6629": (
        "Round-31 validated omission: accepted Android EN 2188 is followed only by empty slot 2189, "
        "then the scene resumes at accepted 2190; there is no Android-English anchor for the standalone "
        "SNES PLAYER_NAME(2) ':We can too!' fragment."
    ),
    "C9:A730": (
        "Round-51 residual audit: the controller instruction 'Press START to see the map.' was already "
        "user-validated as absent from Android and retained as a manual supplement. Exhaustive scrtxt EN "
        "inspection contains no START/map controller instruction counterpart; keep it outside Android identity."
    ),
    "C9:A74E": (
        "Round-51 residual audit: the controller instruction 'L/R buttons change modes.' was already "
        "user-validated as absent from Android and retained as a manual supplement. Exhaustive scrtxt EN "
        "inspection contains no L/R/button/mode counterpart; keep it outside Android identity."
    ),
    "C9:CE5A": (
        "Round-51 residual audit: the stock 30-GP caller belongs to the standard shared inn path $0330/$0331. "
        "Android scrtxt has exact standard prompts for 5, 10, 15, 50, 100, 120, 150 and 200 GP, but no "
        "standard 30-GP prompt. Android 194 is a distinct Neko/meow localization and must not be reused."
    ),
}

# Round 57 compares the reviewed Android omissions against the original
# Japanese SNES ROM supplied by the user. This is provenance/serialization
# evidence only; it never creates Android identity.


# These semantic carriers are real stock prose fragments, but they are shared
# subroutine templates whose Android identity is determined by the numeric
# caller.  No single Android scrtxt record owns them independently: executions
# correspond to the reviewed per-price prompt family (110/229/502/1365/1907/
# 1961/2319/2498, with equivalent duplicates).  Keep them unresolved in the
# 1798/1838 one-carrier identity count while recording that this is deliberate,
# not an unreviewed lexical hole.
DIALOGUE_VALIDATED_CONTEXTUAL_TEMPLATES = {
    "C9:CEA3": (
        "Round-51 residual audit: shared $0330 prefix 'One night is' has no single Android identity. "
        "Its runtime meaning is completed by the caller-supplied price before shared $0331; Android stores "
        "the resulting complete prompt as separate per-price records. Serialization remains the validated "
        "parameterized inn template and must not assign this carrier to representative Android 110."
    ),
    "C9:CEB3": (
        "Round-51 residual audit: shared $0331 suffix 'GP. Want to stay?' has no single Android identity. "
        "It is reused after every caller-supplied price, while Android stores complete per-price prompts. "
        "Serialization remains the validated parameterized inn template and must not inflate semantic alignment "
        "by assigning the shared suffix to representative Android 110."
    ),
}

# Reviewed structural corrections that intentionally replace an automatic
# lexical choice. The generic calibration guard remains active for every other
# reviewed source ID.
DIALOGUE_REVIEWED_AUTO_OVERRIDES = frozenset({"CA:696C", "C9:E5BF"})

# The pilot proved that these duplicated Android locations carry equivalent
# English/French content even though provenance cannot select one copy. Keep the
# alternatives explicit instead of inventing a single Android ID.
DIALOGUE_VALIDATED_ALTERNATIVE_GROUPS = {
    "C9:089B": ((3314,), (3360,)),
    "C9:0C19": ((2667,), (2793,)),
    "C9:0B03": ((2449, 2450), (2463, 2464)),
    "C9:392C": ((792,), (796,)),
}

# These events were explicitly reviewed by the user as visually complete even
# though the Android adaptation intentionally omits some stock SNES semantic
# fragments. Keep their exact simulator-clean French-only bytes, but do not
# count them as PARTIEL in the preview/report. Alignment may later prove an
# identity for an omitted source fragment; that new identity must not silently
# change the already runtime-validated translated serialization.
DIALOGUE_USER_VALIDATED_VISUALLY_COMPLETE_SUPPRESSIONS = {
    "0103": frozenset({"C9:2627", "C9:26A8", "C9:2728", "C9:2735", "C9:2745"}),
    "013A": frozenset({"C9:40D7"}),
    "017F": frozenset({"C9:55FC"}),
    "01DC": frozenset({"C9:804A"}),
}

# User-approved Android omissions that are safe to suppress locally even though
# the containing event remains PARTIEL for unrelated mapped/layout-deferred
# carriers.  These IDs do not make the whole event visually complete.
DIALOGUE_USER_VALIDATED_PARTIAL_SUPPRESSIONS = {
    "010C": frozenset({"C9:30F5"}),
    "02FC": frozenset({"C9:CB28"}),
    "0558": frozenset({"CA:6629"}),
}
# Round 69: after scene-level semantic review, the following former PARTIEL
# events are considered fully translated/complete. They remain traceable below
# through user_validated_visually_complete_events, preserving whether completion
# came from a manual supplement, a shared-prefix resegmentation, or a validated
# SNES/JP-absent suppression.
DIALOGUE_USER_VALIDATED_SEMANTICALLY_COMPLETE_EVENTS = frozenset({
    "001E", "0042", "00EE", "00F1", "00F3", "0207", "0208", "024F",
    "0278", "02E1", "02FC", "035F", "04E1", "04E8", "0558",
})
DIALOGUE_USER_VALIDATED_VISUALLY_COMPLETE_EVENTS = frozenset(
    set(DIALOGUE_USER_VALIDATED_VISUALLY_COMPLETE_SUPPRESSIONS)
    | set(DIALOGUE_USER_VALIDATED_SEMANTICALLY_COMPLETE_EVENTS)
)

# These events remain semantically alignment-incomplete and keep their exact
# mixed/stock serialization, but runtime review confirmed that no missing or
# English content is visibly exposed to the player. They therefore remain
# traceable as unresolved alignment without carrying the PARTIEL badge.
DIALOGUE_USER_VALIDATED_VISUALLY_COMPLETE_STATUS_OVERRIDES = frozenset({"0602"})

# $01DC has one Android-adaptation omission that includes a structural speaker
# carrier, not just semantic text. The user explicitly validated dropping the
# final stock PLAYER_NAME(0) together with C9:804A because Android 729 begins
# the following Niccolo scene directly after Android 728. The source asset stays
# canonical; this exact command is omitted only in translated serialization.
DIALOGUE_USER_VALIDATED_STRUCTURAL_OMISSIONS = (
    {
        "event_id": "013A",
        "suppressed_semantic_ids": ["C9:40D7"],
        "suppressed_commands": [
            {
                "name": "WAIT",
                "args": "00",
                "immediately_after_text_id": "C9:40D7",
            }
        ],
        "reason": "round67_user_validated_snes_jp_absent_android_fr_adaptation_suppression",
    },
    {
        "event_id": "04E1",
        "suppressed_semantic_ids": ["CA:2C84"],
        "suppressed_commands": [
            {
                "name": "WAIT",
                "args": "00",
                "immediately_after_text_id": "CA:2C84",
            }
        ],
        "reason": "round63_user_validated_resegmented_snes_jp_page_suppression",
    },
    {
        "event_id": "02FC",
        "suppressed_semantic_ids": ["C9:CB28"],
        "suppressed_commands": [
            {
                "name": "PLAYER_NAME",
                "args": "00",
                "immediately_before_text_id": "C9:CB28",
            },
            {
                "name": "WAIT",
                "args": "00",
                "immediately_after_text_id": "C9:CB28",
            },
        ],
        "reason": "round57_user_validated_snes_jp_absent_line",
    },
    {
        "event_id": "0558",
        "suppressed_semantic_ids": ["CA:6629"],
        "suppressed_commands": [
            {
                "name": "PLAYER_NAME",
                "args": "02",
                "immediately_before_text_id": "CA:6629",
            }
        ],
        "reason": "round57_user_validated_snes_jp_absent_line",
    },
    {
        "event_id": "01DC",
        "suppressed_semantic_ids": ["C9:804A"],
        "suppressed_commands": [
            {
                "name": "PLAYER_NAME",
                "args": "00",
                "immediately_before_text_id": "C9:804A",
            }
        ],
        "reason": "user_validated_android_adaptation_omission",
    },
    {
        "event_id": "01DA",
        "suppressed_semantic_ids": ["C9:7E81"],
        "suppressed_commands": [
            {
                "name": "PLAYER_NAME",
                "args": "00",
                "immediately_before_text_id": "C9:7E81",
            }
        ],
        "reason": "round45_user_authorized_android_fr_name_resegmentation",
    },
)


# Round 67: Android FR $04E2 assigns the complete reaction to PLAYER_NAME(2),
# while stock SNES splits the same region between PLAYER_NAME(1) and
# PLAYER_NAME(2). The user explicitly approved redistributing Android 1281 over
# CA:32C5/CA:32D7. Keep the canonical source untouched; translated serialization
# changes only the first adjacent PLAYER_NAME index and omits the now-redundant
# second identical speaker command.
DIALOGUE_USER_VALIDATED_STRUCTURAL_COMMAND_OVERRIDES = (
    {
        "event_id": "01C5",
        "commands": [
            {
                "name": "CHOICE_OPTION",
                "args": "08",
                "immediately_before_text_id": "C9:7140",
                "translated_args": "0D",
            },
        ],
        "reason": "round69_android_fr_continue_exit_choice_anchor",
    },
    {
        "event_id": "0205",
        "commands": [
            {
                "name": "PLAYER_NAME",
                "args": "00",
                "immediately_before_text_id": "C9:90DE",
                "omit": True,
            },
        ],
        "reason": "round69_whole_scene_android_fr_0204_0205_continuation",
    },
    {
        "event_id": "0227",
        "commands": [
            {
                "name": "PLAYER_NAME",
                "args": "01",
                "immediately_before_text_id": "C9:9827",
                "omit": True,
            },
        ],
        "reason": "round69_user_requested_move_player_name_inside_C9_9827",
    },
    {
        "event_id": "04E6",
        "commands": [
            {
                "name": "PLAYER_NAME",
                "args": "00",
                "immediately_before_text_id": "CA:3FC1",
                "omit": True,
            },
            {
                "name": "WAIT",
                "args": "00",
                "immediately_before_text_id": "CA:3FE4",
                "omit": True,
            },
        ],
        "reason": "round69_user_requested_move_player_name_inside_CA_3FC1",
    },
    {
        "event_id": "0559",
        "commands": [
            {
                "name": "PLAYER_NAME",
                "args": "00",
                "immediately_before_text_id": "CA:6741",
                "omit": True,
            },
            {
                "name": "PLAYER_NAME",
                "args": "01",
                "immediately_before_text_id": "CA:6744",
                "omit": True,
            },
        ],
        "reason": "round69_android_fr_2147_player_name_resegmentation",
    },
    {
        "event_id": "0592",
        "commands": [
            {
                "name": "PLAYER_NAME",
                "args": "02",
                "immediately_before_text_id": "CA:748F",
                "omit": True,
            },
        ],
        "reason": "round69_android_fr_1023_omits_sprite_name_label",
    },
    {
        "event_id": "04E2",
        "commands": [
            {
                "name": "PLAYER_NAME",
                "args": "01",
                "immediately_before_text_id": "CA:32C5",
                "translated_args": "02",
            },
            {
                "name": "PLAYER_NAME",
                "args": "02",
                "immediately_before_text_id": "CA:32D7",
                "omit": True,
            },
        ],
        "reason": "round67_user_validated_android_fr_1281_speaker_resegmentation",
    },
)


# $0331 remains semantically PARTIEL because the generic inn prompt carrier
# C9:CEB3 has no single proven Android identity. Suppressing its visible stock
# English must nevertheless preserve its two stock NEWLINEs: runtime testing
# proved that the choice row must stay on its original third physical line for
# the stock selection/highlight geometry to target the rendered Oui/Non row.
# This is layout-only metadata, never localized prose.
DIALOGUE_USER_VALIDATED_PARTIAL_LAYOUT_PRESERVATIONS = ()

# Reviewed PARTIEL-only layout deferrals. These do not weaken Android-English
# identity: the listed mapping remains accepted, but its stock SNES carrier is
# deliberately left untranslated because official Android French cannot be
# serialized without changing the canonical PLAYER_NAME/text ownership. The
# event remains visibly PARTIEL/TO REVIEW, and admission still requires a clean
# independent simulation.
DIALOGUE_REVIEWED_PARTIAL_LAYOUT_DEFERRALS = {}

# Generic structural safe-subset PARTIEL is deliberately disabled for the two
# alignment-incomplete scenes whose handoff already records a semantic/resegmentation
# hazard. Their problem is not merely layout, so leaving a few mapped carriers stock
# would give a misleadingly usable mixed scene.
DIALOGUE_GENERIC_PARTIAL_LAYOUT_DEFERRAL_BLOCKLIST = frozenset({"015A", "0204"})


# Manual supplements never create Android identity. Most are exact SNES carriers
# whose complete absence from Android was explicitly reviewed; Round 62 also
# allows one exact already-mapped carrier as a provenance-rich layout-review
# surcharge. Pending entries always keep the stock USA payload active.
DIALOGUE_USER_VALIDATED_ANDROID_ABSENT_MANUAL_IDS = {
    # Round 57: direct comparison with the original Japanese SNES ROM proves
    # these lines/scenes are genuine SNES content omitted by the Android port.
    # They stay outside Android identity and are routed through the manual
    # supplement file until a human-approved French translation is supplied.
    "0042": frozenset({"C9:1057"}),
    "0207": frozenset({"C9:916F"}),
    "0208": frozenset({"C9:9193"}),
    "024F": frozenset({"C9:9F88"}),
    "0278": frozenset({"C9:A730", "C9:A74E"}),
    "02E1": frozenset({"C9:C56C"}),
    "02FC": frozenset({"C9:CAA6", "C9:CAC2", "C9:CB0C"}),
    # Round 43: Android has no Dryad "magic will work" anchor. The user
    # explicitly authorizes a temporary French payload while keeping the
    # semantic identity unresolved/reviewable.
    "035F": frozenset({"C9:D1B8"}),
}

# Round 64 stages the remaining user-facing "NON TROUVÉ — PAS D’ÉQUIVALENT
# UNIQUE" carriers in the same provenance-rich manual-review schema. These
# entries never create Android identity. Round 65 explicitly approves four of
# the five JP-led proposals; Round 66 explicitly approves the final $0204
# carrier too, while preserving the event's broader resegmentation block.
DIALOGUE_USER_REQUESTED_UNMAPPED_MANUAL_REVIEW_IDS = {
    "00EE": frozenset({"C9:2179"}),
    "013A": frozenset({"C9:40D7"}),
    "00F1": frozenset({"C9:2208"}),
    "00F3": frozenset({"C9:2268"}),
    "04E8": frozenset({"CA:437D"}),
}

# $04E8 already needed an ordinary PARTIEL layout repair before its unresolved
# stock carrier was manually approved. Apply that one validated manual carrier
# only *after* the existing mixed-event repair pipeline has succeeded, then
# re-simulate. This exact deferral prevents the new approval from disabling or
# replacing unrelated, already-proven PARTIEL formatting repairs.
DIALOGUE_PARTIAL_MANUAL_POST_REPAIR_IDS = {
    "04E8": frozenset({"CA:437D"}),
}

# Round 66: $0204 remains deliberately blocked from the generic PARTIEL
# formatter because its Android-FR material is semantically resegmented and
# two mapped carriers still cross unsupported PLAYER_NAME ownership. The user
# nevertheless approved the exact JP-led manual carrier C9:902F. Admit only
# that carrier on top of the otherwise stock USA event, then require a clean
# whole-event simulation. Do not use this as permission to release any of the
# other $0204 Android mappings.
DIALOGUE_MANUAL_ONLY_RESEGMENTED_PARTIAL_IDS = {
}

# Round 62 also uses the same provenance-rich review schema for one already
# identified Android carrier whose official French cannot be serialized through
# the canonical USA WAIT split. This is a review surcharge, not an Android
# omission. Round 63 subsequently validated suppressing the standalone page.
DIALOGUE_USER_REQUESTED_MAPPED_MANUAL_REVIEW_IDS = {
    "04E1": frozenset({"CA:2C84"}),
}

# Exact unresolved shared-prefix redistributions. These preserve Android identity
# honesty: no Android ID is assigned, but a redundant SNES-English prefix may be
# reduced to layout-only bytes when every already-proven Android destination owns
# the localized subject itself. The event remains PARTIEL/alignment-unresolved.
DIALOGUE_REVIEWED_UNMAPPED_LAYOUT_RESEGMENTATIONS = {
    "001E": {
        "C9:0970": {
            "text": "\n",
            "reason": "shared Jehk/Jach subject prefix is absorbed by Android 2453/2455/2458/2461; preserve the stock leading NEWLINE after WAIT $00",
        },
    },
}

# Exact payload exceptions where Android English identity is accepted but the
# user has explicitly rejected the corresponding Android French localization.
# Keep this allow-list exact: this is not a generic preference for stock English.
DIALOGUE_USER_VALIDATED_STOCK_ENGLISH_OVERRIDES = {
    ("0689", "CA:8F20", 769): (
        "Android FR duplicates the Leather-Whip chest text onto the Magic Rope; "
        "$0689 OP_1E A4 proves the Whip/Leather Whip identity, while $0687 OP_1E 46 "
        "is the actual Magic Rope chest."
    ),
}

# Every alignment-incomplete event is reconsidered on each mass pass. Accepted
# mappings are rendered in French while unresolved semantic carriers remain
# untouched, so their stock SNES English stays visible in-game. The event is
# admitted only when that mixed FR/EN serialization is simulator-clean and is
# always marked PARTIEL. User-validated visually complete adaptations keep their
# separate frozen-omission policy.


def _load_manual_dialogue_supplements(source_document: dict) -> dict[str, dict[str, dict]]:
    document = json.loads(DIALOGUE_MANUAL_SUPPLEMENTS.read_text(encoding="utf-8"))
    format_version = document.get("format_version")
    if format_version not in {1, 2} or document.get("language") != "fr":
        raise ValueError("dialogues_manual_supplements.json: unsupported format/language")
    if document.get("source_asset") != "assets/dialogues.json":
        raise ValueError("dialogues_manual_supplements.json: invalid source_asset")
    by_id, _ = event_text_index(source_document)
    result: dict[str, dict[str, dict]] = {}
    for source_entry in document.get("entries", []):
        if not isinstance(source_entry, dict):
            raise ValueError("dialogues_manual_supplements.json: entries must be objects")
        entry = dict(source_entry)
        event_id = entry.get("event_id")
        text_id = entry.get("id")
        status = entry.get("status")
        reason = entry.get("reason")
        if format_version == 1:
            original_en = entry.get("source_en")
            translation_fr = entry.get("text")
            if status == "needs_manual_translation" and translation_fr != original_en:
                raise ValueError(
                    f"Manual supplement ${event_id}/{text_id}: legacy pending entries must retain stock USA text"
                )
            entry.setdefault("original_jp", None)
            entry.setdefault("original_fr", None)
            entry["original_en"] = original_en
            entry["translation_fr"] = translation_fr
        else:
            missing_fields = [
                key for key in ("original_jp", "original_en", "original_fr", "translation_fr")
                if key not in entry
            ]
            if missing_fields:
                raise ValueError(
                    f"Manual supplement ${event_id}/{text_id}: missing v2 fields {missing_fields}"
                )
            original_en = entry.get("original_en")
            translation_fr = entry.get("translation_fr")
            original_jp = entry.get("original_jp")
            original_fr = entry.get("original_fr")
            if original_jp is not None and not isinstance(original_jp, str):
                raise ValueError(f"Manual supplement ${event_id}/{text_id}: original_jp must be string or null")
            if original_fr is not None and not isinstance(original_fr, str):
                raise ValueError(f"Manual supplement ${event_id}/{text_id}: original_fr must be string or null")
            proposal_action = entry.get("proposal_action")
            if not isinstance(translation_fr, str):
                raise ValueError(f"Manual supplement ${event_id}/{text_id}: translation_fr must be a string")
            if not translation_fr and not (
                (status == "needs_manual_translation" and proposal_action == "suppress")
                or status == "suppressed"
            ):
                raise ValueError(
                    f"Manual supplement ${event_id}/{text_id}: empty translation_fr is allowed only "
                    "for a pending explicit suppression proposal or a validated suppression"
                )
        absent_allowed = DIALOGUE_USER_VALIDATED_ANDROID_ABSENT_MANUAL_IDS.get(event_id, frozenset())
        unmapped_review_allowed = DIALOGUE_USER_REQUESTED_UNMAPPED_MANUAL_REVIEW_IDS.get(event_id, frozenset())
        mapped_review_allowed = DIALOGUE_USER_REQUESTED_MAPPED_MANUAL_REVIEW_IDS.get(event_id, frozenset())
        if (
            text_id not in absent_allowed
            and text_id not in unmapped_review_allowed
            and text_id not in mapped_review_allowed
        ):
            raise ValueError(
                f"Manual supplement ${event_id}/{text_id}: carrier is outside the exact manual-review allow-lists"
            )
        meta = by_id.get(text_id)
        if meta is None or meta.get("event_id") != event_id:
            raise ValueError(f"Manual supplement ${event_id}/{text_id}: unknown/mismatched source carrier")
        if original_en != meta.get("source"):
            raise ValueError(
                f"Manual supplement ${event_id}/{text_id}: original_en is not byte-faithful to assets/dialogues.json"
            )
        if status not in {"needs_manual_translation", "translated", "suppressed"}:
            raise ValueError(f"Manual supplement ${event_id}/{text_id}: invalid status")
        if status == "suppressed":
            allowed_suppressions = {
                ("04E1", "CA:2C84"): "user_validated_resegmented_snes_jp_suppression",
                ("013A", "C9:40D7"): "user_validated_snes_jp_absent_suppression",
            }
            expected_reason = allowed_suppressions.get((event_id, text_id))
            if expected_reason is None:
                raise ValueError(f"Manual supplement ${event_id}/{text_id}: suppression is not allow-listed")
        else:
            expected_reason = (
                "user_validated_absent_from_android"
                if text_id in absent_allowed
                else (
                    "user_requested_unmapped_carrier_review"
                    if text_id in unmapped_review_allowed
                    else "user_requested_mapped_carrier_review"
                )
            )
        if reason != expected_reason:
            raise ValueError(
                f"Manual supplement ${event_id}/{text_id}: invalid reason {reason!r}; expected {expected_reason!r}"
            )
        # Round 58: proposals are review-only until explicit user approval.  A
        # pending entry therefore serializes the canonical USA carrier even when
        # translation_fr contains a proposed JP-led French wording.
        entry["_active_text"] = (
            original_en if status == "needs_manual_translation"
            else "" if status == "suppressed"
            else translation_fr
        )
        if text_id in result.setdefault(event_id, {}):
            raise ValueError(f"Manual supplement ${event_id}/{text_id}: duplicate entry")
        result[event_id][text_id] = entry
    expected_by_event: dict[str, set[str]] = {}
    for allow_map in (
        DIALOGUE_USER_VALIDATED_ANDROID_ABSENT_MANUAL_IDS,
        DIALOGUE_USER_REQUESTED_UNMAPPED_MANUAL_REVIEW_IDS,
        DIALOGUE_USER_REQUESTED_MAPPED_MANUAL_REVIEW_IDS,
    ):
        for event_id, allowed in allow_map.items():
            expected_by_event.setdefault(event_id, set()).update(allowed)
    for event_id, expected in expected_by_event.items():
        actual = frozenset(result.get(event_id, {}))
        if actual != frozenset(expected):
            raise ValueError(
                f"Manual supplement ${event_id}: expected {sorted(expected)}, got {sorted(actual)}"
            )
    extra_events = set(result) - set(expected_by_event)
    if extra_events:
        raise ValueError(f"Manual supplement unexpected event(s): {sorted(extra_events)}")
    return result


def _format_manual_supplement(
    source_document: dict, entry: dict, advances: dict[str, int]
) -> tuple[str, dict]:
    text_id = entry["id"]
    _, by_event = event_text_index(source_document)
    source_event = by_event[entry["event_id"]]
    source_token = next(token for token in source_event["tokens"] if token.get("id") == text_id)
    mapping = {
        "event_id": entry["event_id"],
        "snes_ids": [text_id],
        "android_ids": [],
        "confidence": (
            "user_requested_unmapped_manual_review"
            if entry.get("reason") == "user_requested_unmapped_carrier_review"
            else "user_validated_android_absent_manual"
        ),
        "source_display": source_token.get("source", ""),
        "french_display": entry["_active_text"],
    }
    values, report = format_dialogue_mapping(
        source_document, mapping, advances,
        allow_one_extra_page=False,
        use_physical_page_capacity=True,
        prefer_semantic_line_breaks=True,
    )
    # $0208 has a stock PLAYER_NAME immediately before the manual carrier.
    # The generic isolated-carrier formatter does not count the worst-case
    # expanded player name in its first-line capacity, so its otherwise valid
    # two-line compaction would trigger a runtime parser wrap. Preserve the
    # explicit three-line supplement layout for both review and approved text;
    # this keeps PLAYER_NAME capacity honest instead of compacting the carrier
    # in isolation.
    if entry["event_id"] == "0208" and text_id == "C9:9193":
        values[text_id] = entry["_active_text"]
        report["manual_layout_policy"] = "preserve_stock_three_line_layout_for_player_name_capacity"
        report["formatted_entries"] = [{"id": text_id, "text": values[text_id]}]
    report["manual_supplement"] = True
    report["manual_status"] = entry["status"]
    report["manual_reason"] = entry["reason"]
    if entry["status"] == "needs_manual_translation":
        report["manual_translation_proposal"] = entry.get("translation_fr", "")
        report["manual_proposal_basis"] = entry.get("proposal_basis", "")
    if entry.get("temporary"):
        report["manual_temporary"] = True
        report["manual_review_note"] = entry.get("review_note", "")
    return values[text_id], report


def _format_android_extra_page(
    source_document: dict, *, event_id: str, carrier_id: str, android_id: int,
    french: dict[int, str], advances: dict[str, int]
) -> tuple[str, dict]:
    by_id, _ = event_text_index(source_document)
    mapping = {
        "event_id": event_id,
        "snes_ids": [carrier_id],
        "android_ids": [android_id],
        "confidence": "user_validated_android_extra",
        "source_display": by_id[carrier_id]["source"],
        "french_display": french[android_id],
    }
    values, report = format_dialogue_mapping(
        source_document, mapping, advances,
        allow_one_extra_page=False,
        use_physical_page_capacity=True,
        prefer_semantic_line_breaks=True,
    )
    report["android_extra_page"] = True
    return values[carrier_id], report


def _parameterized_inn_prompt(english: dict[int, str], french: dict[int, str]) -> dict:
    android_id = 110
    en = english.get(android_id, "")
    fr = normalize_android_french(french.get(android_id, ""))
    if not en.strip():
        raise ValueError("Parameterized inn template: Android EN identity slot is empty")

    # The stock event supplies the numeric price dynamically. Derive and remove
    # the corresponding leading Android-FR number instead of hardcoding either
    # the price or any localized prose.
    price = re.match(r"^\d+", fr)
    if price is None:
        raise ValueError("Parameterized inn template: Android FR must start with a numeric price")
    suffix = fr[price.end():]
    if not suffix.strip():
        raise ValueError("Parameterized inn template: empty French suffix")

    # Keep the first complete Android-FR sentence on the price line and place
    # the remaining prompt sentence on the next line. The trailing newline keeps
    # the stock choice row on the following physical line. No localized wording
    # is stored in this formatter.
    boundaries = _sentence_break_positions(suffix)
    if len(boundaries) != 1:
        raise ValueError(
            "Parameterized inn template: expected one sentence boundary before the prompt"
        )
    start, end = boundaries[0]
    punctuation_end = end
    while punctuation_end > start and suffix[punctuation_end - 1].isspace():
        punctuation_end -= 1
    first = suffix[:punctuation_end].rstrip()
    second = suffix[end:].strip()
    if not first or not second:
        raise ValueError("Parameterized inn template: incomplete Android-FR sentence structure")
    suffix = first + "\n" + second + "\n"
    return {
        "android_id": android_id,
        "android_english": en,
        "android_french": fr,
        "prefix_translation": "",
        "suffix_translation": suffix,
        "prefix_id": "C9:CEA3",
        "suffix_id": "C9:CEB3",
    }


@lru_cache(maxsize=None)
def _auto_metrics(source: str, candidate: str) -> dict[str, float]:
    """Fast deterministic lexical metrics used only by the automatic aligner."""
    try:
        from rapidfuzz import fuzz
    except ImportError as exc:  # pragma: no cover - user environment diagnostic
        raise ValueError(
            "Automatic dialogue alignment requires RapidFuzz; install requirements.txt"
        ) from exc

    source_norm = normalize_alignment_text(source)
    candidate_norm = normalize_alignment_text(candidate)
    if not source_norm or not candidate_norm:
        return {
            "character_similarity": 0.0,
            "source_token_coverage": 0.0,
            "lexical_score": 0.0,
        }
    character_similarity = float(fuzz.ratio(source_norm, candidate_norm))
    source_tokens = source_norm.split()
    candidate_tokens = set(candidate_norm.split())
    covered = sum(token in candidate_tokens for token in source_tokens)
    source_token_coverage = 100.0 * covered / len(source_tokens)
    lexical_score = character_similarity * 0.75 + source_token_coverage * 0.25
    return {
        "character_similarity": round(character_similarity, 1),
        "source_token_coverage": round(source_token_coverage, 1),
        "lexical_score": round(lexical_score, 1),
    }


def _auto_semantic(text: str) -> bool:
    return bool(normalize_alignment_text(text))


def _auto_make_session(event: dict, session_id: int, start: int, end: int) -> dict:
    tokens = event["tokens"]
    elements = []
    for token_index in range(start, end + 1):
        token = tokens[token_index]
        if token.get("type") == "text" and _auto_semantic(token.get("source", "")):
            elements.append(
                {
                    "token_index": token_index,
                    "id": token["id"],
                    "source": token["source"],
                }
            )
    return {
        "event_id": event["event_id"],
        "session_id": session_id,
        "start": start,
        "end": end,
        "tokens": tokens,
        "elements": elements,
    }


def _auto_sessions(document: dict) -> list[dict]:
    """Split SNES events at TEXT_OPEN/TEXT_CLOSE boundaries.

    This is deliberately a local ordering hint, not a claim that Android uses
    the same event structure. Text outside an explicit open/close pair remains a
    session of its own.
    """
    sessions: list[dict] = []
    for event in document.get("events", []):
        tokens = event.get("tokens", [])
        segment_start = 0
        session_id = 0

        def append_if_semantic(start: int, end: int) -> None:
            nonlocal session_id
            if end < start:
                return
            if any(
                token.get("type") == "text" and _auto_semantic(token.get("source", ""))
                for token in tokens[start : end + 1]
            ):
                sessions.append(_auto_make_session(event, session_id, start, end))
                session_id += 1

        for token_index, token in enumerate(tokens):
            if token.get("type") == "command" and token.get("name") == "TEXT_OPEN":
                append_if_semantic(segment_start, token_index - 1)
                segment_start = token_index + 1
            elif token.get("type") == "command" and token.get("name") == "TEXT_CLOSE":
                append_if_semantic(segment_start, token_index - 1)
                segment_start = token_index + 1
        append_if_semantic(segment_start, len(tokens) - 1)
    return sessions


def _auto_render_span(session: dict, first: int, last: int) -> str:
    """Render a SNES comparison span with adjacent dynamic-name placeholders.

    All text tokens, including punctuation-only tokens such as ``...``, act as
    placeholder boundaries. This prevents a PLAYER_NAME belonging to a preceding
    punctuation token from leaking into the next semantic phrase.
    """
    elements = session["elements"]
    tokens = session["tokens"]
    first_token = elements[first]["token_index"]
    last_token = elements[last]["token_index"]
    previous_text = next(
        (
            index
            for index in range(first_token - 1, session["start"] - 1, -1)
            if tokens[index].get("type") == "text"
        ),
        None,
    )
    next_text = next(
        (
            index
            for index in range(last_token + 1, session["end"] + 1)
            if tokens[index].get("type") == "text"
        ),
        None,
    )
    start = previous_text + 1 if previous_text is not None else session["start"]
    end = next_text - 1 if next_text is not None else session["end"]
    selected = {element["token_index"] for element in elements[first : last + 1]}
    chunks: list[str] = []
    for token_index in range(start, end + 1):
        token = tokens[token_index]
        if token.get("type") == "text":
            if token_index in selected or (
                first_token <= token_index <= last_token
                and not _auto_semantic(token.get("source", ""))
            ):
                chunks.append(token.get("source", ""))
        elif token.get("type") == "command" and token.get("name") == "PLAYER_NAME":
            try:
                player_index = int(token.get("args", "00").split()[0], 16)
            except (ValueError, IndexError):
                player_index = 0
            chunks.append(f"%S({player_index},0)")
    return "".join(chunks)


class _AutoCandidateIndex:
    def __init__(self, english: dict[int, str]):
        try:
            from rapidfuzz import process
        except ImportError as exc:  # pragma: no cover - user environment diagnostic
            raise ValueError(
                "Automatic dialogue alignment requires RapidFuzz; install requirements.txt"
            ) from exc
        self.process = process
        self.anchor_ids = [
            text_id for text_id in sorted(english) if normalize_alignment_text(english[text_id])
        ]
        self.anchor_pos = {text_id: pos for pos, text_id in enumerate(self.anchor_ids)}
        self.choices = {
            text_id: normalize_alignment_text(english[text_id]) for text_id in self.anchor_ids
        }
        self.exact: dict[str, list[int]] = {}
        for text_id, normalized in self.choices.items():
            self.exact.setdefault(normalized, []).append(text_id)
        self.english = english

    def rank(self, source: str, *, limit: int = 20) -> list[dict]:
        from rapidfuzz import fuzz

        normalized = normalize_alignment_text(source)
        if not normalized:
            return []
        candidate_ids: list[int] = list(self.exact.get(normalized, ()))
        candidate_ids.extend(
            item[2]
            for item in self.process.extract(
                normalized,
                self.choices,
                scorer=fuzz.ratio,
                limit=limit,
            )
        )
        seen: set[int] = set()
        ranked: list[dict] = []
        for text_id in candidate_ids:
            if text_id in seen:
                continue
            seen.add(text_id)
            ranked.append({"android_id": text_id, **_auto_metrics(source, self.english[text_id])})
        ranked.sort(
            key=lambda item: (item["lexical_score"], item["character_similarity"]),
            reverse=True,
        )
        return ranked


def _auto_seed(session: dict, element_index: int, index: _AutoCandidateIndex) -> tuple[dict | None, list[dict]]:
    source = _auto_render_span(session, element_index, element_index)
    normalized = normalize_alignment_text(source)
    ranked = index.rank(source)
    if not ranked:
        return None, ranked
    top = ranked[0]
    second = ranked[1]["lexical_score"] if len(ranked) > 1 else 0.0
    margin = top["lexical_score"] - second
    exact_ids = index.exact.get(normalized, ())
    length = len(normalized)
    reason = None
    if len(exact_ids) == 1 and length >= 8:
        reason = "unique_exact"
    elif (
        top["lexical_score"] >= 96
        and margin >= 12
        and length >= 16
        and top["source_token_coverage"] >= 90
    ):
        reason = "near_exact_unique"
    elif (
        top["lexical_score"] >= 90
        and margin >= 18
        and length >= 28
        and top["source_token_coverage"] >= 85
    ):
        reason = "strong_fuzzy_unique"
    if reason is None:
        return None, ranked
    return {
        **top,
        "margin": round(margin, 1),
        "normalized_length": length,
        "reason": reason,
    }, ranked


def _auto_choose_window(
    session: dict,
    seeds: list[dict | None],
    rankings: list[list[dict]],
    index: _AutoCandidateIndex,
) -> tuple[int, int, str] | None:
    strong = [
        (element_index, index.anchor_pos[seed["android_id"]], seed)
        for element_index, seed in enumerate(seeds)
        if seed is not None
    ]
    if strong:
        # Longest increasing local chain. Equal positions are permitted because
        # Android may merge multiple SNES fragments into one anchor.
        dynamic: list[tuple[float, list[int]]] = []
        for point_index, (element_index, anchor_position, seed) in enumerate(strong):
            best = (1.0 + seed["lexical_score"] / 100.0, [point_index])
            for previous_index, (
                previous_element,
                previous_position,
                _previous_seed,
            ) in enumerate(strong[:point_index]):
                if (
                    previous_element < element_index
                    and previous_position <= anchor_position
                    and anchor_position - previous_position <= 120
                ):
                    score = dynamic[previous_index][0] + 1.0 + seed["lexical_score"] / 100.0
                    if score > best[0]:
                        best = (score, dynamic[previous_index][1] + [point_index])
            dynamic.append(best)
        chain_indices = max(dynamic, key=lambda item: item[0])[1]
        positions = [strong[point_index][1] for point_index in chain_indices]
        padding = max(5, len(session["elements"]) * 2)
        return (
            max(0, min(positions) - padding),
            min(len(index.anchor_ids) - 1, max(positions) + padding),
            "seed_chain",
        )

    weak: list[tuple[int, int, dict]] = []
    for element_index, ranked in enumerate(rankings):
        if not ranked:
            continue
        top = ranked[0]
        second = ranked[1]["lexical_score"] if len(ranked) > 1 else 0.0
        length = len(normalize_alignment_text(_auto_render_span(session, element_index, element_index)))
        if (
            top["lexical_score"] >= 88
            and top["lexical_score"] - second >= 12
            and length >= 18
        ):
            weak.append((element_index, index.anchor_pos[top["android_id"]], top))
    if weak:
        _, center, _ = max(weak, key=lambda item: item[2]["lexical_score"])
        padding = max(8, len(session["elements"]) * 3)
        return (
            max(0, center - padding),
            min(len(index.anchor_ids) - 1, center + padding),
            "weak_center",
        )
    return None


def _auto_align_session(
    session: dict,
    window: tuple[int, int],
    index: _AutoCandidateIndex,
    english: dict[int, str],
) -> list[dict]:
    source_count = len(session["elements"])
    lo, hi = window
    android_ids = index.anchor_ids[lo : hi + 1]
    android_count = len(android_ids)
    negative = -1.0e18
    scores = [[negative] * (android_count + 1) for _ in range(source_count + 1)]
    previous = [[None] * (android_count + 1) for _ in range(source_count + 1)]
    scores[0][0] = 0.0
    for source_index in range(source_count + 1):
        for android_index in range(android_count + 1):
            current = scores[source_index][android_index]
            if current <= negative / 2:
                continue
            if source_index < source_count and current - 22 > scores[source_index + 1][android_index]:
                scores[source_index + 1][android_index] = current - 22
                previous[source_index + 1][android_index] = (
                    source_index,
                    android_index,
                    "skip_source",
                    1,
                    0,
                    None,
                )
            if android_index < android_count and current - 6 > scores[source_index][android_index + 1]:
                scores[source_index][android_index + 1] = current - 6
                previous[source_index][android_index + 1] = (
                    source_index,
                    android_index,
                    "skip_android",
                    0,
                    1,
                    None,
                )
            for source_width in range(1, min(3, source_count - source_index) + 1):
                source = _auto_render_span(
                    session,
                    source_index,
                    source_index + source_width - 1,
                )
                for android_width in range(1, min(3, android_count - android_index) + 1):
                    candidate_ids = android_ids[android_index : android_index + android_width]
                    candidate = " ".join(english[text_id] for text_id in candidate_ids)
                    evidence = _auto_metrics(source, candidate)
                    lexical = evidence["lexical_score"]
                    coverage = evidence["source_token_coverage"]
                    if lexical < 45:
                        continue
                    value = (
                        (lexical - 45) * 1.25
                        + (coverage - 50) * 0.15
                        - 4 * (source_width + android_width - 2)
                        - 3 * abs(source_width - android_width)
                    )
                    if lexical >= 95:
                        value += 18
                    if lexical >= 99:
                        value += 12
                    if current + value > scores[source_index + source_width][android_index + android_width]:
                        scores[source_index + source_width][android_index + android_width] = current + value
                        previous[source_index + source_width][android_index + android_width] = (
                            source_index,
                            android_index,
                            "match",
                            source_width,
                            android_width,
                            evidence,
                        )

    endpoint = max(range(android_count + 1), key=lambda position: scores[source_count][position])
    source_index = source_count
    android_index = endpoint
    operations: list[dict] = []
    while source_index or android_index:
        step = previous[source_index][android_index]
        if step is None:
            break
        old_source, old_android, operation, _source_width, _android_width, evidence = step
        if operation == "match":
            operations.append(
                {
                    "first_source": old_source,
                    "last_source": source_index - 1,
                    "first_android": old_android,
                    "last_android": android_index - 1,
                    "android_ids": android_ids[old_android:android_index],
                    "evidence": evidence,
                    "source_display": _auto_render_span(session, old_source, source_index - 1),
                }
            )
        source_index, android_index = old_source, old_android
    operations.reverse()
    return operations


def _auto_accept_session_blocks(
    session: dict,
    operations: list[dict],
    seeds: list[dict | None],
) -> list[dict]:
    matches = [operation for operation in operations if "android_ids" in operation]
    accepted: list[dict] = []
    for match_index, operation in enumerate(matches):
        evidence = operation["evidence"]
        lexical = evidence["lexical_score"]
        coverage = evidence["source_token_coverage"]
        length = len(normalize_alignment_text(operation["source_display"]))
        direct_seed = any(
            seeds[element_index] is not None
            and seeds[element_index]["android_id"] in operation["android_ids"]
            for element_index in range(operation["first_source"], operation["last_source"] + 1)
        )
        left_context = match_index > 0 and matches[match_index - 1]["last_android"] < operation["first_android"]
        right_context = (
            match_index + 1 < len(matches)
            and operation["last_android"] < matches[match_index + 1]["first_android"]
        )
        context = left_context or right_context
        confidence = None
        if direct_seed and lexical >= 70:
            confidence = "very_high_seeded"
        elif lexical >= 94 and coverage >= 88 and length >= 10:
            confidence = "very_high_lexical"
        elif lexical >= 85 and coverage >= 82 and length >= 14 and context:
            confidence = "very_high_context"
        elif lexical >= 78 and coverage >= 88 and length >= 24 and left_context and right_context:
            confidence = "very_high_bracketed"
        elif lexical >= 99 and length < 12 and left_context and right_context:
            confidence = "very_high_short_bracketed"
        if confidence is not None:
            accepted.append({**operation, "confidence": confidence})
    return accepted

# User-validated alignment identities are data, not executable round-specific code.


def _load_reviewed_alignment_recipes() -> list[dict]:
    """Load user-validated SNES/Android identities from structural recipe data."""
    document = _load_recipe_document(
        DIALOGUE_REVIEWED_ALIGNMENT_RECIPES,
        label="Reviewed-alignment recipes",
        expected={"format": "dialogues-reviewed-alignment-recipes-v1"},
    )
    records = document.get("records")
    if not isinstance(records, list):
        raise ValueError("Reviewed-alignment recipes must contain a records list")
    return records


def _decode_review_part(part):
    if isinstance(part, str):
        return part
    if isinstance(part, dict) and part.get("command") == "player_name":
        index = part.get("index")
        if isinstance(index, int) and 0 <= index <= 2:
            return ("player_name", index)
    raise ValueError(f"Unsupported reviewed-alignment part: {part!r}")


def _auto_reviewed_records(source: dict[str, dict]) -> list[dict]:
    """Materialize authoritative reviewed identities from structural recipes."""
    records: list[dict] = []
    for item in _load_reviewed_alignment_recipes():
        event_id = item.get("event_id")
        android_ids = item.get("android_ids")
        raw_parts = item.get("parts")
        if not isinstance(event_id, str) or not isinstance(android_ids, list) or not isinstance(raw_parts, list):
            raise ValueError(f"Invalid reviewed-alignment recipe: {item!r}")
        parts = tuple(_decode_review_part(part) for part in raw_parts)
        snes_ids, source_display = render_snes_review_parts(parts, source, event_id=event_id)
        if item.get("provenance") == "round46":
            record = {
                "event_id": event_id,
                "snes_ids": snes_ids,
                "android_ids": list(android_ids),
                "android_namespace": item.get("android_namespace", "systxt"),
            }
            if "localization_systxt_id" in item:
                record["localization_systxt_id"] = item["localization_systxt_id"]
            record.update({
                "confidence": item.get("confidence", "user_validated"),
                "provenance": item.get("provenance", "reviewed_recipe"),
                "relation": item["relation"],
                "note": item["note"],
                "source_display": source_display,
            })
        else:
            record = {
                "event_id": event_id,
                "snes_ids": snes_ids,
                "android_ids": list(android_ids),
                "confidence": item.get("confidence", "user_validated"),
                "provenance": item.get("provenance", "reviewed_recipe"),
            }
            if "relation" in item:
                record["relation"] = item["relation"]
            if "note" in item:
                record["note"] = item["note"]
            record["source_display"] = source_display
        records.append(record)

    claimed: set[str] = set()
    latest_records: list[dict] = []
    for record in reversed(records):
        if claimed.intersection(record["snes_ids"]):
            continue
        latest_records.append(record)
        claimed.update(record["snes_ids"])
    latest_records.reverse()
    return latest_records



def _auto_french_unit(anchor_id: int, english: dict[int, str], french: dict[int, str]) -> tuple[str, ...]:
    return tuple(
        french[text_id]
        for text_id in english_anchor_interval(anchor_id, english)
        if french[text_id]
    )


def _auto_enrich_record(
    record: dict,
    english: dict[int, str],
    french: dict[int, str],
    *,
    system_english: dict[int, str] | None = None,
    system_french: dict[int, str] | None = None,
) -> dict:
    namespace = record.get("android_namespace", "scrtxt")
    if namespace == "scrtxt":
        local_en, local_fr = english, french
    elif namespace == "systxt":
        if system_english is None or system_french is None:
            raise ValueError("systxt reviewed mapping requires system-text sources")
        local_en, local_fr = system_english, system_french
    else:
        raise ValueError(f"unsupported Android dialogue namespace: {namespace}")
    android_ids = record.get("android_ids", [])
    unit_ids = android_anchor_units(tuple(android_ids), local_en) if android_ids else []
    french_ids = [text_id for text_id in unit_ids if local_fr[text_id]]
    result = dict(record)
    result["android_namespace"] = namespace
    result["android_unit_ids"] = unit_ids
    result["android_english_display"] = " ".join(local_en[text_id] for text_id in android_ids)
    result["french_nonempty_ids"] = french_ids
    identity_french_display = " ".join(local_fr[text_id] for text_id in french_ids)
    result["identity_french_display"] = identity_french_display
    override_id = record.get("localization_systxt_id")
    if override_id is not None:
        if system_english is None or system_french is None or override_id not in system_french:
            raise ValueError("systxt localization override requires valid system-text sources")
        result["localization_override_namespace"] = "systxt"
        result["localization_override_id"] = override_id
        result["localization_override_source_en"] = system_english[override_id]
        result["french_display"] = system_french[override_id]
    else:
        result["french_display"] = identity_french_display
    return result


def _auto_drop_trailing_french_only_player_turns(
    records: list[dict],
    english: dict[int, str],
    french: dict[int, str],
) -> list[dict]:
    """Drop only a new French-only player turn trailing an English anchor.

    Android localization may continue one English anchor through English-empty
    French slots.  Those prose continuations remain owned by the anchor.  A
    later English-empty slot can instead begin a new mobile-only spoken turn as
    ``%S(n,0) : ...``.  If removing that new turn (and only the suffix after it)
    restores the exact SNES placeholder sequence, exclude the mobile-only turn
    from this SNES mapping.  Android English remains the identity layer.
    """
    placeholder_re = re.compile(r"%S\(\d+,0\)")
    repairs: list[dict] = []
    for record in records:
        if record.get("android_namespace", "scrtxt") != "scrtxt":
            continue
        unit_ids = list(record.get("android_unit_ids", []))
        french_ids = list(record.get("french_nonempty_ids", []))
        if not unit_ids or not french_ids:
            continue
        source_placeholders = tuple(placeholder_re.findall(record.get("source_display", "")))
        full_placeholders = tuple(
            placeholder_re.findall(normalize_android_french(record.get("french_display", "")))
        )
        if full_placeholders == source_placeholders:
            continue

        # Only inspect French-bearing slots whose Android-English counterpart is
        # empty and which occur after the final non-empty English anchor owned by
        # this record.  Preserve any preceding French-only prose continuation.
        last_english_pos = max(
            (pos for pos, text_id in enumerate(unit_ids) if english.get(text_id, "").strip()),
            default=-1,
        )
        for pos in range(last_english_pos + 1, len(unit_ids)):
            text_id = unit_ids[pos]
            if english.get(text_id, "").strip() or not french.get(text_id, "").strip():
                continue
            french_text = normalize_android_french(french[text_id]).lstrip()
            if not re.match(r"^%S\(\d+,0\)\s*:", french_text):
                continue
            suffix_ids = set(unit_ids[pos:])
            kept_ids = [candidate for candidate in french_ids if candidate not in suffix_ids]
            kept_display = " ".join(french[candidate] for candidate in kept_ids)
            kept_placeholders = tuple(
                placeholder_re.findall(normalize_android_french(kept_display))
            )
            if kept_placeholders != source_placeholders:
                continue
            dropped_ids = [candidate for candidate in french_ids if candidate in suffix_ids]
            record["french_nonempty_ids"] = kept_ids
            record["french_display"] = kept_display
            record["dropped_trailing_french_only_player_turn_ids"] = dropped_ids
            repairs.append(
                {
                    "event_id": record.get("event_id"),
                    "snes_ids": list(record.get("snes_ids", [])),
                    "android_ids": list(record.get("android_ids", [])),
                    "dropped_french_ids": dropped_ids,
                }
            )
            break
    return repairs


def _auto_reattribute_forward_player_french_slots(
    records: list[dict],
    english: dict[int, str],
    french: dict[int, str],
) -> list[dict]:
    """Move an English-empty French PLAYER_NAME continuation to the next anchor.

    Android normally stores localized spill text in English-empty slots owned by
    the preceding non-empty English anchor.  One stronger structural shape can
    prove the opposite ownership: an intervening French-only slot starts with a
    PLAYER_NAME placeholder absent from the preceding English anchor, the next
    English anchor starts with that exact placeholder, and the next anchor's
    French text omits it.  If the resulting placeholder sequences exactly match
    the two already-aligned SNES mappings, reattribute only that French slot to
    the following mapping.  Android English remains the identity layer and no
    SNES command is created, removed, or moved.
    """
    placeholder_re = re.compile(r"%S\(\d+,0\)")
    repairs: list[dict] = []
    for left, right in zip(records, records[1:]):
        if left.get("event_id") != right.get("event_id"):
            continue
        if left.get("session_id") is None or left.get("session_id") != right.get("session_id"):
            continue
        left_android = left.get("android_ids", [])
        right_android = right.get("android_ids", [])
        if len(left_android) != 1 or len(right_android) != 1:
            continue
        left_anchor = left_android[0]
        right_anchor = right_android[0]
        interval = english_anchor_interval(left_anchor, english)
        if not interval or interval[-1] + 1 != right_anchor or not english.get(right_anchor):
            continue
        spill_ids = [text_id for text_id in interval[1:] if french.get(text_id)]
        if len(spill_ids) != 1:
            continue
        spill_id = spill_ids[0]
        spill_text = normalize_android_french(french[spill_id]).strip()
        match = re.match(r"(%S\(\d+,0\))", spill_text)
        if match is None:
            continue
        placeholder = match.group(1)
        left_en_placeholders = tuple(placeholder_re.findall(normalize_android_french(english[left_anchor])))
        if placeholder in left_en_placeholders:
            continue
        right_en = normalize_android_french(english[right_anchor]).strip()
        right_fr = normalize_android_french(french[right_anchor]).strip()
        if not right_en.startswith(placeholder) or right_fr.startswith(placeholder):
            continue

        left_fr_ids = [text_id for text_id in left.get("french_nonempty_ids", []) if text_id != spill_id]
        right_fr_ids = [spill_id, *right.get("french_nonempty_ids", [])]
        left_display = " ".join(french[text_id] for text_id in left_fr_ids)
        right_display = " ".join(french[text_id] for text_id in right_fr_ids)
        if tuple(placeholder_re.findall(normalize_android_french(left_display))) != tuple(
            placeholder_re.findall(left.get("source_display", ""))
        ):
            continue
        if tuple(placeholder_re.findall(normalize_android_french(right_display))) != tuple(
            placeholder_re.findall(right.get("source_display", ""))
        ):
            continue

        left["french_nonempty_ids"] = left_fr_ids
        left["french_display"] = left_display
        left["forward_reattributed_french_ids"] = [spill_id]
        right["french_nonempty_ids"] = right_fr_ids
        right["french_display"] = right_display
        right["backward_reattributed_french_ids"] = [spill_id]
        repairs.append(
            {
                "event_id": left["event_id"],
                "from_android_anchor": left_anchor,
                "french_slot_id": spill_id,
                "to_android_anchor": right_anchor,
                "player_placeholder": placeholder,
            }
        )
    return repairs


def _auto_same_session_context_expand(
    sessions: list[dict],
    records: list[dict],
    index: _AutoCandidateIndex,
    english: dict[int, str],
) -> list[dict]:
    owner = {snes_id: record for record in records for snes_id in record["snes_ids"]}
    additions: list[dict] = []
    for _iteration in range(3):
        added = 0
        for session in sessions:
            elements = session["elements"]
            for element_index, element in enumerate(elements):
                if element["id"] in owner or element["id"] in DIALOGUE_FORCED_UNMAPPED:
                    continue
                source = _auto_render_span(session, element_index, element_index)
                normalized = normalize_alignment_text(source)
                length = len(normalized)
                previous_owner = None
                next_owner = None
                for search in range(element_index - 1, -1, -1):
                    if elements[search]["id"] in owner and owner[elements[search]["id"]].get("android_ids"):
                        previous_owner = owner[elements[search]["id"]]
                        break
                for search in range(element_index + 1, len(elements)):
                    if elements[search]["id"] in owner and owner[elements[search]["id"]].get("android_ids"):
                        next_owner = owner[elements[search]["id"]]
                        break
                pool: list[int] = []
                context_type = None
                if previous_owner and next_owner:
                    previous_position = max(index.anchor_pos[text_id] for text_id in previous_owner["android_ids"])
                    next_position = min(index.anchor_pos[text_id] for text_id in next_owner["android_ids"])
                    if previous_position <= next_position and next_position - previous_position <= 35:
                        pool = index.anchor_ids[previous_position : next_position + 1]
                        context_type = "bracketed"
                elif previous_owner:
                    position = max(index.anchor_pos[text_id] for text_id in previous_owner["android_ids"])
                    pool = index.anchor_ids[max(0, position - 1) : min(len(index.anchor_ids), position + 10)]
                    context_type = "after"
                elif next_owner:
                    position = min(index.anchor_pos[text_id] for text_id in next_owner["android_ids"])
                    pool = index.anchor_ids[max(0, position - 9) : min(len(index.anchor_ids), position + 2)]
                    context_type = "before"
                if not pool:
                    continue
                ranked = sorted(
                    (
                        {"android_id": text_id, **_auto_metrics(source, english[text_id])}
                        for text_id in pool
                    ),
                    key=lambda item: (item["lexical_score"], item["character_similarity"]),
                    reverse=True,
                )
                top = ranked[0]
                second_score = ranked[1]["lexical_score"] if len(ranked) > 1 else 0.0
                margin = top["lexical_score"] - second_score
                exact_local = normalize_alignment_text(english[top["android_id"]]) == normalized
                accept = False
                confidence = None
                if context_type == "bracketed":
                    if exact_local and length >= 4 and (
                        margin >= 5 or sum(item["lexical_score"] >= 99.9 for item in ranked) == 1
                    ):
                        accept = True
                        confidence = "very_high_local_exact"
                    elif top["lexical_score"] >= 88 and top["source_token_coverage"] >= 85 and length >= 14 and margin >= 7:
                        accept = True
                        confidence = "very_high_local_fuzzy"
                    elif top["lexical_score"] >= 82 and top["source_token_coverage"] >= 90 and length >= 24 and margin >= 10:
                        accept = True
                        confidence = "very_high_local_coverage"
                else:
                    if exact_local and length >= 8 and margin >= 10:
                        accept = True
                        confidence = "very_high_one_side_exact"
                    elif top["lexical_score"] >= 92 and top["source_token_coverage"] >= 90 and length >= 18 and margin >= 12:
                        accept = True
                        confidence = "very_high_one_side_fuzzy"
                if accept:
                    record = {
                        "event_id": session["event_id"],
                        "session_id": session["session_id"],
                        "snes_ids": [element["id"]],
                        "android_ids": [top["android_id"]],
                        "confidence": confidence,
                        "provenance": "automatic_local_context",
                        "source_display": source,
                        "lexical_evidence": {
                            key: top[key]
                            for key in ("character_similarity", "source_token_coverage", "lexical_score")
                        },
                        "candidate_margin": round(margin, 1),
                    }
                    owner[element["id"]] = record
                    records.append(record)
                    additions.append(record)
                    added += 1
        if not added:
            break
    return additions


def _auto_event_context_expand(
    sessions: list[dict],
    records: list[dict],
    index: _AutoCandidateIndex,
    english: dict[int, str],
) -> list[dict]:
    owner = {snes_id: record for record in records for snes_id in record["snes_ids"]}
    sessions_by_event: dict[str, list[dict]] = {}
    for session in sessions:
        sessions_by_event.setdefault(session["event_id"], []).append(session)

    def session_positions(session: dict) -> list[int]:
        positions: list[int] = []
        for element in session["elements"]:
            record = owner.get(element["id"])
            if record:
                positions.extend(
                    index.anchor_pos[text_id]
                    for text_id in record.get("android_ids", [])
                    if text_id in index.anchor_pos
                )
        return positions

    additions: list[dict] = []
    for _iteration in range(2):
        added = 0
        for event_sessions in sessions_by_event.values():
            for session_index, session in enumerate(event_sessions):
                if session_positions(session):
                    continue
                if not any(
                    element["id"] not in owner and element["id"] not in DIALOGUE_FORCED_UNMAPPED
                    for element in session["elements"]
                ):
                    continue
                previous = None
                following = None
                for search in range(session_index - 1, -1, -1):
                    positions = session_positions(event_sessions[search])
                    if positions:
                        previous = (search, positions)
                        break
                for search in range(session_index + 1, len(event_sessions)):
                    positions = session_positions(event_sessions[search])
                    if positions:
                        following = (search, positions)
                        break
                window = None
                context_type = None
                if previous and following:
                    low = max(previous[1])
                    high = min(following[1])
                    if (
                        low <= high
                        and high - low <= 45
                        and session_index - previous[0] <= 3
                        and following[0] - session_index <= 3
                    ):
                        window = (max(0, low - 2), min(len(index.anchor_ids) - 1, high + 2))
                        context_type = "event_bracketed"
                elif previous and session_index - previous[0] <= 2:
                    center = max(previous[1])
                    window = (max(0, center - 1), min(len(index.anchor_ids) - 1, center + 12))
                    context_type = "event_one_side"
                elif following and following[0] - session_index <= 2:
                    center = min(following[1])
                    window = (max(0, center - 12), min(len(index.anchor_ids) - 1, center + 1))
                    context_type = "event_one_side"
                if window is None:
                    continue
                operations = _auto_align_session(session, window, index, english)
                matches = [operation for operation in operations if "android_ids" in operation]
                for match_index, operation in enumerate(matches):
                    snes_ids = [
                        session["elements"][element_index]["id"]
                        for element_index in range(operation["first_source"], operation["last_source"] + 1)
                    ]
                    if any(snes_id in owner or snes_id in DIALOGUE_FORCED_UNMAPPED for snes_id in snes_ids):
                        continue
                    evidence = operation["evidence"]
                    lexical = evidence["lexical_score"]
                    coverage = evidence["source_token_coverage"]
                    length = len(normalize_alignment_text(operation["source_display"]))
                    confidence = None
                    if lexical >= 96 and coverage >= 90 and length >= 12:
                        confidence = "very_high_event_context_lexical"
                    elif context_type == "event_bracketed" and lexical >= 90 and coverage >= 88 and length >= 16:
                        confidence = "very_high_event_bracketed"
                    elif (
                        context_type == "event_bracketed"
                        and lexical >= 84
                        and coverage >= 92
                        and length >= 28
                        and (match_index > 0 or match_index + 1 < len(matches))
                    ):
                        confidence = "very_high_event_sequence"
                    if confidence is None:
                        continue
                    record = {
                        "event_id": session["event_id"],
                        "session_id": session["session_id"],
                        "snes_ids": snes_ids,
                        "android_ids": operation["android_ids"],
                        "confidence": confidence,
                        "provenance": "automatic_event_context",
                        "source_display": operation["source_display"],
                        "lexical_evidence": evidence,
                    }
                    records.append(record)
                    additions.append(record)
                    for snes_id in snes_ids:
                        owner[snes_id] = record
                    added += len(snes_ids)
        if not added:
            break
    return additions


def _auto_choice_near(session: dict, element: dict) -> bool:
    token_index = element["token_index"]
    for token in session["tokens"][
        max(session["start"], token_index - 2) : min(session["end"] + 1, token_index + 3)
    ]:
        if token.get("type") == "command" and token.get("name") in {
            "CHOICE_BEGIN",
            "CHOICE_OPTION",
            "CHOICE_END",
        }:
            return True
    return False


def _auto_add_exact_equivalences(
    sessions: list[dict],
    records: list[dict],
    index: _AutoCandidateIndex,
    english: dict[int, str],
    french: dict[int, str],
) -> list[dict]:
    owner = {snes_id: record for record in records for snes_id in record["snes_ids"]}
    additions: list[dict] = []
    for session in sessions:
        for element_index, element in enumerate(session["elements"]):
            snes_id = element["id"]
            if snes_id in owner or snes_id in DIALOGUE_FORCED_UNMAPPED:
                continue
            source = _auto_render_span(session, element_index, element_index)
            normalized = normalize_alignment_text(source)
            exact_ids = index.exact.get(normalized, [])
            if len(exact_ids) == 1:
                if len(normalized) >= 10 or _auto_choice_near(session, element):
                    record = {
                        "event_id": session["event_id"],
                        "session_id": session["session_id"],
                        "snes_ids": [snes_id],
                        "android_ids": list(exact_ids),
                        "confidence": "very_high_unique_exact",
                        "provenance": "automatic_exact",
                        "source_display": source,
                        "lexical_evidence": _auto_metrics(source, english[exact_ids[0]]),
                    }
                    records.append(record)
                    additions.append(record)
                    owner[snes_id] = record
            elif len(exact_ids) > 1:
                french_units = {_auto_french_unit(text_id, english, french) for text_id in exact_ids}
                if len(french_units) == 1 and next(iter(french_units), ()):
                    record = {
                        "event_id": session["event_id"],
                        "session_id": session["session_id"],
                        "snes_ids": [snes_id],
                        "android_ids": [],
                        "android_alternative_anchor_groups": [[text_id] for text_id in exact_ids],
                        "confidence": "very_high_equivalent_duplicate",
                        "provenance": "automatic_equivalent_duplicate",
                        "source_display": source,
                        "french_display": " ".join(next(iter(french_units))),
                    }
                    records.append(record)
                    additions.append(record)
                    owner[snes_id] = record
    return additions


def _auto_add_placeholder_index_equivalent_duplicates(
    sessions: list[dict],
    records: list[dict],
    index: _AutoCandidateIndex,
    english: dict[int, str],
    french: dict[int, str],
) -> list[dict]:
    """Resolve still-free exact duplicates equivalent only by PLAYER_NAME index.

    Android EN remains the identity proof: every candidate occurrence must be
    an exact normalized English duplicate of the SNES span. Android FR is used
    only to establish that choosing among those already-identical English copies
    cannot change the localized prose: every complete French unit must be
    identical after canonicalizing only ``%S(n,0)`` indexes. Running this pass
    after all pre-existing rules prevents it from replacing an already-owned
    mapping with a different duplicate occurrence.

    Calibration against the pre-rule accepted corpus finds 1/1 historical
    mapping eligible for this index-only extension and zero conflicts. The
    narrow sample is supplemented by the stronger invariant that every Android
    EN candidate is an exact duplicate and every complete FR unit is identical
    after changing only the dynamic PLAYER_NAME index.
    """
    owner = {snes_id: record for record in records for snes_id in record["snes_ids"]}

    def accepted_android_ids(record: dict) -> set[int]:
        result = set(record.get("android_ids", []))
        for group in record.get("android_alternative_anchor_groups", []):
            result.update(group)
        return result

    calibration_attempts = 0
    calibration_conflicts: list[tuple[str, list[int], list[int]]] = []
    for session in sessions:
        for element_index, element in enumerate(session["elements"]):
            snes_id = element["id"]
            accepted = owner.get(snes_id)
            if accepted is None or len(accepted.get("snes_ids", [])) != 1:
                continue
            source = _auto_render_span(session, element_index, element_index)
            exact_ids = index.exact.get(normalize_alignment_text(source), [])
            if len(exact_ids) < 2:
                continue
            french_units = [_auto_french_unit(text_id, english, french) for text_id in exact_ids]
            if not all(french_units) or len(set(french_units)) == 1:
                continue
            canonical_units = {
                tuple(re.sub(r"%S\(\d+,0\)", "%S(#,0)", part) for part in unit)
                for unit in french_units
            }
            if len(canonical_units) != 1:
                continue
            calibration_attempts += 1
            accepted_ids = accepted_android_ids(accepted)
            if not accepted_ids.intersection(exact_ids):
                calibration_conflicts.append(
                    (snes_id, list(exact_ids), sorted(accepted_ids))
                )
    if calibration_conflicts:
        raise ValueError(
            "PLAYER_NAME-index duplicate alignment contradicts accepted mappings: "
            + ", ".join(item[0] for item in calibration_conflicts[:10])
        )
    if calibration_attempts != 1:
        raise ValueError(
            "PLAYER_NAME-index duplicate calibration corpus changed unexpectedly: "
            f"expected 1 eligible accepted mapping, found {calibration_attempts}"
        )

    additions: list[dict] = []
    for session in sessions:
        for element_index, element in enumerate(session["elements"]):
            snes_id = element["id"]
            if snes_id in owner or snes_id in DIALOGUE_FORCED_UNMAPPED:
                continue
            source = _auto_render_span(session, element_index, element_index)
            exact_ids = index.exact.get(normalize_alignment_text(source), [])
            if len(exact_ids) < 2:
                continue
            french_units = [_auto_french_unit(text_id, english, french) for text_id in exact_ids]
            if not all(french_units):
                continue
            # Literal-equivalent duplicates are already handled by the original
            # exact-equivalence pass. This rule is only for placeholder-index
            # variants that would otherwise remain unresolved.
            if len(set(french_units)) == 1:
                continue
            canonical_units = {
                tuple(re.sub(r"%S\(\d+,0\)", "%S(#,0)", part) for part in unit)
                for unit in french_units
            }
            if len(canonical_units) != 1:
                continue
            chosen_french = french_units[0]
            record = {
                "event_id": session["event_id"],
                "session_id": session["session_id"],
                "snes_ids": [snes_id],
                "android_ids": [],
                "android_alternative_anchor_groups": [[text_id] for text_id in exact_ids],
                "confidence": "very_high_equivalent_duplicate_player_index",
                "provenance": "automatic_equivalent_duplicate",
                "relation": "exact_duplicate_equivalent_french_player_index",
                "source_display": source,
                "french_display": " ".join(chosen_french),
            }
            records.append(record)
            additions.append(record)
            owner[snes_id] = record
    return additions


def _auto_add_raw_unique_exact_player_context_neighbor(
    sessions: list[dict],
    records: list[dict],
    index: _AutoCandidateIndex,
    english: dict[int, str],
    french: dict[int, str],
) -> list[dict]:
    """Recover a raw-carrier exact obscured only by adjacent PLAYER_NAME context.

    ``_auto_render_span()`` deliberately includes nearby PLAYER_NAME commands so
    structural context is available to later binding.  In a small set of cases
    that context makes an otherwise unique Android-English exact look non-exact.
    Accept the raw carrier only when it is at least ten normalized characters,
    removing PLAYER_NAME markup from the rendered span restores the exact raw
    text, and the unique Android occurrence is immediately adjacent to an
    already-owned Android anchor in the same SNES session.  Decisions are
    non-cascading.

    Calibration against the pre-rule accepted corpus reproduces 36/36 eligible
    mappings with zero conflicts.
    """
    owner = {snes_id: record for record in records for snes_id in record["snes_ids"]}
    player_markup_re = re.compile(r"%S\(\d+,0\)")

    def accepted_android_ids(record: dict) -> set[int]:
        result = set(record.get("android_ids", []))
        for group in record.get("android_alternative_anchor_groups", []):
            result.update(group)
        return result

    calibration_attempts = 0
    calibration_conflicts: list[tuple[str, int, list[int]]] = []
    for session in sessions:
        elements = session["elements"]
        for element_index, element in enumerate(elements):
            snes_id = element["id"]
            accepted = owner.get(snes_id)
            if accepted is None or len(accepted.get("snes_ids", [])) != 1:
                continue
            raw_source = element.get("source", "")
            normalized = normalize_alignment_text(raw_source)
            if len(normalized) < 10:
                continue
            exact_ids = index.exact.get(normalized, [])
            if len(exact_ids) != 1:
                continue
            android_id = exact_ids[0]
            if not _auto_french_unit(android_id, english, french):
                continue
            rendered = _auto_render_span(session, element_index, element_index)
            if normalize_alignment_text(rendered) == normalized:
                continue
            if normalize_alignment_text(player_markup_re.sub("", rendered)) != normalized:
                continue

            previous_position = None
            following_position = None
            for search in range(element_index - 1, -1, -1):
                record = owner.get(elements[search]["id"])
                android_ids = record.get("android_ids", []) if record else []
                positions = [
                    index.anchor_pos[text_id]
                    for text_id in android_ids
                    if text_id in index.anchor_pos
                ]
                if positions:
                    previous_position = max(positions)
                    break
            for search in range(element_index + 1, len(elements)):
                record = owner.get(elements[search]["id"])
                android_ids = record.get("android_ids", []) if record else []
                positions = [
                    index.anchor_pos[text_id]
                    for text_id in android_ids
                    if text_id in index.anchor_pos
                ]
                if positions:
                    following_position = min(positions)
                    break
            candidate_position = index.anchor_pos[android_id]
            immediate = (
                previous_position is not None
                and candidate_position == previous_position + 1
            ) or (
                following_position is not None
                and candidate_position == following_position - 1
            )
            if not immediate:
                continue
            calibration_attempts += 1
            accepted_ids = accepted_android_ids(accepted)
            if android_id not in accepted_ids:
                calibration_conflicts.append(
                    (snes_id, android_id, sorted(accepted_ids))
                )
    if calibration_conflicts:
        raise ValueError(
            "Raw unique exact PLAYER_NAME-context alignment contradicts accepted mappings: "
            + ", ".join(item[0] for item in calibration_conflicts[:10])
        )
    if calibration_attempts != 36:
        raise ValueError(
            "Raw unique exact PLAYER_NAME-context calibration corpus changed unexpectedly: "
            f"expected 36 eligible accepted mappings, found {calibration_attempts}"
        )

    proposals: list[dict] = []
    for session in sessions:
        elements = session["elements"]
        for element_index, element in enumerate(elements):
            snes_id = element["id"]
            if snes_id in owner or snes_id in DIALOGUE_FORCED_UNMAPPED:
                continue
            raw_source = element.get("source", "")
            normalized = normalize_alignment_text(raw_source)
            if len(normalized) < 10:
                continue
            exact_ids = index.exact.get(normalized, [])
            if len(exact_ids) != 1:
                continue
            android_id = exact_ids[0]
            if not _auto_french_unit(android_id, english, french):
                continue

            rendered = _auto_render_span(session, element_index, element_index)
            if normalize_alignment_text(rendered) == normalized:
                continue
            if normalize_alignment_text(player_markup_re.sub("", rendered)) != normalized:
                continue

            previous_position = None
            following_position = None
            for search in range(element_index - 1, -1, -1):
                record = owner.get(elements[search]["id"])
                android_ids = record.get("android_ids", []) if record else []
                positions = [
                    index.anchor_pos[text_id]
                    for text_id in android_ids
                    if text_id in index.anchor_pos
                ]
                if positions:
                    previous_position = max(positions)
                    break
            for search in range(element_index + 1, len(elements)):
                record = owner.get(elements[search]["id"])
                android_ids = record.get("android_ids", []) if record else []
                positions = [
                    index.anchor_pos[text_id]
                    for text_id in android_ids
                    if text_id in index.anchor_pos
                ]
                if positions:
                    following_position = min(positions)
                    break

            candidate_position = index.anchor_pos[android_id]
            immediate = (
                previous_position is not None
                and candidate_position == previous_position + 1
            ) or (
                following_position is not None
                and candidate_position == following_position - 1
            )
            if not immediate:
                continue
            proposals.append(
                {
                    "event_id": session["event_id"],
                    "session_id": session["session_id"],
                    "snes_id": snes_id,
                    "android_id": android_id,
                    "source_display": raw_source,
                }
            )

    additions: list[dict] = []
    for proposal in proposals:
        snes_id = proposal["snes_id"]
        if snes_id in owner:
            continue
        android_id = proposal["android_id"]
        record = {
            "event_id": proposal["event_id"],
            "session_id": proposal["session_id"],
            "snes_ids": [snes_id],
            "android_ids": [android_id],
            "confidence": "very_high_raw_unique_exact_player_context_neighbor",
            "provenance": "automatic_exact_context",
            "relation": "raw_unique_exact_player_context_immediate_neighbor",
            "source_display": proposal["source_display"],
            "lexical_evidence": _auto_metrics(proposal["source_display"], english[android_id]),
        }
        records.append(record)
        additions.append(record)
        owner[snes_id] = record
    return additions

def _auto_add_exact_segmentation_equivalences(
    sessions: list[dict],
    records: list[dict],
    index: _AutoCandidateIndex,
    english: dict[int, str],
    french: dict[int, str],
) -> list[dict]:
    """Recover exact English identities whose SNES/Android segmentation differs.

    Compare contiguous spans of one to three semantic SNES elements with one to
    three consecutive non-empty Android-English anchors.  Ordinary 1:1 exact
    identities remain owned by the simpler exact-equivalence pass.  Every other
    segmentation is accepted only on exact normalized English equality and only
    when all duplicate Android segmentations yield one identical, non-empty
    complete French localization.  Overlapping source-span proposals are left
    unresolved rather than choosing between equally exact segmentations.
    """
    owner = {snes_id: record for record in records for snes_id in record["snes_ids"]}

    exact_android_segments: dict[str, list[tuple[int, ...]]] = {}
    for position in range(len(index.anchor_ids)):
        for width in (1, 2, 3):
            if position + width > len(index.anchor_ids):
                continue
            group = tuple(index.anchor_ids[position : position + width])
            normalized = normalize_alignment_text(" ".join(english[text_id] for text_id in group))
            if normalized:
                exact_android_segments.setdefault(normalized, []).append(group)

    def french_group(group: tuple[int, ...]) -> tuple[str, ...]:
        return tuple(
            french[text_id]
            for text_id in android_anchor_units(group, english)
            if french[text_id]
        )

    proposals: list[dict] = []
    for session in sessions:
        elements = session["elements"]
        for first in range(len(elements)):
            for source_width in (1, 2, 3):
                last = first + source_width - 1
                if last >= len(elements):
                    continue
                snes_ids = tuple(element["id"] for element in elements[first : last + 1])
                if any(snes_id in owner or snes_id in DIALOGUE_FORCED_UNMAPPED for snes_id in snes_ids):
                    continue
                source_display = _auto_render_span(session, first, last)
                normalized = normalize_alignment_text(source_display)
                groups = list(exact_android_segments.get(normalized, []))
                if not groups:
                    continue
                if source_width == 1:
                    # A competing one-anchor exact identity is either already
                    # handled by the ordinary pass or intentionally ambiguous;
                    # do not use a wider Android segmentation to override it.
                    if any(len(group) == 1 for group in groups):
                        continue
                    groups = [group for group in groups if len(group) > 1]
                    if not groups:
                        continue
                french_versions = {french_group(group) for group in groups}
                if len(french_versions) != 1 or not next(iter(french_versions), ()):
                    continue
                proposals.append(
                    {
                        "event_id": session["event_id"],
                        "session_id": session["session_id"],
                        "snes_ids": snes_ids,
                        "android_groups": groups,
                        "source_display": source_display,
                        "french_version": next(iter(french_versions)),
                    }
                )

    source_spans_by_id: dict[str, set[tuple[str, ...]]] = {}
    for proposal in proposals:
        span = tuple(proposal["snes_ids"])
        for snes_id in span:
            source_spans_by_id.setdefault(snes_id, set()).add(span)

    additions: list[dict] = []
    for proposal in proposals:
        snes_ids = tuple(proposal["snes_ids"])
        if any(len(source_spans_by_id[snes_id]) != 1 for snes_id in snes_ids):
            continue
        if any(snes_id in owner for snes_id in snes_ids):
            continue
        groups = proposal["android_groups"]
        if len(groups) == 1:
            android_ids = list(groups[0])
            record = {
                "event_id": proposal["event_id"],
                "session_id": proposal["session_id"],
                "snes_ids": list(snes_ids),
                "android_ids": android_ids,
                "confidence": "very_high_exact_segmentation",
                "provenance": "automatic_exact_segmentation",
                "relation": "exact_segmentation",
                "source_display": proposal["source_display"],
                "lexical_evidence": _auto_metrics(
                    proposal["source_display"],
                    " ".join(english[text_id] for text_id in android_ids),
                ),
            }
        else:
            record = {
                "event_id": proposal["event_id"],
                "session_id": proposal["session_id"],
                "snes_ids": list(snes_ids),
                "android_ids": [],
                "android_alternative_anchor_groups": [list(group) for group in groups],
                "confidence": "very_high_exact_segmentation_equivalent_duplicate",
                "provenance": "automatic_exact_segmentation",
                "relation": "exact_segmentation",
                "source_display": proposal["source_display"],
                "french_display": " ".join(proposal["french_version"]),
            }
        records.append(record)
        additions.append(record)
        for snes_id in snes_ids:
            owner[snes_id] = record
    return additions


def _auto_add_contextual_exact_duplicates(
    source_document: dict,
    sessions: list[dict],
    records: list[dict],
    index: _AutoCandidateIndex,
    english: dict[int, str],
    french: dict[int, str],
) -> list[dict]:
    """Disambiguate divergent exact duplicates from tight event-local context.

    Exact Android-English duplicates may carry different French localizations,
    so equality alone cannot choose an occurrence.  Accept one occurrence only
    when already-owned semantic neighbors make it structurally unique: either
    exactly one duplicate lies strictly between two nearby monotonic anchors,
    or exactly one duplicate is the immediately adjacent non-empty Android
    anchor to an established neighbor.  The pass is intentionally non-
    cascading: every decision uses ownership that existed on entry.
    """
    owner = {snes_id: record for record in records for snes_id in record["snes_ids"]}
    rendered_by_id: dict[str, str] = {}
    session_by_id: dict[str, int] = {}
    for session in sessions:
        for element_index, element in enumerate(session["elements"]):
            rendered_by_id[element["id"]] = _auto_render_span(session, element_index, element_index)
            session_by_id[element["id"]] = session["session_id"]

    proposals: list[dict] = []
    for event in source_document.get("events", []):
        semantic_tokens = [
            token
            for token in event.get("tokens", [])
            if token.get("type") == "text" and _auto_semantic(token.get("source", ""))
        ]
        semantic_ids = [token["id"] for token in semantic_tokens]
        for token_index, token in enumerate(semantic_tokens):
            snes_id = token["id"]
            if snes_id in owner or snes_id in DIALOGUE_FORCED_UNMAPPED:
                continue
            source_display = rendered_by_id.get(snes_id, token.get("source", ""))
            exact_ids = index.exact.get(normalize_alignment_text(source_display), [])
            if len(exact_ids) < 2:
                continue
            french_versions = {_auto_french_unit(text_id, english, french) for text_id in exact_ids}
            if len(french_versions) <= 1:
                continue

            previous_position = None
            following_position = None
            for search in range(token_index - 1, -1, -1):
                record = owner.get(semantic_ids[search])
                android_ids = record.get("android_ids", []) if record else []
                positions = [index.anchor_pos[text_id] for text_id in android_ids if text_id in index.anchor_pos]
                if positions:
                    previous_position = max(positions)
                    break
            for search in range(token_index + 1, len(semantic_ids)):
                record = owner.get(semantic_ids[search])
                android_ids = record.get("android_ids", []) if record else []
                positions = [index.anchor_pos[text_id] for text_id in android_ids if text_id in index.anchor_pos]
                if positions:
                    following_position = min(positions)
                    break

            chosen: int | None = None
            context = None
            if (
                previous_position is not None
                and following_position is not None
                and previous_position < following_position
                and following_position - previous_position <= 12
            ):
                bracketed = [
                    text_id
                    for text_id in exact_ids
                    if previous_position < index.anchor_pos[text_id] < following_position
                ]
                if len(bracketed) == 1:
                    chosen = bracketed[0]
                    context = "tight_bracket"

            if chosen is None:
                adjacent: list[int] = []
                if previous_position is not None:
                    adjacent.extend(
                        text_id
                        for text_id in exact_ids
                        if index.anchor_pos[text_id] == previous_position + 1
                    )
                if following_position is not None:
                    adjacent.extend(
                        text_id
                        for text_id in exact_ids
                        if index.anchor_pos[text_id] == following_position - 1
                    )
                adjacent = list(dict.fromkeys(adjacent))
                if len(adjacent) == 1:
                    chosen = adjacent[0]
                    context = "immediate_neighbor"

            if chosen is None or not _auto_french_unit(chosen, english, french):
                continue
            proposals.append(
                {
                    "event_id": event["event_id"],
                    "session_id": session_by_id.get(snes_id),
                    "snes_id": snes_id,
                    "android_id": chosen,
                    "context": context,
                    "source_display": source_display,
                }
            )

    additions: list[dict] = []
    for proposal in proposals:
        snes_id = proposal["snes_id"]
        if snes_id in owner:
            continue
        android_id = proposal["android_id"]
        record = {
            "event_id": proposal["event_id"],
            "session_id": proposal["session_id"],
            "snes_ids": [snes_id],
            "android_ids": [android_id],
            "confidence": (
                "very_high_exact_context_bracket"
                if proposal["context"] == "tight_bracket"
                else "very_high_exact_context_adjacent"
            ),
            "provenance": "automatic_exact_context",
            "relation": "exact_duplicate_context",
            "source_display": proposal["source_display"],
            "lexical_evidence": _auto_metrics(proposal["source_display"], english[android_id]),
        }
        records.append(record)
        additions.append(record)
        owner[snes_id] = record
    return additions


def _auto_add_tight_single_gap_context(
    source_document: dict,
    records: list[dict],
    index: _AutoCandidateIndex,
    english: dict[int, str],
    french: dict[int, str],
) -> list[dict]:
    """Fill a single free semantic Android anchor inside a tight owned bracket.

    When the nearest mapped semantic SNES neighbors define a monotonic Android
    interval of at most 12 semantic anchors, accept the unresolved carrier only
    if exactly one semantic Android anchor in that interval is still unowned,
    its French is non-empty, source-token coverage is >=80%, and lexical score
    is >=60. Proposals competing for the same Android anchor are rejected as a
    group. Decisions are non-cascading.

    Calibration against the pre-rule accepted corpus reproduces 495/495
    eligible historical single-anchor mappings with zero conflicts.
    """
    owner = {snes_id: record for record in records for snes_id in record["snes_ids"]}
    android_owned = {
        text_id
        for record in records
        for text_id in record.get("android_ids", [])
        if text_id in index.anchor_pos
    }
    proposals: list[dict] = []
    for event in source_document.get("events", []):
        semantic_tokens = [
            token
            for token in event.get("tokens", [])
            if token.get("type") == "text" and _auto_semantic(token.get("source", ""))
        ]
        semantic_ids = [token["id"] for token in semantic_tokens]
        for token_index, token in enumerate(semantic_tokens):
            snes_id = token["id"]
            if snes_id in owner or snes_id in DIALOGUE_FORCED_UNMAPPED:
                continue
            previous_position = None
            following_position = None
            for search in range(token_index - 1, -1, -1):
                record = owner.get(semantic_ids[search])
                android_ids = record.get("android_ids", []) if record else []
                positions = [index.anchor_pos[text_id] for text_id in android_ids if text_id in index.anchor_pos]
                if positions:
                    previous_position = max(positions)
                    break
            for search in range(token_index + 1, len(semantic_ids)):
                record = owner.get(semantic_ids[search])
                android_ids = record.get("android_ids", []) if record else []
                positions = [index.anchor_pos[text_id] for text_id in android_ids if text_id in index.anchor_pos]
                if positions:
                    following_position = min(positions)
                    break
            if (
                previous_position is None
                or following_position is None
                or not previous_position < following_position
                or following_position - previous_position > 12
            ):
                continue
            candidates = [
                text_id
                for text_id in index.anchor_ids[previous_position + 1 : following_position]
                if text_id not in android_owned and _auto_french_unit(text_id, english, french)
            ]
            if len(candidates) != 1:
                continue
            android_id = candidates[0]
            source_display = token.get("source", "")
            evidence = _auto_metrics(source_display, english[android_id])
            if evidence["source_token_coverage"] < 80 or evidence["lexical_score"] < 60:
                continue
            proposals.append(
                {
                    "event_id": event["event_id"],
                    "snes_id": snes_id,
                    "android_id": android_id,
                    "source_display": source_display,
                    "lexical_evidence": evidence,
                }
            )

    proposal_counts: dict[int, int] = {}
    for proposal in proposals:
        proposal_counts[proposal["android_id"]] = proposal_counts.get(proposal["android_id"], 0) + 1

    additions: list[dict] = []
    for proposal in proposals:
        snes_id = proposal["snes_id"]
        android_id = proposal["android_id"]
        if snes_id in owner or proposal_counts[android_id] != 1:
            continue
        record = {
            "event_id": proposal["event_id"],
            "snes_ids": [snes_id],
            "android_ids": [android_id],
            "confidence": "very_high_tight_single_gap",
            "provenance": "automatic_exact_context",
            "relation": "tight_single_gap_context",
            "source_display": proposal["source_display"],
            "lexical_evidence": proposal["lexical_evidence"],
        }
        records.append(record)
        additions.append(record)
        owner[snes_id] = record
    return additions


def _auto_add_isolated_high_coverage_global(
    source_document: dict,
    records: list[dict],
    index: _AutoCandidateIndex,
    english: dict[int, str],
    french: dict[int, str],
) -> list[dict]:
    """Accept a long isolated global candidate with very high lexical coverage.

    This rule is deliberately unavailable to short/generic strings. The raw
    normalized SNES carrier must be at least 40 characters, the global best
    Android-English candidate must have lexical score >=82, source-token
    coverage >=92%, character similarity >=80%, and a >=20-point margin over
    the runner-up. The Android anchor must be currently unowned and proposals
    must be unique. Calibration reproduces 483/483 eligible historical mappings
    with zero conflicts.
    """
    owner = {snes_id: record for record in records for snes_id in record["snes_ids"]}
    android_owned = {text_id for record in records for text_id in record.get("android_ids", [])}
    proposals: list[dict] = []
    for event in source_document.get("events", []):
        for token in event.get("tokens", []):
            if token.get("type") != "text" or not _auto_semantic(token.get("source", "")):
                continue
            snes_id = token["id"]
            if snes_id in owner or snes_id in DIALOGUE_FORCED_UNMAPPED:
                continue
            source_display = token.get("source", "")
            if len(normalize_alignment_text(source_display)) < 40:
                continue
            ranked = index.rank(source_display, limit=5)
            if len(ranked) < 2:
                continue
            top, second = ranked[0], ranked[1]
            android_id = top["android_id"]
            if android_id in android_owned or not _auto_french_unit(android_id, english, french):
                continue
            if (
                top["lexical_score"] < 82
                or top["source_token_coverage"] < 92
                or top["character_similarity"] < 80
                or top["lexical_score"] - second["lexical_score"] < 20
            ):
                continue
            proposals.append(
                {
                    "event_id": event["event_id"],
                    "snes_id": snes_id,
                    "android_id": android_id,
                    "source_display": source_display,
                    "lexical_evidence": {
                        key: top[key]
                        for key in ("character_similarity", "source_token_coverage", "lexical_score")
                    },
                    "candidate_margin": round(top["lexical_score"] - second["lexical_score"], 1),
                }
            )

    proposal_counts: dict[int, int] = {}
    for proposal in proposals:
        proposal_counts[proposal["android_id"]] = proposal_counts.get(proposal["android_id"], 0) + 1
    additions: list[dict] = []
    for proposal in proposals:
        snes_id = proposal["snes_id"]
        android_id = proposal["android_id"]
        if snes_id in owner or proposal_counts[android_id] != 1:
            continue
        record = {
            "event_id": proposal["event_id"],
            "snes_ids": [snes_id],
            "android_ids": [android_id],
            "confidence": "very_high_isolated_global_coverage",
            "provenance": "automatic_global_coverage",
            "relation": "isolated_high_coverage_global",
            "source_display": proposal["source_display"],
            "lexical_evidence": proposal["lexical_evidence"],
            "candidate_margin": proposal["candidate_margin"],
        }
        records.append(record)
        additions.append(record)
        owner[snes_id] = record
    return additions


def _auto_add_isolated_contained_extension(
    source_document: dict,
    records: list[dict],
    index: _AutoCandidateIndex,
    english: dict[int, str],
    french: dict[int, str],
) -> list[dict]:
    """Accept a long SNES carrier verbatim-contained in a longer Android line.

    This handles version adaptations where Android English preserves the whole
    SNES wording in order but adds one clause before or after it.  The source
    must be at least 35 normalized characters, all normalized SNES tokens must
    occur as one contiguous token sequence inside the best Android-English
    candidate, token coverage must be 100%, lexical score >=76, character
    similarity >=68%, and the best candidate must lead the runner-up by >=30
    points.  The Android anchor must be free and each proposed anchor unique.

    Calibration against the accepted mapping corpus reproduces 535/535
    eligible historical mappings with zero conflicts.
    """
    owner = {snes_id: record for record in records for snes_id in record["snes_ids"]}
    android_owned = {text_id for record in records for text_id in record.get("android_ids", [])}

    def is_contained(source_display: str, android_display: str) -> bool:
        source_tokens = normalize_alignment_text(source_display).split()
        android_tokens = normalize_alignment_text(android_display).split()
        if not source_tokens or len(source_tokens) > len(android_tokens):
            return False
        width = len(source_tokens)
        return any(
            android_tokens[start:start + width] == source_tokens
            for start in range(len(android_tokens) - width + 1)
        )

    # Measure the rule against mappings that are already accepted before it is
    # allowed to propose anything new.  Only one-carrier records with concrete
    # Android provenance are comparable here; multi-carrier structural mappings
    # are intentionally outside this global lexical rule.
    calibration_attempts = 0
    calibration_conflicts: list[tuple[str, int, list[int]]] = []
    for event in source_document.get("events", []):
        for token in event.get("tokens", []):
            if token.get("type") != "text" or not _auto_semantic(token.get("source", "")):
                continue
            snes_id = token["id"]
            accepted = owner.get(snes_id)
            if (
                accepted is None
                or len(accepted.get("snes_ids", [])) != 1
                or not accepted.get("android_ids")
            ):
                continue
            source_display = token.get("source", "")
            if len(normalize_alignment_text(source_display)) < 35:
                continue
            ranked = index.rank(source_display, limit=5)
            if len(ranked) < 2:
                continue
            top, second = ranked[0], ranked[1]
            if (
                not is_contained(source_display, english[top["android_id"]])
                or top["source_token_coverage"] < 100
                or top["lexical_score"] < 76
                or top["character_similarity"] < 68
                or top["lexical_score"] - second["lexical_score"] < 30
            ):
                continue
            calibration_attempts += 1
            if top["android_id"] not in accepted["android_ids"]:
                calibration_conflicts.append(
                    (snes_id, top["android_id"], list(accepted["android_ids"]))
                )
    if calibration_conflicts:
        raise ValueError(
            "Contained-extension alignment contradicts accepted mappings: "
            + ", ".join(item[0] for item in calibration_conflicts[:10])
        )

    proposals: list[dict] = []
    for event in source_document.get("events", []):
        for token in event.get("tokens", []):
            if token.get("type") != "text" or not _auto_semantic(token.get("source", "")):
                continue
            snes_id = token["id"]
            if snes_id in owner or snes_id in DIALOGUE_FORCED_UNMAPPED:
                continue
            source_display = token.get("source", "")
            if len(normalize_alignment_text(source_display)) < 35:
                continue
            ranked = index.rank(source_display, limit=5)
            if len(ranked) < 2:
                continue
            top, second = ranked[0], ranked[1]
            android_id = top["android_id"]
            if android_id in android_owned or not _auto_french_unit(android_id, english, french):
                continue
            if not is_contained(source_display, english[android_id]):
                continue
            if (
                top["source_token_coverage"] < 100
                or top["lexical_score"] < 76
                or top["character_similarity"] < 68
                or top["lexical_score"] - second["lexical_score"] < 30
            ):
                continue
            proposals.append(
                {
                    "event_id": event["event_id"],
                    "snes_id": snes_id,
                    "android_id": android_id,
                    "source_display": source_display,
                    "lexical_evidence": {
                        key: top[key]
                        for key in ("character_similarity", "source_token_coverage", "lexical_score")
                    },
                    "candidate_margin": round(top["lexical_score"] - second["lexical_score"], 1),
                }
            )

    proposal_counts: dict[int, int] = {}
    for proposal in proposals:
        proposal_counts[proposal["android_id"]] = proposal_counts.get(proposal["android_id"], 0) + 1
    additions: list[dict] = []
    for proposal in proposals:
        snes_id = proposal["snes_id"]
        android_id = proposal["android_id"]
        if snes_id in owner or proposal_counts[android_id] != 1:
            continue
        record = {
            "event_id": proposal["event_id"],
            "snes_ids": [snes_id],
            "android_ids": [android_id],
            "confidence": "very_high_isolated_contained_extension",
            "provenance": "automatic_global_containment",
            "relation": "isolated_contained_android_extension",
            "source_display": proposal["source_display"],
            "lexical_evidence": proposal["lexical_evidence"],
            "candidate_margin": proposal["candidate_margin"],
        }
        records.append(record)
        additions.append(record)
        owner[snes_id] = record
    return additions

def _auto_add_raw_contextual_exact_duplicates(
    source_document: dict,
    records: list[dict],
    index: _AutoCandidateIndex,
    english: dict[int, str],
    french: dict[int, str],
) -> list[dict]:
    """Disambiguate divergent exact duplicates using the raw SNES text carrier.

    This complements the rendered-span exact-context pass for cases where a
    following PLAYER_NAME/staging command is structurally attached to the SNES
    carrier by the session renderer but belongs to the next Android record.
    Identity is accepted only when the raw carrier has divergent exact Android
    duplicates and already-owned semantic neighbors make exactly one occurrence
    unique inside a tight bracket or as the sole immediate neighbor. Decisions
    are non-cascading. Calibration reproduces 27/27 eligible historical mappings
    with zero conflicts.
    """
    owner = {snes_id: record for record in records for snes_id in record["snes_ids"]}
    proposals: list[dict] = []
    for event in source_document.get("events", []):
        semantic_tokens = [
            token
            for token in event.get("tokens", [])
            if token.get("type") == "text" and _auto_semantic(token.get("source", ""))
        ]
        semantic_ids = [token["id"] for token in semantic_tokens]
        for token_index, token in enumerate(semantic_tokens):
            snes_id = token["id"]
            if snes_id in owner or snes_id in DIALOGUE_FORCED_UNMAPPED:
                continue
            source_display = token.get("source", "")
            exact_ids = index.exact.get(normalize_alignment_text(source_display), [])
            if len(exact_ids) < 2:
                continue
            french_versions = {
                _auto_french_unit(text_id, english, french)
                for text_id in exact_ids
                if _auto_french_unit(text_id, english, french)
            }
            if len(french_versions) <= 1:
                continue

            previous_position = None
            following_position = None
            for search in range(token_index - 1, -1, -1):
                record = owner.get(semantic_ids[search])
                android_ids = record.get("android_ids", []) if record else []
                positions = [index.anchor_pos[text_id] for text_id in android_ids if text_id in index.anchor_pos]
                if positions:
                    previous_position = max(positions)
                    break
            for search in range(token_index + 1, len(semantic_ids)):
                record = owner.get(semantic_ids[search])
                android_ids = record.get("android_ids", []) if record else []
                positions = [index.anchor_pos[text_id] for text_id in android_ids if text_id in index.anchor_pos]
                if positions:
                    following_position = min(positions)
                    break

            chosen = None
            context = None
            if (
                previous_position is not None
                and following_position is not None
                and previous_position < following_position
                and following_position - previous_position <= 12
            ):
                bracketed = [
                    text_id
                    for text_id in exact_ids
                    if previous_position < index.anchor_pos[text_id] < following_position
                ]
                if len(bracketed) == 1:
                    chosen = bracketed[0]
                    context = "tight_bracket"
            if chosen is None:
                adjacent: list[int] = []
                if previous_position is not None:
                    adjacent.extend(
                        text_id
                        for text_id in exact_ids
                        if index.anchor_pos[text_id] == previous_position + 1
                    )
                if following_position is not None:
                    adjacent.extend(
                        text_id
                        for text_id in exact_ids
                        if index.anchor_pos[text_id] == following_position - 1
                    )
                adjacent = list(dict.fromkeys(adjacent))
                if len(adjacent) == 1:
                    chosen = adjacent[0]
                    context = "immediate_neighbor"
            if chosen is None or not _auto_french_unit(chosen, english, french):
                continue
            proposals.append(
                {
                    "event_id": event["event_id"],
                    "snes_id": snes_id,
                    "android_id": chosen,
                    "context": context,
                    "source_display": source_display,
                }
            )

    additions: list[dict] = []
    for proposal in proposals:
        snes_id = proposal["snes_id"]
        if snes_id in owner:
            continue
        android_id = proposal["android_id"]
        record = {
            "event_id": proposal["event_id"],
            "snes_ids": [snes_id],
            "android_ids": [android_id],
            "confidence": (
                "very_high_raw_exact_context_bracket"
                if proposal["context"] == "tight_bracket"
                else "very_high_raw_exact_context_adjacent"
            ),
            "provenance": "automatic_exact_context",
            "relation": "raw_exact_duplicate_context",
            "source_display": proposal["source_display"],
            "lexical_evidence": _auto_metrics(proposal["source_display"], english[android_id]),
        }
        records.append(record)
        additions.append(record)
        owner[snes_id] = record
    return additions


def _auto_add_short_unique_immediate_neighbor(
    sessions: list[dict],
    records: list[dict],
    index: _AutoCandidateIndex,
    english: dict[int, str],
    french: dict[int, str],
) -> list[dict]:
    """Accept a very short globally-unique exact only beside an owned anchor.

    Generic short exacts remain unsafe even when globally unique.  This narrower
    rule additionally requires the sole Android-English exact occurrence to be
    immediately adjacent to the nearest already-owned Android anchor on either
    side inside the same SNES dialogue session.  Decisions are non-cascading.

    Calibration against the pre-rule accepted corpus reproduces 37/37 eligible
    historical mappings with zero conflicts.
    """
    owner = {snes_id: record for record in records for snes_id in record["snes_ids"]}
    proposals: list[dict] = []
    for session in sessions:
        elements = session["elements"]
        for element_index, element in enumerate(elements):
            snes_id = element["id"]
            if snes_id in owner or snes_id in DIALOGUE_FORCED_UNMAPPED:
                continue
            source_display = _auto_render_span(session, element_index, element_index)
            normalized = normalize_alignment_text(source_display)
            if not normalized or len(normalized) >= 8:
                continue
            exact_ids = index.exact.get(normalized, [])
            if len(exact_ids) != 1:
                continue
            android_id = exact_ids[0]
            if not _auto_french_unit(android_id, english, french):
                continue

            previous_record = None
            following_record = None
            for search in range(element_index - 1, -1, -1):
                candidate = owner.get(elements[search]["id"])
                if candidate and candidate.get("android_ids"):
                    previous_record = candidate
                    break
            for search in range(element_index + 1, len(elements)):
                candidate = owner.get(elements[search]["id"])
                if candidate and candidate.get("android_ids"):
                    following_record = candidate
                    break

            candidate_position = index.anchor_pos[android_id]
            immediate = False
            if previous_record:
                positions = [
                    index.anchor_pos[text_id]
                    for text_id in previous_record["android_ids"]
                    if text_id in index.anchor_pos
                ]
                immediate = bool(positions) and candidate_position == max(positions) + 1
            if not immediate and following_record:
                positions = [
                    index.anchor_pos[text_id]
                    for text_id in following_record["android_ids"]
                    if text_id in index.anchor_pos
                ]
                immediate = bool(positions) and candidate_position == min(positions) - 1
            if not immediate:
                continue

            proposals.append(
                {
                    "event_id": session["event_id"],
                    "session_id": session["session_id"],
                    "snes_id": snes_id,
                    "android_id": android_id,
                    "source_display": source_display,
                }
            )

    additions: list[dict] = []
    for proposal in proposals:
        snes_id = proposal["snes_id"]
        if snes_id in owner:
            continue
        android_id = proposal["android_id"]
        record = {
            "event_id": proposal["event_id"],
            "session_id": proposal["session_id"],
            "snes_ids": [snes_id],
            "android_ids": [android_id],
            "confidence": "very_high_short_unique_immediate",
            "provenance": "automatic_exact_context",
            "relation": "short_unique_exact_immediate_neighbor",
            "source_display": proposal["source_display"],
            "lexical_evidence": _auto_metrics(proposal["source_display"], english[android_id]),
        }
        records.append(record)
        additions.append(record)
        owner[snes_id] = record
    return additions


def _auto_add_short_exact_punctuation_bracket(
    source_document: dict,
    sessions: list[dict],
    records: list[dict],
    index: _AutoCandidateIndex,
    english: dict[int, str],
    french: dict[int, str],
) -> list[dict]:
    """Accept a short globally-unique exact only inside a tight semantic bracket.

    Short exact strings are unsafe globally (validated counterexamples include
    generic labels/cries such as Kakkara, Sure!, and Okay).  This pass therefore
    requires both neighboring semantic SNES elements to already own monotonic
    Android anchors no more than 12 non-empty anchors apart.  The exact Android
    occurrence must be unique, lie strictly inside that bracket, and every other
    Android anchor inside the bracket must be punctuation/layout-only after the
    same normalization used by the identity layer.  Decisions are non-cascading.

    Calibration against the pre-rule accepted corpus reproduces 35/35 eligible
    historical mappings with zero conflicts.
    """
    owner = {snes_id: record for record in records for snes_id in record["snes_ids"]}
    rendered_by_id: dict[str, str] = {}
    session_by_id: dict[str, int] = {}
    for session in sessions:
        for element_index, element in enumerate(session["elements"]):
            rendered_by_id[element["id"]] = _auto_render_span(session, element_index, element_index)
            session_by_id[element["id"]] = session["session_id"]

    proposals: list[dict] = []
    for event in source_document.get("events", []):
        semantic_tokens = [
            token
            for token in event.get("tokens", [])
            if token.get("type") == "text" and _auto_semantic(token.get("source", ""))
        ]
        semantic_ids = [token["id"] for token in semantic_tokens]
        for token_index, token in enumerate(semantic_tokens):
            snes_id = token["id"]
            if snes_id in owner or snes_id in DIALOGUE_FORCED_UNMAPPED:
                continue
            # Use the text carrier itself here rather than _auto_render_span():
            # a following PLAYER_NAME/action belongs to layout/staging and can
            # be rendered into the preceding alignment span even when Android
            # places that command context on the next record. The two-sided
            # semantic bracket below is the identity proof; formatter/simulator
            # remain the independent structural/layout gate.
            source_display = token.get("source", "")
            normalized = normalize_alignment_text(source_display)
            if not normalized or len(normalized) >= 12:
                continue
            exact_ids = index.exact.get(normalized, [])
            if len(exact_ids) != 1:
                continue
            android_id = exact_ids[0]
            if not _auto_french_unit(android_id, english, french):
                continue

            previous_position = None
            following_position = None
            for search in range(token_index - 1, -1, -1):
                record = owner.get(semantic_ids[search])
                android_ids = record.get("android_ids", []) if record else []
                positions = [index.anchor_pos[text_id] for text_id in android_ids if text_id in index.anchor_pos]
                if positions:
                    previous_position = max(positions)
                    break
            for search in range(token_index + 1, len(semantic_ids)):
                record = owner.get(semantic_ids[search])
                android_ids = record.get("android_ids", []) if record else []
                positions = [index.anchor_pos[text_id] for text_id in android_ids if text_id in index.anchor_pos]
                if positions:
                    following_position = min(positions)
                    break

            candidate_position = index.anchor_pos.get(android_id)
            if (
                previous_position is None
                or following_position is None
                or candidate_position is None
                or not previous_position < candidate_position < following_position
                or following_position - previous_position > 12
            ):
                continue
            interior = index.anchor_ids[previous_position + 1 : following_position]
            if any(
                text_id != android_id and normalize_alignment_text(english[text_id])
                for text_id in interior
            ):
                continue
            proposals.append(
                {
                    "event_id": event["event_id"],
                    "session_id": session_by_id.get(snes_id),
                    "snes_id": snes_id,
                    "android_id": android_id,
                    "source_display": source_display,
                }
            )

    additions: list[dict] = []
    for proposal in proposals:
        snes_id = proposal["snes_id"]
        if snes_id in owner:
            continue
        android_id = proposal["android_id"]
        record = {
            "event_id": proposal["event_id"],
            "session_id": proposal["session_id"],
            "snes_ids": [snes_id],
            "android_ids": [android_id],
            "confidence": "very_high_short_exact_punctuation_bracket",
            "provenance": "automatic_exact_context",
            "relation": "short_exact_punctuation_bracket",
            "source_display": proposal["source_display"],
            "lexical_evidence": _auto_metrics(proposal["source_display"], english[android_id]),
        }
        records.append(record)
        additions.append(record)
        owner[snes_id] = record
    return additions


@lru_cache(maxsize=None)
def _auto_source_rom_position(snes_id: str) -> int | None:
    """Return a linear C9/CA ROM position for one canonical dialogue text ID."""
    match = re.fullmatch(r"([0-9A-F]{2}):([0-9A-F]{4})", snes_id)
    if match is None:
        return None
    return (int(match.group(1), 16) << 16) + int(match.group(2), 16)


def _auto_rom_neighborhood_duplicate_prediction(
    snes_id: str,
    records: list[dict],
    source: dict[str, dict],
    index: _AutoCandidateIndex,
    english: dict[int, str],
    *,
    exclude_record: dict | None = None,
) -> dict | None:
    """Choose an exact duplicate only when nearby ROM carriers form one Android cluster.

    This intentionally does not require strict Android monotonicity: adjacent SNES
    events can be reordered locally on Android.  Instead, the twelve closest
    already-aligned source carriers within 0x300 bytes vote for the Android
    neighborhood that best fits each exact-English duplicate.  Close SNES
    carriers count more heavily; a carrier from the same SNES event receives a
    small additional weight.  The rule abstains unless the best duplicate has a
    >=20% score margin over the runner-up.
    """
    target_position = _auto_source_rom_position(snes_id)
    if target_position is None or snes_id not in source:
        return None
    normalized = normalize_alignment_text(source[snes_id]["source"])
    exact_ids = list(index.exact.get(normalized, ()))
    if len(exact_ids) < 2:
        return None

    occurrences: list[dict] = []
    for record in records:
        if record is exclude_record or not record.get("android_ids"):
            continue
        android_positions = [
            index.anchor_pos[text_id]
            for text_id in record["android_ids"]
            if text_id in index.anchor_pos
        ]
        if not android_positions:
            continue
        for neighbor_id in record.get("snes_ids", []):
            neighbor_position = _auto_source_rom_position(neighbor_id)
            if neighbor_position is None:
                continue
            snes_distance = abs(neighbor_position - target_position)
            if snes_distance > 0x300:
                continue
            occurrences.append(
                {
                    "snes_id": neighbor_id,
                    "event_id": source[neighbor_id]["event_id"],
                    "snes_distance": snes_distance,
                    "android_ids": list(record["android_ids"]),
                    "android_min": min(android_positions),
                    "android_max": max(android_positions),
                }
            )
    occurrences.sort(key=lambda item: item["snes_distance"])
    neighbors = occurrences[:12]
    if len(neighbors) < 4:
        return None

    scores: dict[int, float] = {}
    target_event = source[snes_id]["event_id"]
    for android_id in exact_ids:
        candidate_position = index.anchor_pos[android_id]
        score = 0.0
        for neighbor in neighbors:
            if neighbor["android_min"] <= candidate_position <= neighbor["android_max"]:
                android_distance = 0
            else:
                android_distance = min(
                    abs(candidate_position - neighbor["android_min"]),
                    abs(candidate_position - neighbor["android_max"]),
                )
            weight = 1.0 / (1.0 + neighbor["snes_distance"] / 64.0)
            if neighbor["event_id"] == target_event:
                weight *= 1.5
            score += weight * math.exp(-android_distance / 12.0)
        scores[android_id] = score

    ranked = sorted(scores, key=scores.get, reverse=True)
    if len(ranked) < 2 or scores[ranked[0]] <= 0:
        return None
    best, second = ranked[0], ranked[1]
    relative_margin = (scores[best] - scores[second]) / max(scores[best], 1.0e-9)
    if relative_margin < 0.20:
        return None
    return {
        "android_id": best,
        "candidate_android_ids": exact_ids,
        "relative_score_margin": round(relative_margin, 3),
        "neighbor_count": len(neighbors),
        "neighbors": neighbors,
    }


def _auto_add_rom_neighborhood_exact_duplicates(
    records: list[dict],
    source: dict[str, dict],
    index: _AutoCandidateIndex,
    english: dict[int, str],
    french: dict[int, str],
) -> tuple[list[dict], dict]:
    """Resolve substantive divergent exact duplicates from nearby ROM provenance.

    Calibration is leave-one-out over every already-accepted simple exact
    duplicate whose Android copies have different French localization units.
    The scoring model may abstain, but every confident calibration prediction
    must reproduce the accepted Android identity.  Application is narrower than
    calibration: at least three normalized source words are required so generic
    labels/short replies such as Water Palace, Sure!, Okay, or What the...!
    remain outside this rule even if their physical neighborhood looks suggestive.
    """
    claimed_context_ids: set[str] = set()
    context_records: list[dict] = []
    for record in records:
        if any(snes_id in claimed_context_ids for snes_id in record.get("snes_ids", [])):
            continue
        context_records.append(record)
        claimed_context_ids.update(record.get("snes_ids", []))

    calibration_attempts = 0
    calibration_matches = 0
    calibration_conflicts: list[dict] = []
    for record in context_records:
        if len(record.get("snes_ids", [])) != 1 or len(record.get("android_ids", [])) != 1:
            continue
        snes_id = record["snes_ids"][0]
        if snes_id not in source:
            continue
        accepted_android_id = record["android_ids"][0]
        normalized = normalize_alignment_text(source[snes_id]["source"])
        if normalized != normalize_alignment_text(english.get(accepted_android_id, "")):
            continue
        exact_ids = list(index.exact.get(normalized, ()))
        if len(exact_ids) < 2:
            continue
        french_units = {_auto_french_unit(text_id, english, french) for text_id in exact_ids}
        if len(french_units) <= 1:
            continue
        prediction = _auto_rom_neighborhood_duplicate_prediction(
            snes_id,
            context_records,
            source,
            index,
            english,
            exclude_record=record,
        )
        if prediction is None:
            continue
        calibration_attempts += 1
        if prediction["android_id"] == accepted_android_id:
            calibration_matches += 1
        else:
            calibration_conflicts.append(
                {
                    "snes_id": snes_id,
                    "accepted_android_id": accepted_android_id,
                    "predicted_android_id": prediction["android_id"],
                }
            )
    if calibration_conflicts:
        raise ValueError(
            "ROM-neighborhood exact-duplicate alignment contradicts accepted mappings: "
            + ", ".join(item["snes_id"] for item in calibration_conflicts[:10])
        )

    owner = {snes_id for record in context_records for snes_id in record.get("snes_ids", [])}
    additions: list[dict] = []
    proposals: list[dict] = []
    for snes_id, entry in source.items():
        if snes_id in owner or snes_id in DIALOGUE_FORCED_UNMAPPED:
            continue
        normalized = normalize_alignment_text(entry["source"])
        if len(normalized.split()) < 3:
            continue
        exact_ids = list(index.exact.get(normalized, ()))
        if len(exact_ids) < 2:
            continue
        french_units = {_auto_french_unit(text_id, english, french) for text_id in exact_ids}
        if len(french_units) <= 1:
            continue
        prediction = _auto_rom_neighborhood_duplicate_prediction(
            snes_id,
            context_records,
            source,
            index,
            english,
        )
        if prediction is None:
            continue
        android_id = prediction["android_id"]
        record = {
            "event_id": entry["event_id"],
            "snes_ids": [snes_id],
            "android_ids": [android_id],
            "confidence": "very_high_rom_neighborhood_exact_duplicate",
            "provenance": "automatic_rom_neighborhood",
            "relation": "exact_duplicate_resolved_by_rom_neighborhood",
            "source_display": entry["source"],
            "lexical_evidence": _auto_metrics(entry["source"], english[android_id]),
            "rom_neighborhood_evidence": prediction,
        }
        proposals.append(record)
        owner.add(snes_id)

    records.extend(proposals)
    additions.extend(proposals)
    return additions, {
        "accepted_mapping_attempts": calibration_attempts,
        "accepted_mapping_reproductions": calibration_matches,
        "conflicts": 0,
    }


def _auto_android_group_raw_payload(
    group: tuple[int, ...] | list[int],
    english: dict[int, str],
    french: dict[int, str],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return the strict Android EN/FR payload represented by one anchor group."""
    french_ids: list[int] = []
    for android_id in group:
        for text_id in android_anchor_units((android_id,), english):
            if text_id not in french_ids:
                french_ids.append(text_id)
    return (
        tuple(english[android_id] for android_id in group),
        tuple(french[text_id] for text_id in french_ids if french[text_id]),
    )


def _auto_equivalent_group_position_prediction(
    snes_ids: list[str] | tuple[str, ...],
    android_groups: list[list[int]] | tuple[tuple[int, ...], ...],
    context_records: list[dict],
    source: dict[str, dict],
    index: _AutoCandidateIndex,
) -> dict | None:
    """Pick one translation-equivalent Android occurrence from frozen context.

    This is only a provenance tie-breaker.  It is deliberately evaluated from
    records that were concrete before this rule runs, so positionally chosen
    equivalent duplicates never become evidence for another mapping in the same
    pass.  Nearby carriers from the same SNES event receive a strong preference;
    otherwise the broader ROM-neighborhood cloud acts as the fallback.
    """
    target_positions = [
        position
        for snes_id in snes_ids
        if (position := _auto_source_rom_position(snes_id)) is not None
    ]
    if not target_positions:
        return None
    target_events = {
        source[snes_id]["event_id"] for snes_id in snes_ids if snes_id in source
    }
    target_set = set(snes_ids)

    occurrences: list[dict] = []
    for record in context_records:
        if not record.get("android_ids") or target_set.intersection(record.get("snes_ids", [])):
            continue
        android_positions = [
            index.anchor_pos[text_id]
            for text_id in record["android_ids"]
            if text_id in index.anchor_pos
        ]
        if not android_positions:
            continue
        for neighbor_id in record.get("snes_ids", []):
            neighbor_position = _auto_source_rom_position(neighbor_id)
            if neighbor_position is None or neighbor_id not in source:
                continue
            snes_distance = min(abs(neighbor_position - target) for target in target_positions)
            if snes_distance > 0x300:
                continue
            occurrences.append(
                {
                    "snes_id": neighbor_id,
                    "event_id": source[neighbor_id]["event_id"],
                    "snes_distance": snes_distance,
                    "android_ids": list(record["android_ids"]),
                    "android_min": min(android_positions),
                    "android_max": max(android_positions),
                }
            )
    occurrences.sort(key=lambda item: item["snes_distance"])
    neighbors = occurrences[:12]
    if not neighbors:
        return None

    scores: list[tuple[float, float, list[int]]] = []
    for group in android_groups:
        positions = [index.anchor_pos[text_id] for text_id in group if text_id in index.anchor_pos]
        if not positions:
            continue
        candidate_min = min(positions)
        candidate_max = max(positions)
        candidate_center = (candidate_min + candidate_max) / 2.0
        score = 0.0
        weighted_distance = 0.0
        total_weight = 0.0
        for neighbor in neighbors:
            if neighbor["android_min"] <= candidate_center <= neighbor["android_max"]:
                android_distance = 0.0
            else:
                android_distance = min(
                    abs(candidate_center - neighbor["android_min"]),
                    abs(candidate_center - neighbor["android_max"]),
                )
            weight = 1.0 / (1.0 + neighbor["snes_distance"] / 64.0)
            if neighbor["event_id"] in target_events:
                # Same-event dialogue structure outranks the looser physical-ROM
                # cloud. This preserves proven prompt/choice and scene runs.
                weight *= 6.0
            score += weight * math.exp(-android_distance / 12.0)
            weighted_distance += weight * android_distance
            total_weight += weight
        mean_distance = weighted_distance / total_weight if total_weight else float("inf")
        scores.append((score, -mean_distance, list(group)))
    if not scores:
        return None
    scores.sort(key=lambda item: (item[0], item[1], -min(item[2])), reverse=True)
    best_score, best_negative_distance, best_group = scores[0]
    runner_score = scores[1][0] if len(scores) > 1 else 0.0
    return {
        "android_ids": best_group,
        "candidate_android_groups": [list(group) for group in android_groups],
        "score": round(best_score, 6),
        "runner_up_score": round(runner_score, 6),
        "mean_android_anchor_distance": round(-best_negative_distance, 3),
        "neighbor_count": len(neighbors),
        "neighbors": neighbors,
    }


def _auto_add_equivalent_duplicate_positional_tiebreak(
    records: list[dict],
    source: dict[str, dict],
    index: _AutoCandidateIndex,
    english: dict[int, str],
    french: dict[int, str],
) -> tuple[list[dict], dict]:
    """Resolve strict EN+FR-equivalent duplicates without cascading evidence.

    Two separate operations are intentionally performed from the same frozen
    context. First, a strong fuzzy identity may ignore repeated copies of the
    *same raw Android EN+FR payload* when measuring its margin against the next
    genuinely different candidate. Second, mappings whose translation was
    already accepted through equivalent alternative groups receive one concrete
    Android provenance chosen by the neighboring dialogue block.

    Chosen equivalent occurrences are never fed back into any other alignment
    rule in this pass. Android French establishes equivalence only after Android
    English has identified the candidate payload; it never proves identity.
    """
    frozen_context = [record for record in records if record.get("android_ids")]

    payload_groups: dict[tuple[str, tuple[str, ...]], list[int]] = {}
    for android_id in index.anchor_ids:
        french_unit = _auto_french_unit(android_id, english, french)
        if not french_unit:
            continue
        payload_groups.setdefault((english[android_id], french_unit), []).append(android_id)

    def ranked_payloads(source_display: str) -> list[dict]:
        ranked = index.rank(source_display, limit=100)
        result: list[dict] = []
        seen: set[tuple[str, tuple[str, ...]]] = set()
        for candidate in ranked:
            android_id = candidate["android_id"]
            key = (english[android_id], _auto_french_unit(android_id, english, french))
            if not key[1] or key in seen:
                continue
            seen.add(key)
            result.append(
                {
                    "android_ids": list(payload_groups.get(key, [android_id])),
                    "metrics": candidate,
                }
            )
        return result

    def qualified_payload(source_display: str) -> dict | None:
        normalized = normalize_alignment_text(source_display)
        if len(normalized) < 24:
            return None
        ranked = ranked_payloads(source_display)
        if len(ranked) < 2 or len(ranked[0]["android_ids"]) < 2:
            return None
        top = ranked[0]
        second = ranked[1]
        metrics = top["metrics"]
        margin = metrics["lexical_score"] - second["metrics"]["lexical_score"]
        if (
            metrics["lexical_score"] < 90
            or metrics["source_token_coverage"] < 80
            or metrics["character_similarity"] < 90
            or margin < 20
        ):
            return None
        return {
            "android_ids": top["android_ids"],
            "metrics": metrics,
            "candidate_margin": round(margin, 1),
        }

    # Calibrate semantic recognition against the complete already-accepted
    # one-carrier corpus, including mappings that intentionally stored several
    # equivalent Android alternatives. Round 35 yields 35/35 reproductions.
    calibration_attempts = 0
    calibration_matches = 0
    calibration_conflicts: list[str] = []
    for record in records:
        if len(record.get("snes_ids", [])) != 1:
            continue
        snes_id = record["snes_ids"][0]
        accepted_ids = set(record.get("android_ids", []))
        for group in record.get("android_alternative_anchor_groups", []):
            accepted_ids.update(group)
        if not accepted_ids or snes_id not in source:
            continue
        qualified = qualified_payload(source[snes_id]["source"])
        if qualified is None:
            continue
        calibration_attempts += 1
        if accepted_ids.intersection(qualified["android_ids"]):
            calibration_matches += 1
        else:
            calibration_conflicts.append(snes_id)
    if calibration_conflicts:
        raise ValueError(
            "Equivalent-duplicate semantic grouping contradicts accepted mappings: "
            + ", ".join(calibration_conflicts[:10])
        )
    if calibration_attempts != 35 or calibration_matches != 35:
        raise ValueError(
            "Equivalent-duplicate semantic calibration corpus changed unexpectedly: "
            f"expected 35/35, found {calibration_matches}/{calibration_attempts}"
        )

    owner = {snes_id for record in records for snes_id in record.get("snes_ids", [])}
    additions: list[dict] = []
    for snes_id, entry in source.items():
        if snes_id in owner or snes_id in DIALOGUE_FORCED_UNMAPPED:
            continue
        if not _auto_semantic(entry["source"]):
            continue
        qualified = qualified_payload(entry["source"])
        if qualified is None:
            continue
        android_groups = [[android_id] for android_id in qualified["android_ids"]]
        prediction = _auto_equivalent_group_position_prediction(
            [snes_id], android_groups, frozen_context, source, index
        )
        if prediction is None:
            continue
        android_ids = prediction["android_ids"]
        record = {
            "event_id": entry["event_id"],
            "snes_ids": [snes_id],
            "android_ids": android_ids,
            "confidence": "very_high_equivalent_duplicate_positional_tiebreak",
            "provenance": "automatic_equivalent_duplicate_positional_tiebreak",
            "relation": "equivalent_duplicate_resolved_by_positional_tiebreak",
            "source_display": entry["source"],
            "lexical_evidence": {
                key: qualified["metrics"][key]
                for key in ("character_similarity", "source_token_coverage", "lexical_score")
            },
            "candidate_margin": qualified["candidate_margin"],
            "equivalent_android_ids": list(qualified["android_ids"]),
            "positional_tiebreak_evidence": prediction,
        }
        records.append(record)
        additions.append(record)
        owner.add(snes_id)

    # Resolve old translation-equivalent alternatives to one concrete origin.
    # Use only the pre-rule concrete context above: neither the new additions nor
    # another resolved alternative can influence the next choice.
    resolved_records = 0
    resolved_source_ids = 0
    for record in records:
        alternatives = record.get("android_alternative_anchor_groups")
        if not alternatives:
            continue
        payloads = [
            _auto_android_group_raw_payload(group, english, french)
            for group in alternatives
        ]
        if not payloads or len(set(payloads)) != 1 or not payloads[0][1]:
            continue
        prediction = _auto_equivalent_group_position_prediction(
            record.get("snes_ids", []), alternatives, frozen_context, source, index
        )
        if prediction is None:
            continue
        original_alternatives = [list(group) for group in alternatives]
        record["android_ids"] = list(prediction["android_ids"])
        record["android_equivalent_alternative_anchor_groups"] = original_alternatives
        record["provenance_resolution"] = "equivalent_duplicate_positional_tiebreak"
        record["positional_tiebreak_evidence"] = prediction
        del record["android_alternative_anchor_groups"]
        resolved_records += 1
        resolved_source_ids += len(record.get("snes_ids", []))

    return additions, {
        "semantic_group_calibration_attempts": calibration_attempts,
        "semantic_group_calibration_reproductions": calibration_matches,
        "conflicts": 0,
        "new_mapping_count": len(additions),
        "resolved_alternative_record_count": resolved_records,
        "resolved_alternative_source_id_count": resolved_source_ids,
        "non_cascading": True,
    }


def _auto_add_isolated_event_rom_neighborhood_fuzzy(
    source_document: dict,
    records: list[dict],
    source: dict[str, dict],
    index: _AutoCandidateIndex,
    english: dict[int, str],
    french: dict[int, str],
) -> tuple[list[dict], dict]:
    """Resolve one-carrier events from strong lexical + frozen ROM-neighborhood evidence.

    This Round-37 rule deliberately targets only events containing exactly one
    semantic SNES carrier.  The best distinct Android-English payload must be
    substantially better than the runner-up and must also sit inside the
    Android cluster independently suggested by already accepted nearby ROM
    carriers.  Translation-equivalent duplicate provenances accepted in Round
    36 are allowed as prior-pass anchors, but additions made by this rule are
    evaluated from one frozen context and therefore cannot cascade.

    Exact Android-English duplicates whose complete French localization differs
    remain outside this rule.  Android FR is never used to establish identity.
    """
    frozen_context = [record for record in records if record.get("android_ids")]
    owner = {snes_id for record in records for snes_id in record.get("snes_ids", [])}
    android_owned = {
        android_id
        for record in records
        for android_id in record.get("android_ids", [])
    }
    semantic_by_event: dict[str, list[str]] = {}
    for event in source_document.get("events", []):
        semantic_by_event[event["event_id"]] = [
            token["id"]
            for token in event.get("tokens", [])
            if token.get("type") == "text" and _auto_semantic(token.get("source", ""))
        ]

    def ranked_distinct(source_display: str) -> list[dict]:
        result: list[dict] = []
        seen: set[str] = set()
        for candidate in index.rank(source_display, limit=100):
            key = normalize_alignment_text(english[candidate["android_id"]])
            if key in seen:
                continue
            seen.add(key)
            result.append(candidate)
        return result

    def evaluate(snes_id: str) -> dict | None:
        source_display = source[snes_id]["source"]
        if len(normalize_alignment_text(source_display)) < 20:
            return None
        ranked = ranked_distinct(source_display)
        if len(ranked) < 2:
            return None
        top, second = ranked[0], ranked[1]
        android_id = top["android_id"]

        # Preserve the stronger duplicate policy: if the SNES carrier itself is
        # an exact duplicate whose Android copies localize differently, this
        # fuzzy/positional rule is not allowed to choose between them.
        exact_ids = index.exact.get(normalize_alignment_text(source_display), [])
        if len(exact_ids) > 1:
            french_units = {_auto_french_unit(text_id, english, french) for text_id in exact_ids}
            if len(french_units) > 1:
                return None

        positional = _auto_equivalent_group_position_prediction(
            [snes_id], [[android_id]], frozen_context, source, index
        )
        if positional is None or positional["neighbor_count"] < 4:
            return None
        margin = top["lexical_score"] - second["lexical_score"]
        standard = (
            top["lexical_score"] >= 75
            and top["source_token_coverage"] >= 70
            and top["character_similarity"] >= 70
            and margin >= 20
            and positional["score"] >= 0.25
            and positional["mean_android_anchor_distance"] <= 160
        )
        close_paraphrase = (
            top["lexical_score"] >= 80
            and top["source_token_coverage"] >= 65
            and top["character_similarity"] >= 85
            and margin >= 20
            and positional["score"] >= 0.5
            and positional["mean_android_anchor_distance"] <= 80
        )
        if not (standard or close_paraphrase):
            return None
        return {
            "android_id": android_id,
            "metrics": top,
            "candidate_margin": round(margin, 1),
            "positional_evidence": positional,
            "threshold_branch": "standard" if standard else "close_paraphrase",
        }

    # Calibrate only against already accepted one-carrier events of the same
    # structural class. Round 43's orb-family context removed C9:D239/C9:D31C
    # from positional eligibility. Round 44's new local-sequence/inn anchors remove one additional historical
    # probe from eligibility. Round 45's Kakkara scene anchor restores enough
    # local context for C9:1984 to re-enter the historical probe set; it still
    # reproduces its accepted mapping, so the calibrated corpus is 188/188.
    calibration_attempts = 0
    calibration_matches = 0
    calibration_conflicts: list[str] = []
    for record in frozen_context:
        if len(record.get("snes_ids", [])) != 1:
            continue
        snes_id = record["snes_ids"][0]
        if snes_id not in source:
            continue
        event_id = source[snes_id]["event_id"]
        if len(semantic_by_event.get(event_id, [])) != 1:
            continue
        # Explicit structural overrides are deliberately outside the generic
        # fuzzy calibration domain: Round 85 corrects C9:E5BF because Android
        # FR redistributed the local NPC lines differently from Android EN.
        if snes_id in DIALOGUE_REVIEWED_AUTO_OVERRIDES:
            continue
        candidate = evaluate(snes_id)
        if candidate is None:
            continue
        calibration_attempts += 1
        predicted = normalize_alignment_text(english[candidate["android_id"]])
        accepted = {
            normalize_alignment_text(english[android_id])
            for android_id in record.get("android_ids", [])
            if android_id in english
        }
        if predicted in accepted:
            calibration_matches += 1
        else:
            calibration_conflicts.append(snes_id)
    if calibration_conflicts:
        raise ValueError(
            "Isolated-event ROM-neighborhood fuzzy alignment contradicts accepted mappings: "
            + ", ".join(calibration_conflicts[:10])
        )
    if calibration_attempts != 187 or calibration_matches != 187:
        raise ValueError(
            "Isolated-event ROM-neighborhood fuzzy calibration corpus changed unexpectedly: "
            f"expected 187/187, found {calibration_matches}/{calibration_attempts}"
        )

    additions: list[dict] = []
    for event_id, semantic_ids in semantic_by_event.items():
        if len(semantic_ids) != 1:
            continue
        snes_id = semantic_ids[0]
        if snes_id in owner or snes_id in DIALOGUE_FORCED_UNMAPPED:
            continue
        candidate = evaluate(snes_id)
        if candidate is None:
            continue
        android_id = candidate["android_id"]
        # A free Android anchor is required here. Re-use across unrelated SNES
        # carriers needs explicit structural review rather than a generic fuzzy rule.
        if android_id in android_owned or not _auto_french_unit(android_id, english, french):
            continue
        record = {
            "event_id": event_id,
            "snes_ids": [snes_id],
            "android_ids": [android_id],
            "confidence": "very_high_isolated_rom_neighborhood_fuzzy",
            "provenance": "automatic_isolated_rom_neighborhood_fuzzy",
            "relation": "isolated_single_carrier_resolved_by_lexical_and_rom_neighborhood",
            "source_display": source[snes_id]["source"],
            "lexical_evidence": {
                key: candidate["metrics"][key]
                for key in ("character_similarity", "source_token_coverage", "lexical_score")
            },
            "candidate_margin": candidate["candidate_margin"],
            "threshold_branch": candidate["threshold_branch"],
            "rom_neighborhood_evidence": candidate["positional_evidence"],
        }
        additions.append(record)
        owner.add(snes_id)
        android_owned.add(android_id)

    records.extend(additions)
    return additions, {
        "accepted_mapping_attempts": calibration_attempts,
        "accepted_mapping_reproductions": calibration_matches,
        "conflicts": 0,
        "new_mapping_count": len(additions),
        "non_cascading": True,
    }


def _auto_add_isolated_event_local_extension(
    source_document: dict,
    records: list[dict],
    source: dict[str, dict],
    index: _AutoCandidateIndex,
    english: dict[int, str],
    french: dict[int, str],
) -> tuple[list[dict], dict]:
    """Resolve a unique longer Android line from exceptionally tight local context.

    This Round-38 rule is intentionally narrower than ordinary fuzzy matching.
    It targets one-semantic-carrier events where Android English expands the SNES
    line, but the candidate has very high source-token coverage and lies almost
    exactly inside a dense block of already accepted neighboring dialogue.  The
    Android-English payload must be globally unique; divergent duplicate copies
    are therefore outside this rule by construction.

    Round-37 mappings are accepted prior-pass context for this rule. Additions
    made here are still evaluated from one frozen context and cannot cascade.
    Android French never participates in semantic candidate selection.
    """
    frozen_context = [record for record in records if record.get("android_ids")]
    owner = {snes_id for record in records for snes_id in record.get("snes_ids", [])}
    android_owned = {
        android_id for record in records for android_id in record.get("android_ids", [])
    }
    semantic_by_event: dict[str, list[str]] = {}
    for event in source_document.get("events", []):
        semantic_by_event[event["event_id"]] = [
            token["id"]
            for token in event.get("tokens", [])
            if token.get("type") == "text" and _auto_semantic(token.get("source", ""))
        ]

    def ranked_distinct(source_display: str) -> list[dict]:
        result: list[dict] = []
        seen: set[str] = set()
        for candidate in index.rank(source_display, limit=100):
            key = normalize_alignment_text(english[candidate["android_id"]])
            if key in seen:
                continue
            seen.add(key)
            result.append(candidate)
        return result

    def evaluate(snes_id: str) -> dict | None:
        source_display = source[snes_id]["source"]
        source_norm = normalize_alignment_text(source_display)
        source_words = source_norm.split()
        if len(source_norm) < 25 or len(source_words) < 6:
            return None
        ranked = ranked_distinct(source_display)
        if len(ranked) < 2:
            return None
        top, second = ranked[0], ranked[1]
        android_id = top["android_id"]
        android_norm = normalize_alignment_text(english[android_id])
        # The semantic Android-English line must itself be unique. This keeps
        # duplicate-provenance/relocalization decisions in their dedicated rules.
        if len(index.exact.get(android_norm, [])) != 1:
            return None
        if len(android_norm.split()) <= len(source_words):
            return None
        positional = _auto_equivalent_group_position_prediction(
            [snes_id], [[android_id]], frozen_context, source, index
        )
        if positional is None:
            return None
        margin = top["lexical_score"] - second["lexical_score"]
        if not (
            top["lexical_score"] >= 65
            and top["source_token_coverage"] >= 85
            and margin >= 8
            and positional["score"] >= 1.5
            and positional["mean_android_anchor_distance"] <= 40
            and positional["neighbor_count"] >= 8
        ):
            return None
        return {
            "android_id": android_id,
            "metrics": top,
            "candidate_margin": round(margin, 1),
            "positional_evidence": positional,
        }

    calibration_attempts = 0
    calibration_matches = 0
    calibration_conflicts: list[str] = []
    for record in frozen_context:
        if len(record.get("snes_ids", [])) != 1:
            continue
        snes_id = record["snes_ids"][0]
        if snes_id not in source:
            continue
        event_id = source[snes_id]["event_id"]
        if len(semantic_by_event.get(event_id, [])) != 1:
            continue
        candidate = evaluate(snes_id)
        if candidate is None:
            continue
        calibration_attempts += 1
        predicted = normalize_alignment_text(english[candidate["android_id"]])
        accepted = {
            normalize_alignment_text(english[android_id])
            for android_id in record.get("android_ids", [])
            if android_id in english
        }
        if predicted in accepted:
            calibration_matches += 1
        else:
            calibration_conflicts.append(snes_id)
    if calibration_conflicts:
        raise ValueError(
            "Isolated-event local-extension alignment contradicts accepted mappings: "
            + ", ".join(calibration_conflicts[:10])
        )
    if calibration_attempts != 5 or calibration_matches != 5:
        raise ValueError(
            "Isolated-event local-extension calibration corpus changed unexpectedly: "
            f"expected 5/5, found {calibration_matches}/{calibration_attempts}"
        )

    additions: list[dict] = []
    for event_id, semantic_ids in semantic_by_event.items():
        if len(semantic_ids) != 1:
            continue
        snes_id = semantic_ids[0]
        if snes_id in owner or snes_id in DIALOGUE_FORCED_UNMAPPED:
            continue
        candidate = evaluate(snes_id)
        if candidate is None:
            continue
        android_id = candidate["android_id"]
        if android_id in android_owned or not _auto_french_unit(android_id, english, french):
            continue
        record = {
            "event_id": event_id,
            "snes_ids": [snes_id],
            "android_ids": [android_id],
            "confidence": "very_high_isolated_local_extension",
            "provenance": "automatic_isolated_local_extension",
            "relation": "isolated_android_extension_resolved_by_dense_local_context",
            "source_display": source[snes_id]["source"],
            "lexical_evidence": {
                key: candidate["metrics"][key]
                for key in ("character_similarity", "source_token_coverage", "lexical_score")
            },
            "candidate_margin": candidate["candidate_margin"],
            "rom_neighborhood_evidence": candidate["positional_evidence"],
        }
        additions.append(record)
        owner.add(snes_id)
        android_owned.add(android_id)

    records.extend(additions)
    return additions, {
        "accepted_mapping_attempts": calibration_attempts,
        "accepted_mapping_reproductions": calibration_matches,
        "conflicts": 0,
        "new_mapping_count": len(additions),
        "non_cascading": True,
        "uses_round37_as_prior_pass_context": True,
    }

def _auto_add_validated_alternatives(
    records: list[dict],
    source: dict[str, dict],
    english: dict[int, str],
    french: dict[int, str],
) -> None:
    owner = {snes_id for record in records for snes_id in record["snes_ids"]}
    for snes_id, alternatives in DIALOGUE_VALIDATED_ALTERNATIVE_GROUPS.items():
        if snes_id in owner:
            continue
        french_versions = []
        for group in alternatives:
            unit_ids = android_anchor_units(tuple(group), english)
            french_versions.append(tuple(french[text_id] for text_id in unit_ids if french[text_id]))
        if not french_versions or len(set(french_versions)) != 1:
            raise ValueError(f"Validated alternative Android groups diverged in French for {snes_id}")
        records.append(
            {
                "event_id": source[snes_id]["event_id"],
                "snes_ids": [snes_id],
                "android_ids": [],
                "android_alternative_anchor_groups": [list(group) for group in alternatives],
                "confidence": "user_validated_equivalent_alternatives",
                "provenance": "pilot_manual_review",
                "source_display": source[snes_id]["source"],
                "french_display": " ".join(french_versions[0]),
            }
        )


def _auto_unmapped_reason(
    snes_id: str,
    source_text: str,
    index: _AutoCandidateIndex,
    english: dict[int, str],
    french: dict[int, str],
) -> dict:
    if snes_id in DIALOGUE_VALIDATED_ANDROID_OMISSIONS:
        return {
            "reason": "validated_android_omission",
            "note": DIALOGUE_VALIDATED_ANDROID_OMISSIONS[snes_id],
            "top_candidates": index.rank(source_text, limit=3),
        }
    if snes_id in DIALOGUE_VALIDATED_CONTEXTUAL_TEMPLATES:
        return {
            "reason": "validated_contextual_template",
            "note": DIALOGUE_VALIDATED_CONTEXTUAL_TEMPLATES[snes_id],
            "top_candidates": index.rank(source_text, limit=3),
        }
    if snes_id in DIALOGUE_FORCED_UNMAPPED:
        return {
            "reason": "validated_no_equivalent",
            "note": DIALOGUE_FORCED_UNMAPPED[snes_id],
            "top_candidates": index.rank(source_text, limit=3),
        }
    normalized = normalize_alignment_text(source_text)
    exact_ids = index.exact.get(normalized, [])
    if len(exact_ids) > 1:
        french_units = {_auto_french_unit(text_id, english, french) for text_id in exact_ids}
        if len(french_units) > 1:
            return {
                "reason": "ambiguous_exact_duplicates_with_different_french",
                "note": "Exact Android-English duplicates do not carry one identical French localization block.",
                "top_candidates": index.rank(source_text, limit=5),
            }
    ranked = index.rank(source_text, limit=3)
    if not ranked:
        return {
            "reason": "no_lexical_candidate",
            "note": "No non-empty Android-English lexical candidate.",
            "top_candidates": [],
        }
    top = ranked[0]
    second = ranked[1]["lexical_score"] if len(ranked) > 1 else 0.0
    margin = top["lexical_score"] - second
    if top["lexical_score"] >= 90 and margin < 8:
        reason = "strong_but_ambiguous"
        note = "Strong lexical similarity, but candidate separation is too small without decisive local context."
    elif top["lexical_score"] >= 80:
        reason = "insufficient_context_or_segmentation"
        note = "Plausible lexical candidate exists, but the conservative local-order/segmentation rules did not establish very-high confidence."
    else:
        reason = "insufficient_lexical_confidence"
        note = "Best Android-English candidate is too different to accept automatically."
    return {
        "reason": reason,
        "note": note,
        "top_candidates": ranked,
    }


def make_dialogue_auto_alignment(
    english: dict[int, str],
    french: dict[int, str],
    *,
    english_path: Path,
    french_path: Path,
) -> dict:
    """Align the complete canonical SNES dialogue inventory conservatively.

    This produces correspondence metadata only. It deliberately does not write
    unformatted Android French prose to ``translations/dialogues_french.json``.
    """
    require_parallel_scrtxt(english, french)
    system_english = read_scrtxt(DEFAULT_SYSTXT_EN)
    system_french = read_scrtxt(DEFAULT_SYSTXT_FR)
    require_parallel_scrtxt(system_english, system_french)
    document = json.loads(DIALOGUE_SOURCE.read_text(encoding="utf-8"))
    source = load_dialogue_text_entries()
    sessions = _auto_sessions(document)
    index = _AutoCandidateIndex(english)

    # 1. Generic automatic session pass, calibrated against but not seeded by
    # the reviewed rounds.
    auto_records: list[dict] = []
    for session in sessions:
        seeds: list[dict | None] = []
        rankings: list[list[dict]] = []
        for element_index in range(len(session["elements"])):
            seed, ranked = _auto_seed(session, element_index, index)
            seeds.append(seed)
            rankings.append(ranked)
        window = _auto_choose_window(session, seeds, rankings, index)
        if window is None:
            continue
        operations = _auto_align_session(session, (window[0], window[1]), index, english)
        for accepted in _auto_accept_session_blocks(session, operations, seeds):
            snes_ids = [
                session["elements"][element_index]["id"]
                for element_index in range(accepted["first_source"], accepted["last_source"] + 1)
            ]
            if any(snes_id in DIALOGUE_FORCED_UNMAPPED for snes_id in snes_ids):
                continue
            auto_records.append(
                {
                    "event_id": session["event_id"],
                    "session_id": session["session_id"],
                    "snes_ids": snes_ids,
                    "android_ids": accepted["android_ids"],
                    "confidence": accepted["confidence"],
                    "provenance": "automatic_session_alignment",
                    "source_display": accepted["source_display"],
                    "lexical_evidence": accepted["evidence"],
                }
            )

    # 2. User-validated rounds are authoritative. Auto blocks never override a
    # reviewed source ID; calibration check below also verifies that the generic
    # pass did not contradict any reviewed mapping it attempted.
    reviewed = _auto_reviewed_records(source)
    reviewed_ids = {snes_id for record in reviewed for snes_id in record["snes_ids"]}
    calibration_attempts = 0
    calibration_matches = 0
    calibration_conflicts: list[dict] = []
    reviewed_by_id = {snes_id: record for record in reviewed for snes_id in record["snes_ids"]}
    for record in auto_records:
        overlap = reviewed_ids.intersection(record["snes_ids"])
        if not overlap:
            continue
        for snes_id in overlap:
            reviewed_record = reviewed_by_id[snes_id]
            if reviewed_record.get("android_namespace", "scrtxt") != "scrtxt":
                # Generic automatic matching intentionally indexes scrtxt only;
                # a reviewed systxt ownership is outside this calibration domain.
                continue
            calibration_attempts += 1
            expected = set(reviewed_record["android_ids"])
            observed = set(record["android_ids"])
            if expected.intersection(observed):
                calibration_matches += 1
            elif snes_id in DIALOGUE_REVIEWED_AUTO_OVERRIDES:
                # Round-specific structural evidence intentionally corrects the
                # generic lexical choice; reviewed records remain authoritative.
                continue
            else:
                calibration_conflicts.append(
                    {
                        "snes_id": snes_id,
                        "expected_android_ids": sorted(expected),
                        "automatic_android_ids": sorted(observed),
                    }
                )
    if calibration_conflicts:
        raise ValueError(
            "Automatic dialogue alignment contradicts user-validated calibration: "
            + ", ".join(item["snes_id"] for item in calibration_conflicts[:10])
        )
    records = [record for record in auto_records if not reviewed_ids.intersection(record["snes_ids"])]
    records.extend(reviewed)

    # 3. Expand only through already-established local/session context, then
    # through immediately neighboring dialogue sessions inside the same event.
    _auto_same_session_context_expand(sessions, records, index, english)
    _auto_event_context_expand(sessions, records, index, english)

    # 4. Preserve the user-reviewed pilot alternatives first, then handle other
    # safe exact cases. Exact duplicates are accepted automatically only if
    # every copy yields the same complete French localization interval.
    _auto_add_validated_alternatives(records, source, english, french)
    _auto_add_exact_equivalences(sessions, records, index, english, french)
    _auto_add_exact_segmentation_equivalences(sessions, records, index, english, french)

    # Exact segmentation can establish a new local anchor in sessions that had
    # no usable single-fragment seed. Re-run the existing conservative context
    # expansion once; thresholds and ordering rules are unchanged.
    _auto_same_session_context_expand(sessions, records, index, english)
    _auto_event_context_expand(sessions, records, index, english)
    _auto_add_contextual_exact_duplicates(document, sessions, records, index, english, french)
    _auto_add_raw_contextual_exact_duplicates(document, records, index, english, french)
    _auto_add_short_exact_punctuation_bracket(document, sessions, records, index, english, french)
    _auto_add_tight_single_gap_context(document, records, index, english, french)
    _auto_add_isolated_high_coverage_global(document, records, index, english, french)
    _auto_add_isolated_contained_extension(document, records, index, english, french)
    _auto_add_short_unique_immediate_neighbor(sessions, records, index, english, french)
    # New high-leverage rules run last so they can fill only genuinely free
    # identities and never replace a mapping already accepted by older passes.
    _auto_add_placeholder_index_equivalent_duplicates(
        sessions, records, index, english, french
    )
    _auto_add_raw_unique_exact_player_context_neighbor(
        sessions, records, index, english, french
    )
    _rom_neighborhood_additions, rom_neighborhood_calibration = (
        _auto_add_rom_neighborhood_exact_duplicates(
            records, source, index, english, french
        )
    )
    _equivalent_tiebreak_additions, equivalent_tiebreak_calibration = (
        _auto_add_equivalent_duplicate_positional_tiebreak(
            records, source, index, english, french
        )
    )
    _isolated_rom_fuzzy_additions, isolated_rom_fuzzy_calibration = (
        _auto_add_isolated_event_rom_neighborhood_fuzzy(
            document, records, source, index, english, french
        )
    )
    _isolated_local_extension_additions, isolated_local_extension_calibration = (
        _auto_add_isolated_event_local_extension(
            document, records, source, index, english, french
        )
    )

    # Enforce single ownership for every semantic SNES text ID.
    owner: dict[str, dict] = {}
    unique_records: list[dict] = []
    for record in records:
        if any(snes_id in owner for snes_id in record["snes_ids"]):
            # This should only be possible if an automatic expansion overlaps a
            # previously accepted block; keeping first ownership is conservative.
            continue
        unique_records.append(record)
        for snes_id in record["snes_ids"]:
            owner[snes_id] = record

    source_order = {text_id: order for order, text_id in enumerate(source)}
    enriched_records: list[dict] = []
    for record in unique_records:
        if record.get("android_ids"):
            record = _auto_enrich_record(
                record, english, french,
                system_english=system_english, system_french=system_french,
            )
        enriched_records.append(record)
    enriched_records.sort(key=lambda record: min(source_order[snes_id] for snes_id in record["snes_ids"]))
    dropped_trailing_french_only_player_turns = _auto_drop_trailing_french_only_player_turns(
        enriched_records, english, french
    )
    french_slot_reattributions = _auto_reattribute_forward_player_french_slots(
        enriched_records, english, french
    )

    semantic_ids = [text_id for text_id, entry in source.items() if _auto_semantic(entry["source"])]
    mapped_ids = {snes_id for record in enriched_records for snes_id in record["snes_ids"]}
    unmapped: list[dict] = []
    for snes_id in semantic_ids:
        if snes_id in mapped_ids:
            continue
        entry = source[snes_id]
        detail = _auto_unmapped_reason(snes_id, entry["source"], index, english, french)
        candidates = []
        for candidate in detail.pop("top_candidates"):
            android_id = candidate["android_id"]
            candidates.append(
                {
                    **candidate,
                    "android_english": english[android_id],
                    "french_unit_ids": [
                        text_id for text_id in english_anchor_interval(android_id, english) if french[text_id]
                    ],
                    "french_display": " ".join(
                        french[text_id]
                        for text_id in english_anchor_interval(android_id, english)
                        if french[text_id]
                    ),
                }
            )
        unmapped.append(
            {
                "event_id": entry["event_id"],
                "snes_id": snes_id,
                "source": entry["source"],
                **detail,
                "top_candidates": candidates,
            }
        )

    total_text_tokens = len(source)
    semantic_count = len(semantic_ids)
    semantic_id_set = set(semantic_ids)
    mapped_semantic_count = len(mapped_ids & semantic_id_set)
    mapped_total_count = len(mapped_ids)
    nonsemantic_count = total_text_tokens - semantic_count
    confidence_counts: dict[str, int] = {}
    provenance_counts: dict[str, int] = {}
    for record in enriched_records:
        width = len(record["snes_ids"])
        confidence_counts[record["confidence"]] = confidence_counts.get(record["confidence"], 0) + width
        provenance_counts[record["provenance"]] = provenance_counts.get(record["provenance"], 0) + width

    return {
        "format_version": 1,
        "status": "automatic_conservative_alignment",
        "source_asset": "dialogues.json",
        "android_english": {
            "path": "sources/android/scrtxt_en.bin",
            "sha256": sha256(english_path),
        },
        "android_french": {
            "path": "sources/android/scrtxt_fr.bin",
            "sha256": sha256(french_path),
        },
        "android_system_english": {
            "path": "sources/android/systxt_en.bin",
            "sha256": sha256(DEFAULT_SYSTXT_EN),
        },
        "android_system_french": {
            "path": "sources/android/systxt_fr.bin",
            "sha256": sha256(DEFAULT_SYSTXT_FR),
        },
        "policy": {
            "english_identity_is_primary": True,
            "automatic_translation_generation": False,
            "accepted_automatic_confidence": "very_high only",
            "notes": [
                "Alignment operates on TEXT_OPEN/TEXT_CLOSE-local dialogue sessions rather than assuming whole-event Android monotonicity.",
                "Dynamic PLAYER_NAME commands are normalized to Android %S(index,0) placeholders for comparison only.",
                "French is recovered through complete English-anchor localization intervals after English identity is established.",
                "Strictly identical Android EN+FR duplicate payloads may use neighboring dialogue blocks as a non-cascading provenance tie-breaker; the original equivalent alternatives remain traceable in metadata.",
                "Unmatched or ambiguous SNES prose is retained as unmapped and is never forced onto the nearest candidate.",
                "SNES wrapping/page/layout formatting is a separate later step; Android French prose is not written to translations/dialogues_french.json here.",
            ],
        },
        "calibration": {
            "reviewed_source_id_count": len(reviewed_ids) + len(DIALOGUE_VALIDATED_ALTERNATIVE_GROUPS),
            "automatic_attempts_on_reviewed_ids": calibration_attempts,
            "automatic_matches_on_reviewed_ids": calibration_matches,
            "automatic_conflicts": 0,
            "rom_neighborhood_exact_duplicates": rom_neighborhood_calibration,
            "equivalent_duplicate_positional_tiebreak": equivalent_tiebreak_calibration,
            "isolated_event_rom_neighborhood_fuzzy": isolated_rom_fuzzy_calibration,
            "isolated_event_local_extension": isolated_local_extension_calibration,
        },
        "coverage": {
            "source_text_token_count": total_text_tokens,
            "semantic_source_id_count": semantic_count,
            "layout_or_punctuation_only_source_id_count": nonsemantic_count,
            "mapped_source_id_count": mapped_total_count,
            "mapped_semantic_source_id_count": mapped_semantic_count,
            "mapped_layout_or_punctuation_only_source_id_count": mapped_total_count - mapped_semantic_count,
            "unmapped_semantic_source_id_count": semantic_count - mapped_semantic_count,
            "mapped_semantic_percent": round(100.0 * mapped_semantic_count / semantic_count, 1),
            "confidence_source_id_counts": confidence_counts,
            "provenance_source_id_counts": provenance_counts,
        },
        "dropped_trailing_french_only_player_turns": dropped_trailing_french_only_player_turns,
        "french_slot_reattributions": french_slot_reattributions,
        "mappings": enriched_records,
        "unmapped": unmapped,
    }


# WAIT $00 rolling-window cleanup is presentation-sensitive.  Keep automatic
# repairs restricted to the checkpoint that predates the round-8 partial-block
# review; newly exposed overlaps must be reviewed explicitly before changing
# stock persistence semantics.
# Do not rewrite stock WAIT $00 presentation automatically.  Exact visible
# carry-over after an interactive WAIT is a legitimate rolling-window state,
# not proof of duplicated dialogue.  Any future presentation change must be
# reviewed and implemented explicitly for that event.
DIALOGUE_RUNTIME_VALIDATED_WAIT00_OVERLAP_EVENTS = frozenset()


def _wait00_page_overlap_count(simulation) -> int:
    """Count exact visible-line carry-over after interactive WAIT $00 pauses.

    The stock dialogue box is a rolling three-line window, so WAIT $00 alone
    can leave the suffix of the previous state visible when later text starts.
    For the localized layout this is undesirable only when the *exact same
    rendered line(s)* appear again at the start of the next simulated state.
    Timed waits such as WAIT $04/$08 are deliberately ignored.
    """
    count = 0
    for box in simulation.boxes:
        pages = box.pages
        for index in range(1, len(pages)):
            previous_page = pages[index - 1]
            if previous_page.transition != "WAIT $00":
                continue
            previous = [line.text for line in previous_page.lines]
            current = [line.text for line in pages[index].lines]
            best = 0
            for size in range(1, min(len(previous), len(current), DIALOGUE_PAGE_LINES) + 1):
                overlap = previous[-size:]
                if overlap == current[:size] and any(line.strip() for line in overlap):
                    best = size
            count += best
    return count


def _wait00_repair_variants(event: dict, translations: dict[str, str]):
    """Yield conservative source-WAIT repairs for rolling-window duplicates.

    A candidate is never accepted merely from source shape: the caller must
    reserialize and resimulate it, and keep it only when the exact WAIT $00
    carry-over count decreases with no simulator regression.

    Two stock patterns are handled:
    - WAIT $00 -> later translated prose: clear before that prose;
    - WAIT $00 -> newline-only layout token -> end/close: suppress the orphan
      newline so it cannot create one final repeated rolling-window state.

    Intervening non-layout event commands are preserved in place. If a
    newline-only token exists before later prose, it becomes a clear-only text
    chunk so TEXT_CLEAR occurs at the original layout position.
    """
    tokens = event["tokens"]
    boundaries = {"WAIT", "TEXT_CLEAR", "TEXT_OPEN", "TEXT_CLOSE", "END"}
    for index, token in enumerate(tokens):
        if not (
            token.get("type") == "command"
            and token.get("name") == "WAIT"
            and token.get("args", "").strip().upper() == "00"
        ):
            continue

        layout_ids: list[str] = []
        next_text_id: str | None = None
        blocked = False
        for following in tokens[index + 1:]:
            kind = following.get("type")
            if kind == "command" and following.get("name") in boundaries:
                blocked = True
                break
            if kind != "text":
                continue
            text_id = following["id"]
            source = following.get("source", "")
            value = translations.get(text_id)
            if not source.strip():
                layout_ids.append(text_id)
                continue
            if value is not None and value.strip("\n\v\f "):
                next_text_id = text_id
                break
            # A semantic source token with no local translated bytes means the
            # binding is not simple enough for this layout-only cleanup.
            if _auto_semantic(source):
                blocked = True
                break

        if blocked and not next_text_id and not layout_ids:
            continue

        candidate = dict(translations)
        description: dict[str, object] = {
            "wait_token_index": index,
            "layout_text_ids": list(layout_ids),
            "next_text_id": next_text_id,
        }
        changed = False

        if next_text_id is not None:
            # Remove any newline-only rolling-scroll bytes. When such a token
            # exists, put the clear exactly there; otherwise prefix the next
            # translated prose chunk with the clear-only marker.
            if layout_ids:
                for layout_id in layout_ids:
                    candidate[layout_id] = ""
                candidate[layout_ids[0]] = "\v"
                description["strategy"] = "replace_layout_newline_with_text_clear"
                changed = True
            else:
                value = candidate[next_text_id]
                if not value.startswith("\v"):
                    candidate[next_text_id] = "\v" + value
                    description["strategy"] = "clear_before_next_translated_chunk"
                    changed = True
        elif layout_ids:
            # No later prose before the dialogue boundary: a newline after the
            # pause can only create a trailing rolling-window state. Drop it.
            for layout_id in layout_ids:
                if candidate.get(layout_id) != "":
                    candidate[layout_id] = ""
                    changed = True
            description["strategy"] = "drop_trailing_layout_newline"

        if changed:
            yield candidate, description


# Runtime-validated WAIT semantics: WAIT pauses without advancing the text
# cursor.  Earlier formatter/simulator revisions implicitly treated WAIT as a
# line terminator, so a small set of already-formatted scenes relied on a line
# break that was never serialized.  Materialize those intended boundaries as
# explicit dialogue NEWLINE bytes ($7F) while leaving every WAIT command intact.
#
# These are layout-only repairs: no Android/SNES semantic mapping is changed.
# ``prepend`` places NEWLINE at the start of the following text carrier;
# ``append`` places it at the end of the preceding carrier when the following
# visible object is PLAYER_NAME and there is no text carrier before it.
DIALOGUE_EXPLICIT_POST_WAIT_NEWLINES = {
    "0103": [
        ("C9:265A", "prepend"),
        ("C9:2715", "prepend"),
        ("C9:2715", "append"),
        ("C9:271E", "prepend"),
        ("C9:2723", "prepend"),
        ("C9:2740", "prepend"),
        ("C9:2753", "prepend"),
    ],
    "0106": [
        ("C9:28EB", "prepend"),
        ("C9:2ADB", "prepend"),
    ],
    "0136": [("C9:3E14", "prepend")],
    "0167": [
        ("C9:4C65", "append"),
        ("C9:4D1B", "prepend"),
    ],
    "016D": [("C9:4F84", "prepend")],
    "016E": [("C9:5233", "prepend")],
    "01C3": [("C9:70BF", "prepend")],
    "0228": [
        ("C9:9893", "prepend"),
        ("C9:98AC", "prepend"),
    ],
    "0259": [("C9:A1B3", "prepend")],
    "026A": [("C9:A4E9", "prepend_clear")],
    "055E": [
        ("CA:688A", "prepend"),
        ("CA:68FF", "prepend"),
    ],
    "059B": [("CA:76B2", "prepend")],
}


def _apply_explicit_post_wait_newlines(
    event_id: str,
    translations: dict[str, str],
    *,
    source_text_by_id: dict[str, str],
) -> list[dict]:
    """Materialize reviewed line boundaries after WAIT as literal $7F.

    A missing translation entry normally means "keep stock source bytes". For
    punctuation/layout-only carriers (notably $0103/$0228), create an explicit
    translation from the canonical source text before adding the newline so the
    visible punctuation itself remains byte-equivalent apart from the new $7F.
    """
    repairs: list[dict] = []
    for text_id, mode in DIALOGUE_EXPLICIT_POST_WAIT_NEWLINES.get(event_id, []):
        value = translations.get(text_id)
        if value is None:
            if text_id not in source_text_by_id:
                raise KeyError(f"Unknown post-WAIT newline carrier {text_id}")
            value = source_text_by_id[text_id]
        if mode == "prepend":
            if not value.startswith("\n"):
                value = "\n" + value
        elif mode == "append":
            if not value.endswith("\n"):
                value = value + "\n"
        elif mode == "prepend_clear":
            if not value.startswith("\v"):
                value = "\v" + value.lstrip("\n")
        else:
            raise ValueError(f"Unsupported post-WAIT newline mode {mode!r}")
        translations[text_id] = value
        repairs.append({
            "layout_text_id": text_id,
            "strategy": f"{mode}_explicit_newline_after_wait",
            "validation_status": "batch_test_candidate",
            "reason": "materialize line boundary previously assumed implicitly at WAIT",
        })
    return repairs

def _repair_unique_post_wait_sentence_newline(
    *,
    base_rom: bytes,
    event: dict,
    translations: dict[str, str],
    font,
    simulation,
) -> tuple[dict[str, str], object, list[dict]]:
    """Insert one proven post-WAIT newline for a localized sentence boundary.

    This fallback is intentionally narrower than the reviewed per-event table.
    It runs only after compact formatting when the sole blocking defect is one
    decoded-capacity wrap.  The canonical event must contain an immediate
    ``text -> WAIT $00 -> text`` boundary where both English and localized text
    end/start complete sentence prose, the stock continuation begins with a
    space (there is no stock newline), and exactly one possible leading NEWLINE
    makes the entire event simulator-clean.  WAIT itself is never changed.
    """
    from shared.dialogue_simulator import simulate_event

    blocking = [
        issue for issue in simulation.issues
        if issue.severity in {"error", "warning"}
    ]
    if {issue.code for issue in blocking} != {"IMPLICIT_RUNTIME_WRAP"}:
        return translations, simulation, []
    if not any(issue.code == "WAIT_SAME_LINE_CONTINUATION" for issue in simulation.issues):
        return translations, simulation, []

    tokens = event.get("tokens", [])
    clean_candidates: list[tuple[dict[str, str], object, dict]] = []
    sentence_end = re.compile(r"[.!?…][\"'”’)]*$")
    sentence_start = re.compile(r"[A-ZÀ-ÖØ-ÞŒ]")
    for index in range(1, len(tokens) - 1):
        wait = tokens[index]
        if wait.get("type") != "command" or wait.get("name") != "WAIT" or wait.get("args") != "00":
            continue
        previous = tokens[index - 1]
        following = tokens[index + 1]
        if previous.get("type") != "text" or following.get("type") != "text":
            continue
        previous_id = previous.get("id")
        following_id = following.get("id")
        if previous_id not in translations or following_id not in translations:
            continue
        source_before = previous.get("source", "").rstrip()
        source_after = following.get("source", "")
        if not sentence_end.search(source_before):
            continue
        if not source_after.startswith(" ") or source_after.startswith(("\n", "\v", "\f")):
            continue

        localized_before = translations[previous_id].rstrip(" \n\v\f")
        localized_after = translations[following_id]
        if not sentence_end.search(localized_before):
            continue
        if localized_after.startswith(("\n", "\v", "\f")):
            continue
        visible_after = localized_after.lstrip()
        if not visible_after or sentence_start.match(visible_after) is None:
            continue

        candidate = dict(translations)
        candidate[following_id] = "\n" + localized_after
        candidate_simulation = simulate_event(
            base_rom,
            event,
            candidate,
            font=font,
            player_names={0: "000000000", 1: "000000000", 2: "000000000"},
        )
        candidate_blocking = [
            issue for issue in candidate_simulation.issues
            if issue.severity in {"error", "warning"}
        ]
        candidate_wraps = sum(
            line.implicit_wrap
            for box in candidate_simulation.boxes
            for page in box.pages
            for line in page.lines
        )
        if candidate_blocking or candidate_wraps:
            continue
        clean_candidates.append((
            candidate,
            candidate_simulation,
            {
                "layout_text_id": following_id,
                "previous_text_id": previous_id,
                "strategy": "unique_simulator_clean_sentence_newline_after_wait00",
                "validation_status": "to_review",
                "reason": "localized complete sentences need one explicit line boundary because WAIT does not advance the cursor",
            },
        ))

    if len(clean_candidates) != 1:
        return translations, simulation, []
    candidate, candidate_simulation, repair = clean_candidates[0]
    return candidate, candidate_simulation, [repair]


WAIT00_FRESH_PAGE_CLEAR_TARGETS = {
    "0106": ("C9:2994", "runtime_validated"),
    "00FB": ("C9:2447", "batch_test_candidate"),
    "0134": ("C9:3D03", "batch_test_candidate"),
    "016D": ("C9:4ECF", "batch_test_candidate"),
    "01CA": ("C9:743D", "batch_test_candidate"),
    "029C": ("C9:B1AD", "batch_test_candidate"),
    "03EE": ("C9:F1E5", "batch_test_candidate"),
    "04A1": ("CA:197E", "batch_test_candidate"),
    "04EA": ("CA:4A6B", "batch_test_candidate"),
    "03E9": ("C9:F036", "round18_batch_test_candidate"),
    "055E": ("CA:687A", "round18_batch_test_candidate"),
}


def _apply_targeted_wait00_fresh_page_clear(
    event_id: str, translations: dict[str, str]
) -> list[dict]:
    """Replace only audited newline-only carriers after the $0106 hazard shape.

    $0106/C9:2994 is runtime-validated. The eight round13 targets are the
    original detector batch; newly visible round18 mappings add two more exact
    detector matches ($03E9/$055E), also kept as explicit test candidates. The
    stock WAIT $00 bytes remain untouched and no generic WAIT carry-over rule is
    enabled.
    """
    target = WAIT00_FRESH_PAGE_CLEAR_TARGETS.get(event_id)
    if target is None:
        return []
    layout_id, validation_status = target
    if translations.get(layout_id) == "\v":
        return []
    translations[layout_id] = "\v"
    return [{
        "layout_text_id": layout_id,
        "strategy": "replace_stock_layout_newline_with_text_clear",
        "validation_status": validation_status,
        "reason": "fresh-page boundary for audited WAIT $00 third-line-scroll hazard",
    }]


def _repair_wait00_page_overlaps(
    *,
    base_rom: bytes,
    event: dict,
    translations: dict[str, str],
    font,
):
    """Greedily keep only simulator-proven reductions of WAIT $00 overlap."""
    from shared.dialogue_simulator import simulate_event

    current = dict(translations)
    simulation = simulate_event(
        base_rom,
        event,
        current,
        font=font,
        player_names={0: "000000000", 1: "000000000", 2: "000000000"},
    )
    repairs: list[dict] = []
    if event.get("event_id") not in DIALOGUE_RUNTIME_VALIDATED_WAIT00_OVERLAP_EVENTS:
        return current, simulation, repairs

    current_overlap = _wait00_page_overlap_count(simulation)
    if not current_overlap:
        return current, simulation, repairs

    # Rebuild candidate variants after every accepted repair because adding a
    # clear can change the simulated page sequence for later WAITs.
    progress = True
    while current_overlap and progress:
        progress = False
        for candidate, description in _wait00_repair_variants(event, current):
            candidate_simulation = simulate_event(
                base_rom,
                event,
                candidate,
                font=font,
                player_names={0: "000000000", 1: "000000000", 2: "000000000"},
            )
            blocking = [
                issue
                for issue in candidate_simulation.issues
                if issue.severity in {"error", "warning"}
            ]
            wraps = sum(
                line.implicit_wrap
                for box in candidate_simulation.boxes
                for page in box.pages
                for line in page.lines
            )
            candidate_overlap = _wait00_page_overlap_count(candidate_simulation)
            if blocking or wraps or candidate_overlap >= current_overlap:
                continue
            description = dict(description)
            description["overlap_lines_before"] = current_overlap
            description["overlap_lines_after"] = candidate_overlap
            repairs.append(description)
            current = candidate
            simulation = candidate_simulation
            current_overlap = candidate_overlap
            progress = True
            break

    return current, simulation, repairs


def _repair_live_line_scroll_risk_with_compact_wrap(
    *,
    base_rom: bytes,
    source_document: dict,
    event: dict,
    event_mappings: list[dict],
    translations: dict[str, str],
    reports: list[dict],
    advances: dict[str, int],
    french: dict[int, str],
    font,
    simulation,
):
    """Remove formatter-added line expansion that causes pre-WAIT live scroll.

    Semantic wrapping may split a short multi-sentence Android string even when
    the same official text fits in fewer physical lines.  If that extra aesthetic
    break makes the live dialogue cursor enter line 4 before the next player
    pause, retry mappings one at a time with the compact width-only wrapper.

    This never inserts WAIT/TEXT_CLEAR and never changes semantic mappings.  A
    compact candidate is kept only when independent resimulation strictly
    reduces ``UNPAUSED_LIVE_LINE_SCROLL_RISK`` with no error, warning, or
    implicit wrap.  This is the generalized form of the runtime-observed $0083
    failure where ``Gestahl : Ha ! Imbécile !`` had been expanded from one safe
    line to two and pushed the following utterance through the rolling window.
    """
    from shared.dialogue_simulator import simulate_event

    def risk_count(sim) -> int:
        return sum(issue.code == "UNPAUSED_LIVE_LINE_SCROLL_RISK" for issue in sim.issues)

    original = dict(translations)
    original_reports = list(reports)
    original_simulation = simulation
    if any(
        token.get("type") == "command" and token.get("name") in {"CHOICE_BEGIN", "CHOICE_END"}
        for token in event.get("tokens", [])
    ):
        return original, original_reports, original_simulation, []

    current = dict(translations)
    current_reports = list(reports)
    current_simulation = simulation
    current_risk = risk_count(current_simulation)
    repairs: list[dict] = []
    if not current_risk:
        return current, current_reports, current_simulation, repairs

    progress = True
    while current_risk and progress:
        progress = False
        for mapping in event_mappings:
            if str(mapping.get("relation", "")).startswith("choice"):
                continue
            try:
                compact_values, compact_report = _format_mass_mapping(
                    source_document,
                    mapping,
                    advances,
                    base_rom=base_rom,
                    french=french,
                    prefer_semantic_line_breaks=False,
                )
            except ValueError:
                continue

            matching_report_index = next((
                index for index, report in enumerate(current_reports)
                if report.get("snes_ids") == mapping.get("snes_ids")
                and report.get("android_ids") == mapping.get("android_ids")
            ), None)
            if matching_report_index is None:
                continue
            old_report = current_reports[matching_report_index]
            if compact_report.get("formatted_markup") == old_report.get("formatted_markup"):
                continue

            candidate = dict(current)
            candidate.update(compact_values)
            # Preserve the small set of already audited event-level layout
            # decisions; compacting one mapping must not silently remove them.
            _apply_user_reviewed_fragment_spacing(event["event_id"], candidate)
            _apply_targeted_wait00_fresh_page_clear(event["event_id"], candidate)
            _apply_explicit_post_wait_newlines(
                event["event_id"], candidate,
                source_text_by_id={
                    token["id"]: token.get("source", "")
                    for token in event.get("tokens", [])
                    if token.get("type") == "text"
                },
            )

            try:
                candidate_simulation = simulate_event(
                    base_rom,
                    event,
                    candidate,
                    font=font,
                    player_names={0: "000000000", 1: "000000000", 2: "000000000"},
                )
            except ValueError:
                continue
            blocking = [
                issue for issue in candidate_simulation.issues
                if issue.severity in {"error", "warning"}
            ]
            wraps = sum(
                line.implicit_wrap
                for box in candidate_simulation.boxes
                for page in box.pages
                for line in page.lines
            )
            candidate_risk = risk_count(candidate_simulation)
            if blocking or wraps or candidate_risk >= current_risk:
                continue

            updated_report = dict(compact_report)
            updated_report["live_line_compact_fallback"] = True
            updated_report["live_line_risk_before"] = current_risk
            updated_report["live_line_risk_after"] = candidate_risk
            current_reports[matching_report_index] = updated_report
            repairs.append({
                "snes_ids": mapping.get("snes_ids", []),
                "android_ids": mapping.get("android_ids", []),
                "strategy": "compact_semantic_wrap_to_preserve_pre_wait_window",
                "formatted_markup_before": old_report.get("formatted_markup"),
                "formatted_markup_after": compact_report.get("formatted_markup"),
                "risk_before": current_risk,
                "risk_after": candidate_risk,
            })
            current = candidate
            current_simulation = candidate_simulation
            current_risk = candidate_risk
            progress = True
            break

    # A partial reduction is not enough to justify changing presentation.  If
    # compacting cannot eliminate the complete pre-WAIT live-scroll defect,
    # keep the original event and leave it TO REVIEW.
    if current_risk:
        return original, original_reports, original_simulation, []
    return current, current_reports, current_simulation, repairs


def _repair_pure_unpaused_scroll(
    *,
    base_rom: bytes,
    source_document: dict,
    event: dict,
    event_mappings: list[dict],
    translations: dict[str, str],
    reports: list[dict],
    advances: dict[str, int],
    font,
    simulation,
):
    """Try one semantic extra page when the only failure is four-line scroll.

    Complete events can overflow the rolling three-line window even though
    each Android/SNES mapping is independently within its own line budget.  Do
    not invent a cross-mapping split: only retry one existing mapping with the
    already validated WAIT $00 + TEXT_CLEAR pagination, and only when that
    mapping has a real sentence/semantic boundary.  Keep a candidate solely if
    the independently serialized event resimulates with no errors, warnings or
    implicit wraps.

    This deliberately ignores events that also contain unsupported layout
    commands or runtime wraps; those need separate structural work.
    """
    from shared.dialogue_simulator import simulate_event

    blocking = [
        issue for issue in simulation.issues
        if issue.severity in {"error", "warning"}
    ]
    wraps = sum(
        line.implicit_wrap
        for box in simulation.boxes
        for page in box.pages
        for line in page.lines
    )
    if wraps or not blocking or {issue.code for issue in blocking} != {"UNPAUSED_SCROLL"}:
        return translations, reports, simulation, []

    clean_candidates: list[tuple[tuple[int, int, int], dict, list[dict], object, dict]] = []
    for mapping_index, mapping in enumerate(event_mappings):
        try:
            values, mapping_report = format_dialogue_mapping(
                source_document,
                mapping,
                advances,
                allow_one_extra_page=True,
                use_physical_page_capacity=True,
                prefer_semantic_line_breaks=True,
                force_one_extra_page=True,
            )
        except ValueError:
            continue
        if mapping_report.get("page_break_strategy") not in {
            "semantic_hard_boundary",
            "sentence_boundary",
        }:
            continue

        candidate = dict(translations)
        candidate.update(values)
        candidate_simulation = simulate_event(
            base_rom,
            event,
            candidate,
            font=font,
            player_names={0: "000000000", 1: "000000000", 2: "000000000"},
        )
        candidate_blocking = [
            issue for issue in candidate_simulation.issues
            if issue.severity in {"error", "warning"}
        ]
        candidate_wraps = sum(
            line.implicit_wrap
            for box in candidate_simulation.boxes
            for page in box.pages
            for line in page.lines
        )
        if candidate_blocking or candidate_wraps:
            continue

        content_counts = [
            sum(bool(line.text.strip()) for line in page.lines)
            for box in candidate_simulation.boxes
            for page in box.pages
        ]
        nonempty_counts = [count for count in content_counts if count]
        final_fullness = nonempty_counts[-1] if nonempty_counts else 0
        minimum_fullness = min(nonempty_counts) if nonempty_counts else 0
        # Prefer a fuller final page (avoid a one-line orphan tail), then the
        # best minimum page fill, then the earliest safe mapping boundary.
        score = (final_fullness, minimum_fullness, -mapping_index)

        candidate_reports = [
            mapping_report if report.get("snes_ids") == mapping.get("snes_ids") else report
            for report in reports
        ]
        repair = {
            "snes_ids": list(mapping.get("snes_ids", [])),
            "android_ids": list(mapping.get("android_ids", [])),
            "strategy": mapping_report.get("page_break_strategy"),
            "page_line_counts": mapping_report.get("page_line_counts", []),
        }
        clean_candidates.append(
            (score, candidate, candidate_reports, candidate_simulation, repair)
        )

    if not clean_candidates:
        return translations, reports, simulation, []
    _, candidate, candidate_reports, candidate_simulation, repair = max(
        clean_candidates, key=lambda item: item[0]
    )
    return candidate, candidate_reports, candidate_simulation, [repair]


def _repair_cross_mapping_sentence_overflow(
    *,
    base_rom: bytes,
    source_document: dict,
    event: dict,
    event_mappings: list[dict],
    translations: dict[str, str],
    reports: list[dict],
    advances: dict[str, int],
    font,
    simulation,
):
    """Repair one proven sentence boundary spanning adjacent mappings.

    A few complete Android mappings correspond to consecutive SNES text tokens
    that the runtime concatenates on the same parser line even though the first
    localized mapping ends a complete sentence and the next starts a new one.
    Only handle the narrow failure signature where that concatenation causes an
    implicit parser wrap (soft or decoded-capacity hard wrap) plus a four-line
    unpaused scroll.  The candidate must:

    * begin at an adjacent mapping boundary separated only by proven
      ``OP_32``/``OP_34`` actor actions and ``COMPLETE_ACTIONS``;
    * follow terminal sentence punctuation in the previous localized mapping;
    * add exactly one explicit newline before the next localized mapping;
    * paginate that next mapping only at a proven semantic/sentence boundary;
    * independently resimulate with no errors, warnings, or implicit wraps.

    Unsupported commands or any other simulator defect keep the event excluded.
    """
    from shared.dialogue_simulator import simulate_event

    blocking = [
        issue for issue in simulation.issues
        if issue.severity in {"error", "warning"}
    ]
    codes = {issue.code for issue in blocking}
    if codes not in ({
        "IMPLICIT_RUNTIME_WRAP",
        "UNPAUSED_SCROLL",
    }, {
        "IMPLICIT_RUNTIME_HARD_WRAP",
        "UNPAUSED_SCROLL",
    }):
        return translations, reports, simulation, []

    clean_candidates: list[tuple[tuple[int, int, int], dict, list[dict], object, dict]] = []
    for mapping_index in range(1, len(event_mappings)):
        previous = event_mappings[mapping_index - 1]
        mapping = event_mappings[mapping_index]

        # The validated cross-mapping repair is only safe across the same
        # event-interruption family already proven for `vwf_dialogues`: actor
        # actions followed by COMPLETE_ACTIONS. Do not bridge arbitrary event
        # commands merely because a candidate happens to resimulate.
        by_id, by_event = event_text_index(source_document)
        previous_indexes = [by_id[text_id]["token_index"] for text_id in previous.get("snes_ids", [])]
        mapping_indexes = [by_id[text_id]["token_index"] for text_id in mapping.get("snes_ids", [])]
        if not previous_indexes or not mapping_indexes:
            continue
        previous_last = max(previous_indexes)
        mapping_first = min(mapping_indexes)
        if mapping_first <= previous_last:
            continue
        bridge = event["tokens"][previous_last + 1:mapping_first]
        if not bridge:
            continue
        bridge_names = []
        bridge_safe = True
        for token in bridge:
            if token.get("type") != "command":
                bridge_safe = False
                break
            name = token.get("name")
            if name not in {"OP_32", "OP_34", "COMPLETE_ACTIONS"}:
                bridge_safe = False
                break
            bridge_names.append(name)
        if not bridge_safe or not ({"OP_32", "OP_34"} & set(bridge_names)):
            continue

        previous_text = "".join(
            translations.get(text_id, "") for text_id in previous.get("snes_ids", [])
        ).rstrip(" \n\f\v")
        if not previous_text or previous_text[-1] not in ".!?…":
            continue

        try:
            values, mapping_report = format_dialogue_mapping(
                source_document,
                mapping,
                advances,
                allow_one_extra_page=True,
                use_physical_page_capacity=True,
                prefer_semantic_line_breaks=True,
                force_one_extra_page=True,
            )
        except ValueError:
            continue
        if mapping_report.get("page_break_strategy") not in {
            "semantic_hard_boundary",
            "sentence_boundary",
        }:
            continue

        first_id = next(
            (text_id for text_id in mapping.get("snes_ids", []) if text_id in values),
            None,
        )
        if first_id is None or values[first_id].startswith(("\n", "\f", "\v")):
            continue

        values = dict(values)
        values[first_id] = "\n" + values[first_id]
        candidate = dict(translations)
        candidate.update(values)
        candidate_simulation = simulate_event(
            base_rom,
            event,
            candidate,
            font=font,
            player_names={0: "000000000", 1: "000000000", 2: "000000000"},
        )
        candidate_blocking = [
            issue for issue in candidate_simulation.issues
            if issue.severity in {"error", "warning"}
        ]
        candidate_wraps = sum(
            line.implicit_wrap
            for box in candidate_simulation.boxes
            for page in box.pages
            for line in page.lines
        )
        if candidate_blocking or candidate_wraps:
            continue

        mapping_report = dict(mapping_report)
        mapping_report["formatted_markup"] = "\n" + mapping_report["formatted_markup"]
        mapping_report["inserted_cross_mapping_sentence_break"] = True
        mapping_report["formatted_entries"] = [
            {
                "id": entry["id"],
                "text": values.get(entry["id"], entry["text"]),
            }
            for entry in mapping_report.get("formatted_entries", [])
        ]

        content_counts = [
            sum(bool(line.text.strip()) for line in page.lines)
            for box in candidate_simulation.boxes
            for page in box.pages
        ]
        nonempty_counts = [count for count in content_counts if count]
        final_fullness = nonempty_counts[-1] if nonempty_counts else 0
        minimum_fullness = min(nonempty_counts) if nonempty_counts else 0
        score = (final_fullness, minimum_fullness, -mapping_index)

        candidate_reports = [
            mapping_report if report.get("snes_ids") == mapping.get("snes_ids") else report
            for report in reports
        ]
        repair = {
            "previous_snes_ids": list(previous.get("snes_ids", [])),
            "snes_ids": list(mapping.get("snes_ids", [])),
            "android_ids": list(mapping.get("android_ids", [])),
            "strategy": mapping_report.get("page_break_strategy"),
            "page_line_counts": mapping_report.get("page_line_counts", []),
            "inserted_leading_newline": True,
            "boundary_commands": bridge_names,
        }
        clean_candidates.append(
            (score, candidate, candidate_reports, candidate_simulation, repair)
        )

    if not clean_candidates:
        return translations, reports, simulation, []
    _, candidate, candidate_reports, candidate_simulation, repair = max(
        clean_candidates, key=lambda item: item[0]
    )
    return candidate, candidate_reports, candidate_simulation, [repair]


def _is_safe_text_free_returning_call(base_rom: bytes, token: dict) -> bool:
    """Prove one OP_20..OP_27 call is linear, text-free and returning."""
    name = token.get("name", "")
    match = re.fullmatch(r"OP_2([0-7])", name)
    if match is None:
        return False
    args = token.get("args", "").split()
    if len(args) != 1:
        return False
    target_event_id = (int(match.group(1), 16) << 8) | int(args[0], 16)
    try:
        called = parse_event(base_rom, target_event_id)
    except ValueError:
        return False
    if any(item.get("type") == "text" for item in called.get("tokens", [])):
        return False
    allowed = {"OP_31", "OP_32", "OP_34", "COMPLETE_ACTIONS", "WAIT", "RETURN", "END"}
    names = [
        item.get("name")
        for item in called.get("tokens", [])
        if item.get("type") == "command"
    ]
    if any(item not in allowed for item in names):
        return False
    return len(names) >= 2 and names[-2:] == ["RETURN", "END"]


def _is_safe_sound_only_returning_call(base_rom: bytes, token: dict) -> bool:
    """Prove one OP_20..OP_27 call only plays sound and returns."""
    name = token.get("name", "")
    match = re.fullmatch(r"OP_2([0-7])", name)
    if match is None:
        return False
    args = token.get("args", "").split()
    if len(args) != 1:
        return False
    target_event_id = (int(match.group(1), 16) << 8) | int(args[0], 16)
    try:
        called = parse_event(base_rom, target_event_id)
    except ValueError:
        return False
    if any(item.get("type") == "text" for item in called.get("tokens", [])):
        return False
    names = [
        item.get("name")
        for item in called.get("tokens", [])
        if item.get("type") == "command"
    ]
    return names == ["PLAY_SOUND", "RETURN", "END"]


def _format_mapping_across_sound_effect_action_boundary(
    source_document: dict,
    mapping: dict,
    advances: dict[str, int],
    *,
    base_rom: bytes,
    prefer_semantic_line_breaks: bool,
) -> tuple[dict[str, str], dict]:
    """Split one localized unit across an existing sound/effect action bridge.

    The accepted shape is intentionally tiny: two semantic text carriers with
    exactly ``OP_20..OP_27`` -> ``OP_2D`` -> ``COMPLETE_ACTIONS`` between them.
    The call must independently decode as sound-only + RETURN + END.  Android EN
    and the SNES mapping must contain no dynamic name; Android FR may add exactly
    one comma-delimited ``%S(n,0),`` vocative.  That Android-only vocative is
    dropped because the SNES has no PLAYER_NAME command to carry it.  The
    remaining French is split only at a complete sentence boundary, while every
    stock event command remains byte-for-byte in place.
    """
    snes_ids = mapping.get("snes_ids", [])
    if len(snes_ids) != 2:
        raise ValueError("Sound/effect action boundary requires exactly two SNES text IDs")
    if len(mapping.get("android_ids", [])) != 1:
        raise ValueError("Sound/effect action boundary requires one Android localization unit")
    if "%S(" in mapping.get("source_display", "") or "%S(" in mapping.get("android_english_display", ""):
        raise ValueError("Sound/effect action boundary requires no SNES/Android-EN PLAYER_NAME")

    by_id, by_event = event_text_index(source_document)
    first = by_id.get(snes_ids[0])
    second = by_id.get(snes_ids[1])
    if first is None or second is None or first["event_id"] != second["event_id"]:
        raise ValueError("Sound/effect action boundary references invalid SNES carriers")
    if first["token_index"] >= second["token_index"]:
        raise ValueError("Sound/effect action boundary IDs are not in token order")
    event = by_event[first["event_id"]]
    bridge = event["tokens"][first["token_index"] + 1:second["token_index"]]
    if len(bridge) != 3 or any(token.get("type") != "command" for token in bridge):
        raise ValueError("Sound/effect action boundary requires exactly three bridge commands")
    call, effect, complete = bridge
    if not _is_safe_sound_only_returning_call(base_rom, call):
        raise ValueError("Sound/effect action boundary call is not proven sound-only returning")
    if effect.get("name") != "OP_2D" or len(effect.get("args", "").split()) != 1:
        raise ValueError("Sound/effect action boundary requires one stock OP_2D effect byte")
    if complete.get("name") != "COMPLETE_ACTIONS":
        raise ValueError("Sound/effect action boundary requires COMPLETE_ACTIONS")

    first_source = re.sub(r"\s+", " ", first["source"].strip())
    if not re.search(r"(?:\.{3}|[.!?…])[”\"»')\]]*$", first_source):
        raise ValueError("Sound/effect action boundary requires a complete source sentence before the bridge")

    french = normalize_android_french(mapping.get("french_display", ""))
    vocatives = list(re.finditer(r"%S\((\d+),0\)\s*,\s*", french))
    if len(vocatives) != 1:
        raise ValueError("Sound/effect action boundary requires exactly one Android-only comma vocative")
    vocative = vocatives[0]
    before = french[:vocative.start()].rstrip()
    after = french[vocative.end():].lstrip()
    if not before or not after:
        raise ValueError("Sound/effect action boundary vocative must be internal to localized prose")
    # Once a sentence-initial vocative is removed, capitalize the first cased
    # character of the following clause mechanically; no wording is rewritten.
    if before[-1] in ".!?:…":
        chars = list(after)
        for index, char in enumerate(chars):
            if char.isalpha():
                chars[index] = char.upper()
                break
        after = "".join(chars)
    french_without_vocative = f"{before} {after}".strip()
    if "%S(" in french_without_vocative:
        raise ValueError("Sound/effect action boundary leaves an unsupported PLAYER_NAME")

    boundaries = _sentence_boundary_positions(french_without_vocative)
    candidates = []
    for boundary in boundaries:
        pieces = [
            french_without_vocative[:boundary].strip(),
            french_without_vocative[boundary:].strip(),
        ]
        if any(not piece for piece in pieces):
            continue
        translations: dict[str, str] = {}
        reports: list[dict] = []
        valid = True
        for text_id, piece in zip(snes_ids, pieces, strict=True):
            local = dict(mapping)
            local["snes_ids"] = [text_id]
            local["source_display"] = by_id[text_id]["source"]
            local["french_display"] = piece
            try:
                values, report = format_dialogue_mapping(
                    source_document,
                    local,
                    advances,
                    allow_one_extra_page=True,
                    use_physical_page_capacity=True,
                    prefer_semantic_line_breaks=prefer_semantic_line_breaks,
                    allow_two_extra_pages=True,
                )
            except ValueError:
                valid = False
                break
            if set(values) & set(translations):
                valid = False
                break
            translations.update(values)
            reports.append(report)
        if not valid:
            continue
        line_counts = [sum(report.get("page_line_counts", [])) for report in reports]
        page_breaks = sum(report.get("inserted_page_break_count", 0) for report in reports)
        score = (page_breaks, max(line_counts, default=0), abs(line_counts[0] - line_counts[1]), boundary)
        candidates.append((score, pieces, translations, reports))

    if not candidates:
        raise ValueError("Sound/effect action boundary found no clean sentence distribution")
    _, pieces, translations, reports = min(candidates, key=lambda item: item[0])
    inserted_boundary_newline = False
    # These event-side effect/action commands do not advance the dialogue
    # cursor.  If the two localized pieces would therefore exceed the same-line
    # parser/pixel budget when concatenated, materialize one explicit newline
    # after the proven complete first sentence.  This is the same conservative
    # presentation repair already accepted across OP_32/OP_34 action boundaries.
    combined = pieces[0] + pieces[1]
    if (
        len(combined) > DIALOGUE_WRAP_CHARS
        or _markup_width(combined, advances) > DIALOGUE_WRAP_PIXELS
    ):
        second_id = snes_ids[1]
        if translations[second_id].startswith(("\n", "\f", "\v")):
            raise ValueError("Sound/effect action boundary already begins with layout control")
        translations[second_id] = "\n" + translations[second_id]
        inserted_boundary_newline = True
        second_report = reports[1]
        second_report["formatted_markup"] = "\n" + second_report.get("formatted_markup", "")
        second_report["formatted_entries"] = [
            {
                "id": entry["id"],
                "text": translations.get(entry["id"], entry["text"]),
            }
            for entry in second_report.get("formatted_entries", [])
        ]
    report = {
        "event_id": mapping["event_id"],
        "snes_ids": snes_ids,
        "android_ids": mapping.get("android_ids", []),
        "confidence": mapping.get("confidence"),
        "source_display": mapping.get("source_display", ""),
        "android_french_raw": mapping.get("french_display", ""),
        "android_french_normalized": french,
        "sound_effect_action_sentence_distribution": True,
        "removed_android_only_vocative_player_index": int(vocative.group(1)),
        "inserted_action_boundary_line_break": inserted_boundary_newline,
        "preserved_bridge": [
            {"name": token.get("name"), "args": token.get("args")}
            for token in bridge
        ],
        "sound_call_proof": {"sound_only_returning": True},
        "distributed_french_parts": pieces,
        "sound_effect_action_parts": reports,
        "formatted_entries": [
            {"id": text_id, "text": translations[text_id]}
            for text_id in snes_ids
            if text_id in translations
        ],
    }
    return translations, report


def _format_mapping_across_shake_effect_boundary(
    source_document: dict,
    mapping: dict,
    advances: dict[str, int],
    *,
    base_rom: bytes,
    prefer_semantic_line_breaks: bool,
) -> tuple[dict[str, str], dict]:
    """Split two sentences around the stock timed shake-effect sequence.

    This deliberately recognizes only the exact linear shape already present
    in event $01C3: sound call, vertical-shake effect, timed WAIT, stop-shake
    effect, sound call. The commands are preserved byte-for-byte; only the two
    mapped text slots are formatted independently around the existing effect.
    """
    snes_ids = mapping.get("snes_ids", [])
    if len(snes_ids) != 2:
        raise ValueError("Shake-effect boundary requires exactly two SNES text IDs")
    if "%S(" in mapping.get("source_display", "") or "%S(" in mapping.get("french_display", ""):
        raise ValueError("Shake-effect boundary does not handle PLAYER_NAME")

    by_id, by_event = event_text_index(source_document)
    metas = [by_id.get(text_id) for text_id in snes_ids]
    if any(meta is None for meta in metas):
        raise ValueError("Shake-effect boundary references an unknown SNES text ID")
    assert all(meta is not None for meta in metas)
    if len({meta["event_id"] for meta in metas}) != 1:
        raise ValueError("Shake-effect boundary cannot cross events")
    indexes = [meta["token_index"] for meta in metas]
    if indexes != sorted(indexes):
        raise ValueError("Shake-effect boundary IDs are not in token order")

    event = by_event[metas[0]["event_id"]]
    if any(
        token.get("type") == "command"
        and token.get("name") in {"CHOICE_BEGIN", "CHOICE_OPTION", "CHOICE_END"}
        for token in event["tokens"]
    ):
        raise ValueError("Shake-effect boundary stays disabled in choice events")

    bridge = event["tokens"][indexes[0] + 1:indexes[1]]
    if len(bridge) != 5 or any(token.get("type") != "command" for token in bridge):
        raise ValueError("Shake-effect boundary does not match the proven five-command shape")
    first_call, shake_on, wait, shake_off, second_call = bridge
    if not _is_safe_sound_only_returning_call(base_rom, first_call):
        raise ValueError("Shake-effect boundary first call is not a proven sound-only return")
    if shake_on.get("name") != "OP_2D" or shake_on.get("args") != "02":
        raise ValueError("Shake-effect boundary does not start the proven vertical-shake effect")
    if wait.get("name") != "WAIT" or wait.get("args") in {None, "00"}:
        raise ValueError("Shake-effect boundary requires its existing timed WAIT")
    if shake_off.get("name") != "OP_2D" or shake_off.get("args") != "04":
        raise ValueError("Shake-effect boundary does not stop the proven shake effect")
    if not _is_safe_sound_only_returning_call(base_rom, second_call):
        raise ValueError("Shake-effect boundary second call is not a proven sound-only return")

    def complete_source(text: str) -> bool:
        compact = re.sub(r"\s+", " ", text.strip())
        return re.search(r"(?:\.{3}|[.!?…])[”\"»')\]]*$", compact) is not None

    if not complete_source(by_id[snes_ids[0]]["source"]):
        raise ValueError("Shake-effect boundary requires a complete source sentence before the effect")

    french = normalize_android_french(mapping.get("french_display", ""))
    boundaries = _sentence_boundary_positions(french)
    if not boundaries:
        raise ValueError("Shake-effect boundary requires a complete French sentence boundary")

    candidates = []
    for boundary in boundaries:
        pieces = [french[:boundary].strip(), french[boundary:].strip()]
        if any(not piece for piece in pieces):
            continue
        translations: dict[str, str] = {}
        reports: list[dict] = []
        valid = True
        for text_id, piece in zip(snes_ids, pieces, strict=True):
            local = dict(mapping)
            local["snes_ids"] = [text_id]
            local["source_display"] = by_id[text_id]["source"]
            local["french_display"] = piece
            try:
                values, report = format_dialogue_mapping(
                    source_document,
                    local,
                    advances,
                    allow_one_extra_page=True,
                    use_physical_page_capacity=True,
                    prefer_semantic_line_breaks=prefer_semantic_line_breaks,
                    allow_two_extra_pages=True,
                )
            except ValueError:
                valid = False
                break
            translations.update(values)
            reports.append(report)
        if not valid:
            continue
        line_counts = [sum(report.get("page_line_counts", [])) for report in reports]
        score = (max(line_counts, default=0), abs(line_counts[0] - line_counts[1]), boundary)
        candidates.append((score, pieces, translations, reports))

    if not candidates:
        raise ValueError("Shake-effect boundary found no clean sentence distribution")
    _, pieces, translations, reports = min(candidates, key=lambda item: item[0])
    return translations, {
        "event_id": mapping["event_id"],
        "snes_ids": snes_ids,
        "android_ids": mapping.get("android_ids", []),
        "confidence": mapping.get("confidence"),
        "source_display": mapping.get("source_display", ""),
        "android_french_raw": mapping.get("french_display", ""),
        "android_french_normalized": french,
        "existing_shake_effect_sentence_distribution": True,
        "preserved_wait_arg": wait.get("args"),
        "boundary_proof": [
            {"name": token.get("name"), "args": token.get("args")}
            for token in bridge
        ],
        "distributed_french_parts": pieces,
        "shake_effect_parts": reports,
        "formatted_entries": [
            {"id": text_id, "text": translations[text_id]}
            for text_id in snes_ids
        ],
    }


def _format_reviewed_sequence_block_with_android_extra(
    source_document: dict,
    mapping: dict,
    advances: dict[str, int],
    *,
    french: dict[int, str],
    prefer_semantic_line_breaks: bool,
) -> tuple[dict[str, str], dict]:
    """Rebind the reviewed 4-anchor/3-statement sequence-block shape.

    The reviewed mapping explicitly records an Android-only extra anchor and a
    stock SNES newline carrier. This fallback is intentionally shape-driven:
    four SNES IDs must be ``semantic / layout-only / semantic / semantic``, the
    three intervening command bridges must be exactly WAIT $00, actor action,
    and WAIT $00 + TEXT_CLEAR, and the first French Android unit must be only a
    speaker hesitation. In that proven shape, the first two Android French
    units form the first SNES statement, while units three and four populate
    the remaining two semantic slots. The stock layout-only token is untouched.
    """
    if mapping.get("confidence") != "user_validated":
        raise ValueError("Reviewed sequence-block fallback requires user-validated alignment")
    if mapping.get("relation") != "sequence_block_with_android_extra":
        raise ValueError("Reviewed sequence-block fallback requires its explicit relation")
    snes_ids = mapping.get("snes_ids", [])
    android_ids = mapping.get("android_ids", [])
    if len(snes_ids) != 4 or len(android_ids) != 4:
        raise ValueError("Reviewed sequence-block fallback requires four SNES and Android IDs")
    if "%S(" in mapping.get("source_display", "") or "%S(" in mapping.get("french_display", ""):
        raise ValueError("Reviewed sequence-block fallback does not handle PLAYER_NAME")

    by_id, by_event = event_text_index(source_document)
    metas = [by_id.get(text_id) for text_id in snes_ids]
    if any(meta is None for meta in metas):
        raise ValueError("Reviewed sequence-block fallback references an unknown SNES text ID")
    assert all(meta is not None for meta in metas)
    if len({meta["event_id"] for meta in metas}) != 1:
        raise ValueError("Reviewed sequence-block fallback cannot cross events")
    indexes = [meta["token_index"] for meta in metas]
    if indexes != sorted(indexes):
        raise ValueError("Reviewed sequence-block fallback IDs are not in token order")
    if re.search(r"[A-Za-z0-9À-ÖØ-öø-ÿŒœ]", by_id[snes_ids[1]]["source"]):
        raise ValueError("Reviewed sequence-block fallback middle token must be layout-only")

    event = by_event[metas[0]["event_id"]]
    if any(
        token.get("type") == "command"
        and token.get("name") in {"CHOICE_BEGIN", "CHOICE_OPTION", "CHOICE_END"}
        for token in event["tokens"]
    ):
        raise ValueError("Reviewed sequence-block fallback stays disabled in choice events")

    bridges = [event["tokens"][a + 1:b] for a, b in zip(indexes, indexes[1:])]
    signatures = [
        [(token.get("name"), token.get("args")) for token in bridge]
        for bridge in bridges
    ]
    expected = [
        [("WAIT", "00")],
        [("OP_32", "04 4C"), ("COMPLETE_ACTIONS", None)],
        [("WAIT", "00"), ("TEXT_CLEAR", None)],
    ]
    if signatures != expected:
        raise ValueError("Reviewed sequence-block fallback does not match its proven stock command shape")

    def complete_sentence(text: str) -> bool:
        compact = re.sub(r"\s+", " ", text.strip())
        return re.search(r"(?:\.{3}|[.!?…])[”\"»')\]]*$", compact) is not None

    for text_id in (snes_ids[0], snes_ids[2], snes_ids[3]):
        if not complete_sentence(by_id[text_id]["source"]):
            raise ValueError("Reviewed sequence-block fallback requires complete source statements")

    chunks = [normalize_android_french(french[text_id]) for text_id in android_ids]
    if any(not chunk for chunk in chunks):
        raise ValueError("Reviewed sequence-block fallback requires four non-empty French anchors")
    if re.fullmatch(r"[^:\n]{1,30}\s*:\s*(?:\.{3}|…)", chunks[0]) is None:
        raise ValueError("Reviewed sequence-block fallback requires a speaker-only hesitation first anchor")
    if any(not complete_sentence(chunk) for chunk in chunks[1:]):
        raise ValueError("Reviewed sequence-block fallback requires complete remaining French anchors")

    pieces = [f"{chunks[0]} {chunks[1]}", chunks[2], chunks[3]]
    semantic_ids = [snes_ids[0], snes_ids[2], snes_ids[3]]
    translations: dict[str, str] = {}
    reports: list[dict] = []
    for text_id, piece in zip(semantic_ids, pieces, strict=True):
        local = dict(mapping)
        local["snes_ids"] = [text_id]
        local["source_display"] = by_id[text_id]["source"]
        local["french_display"] = piece
        values, report = format_dialogue_mapping(
            source_document,
            local,
            advances,
            allow_one_extra_page=True,
            use_physical_page_capacity=True,
            prefer_semantic_line_breaks=prefer_semantic_line_breaks,
            allow_two_extra_pages=True,
        )
        translations.update(values)
        reports.append(report)

    return translations, {
        "event_id": mapping["event_id"],
        "snes_ids": snes_ids,
        "android_ids": android_ids,
        "confidence": mapping.get("confidence"),
        "relation": mapping.get("relation"),
        "source_display": mapping.get("source_display", ""),
        "android_french_raw": mapping.get("french_display", ""),
        "reviewed_sequence_block_distribution": True,
        "preserved_stock_carrier_id": snes_ids[1],
        "boundary_proof": signatures,
        "distributed_french_parts": pieces,
        "reviewed_sequence_block_parts": reports,
        "formatted_entries": [
            {"id": text_id, "text": translations[text_id]}
            for text_id in semantic_ids
        ],
    }


def _format_mapping_across_nonsemantic_action_carrier(
    source_document: dict,
    mapping: dict,
    advances: dict[str, int],
    *,
    base_rom: bytes,
    prefer_semantic_line_breaks: bool,
) -> tuple[dict[str, str], dict]:
    """Split two complete localized sentences around one stock layout carrier.

    This is for the narrow three-slot shape ``semantic / layout-only / semantic``.
    The middle source token is preserved stock and untranslated. Boundaries may
    contain only proven actor-action commands plus a clean-ROM call whose callee
    is independently text-free, branch-free and returning. No WAIT, PLAYER_NAME
    or choice command is accepted here.
    """
    snes_ids = mapping.get("snes_ids", [])
    if len(snes_ids) != 3:
        raise ValueError("Nonsemantic-action carrier requires exactly three SNES text IDs")
    if "%S(" in mapping.get("source_display", "") or "%S(" in mapping.get("french_display", ""):
        raise ValueError("Nonsemantic-action carrier does not handle PLAYER_NAME")

    by_id, by_event = event_text_index(source_document)
    metas = [by_id.get(text_id) for text_id in snes_ids]
    if any(meta is None for meta in metas):
        raise ValueError("Nonsemantic-action carrier references an unknown SNES text ID")
    assert all(meta is not None for meta in metas)
    if len({meta["event_id"] for meta in metas}) != 1:
        raise ValueError("Nonsemantic-action carrier cannot cross events")
    indexes = [meta["token_index"] for meta in metas]
    if indexes != sorted(indexes):
        raise ValueError("Nonsemantic-action carrier IDs are not in token order")
    if re.search(r"[A-Za-z0-9À-ÖØ-öø-ÿŒœ]", by_id[snes_ids[1]]["source"]):
        raise ValueError("Nonsemantic-action carrier middle token is semantic text")

    event = by_event[metas[0]["event_id"]]
    if any(
        token.get("type") == "command"
        and token.get("name") in {"CHOICE_BEGIN", "CHOICE_OPTION", "CHOICE_END"}
        for token in event["tokens"]
    ):
        raise ValueError("Nonsemantic-action carrier stays disabled in choice events")

    boundary_proof: list[list[dict]] = []
    saw_action = False
    for first, second in zip(indexes, indexes[1:]):
        bridge = event["tokens"][first + 1:second]
        if not bridge:
            raise ValueError("Nonsemantic-action carrier found an empty command boundary")
        proof: list[dict] = []
        for token in bridge:
            if token.get("type") != "command":
                raise ValueError("Nonsemantic-action carrier crosses non-command event data")
            name = token.get("name")
            if name in {"OP_32", "OP_34", "COMPLETE_ACTIONS"}:
                if name in {"OP_32", "OP_34"}:
                    saw_action = True
                proof.append({"name": name, "args": token.get("args")})
            elif _is_safe_text_free_returning_call(base_rom, token):
                saw_action = True
                proof.append({"name": name, "args": token.get("args"), "text_free_returning_call": True})
            else:
                raise ValueError(f"Nonsemantic-action carrier crosses unsupported command {name!r}")
        boundary_proof.append(proof)
    if not saw_action:
        raise ValueError("Nonsemantic-action carrier requires a proven actor action")

    def complete_source(text: str) -> bool:
        compact = re.sub(r"\s+", " ", text.strip())
        return re.search(r"(?:\.{3}|[.!?…])[”\"»')\]]*$", compact) is not None

    if not complete_source(by_id[snes_ids[0]]["source"]) or not complete_source(by_id[snes_ids[2]]["source"]):
        raise ValueError("Nonsemantic-action carrier requires complete source sentences on both semantic slots")

    french = normalize_android_french(mapping.get("french_display", ""))
    boundaries = _sentence_boundary_positions(french)
    if not boundaries:
        raise ValueError("Nonsemantic-action carrier requires a complete French sentence boundary")

    candidates = []
    for boundary in boundaries:
        pieces = [french[:boundary].strip(), french[boundary:].strip()]
        if any(not piece for piece in pieces):
            continue
        translations: dict[str, str] = {}
        reports: list[dict] = []
        valid = True
        for text_id, piece in zip((snes_ids[0], snes_ids[2]), pieces, strict=True):
            local = dict(mapping)
            local["snes_ids"] = [text_id]
            local["source_display"] = by_id[text_id]["source"]
            local["french_display"] = piece
            try:
                values, report = format_dialogue_mapping(
                    source_document,
                    local,
                    advances,
                    allow_one_extra_page=True,
                    use_physical_page_capacity=True,
                    prefer_semantic_line_breaks=prefer_semantic_line_breaks,
                    allow_two_extra_pages=True,
                )
            except ValueError:
                valid = False
                break
            translations.update(values)
            reports.append(report)
        if not valid:
            continue
        line_counts = [sum(report.get("page_line_counts", [])) for report in reports]
        score = (max(line_counts, default=0), abs(line_counts[0] - line_counts[1]), boundary)
        candidates.append((score, pieces, translations, reports))

    if not candidates:
        raise ValueError("Nonsemantic-action carrier found no clean sentence distribution")
    _, pieces, translations, reports = min(candidates, key=lambda item: item[0])
    report = {
        "event_id": mapping["event_id"],
        "snes_ids": snes_ids,
        "android_ids": mapping.get("android_ids", []),
        "confidence": mapping.get("confidence"),
        "source_display": mapping.get("source_display", ""),
        "android_french_raw": mapping.get("french_display", ""),
        "android_french_normalized": french,
        "nonsemantic_action_carrier_distribution": True,
        "preserved_stock_carrier_id": snes_ids[1],
        "boundary_proof": boundary_proof,
        "distributed_french_parts": pieces,
        "nonsemantic_action_carrier_parts": reports,
        "formatted_entries": [
            {"id": text_id, "text": translations[text_id]}
            for text_id in (snes_ids[0], snes_ids[2])
            if text_id in translations
        ],
    }
    return translations, report

def _strip_duplicated_trailing_player_context(
    event: dict,
    event_mappings: list[dict],
    *,
    base_rom: bytes,
) -> tuple[list[dict], list[dict]]:
    """Drop only a PLAYER_NAME placeholder duplicated by the next mapping.

    The aligner's ``source_display`` may use a dynamic name between two text
    tokens as context for *both* neighboring mappings. When the canonical event
    contains only that PLAYER_NAME command between the two mapped token ranges,
    and both source displays prove the same suffix/prefix placeholder, the first
    mapping may ignore the duplicate context if its French does not contain it.
    The actual SNES PLAYER_NAME remains owned by the following mapping and is
    never edited. A bridge may also contain an event call only when the clean-ROM
    callee is independently proven text-free, branch-free and returning.
    """
    if len(event_mappings) < 2:
        return event_mappings, []
    token_index_by_id = {
        token["id"]: index
        for index, token in enumerate(event.get("tokens", []))
        if token.get("type") == "text"
    }
    ordered = sorted(
        event_mappings,
        key=lambda mapping: min(token_index_by_id[text_id] for text_id in mapping["snes_ids"]),
    )
    result = [dict(mapping) for mapping in ordered]
    repairs: list[dict] = []


    def bridge_player_context(bridge: list[dict]) -> tuple[str, list[dict]] | None:
        placeholders: list[str] = []
        proof: list[dict] = []
        all_player = True
        proved_call = False
        for token in bridge:
            if token.get("type") != "command":
                return None
            name = token.get("name")
            if name == "PLAYER_NAME":
                args = token.get("args", "00").split()
                if not args:
                    return None
                placeholders.append(f"%S({int(args[0], 16)},0)")
                proof.append({"name": name, "args": token.get("args")})
                continue
            all_player = False
            if name in {"WAIT", "TEXT_CLEAR", "OP_32", "OP_34", "COMPLETE_ACTIONS"}:
                proof.append({"name": name, "args": token.get("args")})
            elif _is_safe_text_free_returning_call(base_rom, token):
                proved_call = True
                proof.append({"name": name, "args": token.get("args"), "text_free_returning_call": True})
            else:
                return None
        if not placeholders or (not all_player and not proved_call):
            return None
        return "".join(placeholders), proof

    for index in range(len(result) - 1):
        current = result[index]
        following = result[index + 1]
        current_last = max(token_index_by_id[text_id] for text_id in current["snes_ids"])
        following_first = min(token_index_by_id[text_id] for text_id in following["snes_ids"])
        if following_first <= current_last:
            continue
        bridge = event["tokens"][current_last + 1:following_first]
        if not bridge:
            continue
        bridge_context = bridge_player_context(bridge)
        if bridge_context is None:
            continue
        suffix, bridge_proof = bridge_context
        current_source = current.get("source_display", "")
        following_source = following.get("source_display", "")
        if not current_source.endswith(suffix) or not following_source.startswith(suffix):
            continue
        if current.get("french_display", "").rstrip().endswith(suffix):
            continue
        current["source_display"] = current_source[:-len(suffix)]
        current["ignored_duplicated_trailing_player_context"] = suffix
        repairs.append(
            {
                "snes_ids": current.get("snes_ids", []),
                "following_snes_ids": following.get("snes_ids", []),
                "player_context": suffix,
                "bridge_proof": bridge_proof,
            }
        )
    return result, repairs


def _strip_trailing_player_context_owned_by_reviewed_hole(
    event: dict,
    event_mappings: list[dict],
    *,
    missing_ids: set[str],
    unmapped_by_id: dict[str, dict],
) -> tuple[list[dict], list[dict]]:
    """Return a trailing PLAYER_NAME to the immediately following hole.

    Automatic alignment may borrow a following dynamic name as context for the
    preceding mapped carrier.  In a PARTIEL event, if that PLAYER_NAME belongs
    immediately to an explicitly reviewed unmapped carrier, it must remain with
    the stock-English hole instead of becoming part of the mapped French unit.
    No command or text carrier is moved: only the alignment-only suffix is
    removed from ``source_display`` before formatting.
    """
    token_index_by_id = {
        token["id"]: index
        for index, token in enumerate(event.get("tokens", []))
        if token.get("type") == "text"
    }
    tokens = event.get("tokens", [])
    result: list[dict] = []
    repairs: list[dict] = []
    reviewed_reasons = {"validated_no_equivalent", "validated_android_omission"}

    for original in event_mappings:
        mapping = dict(original)
        snes_ids = mapping.get("snes_ids", [])
        if not snes_ids:
            result.append(mapping)
            continue
        last_index = max(token_index_by_id[text_id] for text_id in snes_ids)
        if last_index + 2 >= len(tokens):
            result.append(mapping)
            continue
        player = tokens[last_index + 1]
        following = tokens[last_index + 2]
        if (
            player.get("type") != "command"
            or player.get("name") != "PLAYER_NAME"
            or following.get("type") != "text"
            or following.get("id") not in missing_ids
        ):
            result.append(mapping)
            continue
        hole = unmapped_by_id.get(following["id"], {})
        if hole.get("reason") not in reviewed_reasons:
            result.append(mapping)
            continue
        args = player.get("args", "00").split()
        if not args:
            result.append(mapping)
            continue
        placeholder = f"%S({int(args[0], 16)},0)"
        source_display = mapping.get("source_display", "")
        french_display = mapping.get("french_display", "")
        if not source_display.endswith(placeholder):
            result.append(mapping)
            continue
        if french_display.rstrip().endswith(placeholder):
            result.append(mapping)
            continue
        mapping["source_display"] = source_display[:-len(placeholder)]
        mapping["ignored_trailing_player_context_owned_by_reviewed_hole"] = placeholder
        repairs.append({
            "snes_ids": list(snes_ids),
            "hole_snes_id": following["id"],
            "player_context": placeholder,
            "hole_reason": hole.get("reason"),
        })
        result.append(mapping)
    return result, repairs


def _format_structurally_reviewed_choice_prompt(
    source_document: dict,
    mapping: dict,
    advances: dict[str, int],
) -> tuple[dict[str, str], dict]:
    """Format one reviewed Android prompt that precedes a stock choice row.

    Android commonly stores prompt and options as separate localization slots,
    while SNES may keep ``prompt + newline + (`` in one token or place ``(``
    in a tiny stock carrier after ``TEXT_X``. Preserve those stock choice-row
    structures rather than treating the parenthesis as translated prose.

    Compact wrapping is used only for this proven prompt/choice relation. A
    two-line prompt keeps the stock third-line choice row. If official French
    needs exactly three lines, a validated WAIT $00 + TEXT_CLEAR is inserted
    after the complete prompt so the selectable row starts on a fresh page.
    """
    if mapping.get("confidence") != "very_high_structural_review":
        raise ValueError("Choice-prompt split requires structural-review confidence")
    if mapping.get("relation") != "choice_prompt_split":
        raise ValueError("Choice-prompt split requires its explicit relation")
    snes_ids = mapping.get("snes_ids", [])
    if len(snes_ids) != 1:
        raise ValueError("Choice-prompt split requires exactly one SNES text ID")

    by_id, by_event = event_text_index(source_document)
    meta = by_id.get(snes_ids[0])
    if meta is None:
        raise ValueError("Choice-prompt split references an unknown SNES text ID")
    source = meta["source"]
    event = by_event[meta["event_id"]]
    token_index = meta["token_index"]

    embedded_match = re.search(r"(\n[ ]*\()$", source)
    shape: str | None = None
    spaces_and_paren = ""
    structural_suffix = None
    if embedded_match is not None:
        if token_index + 1 >= len(event["tokens"]):
            raise ValueError("Embedded choice prompt has no following token")
        following = event["tokens"][token_index + 1]
        if not (following.get("type") == "command" and following.get("name") == "CHOICE_BEGIN"):
            raise ValueError("Embedded choice prompt is not immediately followed by CHOICE_BEGIN")
        shape = "embedded_parenthesis"
        structural_suffix = embedded_match.group(1)
        spaces_and_paren = structural_suffix[1:]
    elif source.endswith("\n"):
        # Proven alternate SNES shape: prompt token, TEXT_X, tiny '(' carrier,
        # CHOICE_BEGIN. The padding byte emitted after a generated page break is
        # harmless because TEXT_X immediately resets the decoded-row position.
        if token_index + 3 < len(event["tokens"]):
            text_x = event["tokens"][token_index + 1]
            carrier = event["tokens"][token_index + 2]
            choice_begin = event["tokens"][token_index + 3]
            if (
                text_x.get("type") == "command"
                and text_x.get("name") == "TEXT_X"
                and carrier.get("type") in {"text", "ending_text"}
                and re.fullmatch(r"[ ]*\(", carrier.get("source", "")) is not None
                and choice_begin.get("type") == "command"
                and choice_begin.get("name") == "CHOICE_BEGIN"
            ):
                shape = "separate_parenthesis_after_text_x"
                structural_suffix = carrier.get("source", "")
    if shape is None:
        raise ValueError("Choice-prompt split does not match a proven stock choice-row shape")

    values, report = format_dialogue_mapping(
        source_document,
        mapping,
        advances,
        allow_one_extra_page=True,
        use_physical_page_capacity=True,
        prefer_semantic_line_breaks=False,
        allow_two_extra_pages=True,
    )
    text_id = snes_ids[0]
    if text_id not in values:
        raise ValueError("Choice-prompt split did not format its SNES text token")
    line_count = len(report.get("line_widths_pixels", []))
    page_line_counts = report.get("page_line_counts", []) or [line_count]
    final_page_lines = page_line_counts[-1]

    if final_page_lines <= 2:
        if shape == "embedded_parenthesis":
            values[text_id] = values[text_id].rstrip("\n") + "\n" + spaces_and_paren
        choice_transition = "stock_newline"
    elif final_page_lines == 3:
        french = normalize_android_french(mapping.get("french_display", "")).rstrip()
        if re.search(r"(?:\.{3}|[.!?…])[”\"»')\]]*$", french) is None:
            raise ValueError("Full choice-prompt page needs a complete sentence before pagination")
        if shape == "embedded_parenthesis":
            values[text_id] = values[text_id].rstrip("\n") + "\f" + spaces_and_paren
        else:
            # A trailing generated page break is deliberate here: the following
            # stock TEXT_X then starts on a genuinely fresh decoded row before
            # the separate '(' carrier is rendered.
            values[text_id] = values[text_id].rstrip("\n") + "\f"
        choice_transition = "WAIT $00 + TEXT_CLEAR"
    else:
        raise ValueError("Choice prompt final page exceeds the three-line physical capacity")

    report = dict(report)
    report["structural_choice_prompt_split"] = True
    report["choice_prompt_stock_shape"] = shape
    report["preserved_choice_opening_suffix"] = structural_suffix
    report["choice_row_transition"] = choice_transition
    report["formatted_markup"] = values[text_id]
    report["formatted_entries"] = [{"id": text_id, "text": values[text_id]}]
    if choice_transition != "stock_newline":
        report["inserted_page_break_count"] = report.get("inserted_page_break_count", 0) + 1
        report["page_break_encoding"] = "WAIT $00 + TEXT_CLEAR"
        report["page_break_strategy"] = "choice_prompt_complete_sentence"
    return values, report


def _format_structurally_reviewed_choice_destination_list(
    source_document: dict,
    mapping: dict,
    advances: dict[str, int],
    *,
    french: dict[int, str],
) -> tuple[dict[str, str], dict]:
    """Rebuild a SNES numbered destination list from split Android labels.

    Some Cannon Travel scripts store ``1:/2:/3:`` and all destination names in
    one SNES text token, while Android stores the three destination labels in
    adjacent localization records.  The numeric prefixes are layout/selection
    structure, not translated prose, so preserve them from the proven SNES
    shape and insert only the Android French labels.
    """
    if mapping.get("confidence") != "very_high_structural_review":
        raise ValueError("Choice destination list requires structural-review confidence")
    if mapping.get("relation") != "choice_destination_list":
        raise ValueError("Choice destination list requires its explicit relation")
    snes_ids = mapping.get("snes_ids", [])
    android_ids = mapping.get("android_ids", [])
    if len(snes_ids) != 1 or len(android_ids) != 3:
        raise ValueError("Choice destination list requires one SNES ID and three Android IDs")

    by_id, _ = event_text_index(source_document)
    meta = by_id.get(snes_ids[0])
    if meta is None:
        raise ValueError("Choice destination list references an unknown SNES text ID")
    source = meta.get("source", "")
    match = re.fullmatch(r"([ ]*)1:.*\n([ ]*)2:.*\n([ ]*)3:.*", source)
    if match is None:
        raise ValueError("Choice destination list does not match the proven 1:/2:/3: SNES shape")

    labels = [normalize_android_french(french[text_id]).strip() for text_id in android_ids]
    if any(not label or "\n" in label or "\f" in label or "\v" in label for label in labels):
        raise ValueError("Choice destination list requires three single-line French labels")
    rebuilt = "\n".join(
        f"{match.group(index)}{index}:{labels[index - 1]}"
        for index in (1, 2, 3)
    )
    lines = rebuilt.split("\n")
    widths = [sum(advances.get(char, 8) for char in line) for line in lines]
    parser_units = [len(line) for line in lines]
    if any(width > DIALOGUE_WRAP_PIXELS for width in widths):
        raise ValueError("Choice destination list exceeds the 216px safe line target")
    if any(units > DIALOGUE_WRAP_CHARS for units in parser_units):
        raise ValueError("Choice destination list exceeds parser line capacity")
    text_id = snes_ids[0]
    values = {text_id: rebuilt}
    report = {
        "event_id": mapping["event_id"],
        "snes_ids": snes_ids,
        "android_ids": android_ids,
        "confidence": mapping.get("confidence"),
        "source_display": source,
        "android_french_raw": " ".join(french[text_id] for text_id in android_ids),
        "android_french_normalized": " ".join(labels),
        "layout_markup_before_wrap": rebuilt,
        "layout_hints": [],
        "formatted_markup": rebuilt,
        "line_widths_pixels": widths,
        "line_decoded_character_counts": parser_units,
        "line_parser_unit_counts": parser_units,
        "leading_text_x_position": None,
        "leading_text_x_padding_pixels": 0,
        "leading_text_x_parser_units": 0,
        "source_visible_line_budget": 3,
        "effective_line_budget": 3,
        "physical_page_capacity_mode": True,
        "semantic_line_break_preferences": False,
        "page_line_counts": [3],
        "inserted_page_break_count": 0,
        "inserted_leading_clear": False,
        "page_break_encoding": None,
        "page_break_strategy": None,
        "event_level_forced_page_break": False,
        "formatted_entries": [{"id": text_id, "text": rebuilt}],
        "structural_choice_destination_list": True,
        "preserved_numeric_prefixes": [f"{match.group(i)}{i}:" for i in (1, 2, 3)],
    }
    return values, report


def _format_cannon_travel_piece(
    source_document: dict,
    mapping: dict,
    advances: dict[str, int],
    french: dict[int, str],
    *,
    prefer_semantic_line_breaks: bool,
) -> tuple[dict[str, str], dict]:
    """Redistribute Android's merged Cannon Travel response over stock SNES slots.

    Android appends the common boarding sentence to each destination response,
    while SNES calls shared sub-event $00FC for that sentence.  Reviewed round20
    mappings therefore format either the response prefix or the common suffix,
    preserving the original event call structure instead of duplicating prose.
    """
    relation = mapping.get("relation")
    if relation not in {"cannon_response_prefix", "cannon_common_boarding_suffix"}:
        raise ValueError("Not a Cannon Travel split relation")
    french_full = normalize_android_french(mapping.get("french_display", "")).strip()
    # Android ID 159 is the reviewed canonical Water Palace response containing
    # the shared Cannon Travel boarding tail. Derive that tail from the current
    # Android FR resource instead of embedding any localized sentence here.
    common_source = french.get(159)
    if common_source is None or "_" not in common_source:
        raise ValueError("Cannon Travel canonical Android FR slot 159 lost its response/tail boundary")
    suffix = normalize_android_french(common_source.split("_", 1)[1]).strip()
    if not suffix or not french_full.endswith(suffix):
        raise ValueError("Cannon Travel response no longer ends with the canonical Android FR shared tail")
    prefix = french_full[:-len(suffix)].rstrip(" _")
    piece = prefix if relation == "cannon_response_prefix" else suffix
    if not piece:
        raise ValueError("Cannon Travel split produced an empty French piece")
    local = dict(mapping)
    local["french_display"] = piece
    values, report = format_dialogue_mapping(
        source_document,
        local,
        advances,
        allow_one_extra_page=True,
        use_physical_page_capacity=True,
        prefer_semantic_line_breaks=prefer_semantic_line_breaks,
        allow_two_extra_pages=True,
    )
    report = dict(report)
    report["structural_cannon_travel_split"] = relation
    report["android_merged_french"] = french_full
    report["distributed_french_piece"] = piece
    return values, report


def _format_wait_player_resegmentation(
    source_document: dict,
    mapping: dict,
    advances: dict[str, int],
    *,
    prefer_semantic_line_breaks: bool,
) -> tuple[dict[str, str], dict]:
    """Redistribute one Android turn around stock WAIT + PLAYER_NAME.

    The accepted $0167 structure is text, WAIT $00, PLAYER_NAME(1), text.
    Android 1058/1059 puts localized prose on both sides of that dynamic name.
    Keep both SNES commands byte-for-byte and split only the exact normalized
    Android French at its existing %S(1,0) placeholder.
    """
    if mapping.get("confidence") != "very_high_structural_review":
        raise ValueError("WAIT/PLAYER_NAME resegmentation requires structural-review confidence")
    if mapping.get("relation") != "wait_player_resegmentation":
        raise ValueError("WAIT/PLAYER_NAME resegmentation requires its explicit relation")
    snes_ids = mapping.get("snes_ids", [])
    android_ids = mapping.get("android_ids", [])
    if len(snes_ids) != 2 or len(android_ids) != 2:
        raise ValueError("WAIT/PLAYER_NAME resegmentation requires two SNES and two Android IDs")

    by_id, by_event = event_text_index(source_document)
    first = by_id.get(snes_ids[0])
    second = by_id.get(snes_ids[1])
    if first is None or second is None or first["event_id"] != second["event_id"]:
        raise ValueError("WAIT/PLAYER_NAME resegmentation references invalid SNES carriers")
    if first["event_id"] != mapping.get("event_id"):
        raise ValueError("WAIT/PLAYER_NAME resegmentation crosses events")
    event = by_event[first["event_id"]]
    bridge = event["tokens"][first["token_index"] + 1:second["token_index"]]
    if len(bridge) != 2:
        raise ValueError("WAIT/PLAYER_NAME resegmentation requires exactly two bridge commands")
    wait, player = bridge
    if wait.get("type") != "command" or wait.get("name") != "WAIT" or wait.get("args") != "00":
        raise ValueError("WAIT/PLAYER_NAME resegmentation requires stock WAIT $00")
    if player.get("type") != "command" or player.get("name") != "PLAYER_NAME" or player.get("args") != "01":
        raise ValueError("WAIT/PLAYER_NAME resegmentation requires stock PLAYER_NAME 01")

    french_full = normalize_android_french(mapping.get("french_display", "")).strip()
    placeholder = "%S(1,0)"
    if french_full.count(placeholder) != 1:
        raise ValueError("WAIT/PLAYER_NAME resegmentation requires one Android PLAYER_NAME(1) placeholder")
    before, after = (piece.strip() for piece in french_full.split(placeholder, 1))
    if not before or not after:
        raise ValueError("WAIT/PLAYER_NAME resegmentation requires French prose on both sides of the placeholder")

    translations: dict[str, str] = {}
    reports: list[dict] = []
    for index, (text_id, piece) in enumerate(((snes_ids[0], before), (snes_ids[1], after))):
        local = dict(mapping)
        local["snes_ids"] = [text_id]
        if index == 1:
            # The stock PLAYER_NAME command sits immediately before this carrier.
            # Include it in the formatter model so the 9-character worst-case
            # name consumes both VWF width and one parser-safety unit.
            local["source_display"] = placeholder + by_id[text_id]["source"]
            local["french_display"] = placeholder + piece
        else:
            local["source_display"] = by_id[text_id]["source"]
            local["french_display"] = piece
        values, report = format_dialogue_mapping(
            source_document,
            local,
            advances,
            allow_one_extra_page=True,
            use_physical_page_capacity=True,
            prefer_semantic_line_breaks=prefer_semantic_line_breaks,
            allow_two_extra_pages=True,
        )
        translations.update(values)
        reports.append(report)

    return translations, {
        "event_id": mapping["event_id"],
        "snes_ids": snes_ids,
        "android_ids": android_ids,
        "confidence": mapping.get("confidence"),
        "source_display": mapping.get("source_display", ""),
        "android_french_raw": mapping.get("french_display", ""),
        "android_french_normalized": french_full,
        "structural_wait_player_resegmentation": True,
        "preserved_bridge": [
            {"name": wait.get("name"), "args": wait.get("args")},
            {"name": player.get("name"), "args": player.get("args")},
        ],
        "distributed_french_parts": [before, after],
        "resegmentation_parts": reports,
        "formatted_entries": [
            {"id": text_id, "text": translations[text_id]} for text_id in snes_ids
        ],
    }


def _format_timed_wait10_resegmentation(
    source_document: dict,
    mapping: dict,
    advances: dict[str, int],
    *,
    prefer_semantic_line_breaks: bool,
) -> tuple[dict[str, str], dict]:
    """Redistribute one reviewed Android localization across stock WAIT $10.

    The accepted shape is exactly two semantic SNES text carriers separated by
    one untouched WAIT $10 and one Android-English identity.  French is split
    only at a complete-sentence boundary.  A leading canonical PLAYER_NAME may
    be preserved when the reviewed source/Android unit proves the same dynamic
    speaker.  Cursor movement stays SNES-authoritative: if the second stock
    carrier owns a leading newline, keep it there; otherwise materialize the
    already-established pre-WAIT newline used by $02AE.
    """
    if mapping.get("confidence") != "very_high_structural_review":
        raise ValueError("WAIT $10 resegmentation requires structural-review confidence")
    if mapping.get("relation") != "timed_wait10_resegmentation":
        raise ValueError("WAIT $10 resegmentation requires its explicit relation")
    snes_ids = mapping.get("snes_ids", [])
    android_ids = mapping.get("android_ids", [])
    if len(snes_ids) != 2 or len(android_ids) != 1:
        raise ValueError("WAIT $10 resegmentation requires exactly two SNES carriers and one Android anchor")

    by_id, by_event = event_text_index(source_document)
    first = by_id.get(snes_ids[0])
    second = by_id.get(snes_ids[1])
    if first is None or second is None or first["event_id"] != second["event_id"]:
        raise ValueError("WAIT $10 resegmentation references invalid SNES carriers")
    event = by_event[first["event_id"]]
    bridge = event["tokens"][first["token_index"] + 1:second["token_index"]]
    if len(bridge) != 1:
        raise ValueError("WAIT $10 resegmentation requires one untouched bridge command")
    wait = bridge[0]
    if wait.get("type") != "command" or wait.get("name") != "WAIT" or wait.get("args") != "10":
        raise ValueError("WAIT $10 resegmentation requires the stock WAIT $10")

    french_full = normalize_android_french(mapping.get("french_display", "")).strip()
    if not french_full:
        raise ValueError("WAIT $10 resegmentation requires Android French prose")

    leading_player_index: int | None = None
    leading_player = re.match(r"^%S\((\d+),0\)", french_full)
    if leading_player is not None:
        leading_player_index = int(leading_player.group(1))
        source_display = normalize_android_french(mapping.get("source_display", "")).strip()
        if not source_display.startswith(f"%S({leading_player_index},0)"):
            raise ValueError("WAIT $10 resegmentation PLAYER_NAME differs between source and Android French")
        previous_index = first["token_index"] - 1
        if previous_index < 0:
            raise ValueError("WAIT $10 resegmentation requires canonical leading PLAYER_NAME")
        previous = event["tokens"][previous_index]
        if (
            previous.get("type") != "command"
            or previous.get("name") != "PLAYER_NAME"
            or previous.get("args") != f"{leading_player_index:02X}"
        ):
            raise ValueError("WAIT $10 resegmentation requires canonical leading PLAYER_NAME")
        french_full = french_full[leading_player.end():].lstrip()
    elif "%S(" in french_full:
        raise ValueError("WAIT $10 resegmentation supports only one proven leading PLAYER_NAME")

    boundaries = _sentence_boundary_positions(french_full)
    if not boundaries:
        raise ValueError("WAIT $10 resegmentation requires a complete-sentence split")

    second_owns_leading_newline = by_id[snes_ids[1]]["source"].startswith("\n")

    def sentence_count(text: str) -> int:
        compact = re.sub(r"\s+", " ", text.strip())
        return 0 if not compact else len(_sentence_boundary_positions(compact)) + 1

    source_counts = [sentence_count(by_id[text_id]["source"]) for text_id in snes_ids]
    candidates = []
    for boundary in boundaries:
        pieces = [french_full[:boundary].strip(), french_full[boundary:].strip()]
        if any(not piece for piece in pieces):
            continue
        translations: dict[str, str] = {}
        reports: list[dict] = []
        valid = True
        for part_index, (text_id, piece) in enumerate(zip(snes_ids, pieces, strict=True)):
            local = dict(mapping)
            local["snes_ids"] = [text_id]
            local["source_display"] = by_id[text_id]["source"]
            local["french_display"] = piece
            try:
                values, report = format_dialogue_mapping(
                    source_document,
                    local,
                    advances,
                    allow_one_extra_page=True,
                    use_physical_page_capacity=True,
                    prefer_semantic_line_breaks=False if part_index == 0 else prefer_semantic_line_breaks,
                    allow_two_extra_pages=True,
                )
            except ValueError:
                valid = False
                break
            if part_index == 0:
                first_value = values[text_id].rstrip("\n")
                # WAIT does not move the live cursor. Require the first French
                # piece to fit one physical line.  $02AE owns the newline on
                # the pre-WAIT carrier; $042D owns it on the post-WAIT carrier.
                if "\n" in first_value or "\f" in first_value or "\v" in first_value:
                    valid = False
                    break
                values[text_id] = first_value if second_owns_leading_newline else first_value + "\n"
                report = dict(report)
                report["inserted_pre_wait_newline"] = not second_owns_leading_newline
                report["formatted_markup"] = values[text_id]
                report["formatted_entries"] = [{"id": text_id, "text": values[text_id]}]
            elif second_owns_leading_newline:
                second_value = values[text_id]
                # The generic single-carrier formatter promotes a canonical
                # leading newline here to TRANSLATION_CLEAR because it cannot
                # see the preceding timed WAIT.  In this reviewed two-carrier
                # shape that would invent a page clear.  Restore the exact
                # stock newline ownership instead.
                if second_value.startswith("\v"):
                    second_value = second_value[1:]
                else:
                    second_value = second_value.lstrip("\n")
                if "\f" in second_value or "\v" in second_value:
                    valid = False
                    break
                values[text_id] = "\n" + second_value
                report = dict(report)
                report["preserved_stock_post_wait_newline"] = True
                report["formatted_markup"] = values[text_id]
                report["formatted_entries"] = [{"id": text_id, "text": values[text_id]}]
            translations.update(values)
            reports.append(report)
        if not valid:
            continue
        piece_counts = [sentence_count(piece) for piece in pieces]
        score = (
            sum(abs(a - b) for a, b in zip(source_counts, piece_counts, strict=True)),
            sum(report.get("inserted_page_break_count", 0) for report in reports),
            boundary,
        )
        candidates.append((score, pieces, translations, reports))
    if not candidates:
        raise ValueError("WAIT $10 resegmentation found no clean sentence-boundary layout")

    _score, pieces, translations, reports = min(candidates, key=lambda item: item[0])
    return translations, {
        "event_id": mapping["event_id"],
        "snes_ids": snes_ids,
        "android_ids": android_ids,
        "confidence": mapping.get("confidence"),
        "source_display": mapping.get("source_display", ""),
        "android_french_raw": mapping.get("french_display", ""),
        "android_french_normalized": french_full,
        "structural_timed_wait10_resegmentation": True,
        "preserved_bridge": [{"name": wait.get("name"), "args": wait.get("args")}],
        "preserved_leading_player_name_index": leading_player_index,
        "post_wait_stock_newline_preserved": second_owns_leading_newline,
        "source_sentence_counts": source_counts,
        "distributed_french_parts": pieces,
        "resegmentation_parts": reports,
        "formatted_entries": [
            {"id": text_id, "text": translations[text_id]} for text_id in snes_ids
        ],
    }


def _format_paired_direction_labels(
    source_document: dict,
    mapping: dict,
    advances: dict[str, int],
    *,
    prefer_semantic_line_breaks: bool,
) -> tuple[dict[str, str], dict]:
    """Split one Android ↑/↓ destination row onto two stock SNES carriers."""
    if mapping.get("confidence") != "very_high_structural_review":
        raise ValueError("Paired direction labels require structural-review confidence")
    if mapping.get("relation") != "paired_direction_labels":
        raise ValueError("Paired direction labels require its explicit relation")
    snes_ids = mapping.get("snes_ids", [])
    android_ids = mapping.get("android_ids", [])
    if len(snes_ids) != 2 or len(android_ids) != 1:
        raise ValueError("Paired direction labels require two SNES IDs and one Android anchor")

    by_id, by_event = event_text_index(source_document)
    first = by_id.get(snes_ids[0])
    second = by_id.get(snes_ids[1])
    if first is None or second is None or first["event_id"] != second["event_id"]:
        raise ValueError("Paired direction labels reference invalid SNES carriers")
    event = by_event[first["event_id"]]
    bridge = event["tokens"][first["token_index"] + 1:second["token_index"]]
    if len(bridge) != 4:
        raise ValueError("Paired direction labels require the proven four-token bridge")
    up, layout, text_x, down = bridge
    if up.get("type") != "glyph" or up.get("code") != "D1":
        raise ValueError("Paired direction labels require stock D1 up-arrow glyph")
    if layout.get("type") != "text" or normalize_alignment_text(layout.get("source", "")):
        raise ValueError("Paired direction labels require one newline-only stock carrier")
    if text_x.get("type") != "command" or text_x.get("name") != "TEXT_X" or text_x.get("args") != "05":
        raise ValueError("Paired direction labels require stock TEXT_X 05")
    if down.get("type") != "glyph" or down.get("code") != "D2":
        raise ValueError("Paired direction labels require stock D2 down-arrow glyph")

    french_full = normalize_android_french(mapping.get("french_display", "")).strip()
    match = re.fullmatch(r"(.+?)\s*↑\s*↓\s*(.+)", french_full)
    if match is None:
        raise ValueError("Paired direction labels require one Android ↑/↓ French row")
    labels = [match.group(1).strip(), match.group(2).strip()]
    if any(not label for label in labels):
        raise ValueError("Paired direction labels produced an empty localized label")

    translations: dict[str, str] = {}
    reports: list[dict] = []
    for text_id, label in zip(snes_ids, labels, strict=True):
        local = dict(mapping)
        local["snes_ids"] = [text_id]
        local["source_display"] = by_id[text_id]["source"]
        local["french_display"] = label
        values, report = format_dialogue_mapping(
            source_document,
            local,
            advances,
            allow_one_extra_page=False,
            use_physical_page_capacity=True,
            prefer_semantic_line_breaks=prefer_semantic_line_breaks,
            allow_two_extra_pages=False,
        )
        value = values[text_id].strip()
        # Preserve the stock one-cell glue around the D1/D2 structural glyphs;
        # localized wording itself comes only from Android French.
        if by_id[text_id]["source"].startswith(" "):
            value = " " + value
        if by_id[text_id]["source"].endswith(" "):
            value = value + " "
        translations[text_id] = value
        reports.append(report)

    return translations, {
        "event_id": mapping["event_id"],
        "snes_ids": snes_ids,
        "android_ids": android_ids,
        "confidence": mapping.get("confidence"),
        "source_display": mapping.get("source_display", ""),
        "android_french_raw": mapping.get("french_display", ""),
        "android_french_normalized": french_full,
        "structural_paired_direction_labels": True,
        "preserved_bridge": [
            {"type": up.get("type"), "code": up.get("code")},
            {"type": layout.get("type"), "id": layout.get("id")},
            {"name": text_x.get("name"), "args": text_x.get("args")},
            {"type": down.get("type"), "code": down.get("code")},
        ],
        "distributed_french_parts": labels,
        "direction_label_parts": reports,
        "formatted_entries": [
            {"id": text_id, "text": translations[text_id]} for text_id in snes_ids
        ],
    }


def _format_mapping_across_single_text_x(
    source_document: dict,
    mapping: dict,
    advances: dict[str, int],
    *,
    french: dict[int, str],
    prefer_semantic_line_breaks: bool,
) -> tuple[dict[str, str], dict]:
    """Preserve one stock fresh-line TEXT_X between two semantic carriers.

    This narrow formatter applies only when one Android anchor has exactly one
    explicit localization line break and the canonical SNES source has exactly
    two text carriers separated solely by one TEXT_X.  The first stock carrier
    must already end in NEWLINE, proving that TEXT_X is a fresh-line layout
    command rather than a semantic boundary.  The Android line break therefore
    supplies the two localized pieces while the stock newline/TEXT_X ownership
    stays byte-for-byte unchanged.
    """
    snes_ids = mapping.get("snes_ids", [])
    android_ids = mapping.get("android_ids", [])
    if len(snes_ids) != 2 or len(android_ids) != 1:
        raise ValueError("single TEXT_X distribution requires two SNES carriers and one Android anchor")

    by_id, by_event = event_text_index(source_document)
    first = by_id.get(snes_ids[0])
    second = by_id.get(snes_ids[1])
    if first is None or second is None or first["event_id"] != second["event_id"]:
        raise ValueError("single TEXT_X distribution references invalid SNES carriers")
    if first["event_id"] != mapping.get("event_id"):
        raise ValueError("single TEXT_X distribution crosses events")
    event = by_event[first["event_id"]]
    bridge = event["tokens"][first["token_index"] + 1:second["token_index"]]
    if len(bridge) != 1:
        raise ValueError("single TEXT_X distribution requires exactly one bridge command")
    text_x = bridge[0]
    if text_x.get("type") != "command" or text_x.get("name") != "TEXT_X":
        raise ValueError("single TEXT_X distribution requires stock TEXT_X")
    if not by_id[snes_ids[0]]["source"].endswith("\n"):
        raise ValueError("single TEXT_X distribution requires a stock newline before TEXT_X")

    raw_french = french.get(android_ids[0], "")
    raw_lines = [line for line in raw_french.replace("\r\n", "\n").split("\n") if line.strip()]
    if len(raw_lines) != 2:
        raise ValueError("single TEXT_X distribution requires exactly two non-empty Android-French lines")
    pieces = [normalize_android_french(line).strip() for line in raw_lines]
    if any(not piece or "%S(" in piece for piece in pieces):
        raise ValueError("single TEXT_X distribution requires two plain localized text lines")

    common = {
        "allow_one_extra_page": True,
        "use_physical_page_capacity": True,
        "prefer_semantic_line_breaks": prefer_semantic_line_breaks,
        "allow_two_extra_pages": True,
    }
    translations: dict[str, str] = {}
    reports: list[dict] = []
    for index, (text_id, piece) in enumerate(zip(snes_ids, pieces, strict=True)):
        local = dict(mapping)
        local["snes_ids"] = [text_id]
        local["source_display"] = by_id[text_id]["source"]
        local["french_display"] = piece
        values, report = format_dialogue_mapping(source_document, local, advances, **common)
        value = values[text_id]
        if index == 0:
            stripped = value.rstrip("\n")
            if "\n" in stripped or "\f" in stripped or "\v" in stripped:
                raise ValueError("single TEXT_X distribution first localized line no longer fits one physical line")
            value = stripped + "\n"
            values[text_id] = value
            report = dict(report)
            report["preserved_pre_text_x_newline"] = True
            report["formatted_markup"] = value
            report["formatted_entries"] = [{"id": text_id, "text": value}]
        translations.update(values)
        reports.append(report)

    return translations, {
        "event_id": mapping["event_id"],
        "snes_ids": snes_ids,
        "android_ids": android_ids,
        "confidence": mapping.get("confidence"),
        "source_display": mapping.get("source_display", ""),
        "android_french_raw": raw_french,
        "structural_single_text_x_distribution": True,
        "preserved_bridge": [{"name": "TEXT_X", "args": text_x.get("args")}],
        "distributed_french_parts": pieces,
        "text_x_parts": reports,
        "formatted_entries": [
            {"id": text_id, "text": translations[text_id]} for text_id in snes_ids
        ],
    }

def _partial_layout_deferable_formatter_error(message: str) -> bool:
    """Return whether a proven mapping can safely remain stock in PARTIEL.

    This is intentionally narrower than a generic formatter fallback.  It only
    recognizes cases where serializing Android FR would require crossing a
    command boundary that the canonical binder refuses, would require a
    different PLAYER_NAME command stream, or needs literal text on the opposite
    side of a canonical PLAYER_NAME boundary. Leaving the whole mapped carrier
    untranslated preserves the exact stock SNES bytes and does not weaken the
    semantic mapping.
    """
    return (
        "defer structural binding" in message
        or message.startswith("French PLAYER_NAME sequence ")
        or message.startswith(
            "Localized literal text exists where the SNES stream has no text token around PLAYER_NAME"
        )
        or message == "Translated dialogue page break cannot be trailing"
    )


def _reviewed_partial_layout_defer(
    event_id: str, mapping: dict, message: str
) -> str | None:
    """Return review rationale for one exact PARTIEL layout deferral."""
    if not _partial_layout_deferable_formatter_error(message):
        return None
    key = tuple(mapping.get("snes_ids", []))
    return DIALOGUE_REVIEWED_PARTIAL_LAYOUT_DEFERRALS.get(event_id, {}).get(key)


def _collapse_trailing_page_break_into_stock_transition(
    source_document: dict,
    mapping: dict,
    values: dict[str, str],
    report: dict,
) -> tuple[dict[str, str], dict, list[dict]]:
    """Reuse an immediately following stock WAIT $00 + TEXT_CLEAR.

    A formatter may need a page break after the final word of a translated
    carrier. If the canonical SNES stream already supplies exactly WAIT $00
    followed by TEXT_CLEAR immediately after that carrier, serializing another
    generated ``\f`` would duplicate the transition. Remove only that trailing
    layout marker and let the unchanged stock commands own the page change.
    Printable payload and command order are untouched.
    """
    event = next(
        event for event in source_document["events"]
        if event["event_id"] == mapping["event_id"]
    )
    token_indexes = {
        token.get("id"): index
        for index, token in enumerate(event["tokens"])
        if token.get("type") in {"text", "ending_text"}
    }
    out = dict(values)
    repairs: list[dict] = []
    for text_id, value in list(out.items()):
        if not value.endswith("\f"):
            continue
        index = token_indexes.get(text_id)
        if index is None or index + 2 >= len(event["tokens"]):
            continue
        wait, clear = event["tokens"][index + 1:index + 3]
        if not (
            wait.get("type") == "command" and wait.get("name") == "WAIT"
            and wait.get("args") == "00"
            and clear.get("type") == "command" and clear.get("name") == "TEXT_CLEAR"
        ):
            continue
        out[text_id] = value[:-1]
        repairs.append({
            "strategy": "reuse_immediate_stock_wait00_text_clear",
            "text_id": text_id,
            "semantic_payload_changed": False,
            "stock_commands_preserved": True,
        })
    if not repairs:
        return values, report, []
    updated = dict(report)
    updated["formatted_entries"] = [
        {"id": text_id, "text": out[text_id]}
        for text_id in out
    ]
    updated["trailing_page_break_stock_transition_repairs"] = repairs
    return out, updated, repairs


def _mapping_has_unserializable_trailing_page_break(
    source_document: dict, mapping: dict, values: dict[str, str]
) -> bool:
    """Detect a generated trailing page break outside the two choice-safe shapes.

    ``dialogue_codec`` permits a trailing generated page break only immediately
    before CHOICE_BEGIN, or before TEXT_X + the stock decorative ``(`` carrier +
    CHOICE_BEGIN. Everywhere else it would require inventing/moving a structural
    command. A PARTIEL safe-subset may therefore keep the whole mapping stock.
    """
    trailing_ids = {text_id for text_id, value in values.items() if value.endswith("\f")}
    if not trailing_ids:
        return False
    event_id = mapping["event_id"]
    event = next(
        event for event in source_document["events"]
        if event["event_id"] == event_id
    )
    token_indexes = {
        token.get("id"): index
        for index, token in enumerate(event["tokens"])
        if token.get("type") == "text"
    }
    for text_id in trailing_ids:
        if (event_id, text_id) in TRANSLATION_TRAILING_PAGE_BREAK_ALLOWLIST:
            continue
        index = token_indexes.get(text_id)
        if index is None:
            return True
        tokens = event["tokens"]
        allowed = False
        if index + 1 < len(tokens):
            next_token = tokens[index + 1]
            allowed = (
                next_token.get("type") == "command"
                and next_token.get("name") == "CHOICE_BEGIN"
            )
        if not allowed and index + 3 < len(tokens):
            text_x, carrier, choice_begin = tokens[index + 1:index + 4]
            allowed = (
                text_x.get("type") == "command"
                and text_x.get("name") == "TEXT_X"
                and carrier.get("type") in {"text", "ending_text"}
                and carrier.get("source", "").strip() == "("
                and choice_begin.get("type") == "command"
                and choice_begin.get("name") == "CHOICE_BEGIN"
            )
        if not allowed:
            return True
    return False


def _format_user_validated_stock_english_override(
    source_document: dict, mapping: dict
) -> tuple[dict[str, str], dict]:
    """Preserve exact stock-USA text for a proven Android identity with bad FR.

    This is not an unresolved/manual translation. Android English still proves
    semantic identity; the user has explicitly rejected the corresponding
    Android French localization. The exact canonical USA source string is sent
    through the ordinary `french_dialogues` translation serializer, so existing
    in-place/relocation behavior remains authoritative.
    """
    snes_ids = mapping.get("snes_ids", [])
    android_ids = mapping.get("android_ids", [])
    if len(snes_ids) != 1 or len(android_ids) != 1:
        raise ValueError("stock-English localization override requires one SNES carrier and one Android anchor")
    text_id = snes_ids[0]
    override_key = (mapping.get("event_id"), text_id, android_ids[0])
    reviewed_reason = DIALOGUE_USER_VALIDATED_STOCK_ENGLISH_OVERRIDES.get(override_key)
    if reviewed_reason is None:
        raise ValueError(
            "stock-English localization override is not in the exact user-validated allow-list"
        )
    by_id, _ = event_text_index(source_document)
    meta = by_id.get(text_id)
    if meta is None or meta.get("event_id") != mapping.get("event_id"):
        raise ValueError("stock-English localization override references an invalid SNES carrier")
    value = meta.get("source", "")
    if not value:
        raise ValueError("stock-English localization override requires non-empty USA source text")
    return {text_id: value}, {
        "event_id": mapping["event_id"],
        "snes_ids": [text_id],
        "android_ids": list(android_ids),
        "confidence": mapping.get("confidence"),
        "source_display": mapping.get("source_display", value),
        "android_english_display": mapping.get("android_english_display", ""),
        "android_french_rejected": mapping.get("french_display", ""),
        "user_validated_stock_english_override": True,
        "override_reason": (
            "user-validated Android-FR localization error; preserve exact canonical USA source text "
            "while retaining the proven Android-English identity. " + reviewed_reason
        ),
        "formatted_entries": [{"id": text_id, "text": value}],
    }


def _format_called_prefix_android_merge_suffix(
    source_document: dict,
    mapping: dict,
    advances: dict[str, int],
    *,
    prefer_semantic_line_breaks: bool,
) -> tuple[dict[str, str], dict]:
    """Format the exact $0521 Android merge without duplicating called $04D4.

    The SNES event executes $04D4 first, then renders CA:5CE6 in the same live
    dialogue. Android stores both clauses in one localization record separated
    by its presentation ``_`` marker. Identity is already user-validated; this
    formatter only redistributes the official payload over the proven SNES call
    boundary and is deliberately restricted to this one event/carrier/anchor.
    """
    if mapping.get("confidence") != "very_high_structural_review":
        raise ValueError("called-prefix Android merge requires structural-review confidence")
    if mapping.get("relation") != "called_prefix_android_merge_suffix":
        raise ValueError("called-prefix Android merge requires its explicit relation")
    if (mapping.get("event_id"), tuple(mapping.get("snes_ids", [])), tuple(mapping.get("android_ids", []))) != (
        "0521", ("CA:5CE6",), (2203,)
    ):
        raise ValueError("called-prefix Android merge is outside the exact Round-42 allow-list")

    by_id, by_event = event_text_index(source_document)
    meta = by_id.get("CA:5CE6")
    if meta is None or meta.get("event_id") != "0521":
        raise ValueError("Round-42 $0521 carrier changed")
    event = by_event["0521"]
    index = meta["token_index"]
    if index != 1 or index <= 0:
        raise ValueError("Round-42 $0521 carrier position changed")
    call = event["tokens"][index - 1]
    if call.get("type") != "command" or call.get("name") != "OP_24" or call.get("args") != "D4":
        raise ValueError("Round-42 $0521 no longer calls $04D4 immediately before its carrier")

    called = by_event.get("04D4")
    if called is None:
        raise ValueError("Round-42 called event $04D4 missing from canonical source")
    called_texts = [
        token for token in called.get("tokens", [])
        if token.get("type") == "text"
    ]
    if len(called_texts) != 1 or called_texts[0].get("id") != "CA:281B":
        raise ValueError("Round-42 $04D4 text shape changed")
    called_source = called_texts[0].get("source", "")
    local_source = meta.get("source", "")
    if normalize_alignment_text(called_source + " " + local_source) != normalize_alignment_text(
        mapping.get("android_english_display", "")
    ):
        raise ValueError("Round-42 $0521 called-prefix English identity no longer reproduces Android EN")

    french_raw = mapping.get("french_display", "")
    if french_raw.count("_") != 1:
        raise ValueError("Round-42 $0521 Android FR no longer has the single proven merge separator")
    _prefix, suffix = french_raw.split("_", 1)
    if not _prefix.strip() or not suffix.strip():
        raise ValueError("Round-42 $0521 Android FR merge has an empty side")

    local_mapping = dict(mapping)
    local_mapping["french_display"] = suffix.strip()
    values, report = format_dialogue_mapping(
        source_document,
        local_mapping,
        advances,
        allow_one_extra_page=True,
        use_physical_page_capacity=True,
        prefer_semantic_line_breaks=prefer_semantic_line_breaks,
        allow_two_extra_pages=True,
    )
    report = dict(report)
    report["called_prefix_android_merge_suffix"] = True
    report["called_event_id"] = "04D4"
    report["called_prefix_snes_id"] = "CA:281B"
    report["android_french_prefix_not_serialized_here"] = _prefix.strip()
    report["android_french_suffix_serialized_here"] = suffix.strip()
    return values, report


def _format_android_system_chest(
    source_document: dict,
    mapping: dict,
    advances: dict[str, int],
    *,
    prefer_semantic_line_breaks: bool,
) -> tuple[dict[str, str], dict]:
    """Serialize reviewed chest messages directly from Android text resources."""
    if mapping.get("confidence") != "very_high_structural_review":
        raise ValueError("Round-46 chest mapping requires structural-review confidence")
    relation = mapping.get("relation")
    namespace = mapping.get("android_namespace", "scrtxt")
    if relation == "round46_systxt_chest_money" and namespace != "systxt":
        raise ValueError("money chest identity must remain in systxt")
    if relation == "round46_systxt_chest_localization_override" and namespace != "scrtxt":
        raise ValueError("item chest identity must remain in scrtxt")
    event_id = str(mapping.get("event_id"))
    snes_ids = tuple(mapping.get("snes_ids", []))
    android_ids = tuple(mapping.get("android_ids", []))
    if len(snes_ids) != 1 or len(android_ids) != 1:
        raise ValueError("reviewed chest mapping requires one SNES carrier and one Android anchor")
    text_id = snes_ids[0]
    by_id, by_event = event_text_index(source_document)
    if by_id.get(text_id, {}).get("event_id") != event_id:
        raise ValueError("reviewed chest mapping references an invalid SNES carrier")

    # Only structural parameters are allow-listed here. Localized prose comes
    # exclusively from the mapped Android slot at runtime.
    reviewed = {
        ("067E", "CA:8E72", 101254): ("OP_36", "E8 03", "1000"),
        ("067F", "CA:8E8F", 101254): ("OP_36", "32 00", "50"),
        ("0687", "CA:8EEF", 469): ("OP_1E", "46", None),
        ("0689", "CA:8F20", 769): ("OP_1E", "A4", None),
    }
    key = (event_id, text_id, int(android_ids[0]))
    spec = reviewed.get(key)
    if spec is None:
        raise ValueError("reviewed chest mapping is outside the structural allow-list")
    command_name, command_args, amount = spec
    if not any(
        token.get("type") == "command"
        and token.get("name") == command_name
        and token.get("args") == command_args
        for token in by_event[event_id]["tokens"]
    ):
        raise ValueError(f"reviewed chest command changed for ${event_id}")

    localized = normalize_android_french(mapping.get("french_display", "")).strip()
    if amount is not None:
        if localized.count("$0d") != 1:
            raise ValueError(f"money chest Android template changed for ${event_id}")
        localized = localized.replace("$0d", amount)

    local_mapping = dict(mapping)
    local_mapping["french_display"] = localized
    values, report = format_dialogue_mapping(
        source_document,
        local_mapping,
        advances,
        allow_one_extra_page=True,
        use_physical_page_capacity=True,
        prefer_semantic_line_breaks=prefer_semantic_line_breaks,
        allow_two_extra_pages=True,
    )
    report = dict(report)
    report["android_namespace"] = namespace
    report["round46_system_chest"] = True
    report["round46_relation"] = relation
    report["system_template_parameter"] = amount
    report["android_french_raw"] = mapping.get("french_display", "")
    report["android_french_materialized"] = localized
    return values, report


# Exact Android-FR-only vocatives reviewed as localization embellishments.
# The allow-list stores only structural identities and a removal policy; the
# localized sentence itself is always derived from the current Android FR slot.
DIALOGUE_ANDROID_ONLY_VOCATIVE_POLICIES = {
    ("0119", "C9:37AF", 109): "comma_before",
    ("0127", "C9:3AC3", 914): "comma_before",
    ("01B5", "C9:68BA", 574): "placeholder_bang",
    ("0227", "C9:9827", 218): "comma_before",
    ("0295", "C9:AF50", 1518): "placeholder_before_bang",
    ("04E6", "CA:40AF", 87): "comma_before",
    ("04E7", "CA:4126", 91): "leading",
}


def _remove_android_only_vocative(text: str, policy: str) -> str:
    if text.count("%S(") != 1:
        raise ValueError("reviewed Android-only vocative no longer has exactly one placeholder")
    if policy == "comma_before":
        result, count = re.subn(r",\s*%S\(\d+,0\)", "", text, count=1)
    elif policy == "placeholder_bang":
        result, count = re.subn(r"\s*%S\(\d+,0\)\s*!\s*", " ", text, count=1)
    elif policy == "placeholder_before_bang":
        result, count = re.subn(r"\s*%S\(\d+,0\)\s*(?=!)", " ", text, count=1)
    elif policy == "leading":
        result, count = re.subn(r"^%S\(\d+,0\),\s*", "", text, count=1)
        if count and result:
            result = result[:1].upper() + result[1:]
    else:
        raise ValueError(f"unknown Android-only vocative policy {policy!r}")
    if count != 1 or "%S(" in result:
        raise ValueError("reviewed Android-only vocative removal no longer matches Android FR")
    return result.strip()


def _format_without_android_only_vocative(source_document: dict, mapping: dict) -> tuple[dict, dict | None]:
    snes_ids = tuple(mapping.get("snes_ids", []))
    android_ids = tuple(mapping.get("android_ids", []))
    if len(snes_ids) != 1 or len(android_ids) != 1:
        return mapping, None
    key = (mapping.get("event_id"), snes_ids[0], android_ids[0])
    policy = DIALOGUE_ANDROID_ONLY_VOCATIVE_POLICIES.get(key)
    if policy is None:
        return mapping, None
    if mapping.get("android_namespace", "scrtxt") != "scrtxt":
        raise ValueError("Android-only vocative review requires scrtxt identity")
    by_id, _ = event_text_index(source_document)
    if by_id.get(snes_ids[0], {}).get("event_id") != key[0]:
        raise ValueError("Android-only vocative review references an invalid SNES carrier")
    actual_en = normalize_android_prose(mapping.get("android_english_display", "")).strip()
    if "%S(" in actual_en:
        raise ValueError(f"Android-only vocative ${key[0]} unexpectedly exists in Android EN")
    actual_fr = normalize_android_french(mapping.get("french_display", "")).strip()
    localized = _remove_android_only_vocative(actual_fr, policy)
    reviewed = dict(mapping)
    reviewed["french_display"] = localized
    reviewed["identity_french_display"] = localized
    repair = {
        "event_id": key[0], "snes_id": snes_ids[0], "android_id": android_ids[0],
        "strategy": f"remove_android_fr_only_vocative:{policy}",
        "android_identity_unchanged": True, "snes_player_name_commands_unchanged": True,
        "localized": localized,
    }
    reviewed["round48_android_only_vocative_repair"] = repair
    return reviewed, repair


# Round 49 exact formatter-only recoveries. These do not change Android-English
# identity and are intentionally event-specific: one Android-FR-only speaker
# label can be removed where the SNES event has no PLAYER_NAME command at all,
# and one three-part machine-noise line can be distributed across its exact
# stock PLAY_SOUND/WAIT bridge without moving or inventing commands.
DIALOGUE_ANDROID_ONLY_SPEAKER_LABEL_KEYS = {
    ("02CD", "C9:BE42", (1735, 1736)),
}


def _format_without_android_only_speaker_label(
    source_document: dict, mapping: dict
) -> tuple[dict, dict | None]:
    snes_ids = tuple(mapping.get("snes_ids", []))
    android_ids = tuple(mapping.get("android_ids", []))
    if len(snes_ids) != 1:
        return mapping, None
    key = (mapping.get("event_id"), snes_ids[0], android_ids)
    if key not in DIALOGUE_ANDROID_ONLY_SPEAKER_LABEL_KEYS:
        return mapping, None
    if mapping.get("android_namespace", "scrtxt") != "scrtxt":
        raise ValueError("Android-only speaker-label review requires scrtxt identity")
    by_id, by_event = event_text_index(source_document)
    if by_id.get(snes_ids[0], {}).get("event_id") != key[0]:
        raise ValueError("Android-only speaker-label carrier moved")
    if any(t.get("type") == "command" and t.get("name") == "PLAYER_NAME" for t in by_event[key[0]].get("tokens", [])):
        raise ValueError("Android-only speaker-label event unexpectedly gained PLAYER_NAME")
    actual_en = normalize_android_prose(mapping.get("android_english_display", "")).strip()
    if "%S(" in actual_en:
        raise ValueError("Android-only speaker label unexpectedly exists in Android EN")
    actual_fr = normalize_android_french(mapping.get("french_display", "")).strip()
    # Remove the single Android-only dynamic label plus the surrounding French
    # colon/spaces; capitalize only when the placeholder was sentence-initial.
    localized, count = re.subn(r"\s*%S\(\d+,0\)\s*:\s*", " ", actual_fr, count=1)
    if count != 1 or "%S(" in localized:
        raise ValueError("Android-only speaker-label shape changed")
    localized = re.sub(r"\s+", " ", localized).strip()
    reviewed = dict(mapping)
    reviewed["french_display"] = localized
    reviewed["identity_french_display"] = localized
    repair = {
        "event_id": key[0], "snes_id": snes_ids[0], "android_ids": list(android_ids),
        "strategy": "remove_android_fr_only_speaker_label",
        "android_identity_unchanged": True, "snes_player_name_commands_unchanged": True,
        "localized": localized,
    }
    reviewed["round49_android_only_speaker_label_repair"] = repair
    return reviewed, repair


# Round 54 exact recoveries from already-proven Android identities. These are
# event-specific serialization rules only; no generic matcher/formatter is widened.

DIALOGUE_ANDROID_FR_OMISSION_PARTIALS = {
    "013A": ("C9:40D7",),
}

def _apply_reviewed_scene_redistributions(
    event: dict,
    translations: dict[str, str],
    *,
    english: dict[int, str],
    redistribution_values: dict[str, dict[str, str]],
    layout_deferred_ids: list[str],
    missing_ids: list[str],
) -> tuple[list[dict], set[str]]:
    """Apply exact Round-67 user-reviewed cross-carrier scene layouts.

    These are presentation redistributions only. They do not create new Android
    identity. The $04E1 block uses Android FR 3252-3257 across the three
    surviving SNES carriers after the already validated CA:2C84 page suppression.
    The $04E2 reaction deliberately redistributes Android FR 1281 across two SNES
    carriers; translated-only command metadata rebinds both pieces to PLAYER_NAME(2)
    and omits Android FR 1280 per explicit user instruction.
    """
    event_id = event.get("event_id")
    reports: list[dict] = []
    resolved_missing: set[str] = set()

    if event_id == "04E1":
        expected_en_ids = {3252, 3253, 3254, 3255, 3256, 3257}
        if any(not english.get(i, "").strip() for i in expected_en_ids):
            raise ValueError("Round-67 $04E1 Android-English scene anchors changed")
        tokens = event.get("tokens", [])
        ids = [t.get("id") for t in tokens if t.get("type") == "text"]
        for required in ("CA:2BED", "CA:2C3A", "CA:2C84", "CA:2C93"):
            if required not in ids:
                raise ValueError(f"Round-67 $04E1 carrier {required} moved")
        if translations.get("CA:2C84") != "":
            raise ValueError("Round-67 $04E1 requires the validated empty CA:2C84 suppression")

        recipe_values = redistribution_values.get("04E1")
        if recipe_values is None:
            raise ValueError("Round-67 $04E1 Android-FR redistribution recipe missing")
        if recipe_values.get("CA:2C84") != "":
            raise ValueError("Round-67 $04E1 recipe must preserve the CA:2C84 suppression")
        values = {
            text_id: recipe_values[text_id]
            for text_id in ("CA:2BED", "CA:2C3A", "CA:2C93")
        }
        for text_id, value in values.items():
            if text_id in translations and translations[text_id] not in {"", value}:
                raise ValueError(f"Round-67 $04E1 would overwrite translated carrier {text_id}")
            translations[text_id] = value
        resolved_missing.update({"CA:2BED", "CA:2C3A"})
        layout_deferred_ids[:] = [x for x in layout_deferred_ids if x != "CA:2C93"]
        reports.append({
            "event_id": "04E1",
            "snes_ids": ["CA:2BED", "CA:2C3A", "CA:2C93"],
            "android_ids": [3252, 3253, 3254, 3255, 3256, 3257],
            "confidence": "user_reviewed_scene_redistribution",
            "semantic_alignment_count_changed": False,
            "stock_player_name_commands_unchanged": True,
            "round67_user_reviewed_scene_redistribution": True,
            "source": "mappings/android/dialogues_redistribution_recipes.json + sources/android/scrtxt_fr.bin",
            "note": (
                "Use the complete official Android-FR Thanatos monologue through token-index "
                "redistribution recipes. CA:2C84 remains the separately validated suppressed page."
            ),
            "formatted_entries": [{"id": k, "text": v} for k, v in values.items()],
        })

    if event_id == "04E2":
        recipe_values = redistribution_values.get("04E2")
        if recipe_values is None:
            raise ValueError("$04E2 Android-FR redistribution recipe missing")
        values = {
            text_id: recipe_values[text_id]
            for text_id in ("CA:32C5", "CA:32D7")
        }
        for text_id, value in values.items():
            translations[text_id] = value
        layout_deferred_ids[:] = [x for x in layout_deferred_ids if x not in {"CA:32C5", "CA:32D7"}]
        reports.append({
            "event_id": "04E2",
            "snes_ids": ["CA:32C5", "CA:32D7"],
            "android_ids": [1280, 1281],
            "confidence": "user_reviewed_speaker_redistribution",
            "semantic_alignment_count_changed": False,
            "translated_player_name_resegmentation": True,
            "android_fr_1280_intentionally_omitted": True,
            "round67_user_reviewed_scene_redistribution": True,
            "source": "mappings/android/dialogues_redistribution_recipes.json + sources/android/scrtxt_fr.bin",
            "note": (
                "User-directed Android-FR 1281 split reproduced from the token-index recipe; "
                "PLAYER_NAME(2) owns both carriers through translated-only command metadata."
            ),
            "formatted_entries": [{"id": k, "text": v} for k, v in values.items()],
        })
    return reports, resolved_missing

def _format_mass_mapping(
    source_document: dict,
    mapping: dict,
    advances: dict[str, int],
    *,
    base_rom: bytes,
    french: dict[int, str],
    prefer_semantic_line_breaks: bool,
) -> tuple[dict[str, str], dict]:
    """Format one mass-pass mapping through the conservative fallback chain.

    The first formatter error remains the public rejection reason when no
    structural fallback applies. Each fallback is independently narrow and
    raises ``ValueError`` when its proof requirements are not met.
    """
    recipe_result = _render_mapping_layout_recipe(mapping, french)
    if recipe_result is not None:
        return recipe_result

    mapping, _round48_vocative_repair = _format_without_android_only_vocative(
        source_document, mapping
    )
    mapping, _round49_speaker_label_repair = _format_without_android_only_speaker_label(
        source_document, mapping
    )
    common = {
        "allow_one_extra_page": True,
        "use_physical_page_capacity": True,
        "prefer_semantic_line_breaks": prefer_semantic_line_breaks,
        "allow_two_extra_pages": True,
    }
    primary_message: str | None = None
    if mapping.get("relation") == "user_validated_stock_english_override":
        return _format_user_validated_stock_english_override(source_document, mapping)
    if mapping.get("relation") == "called_prefix_android_merge_suffix":
        return _format_called_prefix_android_merge_suffix(
            source_document, mapping, advances,
            prefer_semantic_line_breaks=prefer_semantic_line_breaks,
        )
    if mapping.get("relation") in {"round46_systxt_chest_money", "round46_systxt_chest_localization_override"}:
        return _format_android_system_chest(
            source_document, mapping, advances,
            prefer_semantic_line_breaks=prefer_semantic_line_breaks,
        )
    if mapping.get("relation") == "wait_player_resegmentation":
        return _format_wait_player_resegmentation(
            source_document, mapping, advances, prefer_semantic_line_breaks=prefer_semantic_line_breaks
        )
    if mapping.get("relation") == "timed_wait10_resegmentation":
        return _format_timed_wait10_resegmentation(
            source_document, mapping, advances, prefer_semantic_line_breaks=prefer_semantic_line_breaks
        )
    if mapping.get("relation") == "paired_direction_labels":
        return _format_paired_direction_labels(
            source_document, mapping, advances, prefer_semantic_line_breaks=prefer_semantic_line_breaks
        )
    if mapping.get("relation") in {"cannon_response_prefix", "cannon_common_boarding_suffix"}:
        return _format_cannon_travel_piece(
            source_document, mapping, advances, french, prefer_semantic_line_breaks=prefer_semantic_line_breaks
        )
    if mapping.get("relation") == "choice_prompt_split":
        try:
            return _format_structurally_reviewed_choice_prompt(
                source_document, mapping, advances
            )
        except ValueError:
            pass
    if mapping.get("relation") == "choice_destination_list":
        try:
            return _format_structurally_reviewed_choice_destination_list(
                source_document, mapping, advances, french=french
            )
        except ValueError:
            pass
    try:
        return format_dialogue_mapping(source_document, mapping, advances, **common)
    except ValueError as exc:
        primary_message = str(exc)

    attempts = (
        lambda: _format_mapping_across_single_text_x(
            source_document,
            mapping,
            advances,
            french=french,
            prefer_semantic_line_breaks=prefer_semantic_line_breaks,
        ),
        lambda: format_mapping_across_existing_wait_boundaries(
            source_document, mapping, advances, **common
        ),
        lambda: format_mapping_across_existing_timed_wait_boundary(
            source_document, mapping, advances, **common
        ),
        lambda: format_mapping_across_existing_action_boundary(
            source_document, mapping, advances, **common
        ),
        lambda: _format_mapping_across_nonsemantic_action_carrier(
            source_document,
            mapping,
            advances,
            base_rom=base_rom,
            prefer_semantic_line_breaks=prefer_semantic_line_breaks,
        ),
        lambda: _format_mapping_across_sound_effect_action_boundary(
            source_document,
            mapping,
            advances,
            base_rom=base_rom,
            prefer_semantic_line_breaks=prefer_semantic_line_breaks,
        ),
        lambda: _format_mapping_across_shake_effect_boundary(
            source_document,
            mapping,
            advances,
            base_rom=base_rom,
            prefer_semantic_line_breaks=prefer_semantic_line_breaks,
        ),
        lambda: _format_reviewed_sequence_block_with_android_extra(
            source_document,
            mapping,
            advances,
            french=french,
            prefer_semantic_line_breaks=prefer_semantic_line_breaks,
        ),
    )
    for attempt in attempts:
        try:
            return attempt()
        except ValueError:
            continue
    assert primary_message is not None
    raise ValueError(primary_message)


def _repair_structural_reaction_page_boundary(
    *,
    base_rom: bytes,
    source_document: dict,
    event: dict,
    event_mappings: list[dict],
    translations: dict[str, str],
    reports: list[dict],
    advances: dict[str, int],
    font,
    simulation,
):
    """Repair a structurally reattributed crowd reaction before its answer.

    The Joch running gag uses a stock ``OP_20`` speaker/action boundary between
    the crowd reaction and Jehk's answer. Android keeps the same ordered scene
    but reattributes the reaction to a dynamic party member. Prefer preserving
    the stock command flow: keep the reaction on the live line and rewrap the
    following answer with the reaction's VWF width as first-line prefix. Only
    the older page-boundary fallback remains below for already-supported shapes.
    """
    from shared.dialogue_simulator import simulate_event

    blocking = [i for i in simulation.issues if i.severity in {"error", "warning"}]
    codes = {i.code for i in blocking}

    by_id, _ = event_text_index(source_document)
    for index in range(len(event_mappings) - 1):
        reaction = event_mappings[index]
        answer = event_mappings[index + 1]
        if reaction.get("relation") != "speaker_reattribution":
            continue
        if reaction.get("confidence") != "very_high_structural_review":
            continue
        reaction_ids = reaction.get("snes_ids", [])
        answer_ids = answer.get("snes_ids", [])
        if len(reaction_ids) != 1 or len(answer_ids) != 1:
            continue
        first_meta = by_id.get(reaction_ids[0])
        second_meta = by_id.get(answer_ids[0])
        if first_meta is None or second_meta is None:
            continue
        bridge = event["tokens"][first_meta["token_index"] + 1:second_meta["token_index"]]
        if len(bridge) != 1 or bridge[0].get("type") != "command" or bridge[0].get("name") != "OP_20":
            continue
        reaction_text = translations.get(reaction_ids[0], "").rstrip(" \n\f\v")
        answer_text = translations.get(answer_ids[0], "")
        if not reaction_text or not answer_text or "\f" in answer_text or "\v" in answer_text:
            continue
        # A space is presentation-only glue between the two stock text tokens;
        # the OP_20 action command remains exactly where it was in the source.
        reaction_text += " "
        answer_flat = " ".join(answer_text.split())
        try:
            wrapped, _widths, _chars, _units = semantic_wrap_markup(
                answer_flat,
                advances,
                first_line_prefix_pixels=_markup_width(reaction_text, advances, 0),
                first_line_prefix_units=len(reaction_text),
            )
        except ValueError:
            continue
        candidate = dict(translations)
        candidate[reaction_ids[0]] = reaction_text
        candidate[answer_ids[0]] = wrapped
        try:
            candidate_simulation = simulate_event(
                base_rom, event, candidate, font=font,
                player_names={0: "000000000", 1: "000000000", 2: "000000000"},
            )
        except ValueError:
            continue
        candidate_blocking = [
            i for i in candidate_simulation.issues
            if i.severity in {"error", "warning"} or i.code == "UNPAUSED_LIVE_LINE_SCROLL_RISK"
        ]
        candidate_wraps = sum(
            line.implicit_wrap for box in candidate_simulation.boxes
            for page in box.pages for line in page.lines
        )
        if candidate_blocking or candidate_wraps:
            continue
        candidate_reports = []
        for report in reports:
            updated = dict(report)
            if report.get("snes_ids") == reaction_ids:
                updated["formatted_markup"] = candidate[reaction_ids[0]]
                updated["formatted_entries"] = [{"id": reaction_ids[0], "text": candidate[reaction_ids[0]]}]
                updated["speaker_reattribution_live_line_prefix"] = True
            elif report.get("snes_ids") == answer_ids:
                updated["formatted_markup"] = candidate[answer_ids[0]]
                updated["formatted_entries"] = [{"id": answer_ids[0], "text": candidate[answer_ids[0]]}]
                updated["speaker_reattribution_prefix_aware_wrap"] = True
            candidate_reports.append(updated)
        repair = {
            "snes_ids": reaction_ids,
            "following_snes_ids": answer_ids,
            "bridge": [{"name": "OP_20", "args": bridge[0].get("args")}],
            "strategy": "speaker_reattribution_prefix_aware_wrap",
        }
        return candidate, candidate_reports, candidate_simulation, [repair]

    if codes not in (
        {"IMPLICIT_RUNTIME_WRAP"},
        {"IMPLICIT_RUNTIME_HARD_WRAP"},
        {"IMPLICIT_RUNTIME_WRAP", "UNPAUSED_SCROLL"},
        {"IMPLICIT_RUNTIME_HARD_WRAP", "UNPAUSED_SCROLL"},
    ):
        return translations, reports, simulation, []

    for index in range(len(event_mappings) - 1):
        reaction = event_mappings[index]
        answer = event_mappings[index + 1]
        if reaction.get("relation") != "speaker_reattribution":
            continue
        if reaction.get("confidence") != "very_high_structural_review":
            continue
        reaction_ids = reaction.get("snes_ids", [])
        answer_ids = answer.get("snes_ids", [])
        if len(reaction_ids) != 1 or not answer_ids:
            continue
        first_meta = by_id.get(reaction_ids[0])
        second_meta = by_id.get(answer_ids[0])
        if first_meta is None or second_meta is None:
            continue
        bridge = event["tokens"][first_meta["token_index"] + 1:second_meta["token_index"]]
        if len(bridge) != 1 or bridge[0].get("type") != "command" or bridge[0].get("name") != "OP_20":
            continue
        text_id = reaction_ids[0]
        current = translations.get(text_id, "").rstrip(" \n\f\v")
        if not current or re.search(r"(?:\.{3}|[.!?…])[”\"»')\]]*$", current) is None:
            continue
        candidate = dict(translations)
        candidate[text_id] = current + "\f "
        try:
            candidate_simulation = simulate_event(
                base_rom,
                event,
                candidate,
                font=font,
                player_names={0: "000000000", 1: "000000000", 2: "000000000"},
            )
        except ValueError:
            continue
        candidate_blocking = [
            i for i in candidate_simulation.issues if i.severity in {"error", "warning"}
        ]
        candidate_wraps = sum(
            line.implicit_wrap
            for box in candidate_simulation.boxes
            for page in box.pages
            for line in page.lines
        )
        if candidate_blocking or candidate_wraps:
            continue
        candidate_reports = []
        for report in reports:
            if report.get("snes_ids") == reaction_ids:
                updated = dict(report)
                updated["formatted_markup"] = candidate[text_id]
                updated["formatted_entries"] = [{"id": text_id, "text": candidate[text_id]}]
                updated["inserted_structural_reaction_page_break"] = True
                candidate_reports.append(updated)
            else:
                candidate_reports.append(report)
        repair = {
            "snes_ids": reaction_ids,
            "following_snes_ids": answer_ids,
            "bridge": [{"name": "OP_20", "args": bridge[0].get("args")}],
            "strategy": "speaker_reattribution_page_boundary",
        }
        return candidate, candidate_reports, candidate_simulation, [repair]
    return translations, reports, simulation, []


def _sentence_break_positions(text: str) -> list[tuple[int, int]]:
    """Return complete-sentence boundary spans followed by layout whitespace."""
    out = []
    for match in re.finditer(r"(?:\.{3}|[.!?…]+)(?:[”\"»')\]]*)[ \t\r\n]+", text):
        out.append((match.start(), match.end()))
    return out


def _replace_boundary_whitespace_with_page_break(text: str, *, first: bool) -> str | None:
    boundaries = _sentence_break_positions(text)
    if not boundaries:
        return None
    start, end = boundaries[0] if first else boundaries[-1]
    # Keep the sentence punctuation itself; replace only following whitespace.
    punctuation_end = end
    while punctuation_end > start and text[punctuation_end - 1].isspace():
        punctuation_end -= 1
    return text[:punctuation_end] + "\f" + text[end:]


def _apply_0127_reviewed_pagination(event: dict, translations: dict[str, str]) -> list[dict]:
    """Apply the reviewed $0127 page boundaries from generated Android-FR text.

    The repair identifies sentence boundaries in the freshly formatted carriers;
    it does not contain or compare localized prose.
    """
    if event.get("event_id") != "0127":
        return []
    tokens = event.get("tokens", [])
    expected_structure = {
        18: ("command", "TEXT_OPEN", ""), 19: ("command", "PLAYER_NAME", "00"),
        20: ("text", "C9:3A8C", None), 21: ("command", "OP_32", "00 D0"),
        22: ("command", "OP_32", "05 80"), 23: ("text", "C9:3AA1", None),
        24: ("command", "WAIT", "00"), 25: ("command", "TEXT_CLEAR", ""),
        29: ("text", "C9:3AC3", None), 30: ("command", "WAIT", "08"),
        31: ("text", "C9:3AD8", None), 32: ("command", "OP_32", "06 00"),
        33: ("text", "C9:3ADC", None), 34: ("command", "WAIT", "00"),
        35: ("text", "C9:3B01", None), 36: ("command", "OP_32", "05 44"),
        37: ("text", "C9:3B05", None), 38: ("command", "OP_34", "00 A4"),
        39: ("command", "PLAYER_NAME", "00"), 40: ("text", "C9:3B23", None),
    }
    if len(tokens) <= max(expected_structure):
        raise ValueError("$0127 canonical token structure shortened")
    for index, (kind, identity, args) in expected_structure.items():
        token = tokens[index]
        if token.get("type") != kind:
            raise ValueError(f"$0127 token {index} type changed")
        if kind == "text":
            if token.get("id") != identity:
                raise ValueError(f"$0127 token {index} text carrier changed")
        elif token.get("name") != identity or token.get("args", "") != args:
            raise ValueError(f"$0127 token {index} command changed")

    required = ("C9:3A8C", "C9:3ADC", "C9:3B23")
    if not all(text_id in translations for text_id in required):
        return []
    if any("\f" in translations[text_id] for text_id in ("C9:3A8C", "C9:3B23")):
        return []
    first = _replace_boundary_whitespace_with_page_break(translations["C9:3A8C"], first=False)
    last = _replace_boundary_whitespace_with_page_break(translations["C9:3B23"], first=True)
    if first is None or last is None:
        return []
    translations["C9:3A8C"] = first
    if not translations["C9:3ADC"].startswith(TRANSLATION_CLEAR):
        translations["C9:3ADC"] = TRANSLATION_CLEAR + translations["C9:3ADC"]
    translations["C9:3B23"] = last
    return [{
        "strategy": "sentence_boundary_pagination_from_generated_android_fr",
        "event_id": "0127",
        "player_name_commands_unchanged": True,
        "stock_wait08_unchanged": True,
        "added_interactive_wait_count": 2,
        "added_text_clear_only_count": 1,
    }]


def _apply_04e9_reviewed_wait00_clears(event: dict, translations: dict[str, str]) -> list[dict]:
    """Clear exact full-page carriers after existing WAIT $00 commands."""
    if event.get("event_id") != "04E9":
        return []
    tokens = event.get("tokens", [])
    expected_structure = {
        6: ("text", "CA:46F5", None), 7: ("command", "WAIT", "00"),
        8: ("text", "CA:4745", None), 9: ("command", "WAIT", "00"),
        10: ("text", "CA:4797", None), 11: ("command", "WAIT", "00"),
        12: ("text", "CA:47E7", None),
    }
    if len(tokens) <= max(expected_structure):
        raise ValueError("$04E9 canonical token structure shortened")
    for index, (kind, identity, args) in expected_structure.items():
        token = tokens[index]
        if token.get("type") != kind:
            raise ValueError(f"$04E9 token {index} type changed")
        if kind == "text":
            if token.get("id") != identity:
                raise ValueError(f"$04E9 token {index} carrier changed")
        elif token.get("name") != identity or token.get("args", "") != args:
            raise ValueError(f"$04E9 token {index} command changed")
    target_ids = ("CA:4745", "CA:4797")
    if not all(text_id in translations for text_id in target_ids):
        return []
    repairs = []
    for text_id in target_ids:
        if translations[text_id].startswith(TRANSLATION_CLEAR):
            continue
        translations[text_id] = TRANSLATION_CLEAR + translations[text_id]
        repairs.append({
            "text_id": text_id,
            "strategy": "clear_after_existing_wait00_before_full_page_paragraph",
            "existing_wait00_unchanged": True,
            "added_interactive_wait_count": 0,
            "added_text_clear_only_count": 1,
        })
    return repairs


def _apply_01ce_reviewed_choice_page_clear(event: dict, translations: dict[str, str]) -> list[dict]:
    """Start the exact $01CE donation-choice unit on a fresh page.

    Android EN 536/537/538 is the determinate prompt/Yes/No triplet and the
    reviewed Round-50 mapping splits 536/537 at the stock CHOICE_BEGIN.  The
    stock event already has WAIT $00 before a one-byte newline carrier at
    C9:7824; WAIT does not advance the live cursor.  Replace only that empty
    layout carrier with TEXT_CLEAR so the translated three-line prompt starts
    at the top of a fresh page.  Every money/choice command and the existing
    WAIT $00 remain byte-for-byte in their canonical position.
    """
    if event.get("event_id") != "01CE":
        return []

    tokens = event.get("tokens", [])
    expected_structure = {
        82: ("text", "C9:7808", None),
        83: ("command", "WAIT", "00"),
        84: ("text", "C9:7824", None),
        85: ("command", "MONEY_OPEN", ""),
        86: ("command", "MONEY_PRINT", ""),
        87: ("text", "C9:7827", None),
        88: ("command", "CHOICE_BEGIN", ""),
        89: ("command", "CHOICE_OPTION", "04"),
        90: ("text", "C9:7856", None),
        91: ("command", "CHOICE_OPTION", "0B"),
        92: ("text", "C9:785C", None),
        93: ("command", "CHOICE_END", ""),
    }
    if len(tokens) <= max(expected_structure):
        raise ValueError("Round-50 $01CE canonical token structure shortened")
    for index, (kind, identity, args) in expected_structure.items():
        token = tokens[index]
        if token.get("type") != kind:
            raise ValueError(f"Round-50 $01CE token {index} type changed")
        if kind == "text":
            if token.get("id") != identity:
                raise ValueError(f"Round-50 $01CE token {index} carrier changed")
        elif token.get("name") != identity or token.get("args", "") != args:
            raise ValueError(f"Round-50 $01CE token {index} command changed")

    if tokens[84].get("source") != "\n":
        raise ValueError("Round-50 $01CE C9:7824 is no longer the stock newline-only carrier")

    required_translations = {"C9:7808", "C9:7827", "C9:7856", "C9:785C"}
    if not required_translations.issubset(translations):
        return []
    if "C9:7824" in translations:
        raise ValueError("Round-50 $01CE C9:7824 unexpectedly already translated")

    translations["C9:7824"] = TRANSLATION_CLEAR
    return [
        {
            "text_id": "C9:7824",
            "strategy": "exact_newline_only_carrier_to_clear_after_existing_wait00",
            "existing_wait00_unchanged": True,
            "money_commands_unchanged": True,
            "choice_commands_unchanged": True,
            "added_interactive_wait_count": 0,
            "added_text_clear_only_count": 1,
            "android_identity_added": False,
        }
    ]


def _apply_user_reviewed_fragment_spacing(event_id: str, translations: dict[str, str]) -> list[dict]:
    """Repair exact adjacent-fragment spacing reported in the waterfall scene.

    Event $0106 stores one utterance in four consecutive text fragments. Android
    localizes the fragments separately, and generic per-fragment normalization
    removes the two inter-fragment spaces. Add only those literal spaces; no
    command, wait, or semantic boundary is changed.
    """
    if event_id != "0106":
        return []
    repairs: list[dict] = []
    for left_id, right_id in (("C9:28B7", "C9:28C1"), ("C9:28CB", "C9:28D5")):
        left = translations.get(left_id)
        right = translations.get(right_id)
        if left is None or right is None or left.endswith((" ", "\n", "\v", "\f")) or right.startswith((" ", "\n", "\v", "\f")):
            continue
        translations[left_id] = left + " "
        repairs.append({"left_snes_id": left_id, "right_snes_id": right_id, "strategy": "insert_literal_inter_fragment_space"})
    return repairs


def _strip_canonical_choice_decoration(
    event: dict,
    translations: dict[str, str],
) -> tuple[dict[str, str], dict | None]:
    """Remove one stock outer ``( ... )`` decoration pair from a choice row.

    This is a presentation-only fallback.  It never changes CHOICE_BEGIN,
    CHOICE_OPTION, CHOICE_END, or their coordinates.  The opening/closing
    delimiters are removed only when the canonical USA event proves both sides
    of the pair.  If a delimiter lives in an untranslated punctuation-only
    carrier, an explicit empty/layout-only override is emitted rather than
    copying any stock English prose into the French output.
    """
    tokens = event.get("tokens", [])
    begins = [
        index for index, token in enumerate(tokens)
        if token.get("type") == "command" and token.get("name") == "CHOICE_BEGIN"
    ]
    ends = [
        index for index, token in enumerate(tokens)
        if token.get("type") == "command" and token.get("name") == "CHOICE_END"
    ]
    if len(begins) != 1 or len(ends) != 1 or begins[0] >= ends[0]:
        return translations, None
    begin, end = begins[0], ends[0]
    if not any(
        token.get("type") == "command" and token.get("name") == "CHOICE_OPTION"
        for token in tokens[begin + 1:end]
    ):
        return translations, None

    opening_index = begin - 1
    if opening_index < 0 or tokens[opening_index].get("type") not in {"text", "ending_text"}:
        return translations, None
    opening_token = tokens[opening_index]
    opening_source = opening_token.get("source", "")
    opening_source_match = re.search(r"([ \t]*\()$", opening_source)
    if opening_source_match is None:
        return translations, None

    closing_index = end - 1
    while closing_index > begin and tokens[closing_index].get("type") not in {"text", "ending_text"}:
        closing_index -= 1
    if closing_index <= begin:
        return translations, None
    closing_token = tokens[closing_index]
    closing_source = closing_token.get("source", "")
    closing_source_match = re.search(r"([ \t]*\)[ \t]*)$", closing_source)
    if closing_source_match is None:
        return translations, None

    candidate = dict(translations)

    def strip_token_suffix(token: dict, pattern: str) -> tuple[str, str] | None:
        text_id = token["id"]
        if text_id in candidate:
            current = candidate[text_id]
        else:
            # Only a punctuation/layout-only canonical carrier may be overridden
            # without an existing French value.  Never copy visible stock prose.
            source_without_suffix = re.sub(pattern, "", token.get("source", ""))
            if source_without_suffix.strip(" \t\r\n\f\v"):
                return None
            current = token.get("source", "")
        match = re.search(pattern, current)
        if match is None:
            return None
        removed = match.group(1)
        candidate[text_id] = current[:match.start(1)]
        return text_id, removed

    opening = strip_token_suffix(opening_token, r"([ \t]*\()$")
    if opening is None:
        return translations, None
    closing = strip_token_suffix(closing_token, r"([ \t]*\)[ \t]*)$")
    if closing is None:
        return translations, None

    repair = {
        "strategy": "strip_outer_choice_decoration_for_width",
        "opening_text_id": opening[0],
        "closing_text_id": closing[0],
        "removed_opening_suffix": opening[1],
        "removed_closing_suffix": closing[1],
        "choice_commands_unchanged": True,
    }
    return candidate, repair


def _choice_decoration_reports(
    reports: list[dict],
    translations: dict[str, str],
    repair: dict,
) -> list[dict]:
    """Keep mapping reports synchronized with a stripped choice-decoration fallback."""
    changed_ids = {repair["opening_text_id"], repair["closing_text_id"]}
    updated_reports: list[dict] = []
    for report in reports:
        updated = dict(report)
        entries = [dict(entry) for entry in report.get("formatted_entries", [])]
        touched = False
        for entry in entries:
            text_id = entry.get("id")
            if text_id in changed_ids and text_id in translations:
                entry["text"] = translations[text_id]
                touched = True
        if touched:
            updated["formatted_entries"] = entries
            snes_ids = updated.get("snes_ids", [])
            if len(snes_ids) == 1 and snes_ids[0] in translations:
                updated["formatted_markup"] = translations[snes_ids[0]]
            updated["choice_decoration_mode"] = "stripped_for_width"
            terminal_ids = [
                text_id
                for text_id in (updated.get("preserved_choice_terminal_suffix_ids") or [])
                if text_id != repair["closing_text_id"]
            ]
            updated["preserved_choice_terminal_suffix_ids"] = terminal_ids or None
            if updated.get("preserved_choice_opening_suffix") is not None:
                updated["removed_choice_opening_suffix"] = updated["preserved_choice_opening_suffix"]
                updated["preserved_choice_opening_suffix"] = None
        updated_reports.append(updated)
    return updated_reports


def _apply_reviewed_choice_layout_recipe(
    *,
    base_rom: bytes,
    source_document: dict,
    event: dict,
    event_mappings: list[dict],
    translations: dict[str, str],
    reports: list[dict],
    advances: dict[str, int],
    french: dict[int, str],
    font,
    simulation,
    recipe: dict,
) -> tuple[dict[str, str], list[dict], object, list[dict], list[dict], list[dict]]:
    """Reapply one reviewed Round-72 choice presentation decision.

    The recipe contains only canonical event/carrier identities.  No French
    prose is stored here.  If restoring the canonical choice-row newline would
    otherwise force a fresh page, retry only the mapped opening prompt with the
    already-supported compact wrapper before restoring the row.  Finally strip
    the exact canonical outer parentheses and resimulate.  Later CHOICE_OPTION
    anchor repair remains the responsibility of the ordinary generic pass.
    """
    from shared.dialogue_simulator import simulate_event

    event_id = event.get("event_id")
    if recipe.get("event_id") != event_id:
        raise ValueError(f"Reviewed choice-layout recipe/event mismatch: {event_id}")

    original_translations = dict(translations)
    original_reports = [dict(report) for report in reports]

    row_translations, row_reports, row_simulation, row_repairs = (
        _try_restore_stock_choice_row_prefix(
            base_rom=base_rom,
            event=event,
            translations=translations,
            reports=reports,
            font=font,
            simulation=simulation,
        )
    )
    compact_repairs: list[dict] = []

    # A reviewed stripped row needs only the canonical NEWLINE before the first
    # option, not a new page containing an opening parenthesis.  When semantic
    # wrapping made the prompt three lines and therefore forced the helper onto
    # a fresh page, retry that one Android-backed mapping with the compact VWF
    # wrapper.  This is deterministic source reflow, not a text override.
    if row_repairs and any(
        repair.get("strategy") == "restore_stock_choice_row_suffix_on_fresh_page"
        for repair in row_repairs
    ):
        opening_id = recipe["opening_text_id"]
        owner = [mapping for mapping in event_mappings if opening_id in mapping.get("snes_ids", [])]
        if len(owner) == 1:
            mapping = owner[0]
            try:
                compact_values, compact_report = _format_mass_mapping(
                    source_document,
                    mapping,
                    advances,
                    base_rom=base_rom,
                    french=french,
                    prefer_semantic_line_breaks=False,
                )
                compact_values, compact_report, _ = _collapse_trailing_page_break_into_stock_transition(
                    source_document, mapping, compact_values, compact_report
                )
            except ValueError:
                compact_values = {}
                compact_report = None

            if compact_values and compact_report is not None:
                compact_translations = dict(original_translations)
                compact_translations.update(compact_values)
                compact_reports: list[dict] = []
                replaced = False
                for report in original_reports:
                    if (
                        report.get("snes_ids") == mapping.get("snes_ids")
                        and report.get("android_ids") == mapping.get("android_ids")
                    ):
                        compact_reports.append(compact_report)
                        replaced = True
                    else:
                        compact_reports.append(report)
                if replaced:
                    try:
                        compact_simulation = simulate_event(
                            base_rom,
                            event,
                            compact_translations,
                            font=font,
                            player_names={0: "000000000", 1: "000000000", 2: "000000000"},
                        )
                    except ValueError:
                        compact_simulation = None
                    if compact_simulation is not None:
                        (
                            compact_row_translations,
                            compact_row_reports,
                            compact_row_simulation,
                            compact_row_repairs,
                        ) = _try_restore_stock_choice_row_prefix(
                            base_rom=base_rom,
                            event=event,
                            translations=compact_translations,
                            reports=compact_reports,
                            font=font,
                            simulation=compact_simulation,
                        )
                        if compact_row_repairs and not any(
                            repair.get("strategy") == "restore_stock_choice_row_suffix_on_fresh_page"
                            for repair in compact_row_repairs
                        ):
                            row_translations = compact_row_translations
                            row_reports = compact_row_reports
                            row_simulation = compact_row_simulation
                            row_repairs = compact_row_repairs
                            compact_repairs = [{
                                "event_id": event_id,
                                "strategy": "compact_android_prompt_before_reviewed_choice_row",
                                "snes_ids": list(mapping.get("snes_ids", [])),
                                "android_ids": list(mapping.get("android_ids", [])),
                                "localized_prose_unchanged": True,
                            }]

    stripped, decoration_repair = _strip_canonical_choice_decoration(
        event, row_translations
    )
    if decoration_repair is None:
        raise ValueError(f"Reviewed choice-layout recipe ${event_id} no longer matches canonical decoration")
    if (
        decoration_repair.get("opening_text_id") != recipe.get("opening_text_id")
        or decoration_repair.get("closing_text_id") != recipe.get("closing_text_id")
    ):
        raise ValueError(f"Reviewed choice-layout recipe ${event_id} resolved different carriers")

    stripped_reports = _choice_decoration_reports(
        row_reports, stripped, decoration_repair
    )
    stripped_simulation = simulate_event(
        base_rom,
        event,
        stripped,
        font=font,
        player_names={0: "000000000", 1: "000000000", 2: "000000000"},
    )
    decoration_repair = dict(decoration_repair)
    decoration_repair["reviewed_layout_recipe"] = True
    return (
        stripped,
        stripped_reports,
        stripped_simulation,
        row_repairs,
        [decoration_repair],
        compact_repairs,
    )


def _try_restore_stock_choice_row_prefix(
    *,
    base_rom: bytes,
    event: dict,
    translations: dict[str, str],
    reports: list[dict],
    font,
    simulation,
) -> tuple[dict[str, str], list[dict], object, list[dict]]:
    """Restore only stock choice-row layout that Android prose reflow removed.

    Two conservative source shapes are supported, and only while the current
    simulator reports an overlap at the *first* CHOICE_OPTION anchor:

    * a translated prompt whose USA carrier ended in ``NEWLINE + spaces + (``;
      append that exact stock suffix when the Android wording omitted it;
    * a standalone decorative ``("` carrier; prefix one NEWLINE so dynamic
      stock output immediately before it cannot consume the choice row.

    No option coordinate changes here.  The candidate is retained only when it
    strictly removes the first-anchor overlap without introducing a new class
    of error/warning or an implicit wrap; later-anchor overlap may remain for
    the separately gated adaptive-anchor pass.
    """
    from shared.dialogue_simulator import simulate_event

    tokens = event.get("tokens", [])
    begins = [
        index for index, token in enumerate(tokens)
        if token.get("type") == "command" and token.get("name") == "CHOICE_BEGIN"
    ]
    if len(begins) != 1 or begins[0] == 0:
        return translations, reports, simulation, []
    begin = begins[0]
    if begin + 1 >= len(tokens):
        return translations, reports, simulation, []
    first_option = tokens[begin + 1]
    if first_option.get("type") != "command" or first_option.get("name") != "CHOICE_OPTION":
        return translations, reports, simulation, []
    args = first_option.get("args", "").split()
    if len(args) != 1:
        return translations, reports, simulation, []
    first_position = int(args[0], 16)
    first_marker = f"CHOICE_OPTION ${first_position:02X} rewinds"
    if not any(
        issue.code == "CHOICE_OPTION_OVERLAP"
        and issue.severity in {"error", "warning"}
        and issue.message.startswith(first_marker)
        for issue in simulation.issues
    ):
        return translations, reports, simulation, []

    previous = tokens[begin - 1]
    if previous.get("type") not in {"text", "ending_text"}:
        return translations, reports, simulation, []
    text_id = previous["id"]
    source = previous.get("source", "")
    current = translations.get(text_id, source)
    candidate = dict(translations)
    repair: dict | None = None

    opening_match = re.search(r"(\n[ ]*\()$", source)
    if opening_match and not re.search(r"(?:\n|\f)[ ]*\($", current):
        suffix = opening_match.group(1)
        candidate[text_id] = current.rstrip(" ") + suffix
        repair = {
            "strategy": "restore_stock_choice_row_suffix",
            "text_id": text_id,
            "restored_suffix": suffix,
            "choice_commands_unchanged": True,
        }
    elif re.fullmatch(r"[ ]*\(", source) and re.fullmatch(r"[ ]*\(", current):
        candidate[text_id] = "\n" + current
        repair = {
            "strategy": "fresh_line_before_standalone_choice_decoration",
            "text_id": text_id,
            "prepended_newline": True,
            "choice_commands_unchanged": True,
        }
    else:
        return translations, reports, simulation, []

    try:
        candidate_simulation = simulate_event(
            base_rom,
            event,
            candidate,
            font=font,
            player_names={0: "000000000", 1: "000000000", 2: "000000000"},
        )
    except ValueError:
        return translations, reports, simulation, []

    # If restoring the canonical NEWLINE + '(' would create a fourth visible
    # line before the choice, reuse the same proven choice-row boundary as a
    # generated page transition instead. This is still source-derived: only the
    # stock suffix is restored and no printable Android-FR prose changes.
    if (
        repair is not None
        and repair.get("strategy") == "restore_stock_choice_row_suffix"
        and any(
            issue.code == "UNPAUSED_SCROLL"
            and issue.severity in {"error", "warning"}
            for issue in candidate_simulation.issues
        )
    ):
        suffix = repair["restored_suffix"]
        page_suffix = "\f" + suffix.lstrip("\n")
        page_candidate = dict(translations)
        page_candidate[text_id] = current.rstrip(" ") + page_suffix
        try:
            page_simulation = simulate_event(
                base_rom, event, page_candidate, font=font,
                player_names={0: "000000000", 1: "000000000", 2: "000000000"},
            )
        except ValueError:
            page_simulation = None
        if page_simulation is not None:
            candidate = page_candidate
            candidate_simulation = page_simulation
            repair = {
                "strategy": "restore_stock_choice_row_suffix_on_fresh_page",
                "text_id": text_id,
                "restored_suffix": suffix,
                "generated_page_transition": True,
                "choice_commands_unchanged": True,
            }

    candidate_first_overlap = any(
        issue.code == "CHOICE_OPTION_OVERLAP"
        and issue.severity in {"error", "warning"}
        and issue.message.startswith(first_marker)
        for issue in candidate_simulation.issues
    )
    candidate_wraps = sum(
        line.implicit_wrap
        for box in candidate_simulation.boxes
        for page in box.pages
        for line in page.lines
    )
    if candidate_first_overlap or candidate_wraps:
        return translations, reports, simulation, []

    # Do not accept a layout repair that creates an unrelated blocker.  A
    # remaining later-anchor overlap or width warning is allowed to continue to
    # the existing independent choice-layout fallbacks below.
    original_codes = {
        issue.code for issue in simulation.issues if issue.severity in {"error", "warning"}
    }
    candidate_codes = {
        issue.code
        for issue in candidate_simulation.issues
        if issue.severity in {"error", "warning"}
    }
    if candidate_codes - original_codes:
        return translations, reports, simulation, []

    updated_reports = [dict(report) for report in reports]
    for report in updated_reports:
        if text_id not in report.get("snes_ids", []):
            continue
        entries = [dict(entry) for entry in report.get("formatted_entries", [])]
        for entry in entries:
            if entry.get("id") == text_id:
                entry["text"] = candidate[text_id]
        report["formatted_entries"] = entries
        if len(report.get("snes_ids", [])) == 1:
            report["formatted_markup"] = candidate[text_id]
        report["choice_row_layout_repair"] = repair["strategy"]
    return candidate, updated_reports, candidate_simulation, [repair]


def _try_adaptive_choice_anchor_positions(
    *,
    base_rom: bytes,
    event: dict,
    translations: dict[str, str],
    advances: dict[str, int],
    font,
    simulation,
) -> tuple[object, dict[int, int], list[dict]]:
    """Move only later CHOICE_OPTION anchors right to prevent parser overwrite.

    The first option coordinate remains stock.  A later coordinate may move only
    to the minimum decoded-cell position immediately after the previous localized
    label.  The move is tried only for a simple canonical choice row and is kept
    only when the independently serialized/simulated event becomes fully clean.
    `vwf_dialogues` and the stock highlight then consume the same moved coordinate,
    matching the runtime-validated $03/$11 -> $03/$12 long-label diagnostic.
    """
    from shared.dialogue_simulator import simulate_event

    if not any(
        issue.code == "CHOICE_OPTION_OVERLAP" and issue.severity in {"error", "warning"}
        for issue in simulation.issues
    ):
        return simulation, {}, []

    tokens = event.get("tokens", [])
    begins = [
        index for index, token in enumerate(tokens)
        if token.get("type") == "command" and token.get("name") == "CHOICE_BEGIN"
    ]
    ends = [
        index for index, token in enumerate(tokens)
        if token.get("type") == "command" and token.get("name") == "CHOICE_END"
    ]
    if len(begins) != 1 or len(ends) != 1 or begins[0] >= ends[0]:
        return simulation, {}, []
    begin, end = begins[0], ends[0]

    options: list[tuple[int, int, dict]] = []
    index = begin + 1
    while index < end:
        command = tokens[index]
        if command.get("type") != "command" or command.get("name") != "CHOICE_OPTION":
            return simulation, {}, []
        args = command.get("args", "").split()
        if len(args) != 1:
            return simulation, {}, []
        position = int(args[0], 16)
        if index + 1 >= end:
            return simulation, {}, []
        text_token = tokens[index + 1]
        if text_token.get("type") not in {"text", "ending_text"}:
            return simulation, {}, []
        options.append((index, position, text_token))
        index += 2
    if index != end or len(options) < 2:
        return simulation, {}, []

    positions = [position for _, position, _ in options]
    overrides: dict[int, int] = {}
    repairs: list[dict] = []
    for option_index in range(1, len(options)):
        previous_token = options[option_index - 1][2]
        previous_text = translations.get(previous_token["id"], previous_token.get("source", ""))
        # Choice labels are plain decoded text. Do not infer geometry across any
        # formatter control markup or dynamic structure.
        if any(control in previous_text for control in ("\n", "\f", "\v")):
            return simulation, {}, []
        required = positions[option_index - 1] + len(previous_text)
        source_position = positions[option_index]
        if required <= source_position:
            continue
        if required >= 32:
            return simulation, {}, []
        span_pixels = (required - positions[option_index - 1]) * 8
        if _markup_width(previous_text, advances, 0) > span_pixels:
            return simulation, {}, []
        token_index = options[option_index][0]
        overrides[token_index] = required
        repairs.append({
            "strategy": "shift_choice_option_right_for_decoded_vwf_label",
            "token_index": token_index,
            "source_position": source_position,
            "translated_position": required,
            "previous_text_id": previous_token["id"],
            "decoded_label_cells": len(previous_text),
            "choice_commands_preserved_except_coordinate": True,
        })
        positions[option_index] = required

    if not overrides:
        return simulation, {}, []

    try:
        candidate = simulate_event(
            base_rom,
            event,
            translations,
            font=font,
            player_names={0: "000000000", 1: "000000000", 2: "000000000"},
            choice_option_position_overrides=overrides,
        )
    except ValueError:
        return simulation, {}, []
    blocking = [issue for issue in candidate.issues if issue.severity in {"error", "warning"}]
    wraps = sum(
        line.implicit_wrap
        for box in candidate.boxes
        for page in box.pages
        for line in page.lines
    )
    if blocking or wraps:
        return simulation, {}, []
    return candidate, overrides, repairs


def _try_adaptive_choice_decoration(
    *,
    base_rom: bytes,
    event: dict,
    translations: dict[str, str],
    reports: list[dict],
    font,
    simulation,
) -> tuple[dict[str, str], list[dict], object, list[dict]]:
    """Retry one rejected choice event without its outer stock decoration.

    Decoration is preserved whenever the normal event is already simulator-clean.
    The stripped form is selected only when removing the canonical outer pair is
    sufficient to make the whole event pass the same zero-error/zero-warning/
    zero-implicit-wrap gate.  This keeps the fallback width-driven and avoids a
    global visual rewrite of short choices.
    """
    from shared.dialogue_simulator import simulate_event

    blocking = [issue for issue in simulation.issues if issue.severity in {"error", "warning"}]
    wraps = sum(
        line.implicit_wrap
        for box in simulation.boxes
        for page in box.pages
        for line in page.lines
    )
    if not blocking and not wraps:
        return translations, reports, simulation, []

    candidate, repair = _strip_canonical_choice_decoration(event, translations)
    if repair is None:
        return translations, reports, simulation, []
    try:
        candidate_simulation = simulate_event(
            base_rom,
            event,
            candidate,
            font=font,
            player_names={0: "000000000", 1: "000000000", 2: "000000000"},
        )
    except ValueError:
        return translations, reports, simulation, []
    candidate_blocking = [
        issue for issue in candidate_simulation.issues
        if issue.severity in {"error", "warning"}
    ]
    candidate_wraps = sum(
        line.implicit_wrap
        for box in candidate_simulation.boxes
        for page in box.pages
        for line in page.lines
    )
    if candidate_blocking or candidate_wraps:
        return translations, reports, simulation, []

    candidate_reports = _choice_decoration_reports(reports, candidate, repair)
    return candidate, candidate_reports, candidate_simulation, [repair]


def _try_adaptive_choice_decoration_with_anchor_positions(
    *,
    base_rom: bytes,
    event: dict,
    translations: dict[str, str],
    reports: list[dict],
    advances: dict[str, int],
    font,
    simulation,
) -> tuple[
    dict[str, str],
    list[dict],
    object,
    list[dict],
    dict[int, int],
    list[dict],
]:
    """Strip outer decoration, then retry the validated later-anchor repair.

    This is a composed fallback only: decoration is still preserved whenever a
    less invasive candidate passes.  The first CHOICE_OPTION coordinate remains
    stock; only later coordinates may move right under the existing independent
    simulator gate.
    """
    from shared.dialogue_simulator import simulate_event

    candidate, repair = _strip_canonical_choice_decoration(event, translations)
    if repair is None:
        return translations, reports, simulation, [], {}, []
    try:
        candidate_simulation = simulate_event(
            base_rom,
            event,
            candidate,
            font=font,
            player_names={0: "000000000", 1: "000000000", 2: "000000000"},
        )
    except ValueError:
        return translations, reports, simulation, [], {}, []

    (
        shifted_simulation,
        anchor_overrides,
        anchor_repairs,
    ) = _try_adaptive_choice_anchor_positions(
        base_rom=base_rom,
        event=event,
        translations=candidate,
        advances=advances,
        font=font,
        simulation=candidate_simulation,
    )
    if not anchor_repairs:
        return translations, reports, simulation, [], {}, []

    blocking = [
        issue
        for issue in shifted_simulation.issues
        if issue.severity in {"error", "warning"}
    ]
    wraps = sum(
        line.implicit_wrap
        for box in shifted_simulation.boxes
        for page in box.pages
        for line in page.lines
    )
    if blocking or wraps:
        return translations, reports, simulation, [], {}, []

    candidate_reports = _choice_decoration_reports(reports, candidate, repair)
    for report in candidate_reports:
        report["choice_decoration_anchor_fallback"] = True
    return (
        candidate,
        candidate_reports,
        shifted_simulation,
        [repair],
        anchor_overrides,
        anchor_repairs,
    )


def _simulation_blocking_score(simulation) -> tuple[int, int, int]:
    blocking = [
        issue for issue in simulation.issues
        if issue.severity in {"error", "warning"}
    ]
    wraps = sum(
        line.implicit_wrap
        for box in simulation.boxes
        for page in box.pages
        for line in page.lines
    )
    return (len(blocking) + wraps, len(blocking), wraps)


def _carrier_boundary_can_start_new_line(value: str) -> bool:
    """Return whether a translated carrier may safely start a physical line.

    A carrier beginning with binding punctuation (for example ``:`` or ``!``)
    is semantically attached to the preceding carrier, very often a dynamic
    PLAYER_NAME.  Starting it on a fresh line produces layouts such as
    ``000000000\n: ...`` even though the simulator considers them valid.
    Presentation-only ellipsis carriers remain eligible because they are
    commonly intentional pause beats in the stock event stream.
    """
    stripped = value.lstrip(" ")
    if not stripped:
        return False
    if re.fullmatch(r"[.……]+", stripped.strip()):
        return True
    return stripped[0] not in ":;!?.,’'\")]}%»"


def _try_single_carrier_boundary_newline(
    *,
    base_rom: bytes,
    event: dict,
    translations: dict[str, str],
    font,
    structural_command_overrides: dict[int, tuple[str, str] | None] | None = None,
) -> tuple[dict[str, str], object | None, list[dict]]:
    """Try one deterministic presentation NEWLINE at a translated carrier edge.

    This is a generic layout candidate, never a prose exception. Candidate order
    follows canonical event token order and tries appending to the preceding
    carrier before prepending to the following carrier. A candidate is accepted
    only when the independent simulator reports zero errors, zero warnings and
    zero implicit wraps. Existing control bytes and carrier assignments remain
    otherwise unchanged.
    """
    from shared.dialogue_simulator import simulate_event

    if not translations:
        return translations, None, []

    token_ids = [
        token.get("id")
        for token in event.get("tokens", [])
        if token.get("type") in {"text", "ending_text"}
        and token.get("id") in translations
    ]
    if len(token_ids) < 2:
        return translations, None, []

    player_names = {0: "000000000", 1: "000000000", 2: "000000000"}
    # A boundary is defined between consecutive translated carriers in canonical
    # token order. The commands between them are intentionally left untouched.
    for index in range(len(token_ids) - 1):
        previous_id = token_ids[index]
        next_id = token_ids[index + 1]
        previous = translations[previous_id]
        following = translations[next_id]
        candidates = []
        # Appending the newline to the preceding translated carrier places the
        # physical break *before* any intervening stock commands (notably
        # PLAYER_NAME).  This is safe even when the following carrier begins
        # with binding punctuation: the dynamic name and its ``:``/``!`` stay
        # together on the fresh line.
        if previous and not previous.endswith(("\n", "\v", "\f")):
            candidates.append(("append", previous_id, previous + "\n"))
        # Prepending directly to the following carrier is only valid when that
        # carrier can semantically start a line by itself.
        if (
            _carrier_boundary_can_start_new_line(following)
            and following
            and not following.startswith(("\n", "\v", "\f"))
        ):
            candidates.append(("prepend", next_id, "\n" + following))
        for mode, text_id, replacement in candidates:
            candidate = dict(translations)
            candidate[text_id] = replacement
            try:
                simulation = simulate_event(
                    base_rom,
                    event,
                    candidate,
                    font=font,
                    player_names=player_names,
                    structural_command_overrides=structural_command_overrides,
                )
            except ValueError:
                continue
            if _simulation_blocking_score(simulation)[0] != 0:
                continue
            return candidate, simulation, [{
                "strategy": "single_carrier_boundary_newline",
                "boundary_after_id": previous_id,
                "boundary_before_id": next_id,
                "modified_id": text_id,
                "mode": mode,
                "semantic_payload_changed": False,
            }]

    return translations, None, []


def _automatic_layout_search_score(simulation) -> tuple[int, int, int, int]:
    """Rank rejected layouts for the bounded source-derived fallback search."""
    if simulation is None:
        return (999, 9999, 999, 999)
    blocking = [
        issue for issue in simulation.issues
        if issue.severity in {"error", "warning"}
    ]
    wraps = sum(
        line.implicit_wrap
        for box in simulation.boxes
        for page in box.pages
        for line in page.lines
    )
    width_excess = 0
    unpaused_scroll = 0
    for issue in blocking:
        match = re.search(r"Line advance is (\d+)px \(> (\d+)px", issue.message)
        if match:
            width_excess += int(match.group(1)) - int(match.group(2))
        if issue.code == "UNPAUSED_SCROLL":
            unpaused_scroll += 1
    return (len(blocking) + wraps, width_excess, unpaused_scroll, len(blocking))


@lru_cache(maxsize=1)
def _reviewed_layout_search_recipe_index() -> dict[str, list[dict]]:
    document = _load_recipe_document(
        DIALOGUE_LAYOUT_SEARCH_RECIPES,
        label="Dialogue layout-search recipes",
        expected={"format_version": 1},
    )
    recipes = document.get("events", {})
    if not isinstance(recipes, dict):
        raise ValueError("Dialogue layout-search recipes must contain an events object")
    return {str(event_id): list(steps) for event_id, steps in recipes.items()}


def _apply_reviewed_layout_search_recipe(
    *,
    base_rom: bytes,
    event: dict,
    translations: dict[str, str],
    font,
    structural_command_overrides: dict[int, tuple[str, str] | None] | None = None,
) -> tuple[dict[str, str], object | None, list[dict]]:
    """Apply a reviewed layout-only operation plan, then independently simulate it.

    Recipes contain no translated prose. If any carrier/offset shape has drifted
    or the resulting event is not clean, return no repair so the historical
    exhaustive solver can remain the conservative fallback.
    """
    from shared.dialogue_simulator import simulate_event

    steps = _reviewed_layout_search_recipe_index().get(str(event.get("event_id")))
    if not steps:
        return translations, None, []
    current = dict(translations)
    applied: list[dict] = []
    for expected_step, step in enumerate(steps, 1):
        if int(step.get("step", expected_step)) != expected_step:
            return translations, None, []
        strategy = str(step.get("strategy", ""))
        text_id = str(step.get("text_id", ""))
        if text_id not in current:
            return translations, None, []
        value = current[text_id]
        pos = int(step.get("source_offset", -1))

        if strategy == "newline_carrier_boundary":
            if value.startswith(("\n", "\v", "\f")):
                return translations, None, []
            current[text_id] = "\n" + value
        elif strategy == "newline_before_carrier_via_previous":
            boundary_before_id = step.get("boundary_before_id")
            if not boundary_before_id or boundary_before_id not in current:
                return translations, None, []
            if value.endswith(("\n", "\v", "\f")):
                return translations, None, []
            current[text_id] = value + "\n"
        elif strategy == "newline_word_boundary":
            if pos < 0 or pos >= len(value) or value[pos] != " ":
                return translations, None, []
            current[text_id] = value[:pos] + "\n" + value[pos + 1:]
        elif strategy in {"page_word_boundary", "unpaused_scroll_word_page_boundary"}:
            if pos < 0 or pos >= len(value) or value[pos] != " ":
                return translations, None, []
            current[text_id] = value[:pos] + "\f" + value[pos + 1:]
        elif strategy == "page_sentence_boundary":
            if pos < 0 or pos >= len(value) or not value[pos].isspace():
                return translations, None, []
            end = pos
            while end < len(value) and value[end].isspace() and value[end] not in "\v\f":
                end += 1
            current[text_id] = value[:pos] + "\f" + value[end:]
        else:
            return translations, None, []
        applied.append(dict(step))

    try:
        simulation = simulate_event(
            base_rom,
            event,
            current,
            font=font,
            player_names={0: "000000000", 1: "000000000", 2: "000000000"},
            structural_command_overrides=structural_command_overrides,
        )
    except ValueError:
        return translations, None, []
    if _simulation_blocking_score(simulation)[0] != 0:
        return translations, None, []
    return current, simulation, applied


def _try_unpaused_scroll_page_repairs(
    *,
    base_rom: bytes,
    event: dict,
    translations: dict[str, str],
    font,
    structural_command_overrides: dict[int, tuple[str, str] | None] | None = None,
) -> tuple[dict[str, str], object | None, list[dict]]:
    """Repair pure pagination overflow with deterministic generated page breaks.

    This fallback is intentionally narrow. It runs only when every blocking
    simulator issue is ``UNPAUSED_SCROLL``. It tests a generated WAIT $00 +
    TEXT_CLEAR marker (``\f`` in translation markup) at ordinary word
    boundaries inside already-multiline translated carriers, and keeps only a
    candidate that *strictly* reduces the blocking score. Printable Android-FR
    payload and carrier ownership are unchanged. The process repeats at most
    once per initial scroll defect and returns only a completely clean event.

    Restricting candidates to multiline carriers keeps very long scenes
    tractable while targeting the actual cause: four visible lines accumulated
    between pauses. If no strictly improving boundary exists, the event remains
    rejected for later review rather than guessing.
    """
    from shared.dialogue_simulator import simulate_event

    player_names = {0: "000000000", 1: "000000000", 2: "000000000"}
    try:
        simulation = simulate_event(
            base_rom, event, translations, font=font, player_names=player_names,
            structural_command_overrides=structural_command_overrides,
        )
    except ValueError:
        return translations, None, []

    blocking = [
        issue for issue in simulation.issues
        if issue.severity in {"error", "warning"}
    ]
    if not blocking or any(issue.code != "UNPAUSED_SCROLL" for issue in blocking):
        return translations, None, []

    current = dict(translations)
    current_simulation = simulation
    current_score = _automatic_layout_search_score(simulation)
    repairs: list[dict] = []
    max_steps = len(blocking)

    canonical_ids = [
        token.get("id")
        for token in event.get("tokens", [])
        if token.get("type") in {"text", "ending_text"}
        and token.get("id") in current
    ]
    canonical_ids.extend(sorted(set(current) - set(canonical_ids)))

    for step in range(1, max_steps + 1):
        best = None
        for carrier_order, text_id in enumerate(canonical_ids):
            value = current[text_id]
            # A page break can only solve a rolling four-line defect if the
            # carrier contributes multiple visible lines. This also prevents a
            # combinatorial scan across every word in a long scripted scene.
            if value.count("\n") < 2:
                continue
            for match in reversed(list(re.finditer(r"(?<=\S) (?=[^\s:;!?])", value))):
                pos = match.start()
                replacement = value[:pos] + "\f" + value[pos + 1:]
                candidate = dict(current)
                candidate[text_id] = replacement
                try:
                    candidate_simulation = simulate_event(
                        base_rom, event, candidate, font=font,
                        player_names=player_names,
                        structural_command_overrides=structural_command_overrides,
                    )
                except ValueError:
                    continue
                candidate_score = _automatic_layout_search_score(candidate_simulation)
                if candidate_score >= current_score:
                    continue
                # Stable tie-break: best simulator score, canonical carrier,
                # then latest word boundary to preserve as much preceding layout
                # as possible.
                key = (candidate_score, carrier_order, -pos)
                if best is None or key < best[0]:
                    best = (
                        key, candidate, candidate_simulation,
                        {
                            "strategy": "unpaused_scroll_word_page_boundary",
                            "text_id": text_id,
                            "source_offset": pos,
                            "step": step,
                            "semantic_payload_changed": False,
                        },
                    )
        if best is None:
            break
        _, current, current_simulation, repair = best
        current_score = _automatic_layout_search_score(current_simulation)
        repairs.append(repair)
        if _simulation_blocking_score(current_simulation)[0] == 0:
            return current, current_simulation, repairs

    return translations, None, []


def _try_source_derived_layout_search(
    *,
    base_rom: bytes,
    event: dict,
    translations: dict[str, str],
    font,
    structural_command_overrides: dict[int, tuple[str, str] | None] | None = None,
    max_steps: int = 3,
    max_translated_carriers: int = 40,
) -> tuple[dict[str, str], object | None, list[dict]]:
    """Search a tiny deterministic layout-only neighborhood around Android FR.

    The search never changes printable characters or carrier ownership. It may
    replace one inter-word space by NEWLINE, or one existing sentence/word
    boundary by the already-supported generated WAIT $00 + TEXT_CLEAR page
    marker. Sentence page boundaries are preferred; arbitrary word-boundary page
    breaks are considered only on the final search step. At each step the whole
    event is independently simulated, and the best non-worsening candidate is
    retained. A result is returned only if the final event is completely clean.

    The carrier-count bound deliberately keeps very large scripted scenes out of
    this brute-force fallback; those need a more structural solver rather than a
    costly exhaustive presentation search.
    """
    from shared.dialogue_simulator import simulate_event

    if not translations or len(translations) > max_translated_carriers:
        return translations, None, []

    player_names = {0: "000000000", 1: "000000000", 2: "000000000"}
    try:
        simulation = simulate_event(
            base_rom, event, translations, font=font, player_names=player_names,
            structural_command_overrides=structural_command_overrides,
        )
    except ValueError:
        return translations, None, []
    if _simulation_blocking_score(simulation)[0] == 0:
        return translations, simulation, []

    canonical_ids = [
        token.get("id")
        for token in event.get("tokens", [])
        if token.get("type") in {"text", "ending_text"}
        and token.get("id") in translations
    ]
    # Keep dictionary-only generated carriers deterministic as well.
    canonical_ids.extend(sorted(set(translations) - set(canonical_ids)))

    current = dict(translations)
    current_simulation = simulation
    current_score = _automatic_layout_search_score(simulation)
    repairs: list[dict] = []

    for step in range(1, max_steps + 1):
        allow_word_page = step == max_steps
        best = None
        for carrier_order, text_id in enumerate(canonical_ids):
            value = current[text_id]
            # operation = (strategy, rank, source_offset, target_id, replacement)
            operations: list[tuple[str, int, int, str, str]] = []

            # Prefer preserving a carrier's prose intact.  A boundary break is
            # first expressed by appending NEWLINE to the preceding translated
            # carrier.  Any intervening stock PLAYER_NAME therefore moves with
            # the following punctuation/prose onto the fresh line.  Only when
            # the current carrier can stand alone may the newline be prepended
            # directly to it.
            if carrier_order > 0 and value and not value.startswith(("\n", "\v", "\f")):
                previous_id = canonical_ids[carrier_order - 1]
                previous_value = current[previous_id]
                if previous_value and not previous_value.endswith(("\n", "\v", "\f")):
                    operations.append((
                        "newline_before_carrier_via_previous", 0, -1,
                        previous_id, previous_value + "\n",
                    ))
                if _carrier_boundary_can_start_new_line(value):
                    operations.append((
                        "newline_carrier_boundary", 0, -1,
                        text_id, "\n" + value,
                    ))

            # Prefer a generated page transition after complete sentences.
            for match in reversed(list(re.finditer(r"(?<=[.!?…])(?: +|\n)(?=\S)", value))):
                pos, end = match.start(), match.end()
                operations.append(("page_sentence_boundary", 1, pos, text_id, value[:pos] + "\f" + value[end:]))

            # Internal word-boundary line breaks are a last-resort line-layout
            # operation.  They remain available when width/capacity genuinely
            # requires them, but rank after a carrier boundary and a semantic
            # sentence/page boundary so short phrases are not fragmented merely
            # to repair cursor state inherited from an earlier carrier.
            for match in reversed(list(re.finditer(r"(?<=\S) (?=[^\s:;!?])", value))):
                pos = match.start()
                operations.append(("newline_word_boundary", 2, pos, text_id, value[:pos] + "\n" + value[pos + 1:]))

            # If two earlier layout operations still cannot serialize the event,
            # permit the already-proven word-boundary page fallback used by the
            # three-page formatter. This remains presentation-only.
            if allow_word_page:
                for match in reversed(list(re.finditer(r"(?<=\S) (?=[^\s:;!?])", value))):
                    pos = match.start()
                    operations.append(("page_word_boundary", 3, pos, text_id, value[:pos] + "\f" + value[pos + 1:]))

            for strategy, strategy_rank, pos, target_id, replacement in operations:
                candidate = dict(current)
                candidate[target_id] = replacement
                try:
                    candidate_simulation = simulate_event(
                        base_rom, event, candidate, font=font, player_names=player_names,
                        structural_command_overrides=structural_command_overrides,
                    )
                except ValueError:
                    continue
                candidate_score = _automatic_layout_search_score(candidate_simulation)
                # Stable tie-break: semantic page boundaries, then NEWLINE, then
                # word-page fallback; canonical carrier order; latest boundary.
                key = (candidate_score, strategy_rank, carrier_order, -pos)
                if best is None or key < best[0]:
                    best = (
                        key, candidate, candidate_simulation,
                        {
                            "strategy": strategy,
                            "text_id": target_id,
                            "boundary_before_id": text_id if strategy == "newline_before_carrier_via_previous" else None,
                            "source_offset": pos,
                            "step": step,
                            "semantic_payload_changed": False,
                        },
                    )

        if best is None:
            break
        best_score = best[0][0]
        # Allow an equal-score bridge operation because two layout boundaries
        # can jointly remove a rolling-window defect even when the first one is
        # neutral in isolation. Never accept a worsening intermediate state.
        if best_score > current_score:
            break
        _, current, current_simulation, repair = best
        current_score = best_score
        repairs.append(repair)
        if _simulation_blocking_score(current_simulation)[0] == 0:
            return current, current_simulation, repairs

    return translations, None, []


def _try_direct_simulator_safe_subset(
    *,
    base_rom: bytes,
    event: dict,
    event_mappings: list[dict],
    translations: dict[str, str],
    reports: list[dict],
    font,
    structural_command_overrides: dict[int, tuple[str, str] | None] | None = None,
    max_deferred_mappings: int = 3,
) -> tuple[dict[str, str], list[dict], object | None, list[dict]]:
    """Keep a minimal whole-mapping subset stock when direct simulation proves it.

    This is a deliberately narrow second-stage PARTIEL fallback.  It is tried
    only after the normal complete-event formatting path fails.  The stock
    event itself must simulate cleanly; each candidate mapping must improve the
    direct defect count on its own; and a combination of at most three whole
    mappings must make the remaining already-formatted French directly clean.
    No command, identity, line layout, compact wrapper, or adaptive repair is
    changed by this helper.
    """
    from shared.dialogue_simulator import simulate_event

    if not translations or max_deferred_mappings < 1:
        return translations, reports, None, []

    player_names = {0: "000000000", 1: "000000000", 2: "000000000"}
    try:
        stock_simulation = simulate_event(
            base_rom, event, {}, font=font, player_names=player_names,
            structural_command_overrides=structural_command_overrides,
        )
        base_simulation = simulate_event(
            base_rom, event, translations, font=font, player_names=player_names,
            structural_command_overrides=structural_command_overrides,
        )
    except ValueError:
        return translations, reports, None, []

    if _simulation_blocking_score(stock_simulation)[0] != 0:
        return translations, reports, None, []
    base_score = _simulation_blocking_score(base_simulation)
    if base_score[0] == 0:
        return translations, reports, base_simulation, []

    candidate_mappings: list[dict] = []
    for mapping in event_mappings:
        ids = [text_id for text_id in mapping.get("snes_ids", []) if text_id in translations]
        if not ids or len(ids) == len(translations):
            continue
        candidate_translations = {
            text_id: value for text_id, value in translations.items()
            if text_id not in set(ids)
        }
        try:
            candidate_simulation = simulate_event(
                base_rom, event, candidate_translations,
                font=font, player_names=player_names,
                structural_command_overrides=structural_command_overrides,
            )
        except ValueError:
            continue
        if _simulation_blocking_score(candidate_simulation) < base_score:
            candidate_mappings.append(mapping)

    # Search the smallest deterministic set first.  Candidate order follows
    # the canonical event mapping order, so ties are stable across runs.
    for count in range(1, min(max_deferred_mappings, len(candidate_mappings)) + 1):
        for subset in combinations(candidate_mappings, count):
            deferred_ids = {
                text_id
                for mapping in subset
                for text_id in mapping.get("snes_ids", [])
                if text_id in translations
            }
            remaining = {
                text_id: value for text_id, value in translations.items()
                if text_id not in deferred_ids
            }
            if not remaining:
                continue
            try:
                simulation = simulate_event(
                    base_rom, event, remaining,
                    font=font, player_names=player_names,
                    structural_command_overrides=structural_command_overrides,
                )
            except ValueError:
                continue
            if _simulation_blocking_score(simulation)[0] != 0:
                continue

            deferred_reports: list[dict] = []
            subset_ids = set(deferred_ids)
            kept_reports = [
                report for report in reports
                if not subset_ids.intersection(report.get("snes_ids", []))
            ]
            for mapping in subset:
                ids = [text_id for text_id in mapping.get("snes_ids", []) if text_id in translations]
                deferred_reports.append({
                    "event_id": event["event_id"],
                    "snes_ids": ids,
                    "android_ids": mapping.get("android_ids", []),
                    "confidence": mapping.get("confidence"),
                    "partial_event": True,
                    "layout_deferred": True,
                    "layout_deferred_policy": "direct_simulator_safe_subset",
                    "layout_deferred_formatter_error": (
                        "whole mapping kept stock: minimal direct-simulation safe subset"
                    ),
                    "formatted_entries": [],
                })
            return remaining, kept_reports + deferred_reports, simulation, deferred_reports

    return translations, reports, None, []


def _auto_reflow_fixed_translation_carriers(
    values: dict[str, str],
    advances: dict[str, int],
) -> tuple[dict[str, str], list[dict]]:
    """Reflow already-proven carrier text to the current VWF line contract.

    This is deliberately presentation-only. Existing carrier boundaries,
    explicit NEWLINEs and translation control markers (TEXT_CLEAR / page
    controls) are preserved. Only an individual visible line that no longer
    fits the current ``DIALOGUE_WRAP_PIXELS`` / ``DIALOGUE_WRAP_CHARS`` limits
    is word-wrapped. No prose, identity, command order or carrier assignment is
    changed here; any resulting page/command incompatibility is left for the
    independent simulator to reject.
    """
    out: dict[str, str] = {}
    reports: list[dict] = []

    for text_id, value in values.items():
        # Preserve translation control markers byte-for-byte. Reflow each
        # visible segment independently so an existing TEXT_CLEAR cannot move.
        control_parts = re.split(r'([\v\f])', value)
        rebuilt_parts: list[str] = []
        changed = False
        line_reports: list[dict] = []
        for part in control_parts:
            if part in {"\v", "\f"}:
                rebuilt_parts.append(part)
                continue
            # Preserve every explicit hard newline. Only rewrap the text that
            # lies between two already-reviewed hard boundaries.
            hard_lines = part.split("\n")
            rebuilt_lines: list[str] = []
            for line in hard_lines:
                if not line.strip():
                    rebuilt_lines.append(line)
                    continue
                width = _markup_width(line, advances, 0)
                # PLAYER_NAME markup, when present, must use the conservative
                # dynamic-name wrapper rather than raw-width measurement.
                needs_wrap = width > DIALOGUE_WRAP_PIXELS or len(line) > DIALOGUE_WRAP_CHARS
                if "%S(" in line:
                    try:
                        wrapped, widths, chars, units = semantic_wrap_markup(line, advances)
                    except ValueError:
                        raise
                    needs_wrap = len(widths) > 1 or any(
                        w > DIALOGUE_WRAP_PIXELS or u > DIALOGUE_WRAP_CHARS
                        for w, u in zip(widths, units, strict=True)
                    )
                elif needs_wrap:
                    wrapped, widths, chars, units = semantic_wrap_markup(line, advances)
                else:
                    wrapped = line
                    widths = [width]
                    chars = [len(line)]
                    units = [len(line)]
                rebuilt_lines.append(wrapped)
                if wrapped != line:
                    changed = True
                    line_reports.append({
                        "source_line": line,
                        "wrapped": wrapped,
                        "widths_pixels": widths,
                        "decoded_characters": chars,
                        "parser_units": units,
                    })
            rebuilt_parts.append("\n".join(rebuilt_lines))
        rebuilt = "".join(rebuilt_parts)
        out[text_id] = rebuilt
        if changed:
            reports.append({"id": text_id, "reflowed_lines": line_reports})
    return out, reports


def _try_live_player_prefix_reflow(
    *,
    base_rom: bytes,
    event: dict,
    translations: dict[str, str],
    advances: dict[str, int],
    font,
    structural_command_overrides: dict[int, tuple[str, str] | None] | None = None,
) -> tuple[dict[str, str], object | None, list[dict]]:
    """Reflow only carriers that continue directly after ``PLAYER_NAME``.

    Android-FR carrier payload does not include stock PLAYER_NAME commands.  A
    carrier immediately following one therefore has less live first-line room
    than its standalone string suggests.  Generate a conservative candidate
    using the validated 9-character worst-case name width.  Keep the candidate
    only when whole-event simulation strictly improves; printable text and
    carrier ownership are unchanged.
    """
    from shared.dialogue_simulator import simulate_event

    tokens = event.get("tokens", [])
    candidate = dict(translations)
    repairs: list[dict] = []
    prefix_pixels = player_placeholder_width(advances)
    for index, token in enumerate(tokens):
        if token.get("type") not in {"text", "ending_text"} or index == 0:
            continue
        text_id = token.get("id")
        if text_id not in candidate:
            continue
        previous = tokens[index - 1]
        if previous.get("type") != "command" or previous.get("name") != "PLAYER_NAME":
            continue
        value = candidate[text_id]
        # A leading page/clear control resets the live prefix before prose.
        if not value or value.startswith(("\v", "\f")):
            continue
        parts = value.split("\n")
        first = parts[0]
        if not first.strip():
            continue

        # Earlier formatting may already have inserted a soft wrap inside the
        # same sentence.  Reflowing only ``parts[0]`` can then create an
        # orphan word before the preserved next line (for example
        # ``... ou il`` / ``va`` / ``s'en prendre ...``).  Extend the live
        # prefix reflow through consecutive soft lines until a genuine
        # sentence boundary.  This lets words move across obsolete soft wraps
        # while preserving explicit sentence-level layout.
        logical_first = first
        consumed_parts = 1
        sentence_end_re = re.compile(r"(?:\.{3}|[.!?…])[”\"»')\]]*\s*$")
        while consumed_parts < len(parts):
            if sentence_end_re.search(logical_first.rstrip()):
                break
            next_part = parts[consumed_parts]
            if not next_part.strip():
                break
            logical_first = logical_first.rstrip() + " " + next_part.lstrip()
            consumed_parts += 1

        try:
            wrapped, widths, chars, units = semantic_wrap_markup(
                logical_first,
                advances,
                first_line_prefix_pixels=prefix_pixels,
                first_line_prefix_units=MAX_PLAYER_NAME_CHARS,
            )
        except ValueError:
            continue
        if wrapped == logical_first and consumed_parts == 1:
            continue
        replacement = "\n".join([wrapped, *parts[consumed_parts:]])
        candidate[text_id] = replacement
        repairs.append({
            "strategy": "live_player_name_prefix_reflow",
            "text_id": text_id,
            "prefix_pixels": prefix_pixels,
            "prefix_parser_units": MAX_PLAYER_NAME_CHARS,
            "semantic_payload_changed": False,
        })

    if not repairs:
        return translations, None, []
    player_names = {0: "000000000", 1: "000000000", 2: "000000000"}
    try:
        before = simulate_event(
            base_rom, event, translations, font=font, player_names=player_names,
            structural_command_overrides=structural_command_overrides,
        )
        after = simulate_event(
            base_rom, event, candidate, font=font, player_names=player_names,
            structural_command_overrides=structural_command_overrides,
        )
    except ValueError:
        return translations, None, []
    if _automatic_layout_search_score(after) >= _automatic_layout_search_score(before):
        return translations, None, []
    return candidate, after, repairs

def _repack_fixed_translation_carriers(
    values: dict[str, str],
    advances: dict[str, int],
) -> tuple[dict[str, str], list[dict]]:
    """Repack historical hard NEWLINE layout inside fixed carrier segments.

    Secondary candidate generator only: preserve carrier assignments and page
    controls, normalize old hard NEWLINEs inside each visible segment to spaces,
    then reapply the calibrated 216px / 38-unit wrapper. The whole event must
    independently simulate clean before callers may accept the candidate.
    """
    out: dict[str, str] = {}
    reports: list[dict] = []
    for text_id, value in values.items():
        parts = re.split(r'([\v\f])', value)
        rebuilt: list[str] = []
        changes: list[dict] = []
        for part in parts:
            if part in {"\v", "\f"}:
                rebuilt.append(part)
                continue
            if not part:
                rebuilt.append(part)
                continue
            logical = re.sub(r"[ \t]*\n[ \t]*", " ", part)
            logical = re.sub(r"[ \t]+", " ", logical)
            if not logical.strip():
                rebuilt.append(logical)
                continue
            wrapped, widths, chars, units = semantic_wrap_markup(logical, advances)
            rebuilt.append(wrapped)
            if wrapped != part:
                changes.append({
                    "source_segment": part,
                    "logical_segment": logical,
                    "wrapped": wrapped,
                    "widths_pixels": widths,
                    "decoded_characters": chars,
                    "parser_units": units,
                })
        out[text_id] = "".join(rebuilt)
        if changes:
            reports.append({"id": text_id, "repacked_segments": changes})
    return out, reports


def make_dialogue_format_mass(
    english: dict[int, str],
    french: dict[int, str],
    *,
    english_path: Path,
    french_path: Path,
    base_rom: bytes,
) -> tuple[dict, dict]:
    """Generate the largest conservative complete-event set accepted by the simulator.

    This is deliberately a two-stage gate.  First, every semantic source text
    in an event must already have an accepted Android alignment and every
    mapping must format without crossing an unsupported structural command.
    The formatter may use the full validated three-line physical page capacity
    even when the shorter English source used fewer explicit lines. Ordinary
    overflow may add one validated WAIT $00 + TEXT_CLEAR transition; a longer
    mapping may add two only when both transitions land on complete-sentence
    boundaries and all three pages independently stay within three lines.

    Second, the final serialized event bytes are passed through the independent
    dialogue simulator. Any error, warning, or implicit runtime wrap excludes
    the whole event. Unsupported layout commands therefore remain English until
    the simulator models them explicitly.
    """
    from shared.dialogue_simulator import make_dialogue_font, simulate_event

    validate_base_rom(base_rom)
    alignment = make_dialogue_auto_alignment(
        english,
        french,
        english_path=english_path,
        french_path=french_path,
    )
    source_document = json.loads(DIALOGUE_SOURCE.read_text(encoding="utf-8"))
    manual_supplements_by_event = _load_manual_dialogue_supplements(source_document)
    inn_template = _parameterized_inn_prompt(english, french)
    structural_omission_indexes_by_event = resolve_structural_omission_token_indexes(
        {"user_validated_structural_omissions": list(DIALOGUE_USER_VALIDATED_STRUCTURAL_OMISSIONS)},
        source_document,
    )
    structural_command_overrides_by_event = resolve_structural_command_overrides(
        {"user_validated_structural_command_overrides": list(DIALOGUE_USER_VALIDATED_STRUCTURAL_COMMAND_OVERRIDES)},
        source_document,
    )
    redistribution_values, redistribution_meta = _load_dialogue_redistribution_recipes(french)
    coverage_repair_recipes = _load_dialogue_coverage_repair_recipes(french, source_document)

    # Round 85 reproducibility guardrails. These two changes must survive a
    # completely fresh --only dialogue-format-mass regeneration; silently
    # falling back to a stale recipe/manual file is worse than failing fast.
    lot6 = [
        recipe for recipe in coverage_repair_recipes.get("0559", [])
        if recipe.get("carrier_id") == "CA:6787"
    ]
    if len(lot6) != 1 or lot6[0].get("android_ids") != [2151, 2152, 2153, 2154, 2155]:
        raise ValueError(
            "Round-85 $0559 coverage recipe missing/drifted: expected "
            "CA:6787 <- Android 2151..2155. Refresh "
            "mappings/android/dialogues_coverage_repair_recipes.json."
        )
    if lot6[0].get("separator") != "\f" or lot6[0].get("android_separator") != "\f" or not lot6[0].get("wrap_android_units"):
        raise ValueError("Round-85 $0559 coverage recipe structural settings drifted")

    if "C9:902F" in manual_supplements_by_event.get("0204", {}):
        raise ValueError(
            "Round-85 $0204 migration drifted: C9:902F must no longer be an active "
            "manual supplement; it is reproduced by the proven Android redistribution."
        )

    reviewed_choice_layout_recipes = _load_reviewed_choice_layout_recipes(source_document)
    round68_events = {"0555", "0429", "05F8"}
    round69_events = {
        "0103", "010C", "015A", "01C5", "0204", "0205", "0227", "04E2", "04E5", "04E6", "04E9", "04FD", "0559", "0592", "05B4"
    }
    round67_recipe_events = {"04E1"}
    if set(redistribution_values) != round67_recipe_events | round68_events | round69_events:
        raise ValueError("Dialogue redistribution recipe event set changed")
    source_text_by_id = {
        token["id"]: token.get("source", "")
        for source_event in source_document["events"]
        for token in source_event["tokens"]
        if token.get("type") == "text"
    }
    advances = make_dialogue_advances(base_rom)
    font = make_dialogue_font(base_rom)

    mappings_by_event: dict[str, list[dict]] = {}
    for mapping in alignment["mappings"]:
        mappings_by_event.setdefault(mapping["event_id"], []).append(mapping)
    unmapped_by_id = {entry["snes_id"]: entry for entry in alignment["unmapped"]}

    translations_by_event: dict[str, dict[str, str]] = {}
    reports_by_event: dict[str, list[dict]] = {}
    wait00_repairs_by_event: dict[str, list[dict]] = {}
    unpaused_scroll_repairs_by_event: dict[str, list[dict]] = {}
    live_line_compact_repairs_by_event: dict[str, list[dict]] = {}
    cross_mapping_sentence_repairs_by_event: dict[str, list[dict]] = {}
    structural_reaction_page_repairs_by_event: dict[str, list[dict]] = {}
    duplicated_player_context_repairs_by_event: dict[str, list[dict]] = {}
    reviewed_hole_player_context_repairs_by_event: dict[str, list[dict]] = {}
    fragment_spacing_repairs_by_event: dict[str, list[dict]] = {}
    targeted_wait00_fresh_page_repairs_by_event: dict[str, list[dict]] = {}
    explicit_post_wait_newline_repairs_by_event: dict[str, list[dict]] = {}
    round48_pagination_repairs_by_event: dict[str, list[dict]] = {}
    round49_04e9_wait00_clear_repairs_by_event: dict[str, list[dict]] = {}
    round50_01ce_choice_page_clear_repairs_by_event: dict[str, list[dict]] = {}
    automatic_216px_reflows_by_event: dict[str, list[dict]] = {}
    carrier_boundary_newline_repairs_by_event: dict[str, list[dict]] = {}
    carrier_repack_repairs_by_event: dict[str, list[dict]] = {}
    live_player_prefix_reflow_repairs_by_event: dict[str, list[dict]] = {}
    source_derived_layout_search_repairs_by_event: dict[str, list[dict]] = {}
    choice_row_layout_repairs_by_event: dict[str, list[dict]] = {}
    adaptive_choice_decoration_repairs_by_event: dict[str, list[dict]] = {}
    adaptive_choice_anchor_repairs_by_event: dict[str, list[dict]] = {}
    reviewed_choice_compact_repairs_by_event: dict[str, list[dict]] = {}
    choice_option_position_overrides_by_event: dict[str, dict[int, int]] = {}
    manual_supplement_reports_by_event: dict[str, list[dict]] = {}
    android_extra_reports_by_event: dict[str, list[dict]] = {}
    parameterized_inn_events: set[str] = set()
    accepted_events: list[str] = []
    partial_accepted_events: list[str] = []
    partial_unresolved_semantic_ids_by_event: dict[str, list[str]] = {}
    partial_layout_deferred_semantic_ids_by_event: dict[str, list[str]] = {}
    generic_layout_deferred_semantic_ids_by_event: dict[str, list[str]] = {}
    partial_suppression_reason_by_event: dict[str, str] = {}
    excluded_events: list[dict] = []
    complete_aligned_count = 0
    formatter_candidate_count = 0

    for event in source_document["events"]:
        event_id = event["event_id"]
        semantic_ids = [
            token["id"]
            for token in event["tokens"]
            if token.get("type") == "text" and _auto_semantic(token.get("source", ""))
        ]
        if not semantic_ids:
            continue

        if event_id in round68_events:
            values = dict(redistribution_values[event_id])
            values, automatic_reflow = _auto_reflow_fixed_translation_carriers(values, advances)
            canonical_ids = {
                token.get("id") for token in event["tokens"]
                if token.get("type") in {"text", "ending_text"}
            }
            unknown = sorted(set(values) - canonical_ids)
            if unknown:
                raise ValueError(f"Round-68 ${event_id} unknown carrier(s): {unknown}")
            simulation = simulate_event(
                base_rom, event, values, font=font,
                player_names={0: "000000000", 1: "000000000", 2: "000000000"},
            )
            blocking = [issue for issue in simulation.issues if issue.severity in {"error", "warning"}]
            wraps = sum(
                line.implicit_wrap
                for box in simulation.boxes for page in box.pages for line in page.lines
            )
            if blocking or wraps:
                candidate_values, candidate_simulation, boundary_repairs = _try_single_carrier_boundary_newline(
                    base_rom=base_rom, event=event, translations=values, font=font
                )
                if boundary_repairs:
                    values = candidate_values
                    simulation = candidate_simulation
                    blocking = []
                    wraps = 0
                    carrier_boundary_newline_repairs_by_event[event_id] = boundary_repairs
            if blocking or wraps:
                repacked_values, repack_repairs = _repack_fixed_translation_carriers(
                    dict(redistribution_values[event_id]), advances
                )
                try:
                    repacked_simulation = simulate_event(
                        base_rom, event, repacked_values, font=font,
                        player_names={0: "000000000", 1: "000000000", 2: "000000000"},
                    )
                except ValueError:
                    repacked_simulation = None
                if repacked_simulation is not None and _simulation_blocking_score(repacked_simulation)[0] == 0:
                    values = repacked_values
                    simulation = repacked_simulation
                    blocking = []
                    wraps = 0
                    carrier_repack_repairs_by_event[event_id] = repack_repairs
                elif repacked_simulation is not None:
                    candidate_values, candidate_simulation, boundary_repairs = _try_single_carrier_boundary_newline(
                        base_rom=base_rom, event=event, translations=repacked_values, font=font
                    )
                    if boundary_repairs:
                        values = candidate_values
                        simulation = candidate_simulation
                        blocking = []
                        wraps = 0
                        carrier_repack_repairs_by_event[event_id] = repack_repairs
                        carrier_boundary_newline_repairs_by_event[event_id] = boundary_repairs
            if blocking or wraps:
                prefix_values, prefix_simulation, prefix_repairs = _try_live_player_prefix_reflow(
                    base_rom=base_rom, event=event, translations=values, advances=advances, font=font
                )
                if prefix_repairs:
                    values = prefix_values
                    simulation = prefix_simulation
                    live_player_prefix_reflow_repairs_by_event[event_id] = prefix_repairs
                    blocking = [issue for issue in simulation.issues if issue.severity in {"error", "warning"}]
                    wraps = sum(line.implicit_wrap for box in simulation.boxes for page in box.pages for line in page.lines)
            if blocking or wraps:
                reviewed_values, reviewed_simulation, reviewed_repairs = _apply_reviewed_layout_search_recipe(
                    base_rom=base_rom, event=event, translations=values, font=font
                )
                if reviewed_repairs:
                    values = reviewed_values
                    simulation = reviewed_simulation
                    blocking = []
                    wraps = 0
                    source_derived_layout_search_repairs_by_event[event_id] = reviewed_repairs
            if blocking or wraps:
                page_values, page_simulation, page_repairs = _try_unpaused_scroll_page_repairs(
                    base_rom=base_rom, event=event, translations=values, font=font
                )
                if page_repairs:
                    values = page_values
                    simulation = page_simulation
                    blocking = []
                    wraps = 0
                    source_derived_layout_search_repairs_by_event[event_id] = page_repairs
            if blocking or wraps:
                searched_values, searched_simulation, search_repairs = _try_source_derived_layout_search(
                    base_rom=base_rom, event=event, translations=values, font=font
                )
                if search_repairs:
                    values = searched_values
                    simulation = searched_simulation
                    blocking = []
                    wraps = 0
                    source_derived_layout_search_repairs_by_event[event_id] = search_repairs
            if blocking or wraps:
                excluded_events.append({
                    "event_id": event_id,
                    "stage": "reviewed_redistribution_automatic_reflow",
                    "reason": "automatic_216px_reflow_not_simulator_clean",
                    "reviewed_redistribution_round": 68,
                    "blocking_issue_codes": [issue.code for issue in blocking],
                    "implicit_wraps": wraps,
                    "automatic_216px_reflow": automatic_reflow,
                })
                continue
            accepted_events.append(event_id)
            formatter_candidate_count += 1
            if event_id != "05F8":
                complete_aligned_count += 1
            translations_by_event[event_id] = values
            reports_by_event[event_id] = [{
                "event_id": event_id,
                "snes_ids": list(values),
                "android_ids": redistribution_meta[event_id]["android_ids"],
                "confidence": "user_validated_scene_semantic_redistribution",
                "round68_user_validated_android_fr_scene": True,
                "android_identity_count_changed": False,
                "note": "Keep the original Android-FR scene semantics verbatim; only SNES carriers/pages and translated-only dynamic PLAYER_NAME placement are redistributed.",
                "formatted_entries": [{"id": k, "text": v} for k, v in values.items()],
                "automatic_216px_reflow": automatic_reflow,
            }]
            continue

        if event_id in round69_events:
            values = dict(redistribution_values[event_id])
            # Coverage repairs must also apply to reviewed Round-69 redistribution
            # events. Previously this special branch continued before the generic
            # repair stage, so the Round-85 $0559 Android 2151..2155 extension was
            # present only in a pre-generated JSON and vanished on regeneration.
            round69_coverage_reports = _apply_dialogue_coverage_repairs(
                event_id, values, coverage_repair_recipes, french, advances
            )
            values, automatic_reflow = _auto_reflow_fixed_translation_carriers(values, advances)
            canonical_ids = {
                token.get("id") for token in event["tokens"]
                if token.get("type") in {"text", "ending_text"}
            }
            unknown = sorted(set(values) - canonical_ids)
            if unknown:
                raise ValueError(f"Round-69 ${event_id} unknown carrier(s): {unknown}")
            structural_overrides = structural_command_overrides_by_event.get(event_id)
            simulation = simulate_event(
                base_rom, event, values, font=font,
                player_names={0: "000000000", 1: "000000000", 2: "000000000"},
                structural_command_overrides=structural_overrides,
            )
            blocking = [issue for issue in simulation.issues if issue.severity in {"error", "warning"}]
            wraps = sum(
                line.implicit_wrap
                for box in simulation.boxes for page in box.pages for line in page.lines
            )
            if blocking or wraps:
                candidate_values, candidate_simulation, boundary_repairs = _try_single_carrier_boundary_newline(
                    base_rom=base_rom, event=event, translations=values, font=font,
                    structural_command_overrides=structural_overrides,
                )
                if boundary_repairs:
                    values = candidate_values
                    simulation = candidate_simulation
                    blocking = []
                    wraps = 0
                    carrier_boundary_newline_repairs_by_event[event_id] = boundary_repairs
            if blocking or wraps:
                repacked_values, repack_repairs = _repack_fixed_translation_carriers(
                    dict(redistribution_values[event_id]), advances
                )
                try:
                    repacked_simulation = simulate_event(
                        base_rom, event, repacked_values, font=font,
                        player_names={0: "000000000", 1: "000000000", 2: "000000000"},
                        structural_command_overrides=structural_overrides,
                    )
                except ValueError:
                    repacked_simulation = None
                if repacked_simulation is not None and _simulation_blocking_score(repacked_simulation)[0] == 0:
                    values = repacked_values
                    simulation = repacked_simulation
                    blocking = []
                    wraps = 0
                    carrier_repack_repairs_by_event[event_id] = repack_repairs
                elif repacked_simulation is not None:
                    candidate_values, candidate_simulation, boundary_repairs = _try_single_carrier_boundary_newline(
                        base_rom=base_rom, event=event, translations=repacked_values, font=font,
                        structural_command_overrides=structural_overrides,
                    )
                    if boundary_repairs:
                        values = candidate_values
                        simulation = candidate_simulation
                        blocking = []
                        wraps = 0
                        carrier_repack_repairs_by_event[event_id] = repack_repairs
                        carrier_boundary_newline_repairs_by_event[event_id] = boundary_repairs
            if blocking or wraps:
                reviewed_values, reviewed_simulation, reviewed_repairs = _apply_reviewed_layout_search_recipe(
                    base_rom=base_rom, event=event, translations=values, font=font,
                    structural_command_overrides=structural_overrides,
                )
                if reviewed_repairs:
                    values = reviewed_values
                    simulation = reviewed_simulation
                    blocking = []
                    wraps = 0
                    source_derived_layout_search_repairs_by_event[event_id] = reviewed_repairs
            if blocking or wraps:
                searched_values, searched_simulation, search_repairs = _try_source_derived_layout_search(
                    base_rom=base_rom, event=event, translations=values, font=font,
                    structural_command_overrides=structural_overrides,
                )
                if search_repairs:
                    values = searched_values
                    simulation = searched_simulation
                    blocking = []
                    wraps = 0
                    source_derived_layout_search_repairs_by_event[event_id] = search_repairs
            if blocking or wraps:
                excluded_events.append({
                    "event_id": event_id,
                    "stage": "reviewed_redistribution_automatic_reflow",
                    "reason": "automatic_216px_reflow_not_simulator_clean",
                    "reviewed_redistribution_round": 69,
                    "blocking_issue_codes": [issue.code for issue in blocking],
                    "blocking_issue_messages": [issue.message for issue in blocking[:8]],
                    "implicit_wraps": wraps,
                    "automatic_216px_reflow": automatic_reflow,
                })
                continue
            accepted_events.append(event_id)
            formatter_candidate_count += 1
            complete_aligned_count += 1
            translations_by_event[event_id] = values
            base_round69_report = {
                "event_id": event_id,
                "snes_ids": list(values),
                "android_ids": redistribution_meta[event_id]["android_ids"],
                "confidence": "user_authorized_targeted_scene_redistribution",
                "round69_targeted_redistribution": True,
                "android_identity_count_changed": False,
                "note": "Reviewed Android-FR/SNES resegmentation; no new weak Android identity is created.",
                "formatted_entries": [{"id": k, "text": v} for k, v in values.items()],
                "automatic_216px_reflow": automatic_reflow,
            }
            # Refresh coverage-report payloads after reflow so the report proves
            # the exact final generated value, not a pre-reflow intermediate.
            for coverage_report in round69_coverage_reports:
                coverage_report["formatted_entries"] = [
                    {"id": sid, "text": values.get(sid, "")}
                    for sid in coverage_report.get("snes_ids", [])
                ]
            reports_by_event[event_id] = [base_round69_report, *round69_coverage_reports]
            continue

        event_mappings = mappings_by_event.get(event_id, [])
        event_mappings, duplicated_player_context_repairs = (
            _strip_duplicated_trailing_player_context(
                event, event_mappings, base_rom=base_rom
            )
        )
        duplicated_player_context_repairs_by_event[event_id] = (
            duplicated_player_context_repairs
        )
        mapped_ids: set[str] = set()
        for mapping in event_mappings:
            mapped_ids.update(mapping["snes_ids"])
        mapped_ids.update(
            recipe["carrier_id"] for recipe in coverage_repair_recipes.get(event_id, [])
            if recipe["mode"] == "replace"
        )
        mapped_ids.update(
            clear_id
            for recipe in coverage_repair_recipes.get(event_id, [])
            for clear_id in recipe.get("clear_carrier_ids", [])
        )
        missing_ids = [text_id for text_id in semantic_ids if text_id not in mapped_ids]
        if missing_ids:
            excluded_events.append(
                {
                    "event_id": event_id,
                    "stage": "alignment_incomplete",
                    "semantic_ids": semantic_ids,
                    "missing_semantic_ids": missing_ids,
                    "details": [
                        {
                            "snes_id": text_id,
                            "reason": unmapped_by_id.get(text_id, {}).get("reason", "no accepted automatic mapping"),
                            "note": unmapped_by_id.get(text_id, {}).get("note", ""),
                        }
                        for text_id in missing_ids
                    ],
                }
            )
            continue
        complete_aligned_count += 1

        event_translations: dict[str, str] = {}
        event_reports: list[dict] = []
        formatter_errors: list[dict] = []
        complete_layout_deferred_ids: list[str] = []
        for mapping in event_mappings:
            if mapping.get("relation") == "shared_called_tail_combined_anchor":
                formatter_errors.append({
                    "snes_ids": mapping.get("snes_ids", []),
                    "android_ids": mapping.get("android_ids", []),
                    "message": (
                        "reviewed shared-tail identity: Android anchor combines text "
                        "owned by a called SNES event; keep carrier stock to avoid duplicate insertion"
                    ),
                })
                continue
            try:
                values, mapping_report = _format_mass_mapping(
                    source_document,
                    mapping,
                    advances,
                    base_rom=base_rom,
                    french=french,
                    prefer_semantic_line_breaks=True,
                )
            except ValueError as exc:
                message = str(exc)
                reviewed_defer_note = _reviewed_partial_layout_defer(
                    event_id, mapping, message
                )
                generic_defer = _partial_layout_deferable_formatter_error(message)
                if reviewed_defer_note is not None or generic_defer:
                    deferred = list(mapping.get("snes_ids", []))
                    complete_layout_deferred_ids.extend(deferred)
                    if generic_defer and reviewed_defer_note is None:
                        generic_layout_deferred_semantic_ids_by_event.setdefault(event_id, []).extend(deferred)
                    event_reports.append({
                        "event_id": event_id,
                        "snes_ids": deferred,
                        "android_ids": mapping.get("android_ids", []),
                        "confidence": mapping.get("confidence"),
                        "partial_event": True,
                        "layout_deferred": True,
                        "layout_deferred_formatter_error": message,
                        "layout_deferred_policy": (
                            "reviewed_exact" if reviewed_defer_note is not None
                            else "generic_structural_safe_subset"
                        ),
                        "reviewed_partial_layout_defer_note": reviewed_defer_note,
                        "formatted_entries": [],
                    })
                    continue
                formatter_errors.append(
                    {
                        "snes_ids": mapping.get("snes_ids", []),
                        "android_ids": mapping.get("android_ids", []),
                        "message": str(exc),
                    }
                )
                continue
            values, mapping_report, trailing_transition_repairs = _collapse_trailing_page_break_into_stock_transition(
                source_document, mapping, values, mapping_report
            )
            if _mapping_has_unserializable_trailing_page_break(
                source_document, mapping, values
            ):
                # A generated page transition that is not one of the two
                # serializer-proven choice shapes would require structural
                # rebinding. Keep this entire mapped carrier stock and let the
                # same direct PARTIEL simulation gate decide the event.
                deferred = list(mapping.get("snes_ids", []))
                complete_layout_deferred_ids.extend(deferred)
                generic_layout_deferred_semantic_ids_by_event.setdefault(event_id, []).extend(deferred)
                event_reports.append({
                    "event_id": event_id,
                    "snes_ids": deferred,
                    "android_ids": mapping.get("android_ids", []),
                    "confidence": mapping.get("confidence"),
                    "partial_event": True,
                    "layout_deferred": True,
                    "layout_deferred_formatter_error": "generated trailing page break is not serializable in the canonical command shape",
                    "layout_deferred_policy": "generic_structural_safe_subset",
                    "formatted_entries": [],
                })
                continue
            duplicate = sorted(set(values) & set(event_translations))
            if duplicate:
                formatter_errors.append(
                    {
                        "snes_ids": mapping.get("snes_ids", []),
                        "android_ids": mapping.get("android_ids", []),
                        "message": f"formatter generated duplicate translated source IDs: {duplicate}",
                    }
                )
                continue
            event_translations.update(values)
            event_reports.append(mapping_report)

        coverage_reports = _apply_dialogue_coverage_repairs(
            event_id, event_translations, coverage_repair_recipes, french, advances
        )
        if coverage_reports:
            event_reports.extend(coverage_reports)

        if event_id == "04E2":
            round67_reports, _ = _apply_reviewed_scene_redistributions(
                event, event_translations, english=english, redistribution_values=redistribution_values,
                layout_deferred_ids=complete_layout_deferred_ids, missing_ids=[],
            )
            event_reports = [
                report for report in event_reports
                if not (report.get("layout_deferred") and {"CA:32C5", "CA:32D7"}.intersection(report.get("snes_ids", [])))
            ]
            generic_layout_deferred_semantic_ids_by_event[event_id] = [
                x for x in generic_layout_deferred_semantic_ids_by_event.get(event_id, [])
                if x not in {"CA:32C5", "CA:32D7"}
            ]
            event_reports.extend(round67_reports)

        if formatter_errors:
            excluded_events.append(
                {
                    "event_id": event_id,
                    "stage": "formatter_rejected",
                    "semantic_ids": semantic_ids,
                    "missing_semantic_ids": [],
                    "details": formatter_errors,
                }
            )
            continue
        if complete_layout_deferred_ids and not event_translations:
            excluded_events.append(
                {
                    "event_id": event_id,
                    "stage": "formatter_rejected",
                    "semantic_ids": semantic_ids,
                    "missing_semantic_ids": [],
                    "details": [
                        {
                            "snes_ids": sorted(set(complete_layout_deferred_ids)),
                            "android_ids": [],
                            "message": (
                                "all mapped carriers require structural layout deferral; "
                                "PARTIEL would release no French text"
                            ),
                        }
                    ],
                }
            )
            continue
        formatter_candidate_count += 1

        fragment_spacing_repairs_by_event[event_id] = _apply_user_reviewed_fragment_spacing(
            event_id, event_translations
        )
        targeted_wait00_fresh_page_repairs_by_event[event_id] = _apply_targeted_wait00_fresh_page_clear(
            event_id, event_translations
        )
        explicit_post_wait_newline_repairs_by_event[event_id] = _apply_explicit_post_wait_newlines(
            event_id, event_translations, source_text_by_id=source_text_by_id
        )
        round48_pagination_repairs_by_event[event_id] = _apply_0127_reviewed_pagination(
            event, event_translations
        )
        round49_04e9_wait00_clear_repairs_by_event[event_id] = _apply_04e9_reviewed_wait00_clears(
            event, event_translations
        )
        round50_01ce_choice_page_clear_repairs_by_event[event_id] = _apply_01ce_reviewed_choice_page_clear(
            event, event_translations
        )
        # Final presentation-only pass: legacy/manual/redistributed inserts may
        # have bypassed the ordinary mapping wrapper. Reflow each existing
        # carrier line to the current 216px / 38-unit contract before the
        # independent simulator decides whether the event remains admissible.
        event_translations, automatic_reflow = _auto_reflow_fixed_translation_carriers(
            event_translations, advances
        )
        automatic_216px_reflows_by_event[event_id] = automatic_reflow
        direct_subset_translations = dict(event_translations)
        direct_subset_reports = [dict(report) for report in event_reports]
        if complete_layout_deferred_ids:
            # Generic structural safe-subset PARTIEL gets no adaptive/compact
            # rescue. The remaining mapped French must be clean exactly as
            # formatted while every deferred carrier and every stock command
            # stays untouched.
            try:
                simulation = simulate_event(
                    base_rom,
                    event,
                    event_translations,
                    font=font,
                    player_names={0: "000000000", 1: "000000000", 2: "000000000"},
                    structural_command_overrides=structural_command_overrides_by_event.get(event_id),
                )
            except ValueError as exc:
                excluded_events.append(
                    {
                        "event_id": event_id,
                        "stage": "simulator_rejected",
                        "semantic_ids": semantic_ids,
                        "missing_semantic_ids": [],
                        "details": [{"message": f"direct PARTIEL simulation failed: {exc}"}],
                    }
                )
                continue
            blocking_issues = [
                issue for issue in simulation.issues
                if issue.severity in {"error", "warning"}
            ]
            implicit_wraps = sum(
                line.implicit_wrap
                for box in simulation.boxes
                for page in box.pages
                for line in page.lines
            )
            if blocking_issues or implicit_wraps:
                (
                    subset_translations,
                    subset_reports,
                    subset_simulation,
                    subset_deferred_reports,
                ) = _try_direct_simulator_safe_subset(
                    base_rom=base_rom,
                    event=event,
                    event_mappings=event_mappings,
                    translations=event_translations,
                    reports=event_reports,
                    font=font,
                    structural_command_overrides=structural_command_overrides_by_event.get(event_id),
                    max_deferred_mappings=3,
                )
                if subset_deferred_reports:
                    extra_deferred_ids = sorted({
                        text_id
                        for report in subset_deferred_reports
                        for text_id in report.get("snes_ids", [])
                    })
                    all_deferred_ids = sorted(set(complete_layout_deferred_ids) | set(extra_deferred_ids))
                    accepted_events.append(event_id)
                    partial_accepted_events.append(event_id)
                    partial_unresolved_semantic_ids_by_event[event_id] = all_deferred_ids
                    partial_layout_deferred_semantic_ids_by_event[event_id] = all_deferred_ids
                    partial_suppression_reason_by_event[event_id] = "mapped_but_direct_simulator_deferred"
                    translations_by_event[event_id] = subset_translations
                    reports_by_event[event_id] = subset_reports
                    wait00_repairs_by_event[event_id] = []
                    unpaused_scroll_repairs_by_event[event_id] = []
                    cross_mapping_sentence_repairs_by_event[event_id] = []
                    structural_reaction_page_repairs_by_event[event_id] = []
                    continue
                details = [
                    {
                        "severity": issue.severity,
                        "code": issue.code,
                        "message": issue.message,
                        "box": issue.box,
                        "page": issue.page,
                        "line": issue.line,
                    }
                    for issue in blocking_issues
                ]
                if implicit_wraps and not any(
                    detail.get("code") in {"IMPLICIT_RUNTIME_WRAP", "IMPLICIT_RUNTIME_HARD_WRAP"}
                    for detail in details
                ):
                    details.append({
                        "severity": "error",
                        "code": "IMPLICIT_RUNTIME_WRAP_SUMMARY",
                        "message": f"simulator recorded {implicit_wraps} implicit runtime wrap(s)",
                    })
                excluded_events.append(
                    {
                        "event_id": event_id,
                        "stage": "simulator_rejected",
                        "semantic_ids": semantic_ids,
                        "missing_semantic_ids": [],
                        "details": details,
                    }
                )
                continue
            accepted_events.append(event_id)
            partial_accepted_events.append(event_id)
            deferred_ids = sorted(set(complete_layout_deferred_ids))
            partial_unresolved_semantic_ids_by_event[event_id] = deferred_ids
            partial_layout_deferred_semantic_ids_by_event[event_id] = deferred_ids
            partial_suppression_reason_by_event[event_id] = "mapped_but_layout_deferred"
            translations_by_event[event_id] = event_translations
            reports_by_event[event_id] = event_reports
            wait00_repairs_by_event[event_id] = []
            unpaused_scroll_repairs_by_event[event_id] = []
            cross_mapping_sentence_repairs_by_event[event_id] = []
            structural_reaction_page_repairs_by_event[event_id] = []
            continue

        try:
            event_translations, simulation, wait00_repairs = _repair_wait00_page_overlaps(
                base_rom=base_rom,
                event=event,
                translations=event_translations,
                font=font,
            )
        except ValueError as exc:
            excluded_events.append(
                {
                    "event_id": event_id,
                    "stage": "formatter_rejected",
                    "semantic_ids": semantic_ids,
                    "missing_semantic_ids": [],
                    "details": [
                        {
                            "snes_ids": [],
                            "android_ids": [],
                            "message": f"serialized layout rejected before simulation: {exc}",
                        }
                    ],
                }
            )
            continue
        (
            event_translations,
            event_reports,
            simulation,
            live_line_compact_repairs,
        ) = _repair_live_line_scroll_risk_with_compact_wrap(
            base_rom=base_rom,
            source_document=source_document,
            event=event,
            event_mappings=event_mappings,
            translations=event_translations,
            reports=event_reports,
            advances=advances,
            french=french,
            font=font,
            simulation=simulation,
        )
        live_line_compact_repairs_by_event[event_id] = live_line_compact_repairs
        if event_id in reviewed_choice_layout_recipes:
            (
                event_translations,
                event_reports,
                simulation,
                reviewed_row_repairs,
                reviewed_decoration_repairs,
                reviewed_compact_repairs,
            ) = _apply_reviewed_choice_layout_recipe(
                base_rom=base_rom,
                source_document=source_document,
                event=event,
                event_mappings=event_mappings,
                translations=event_translations,
                reports=event_reports,
                advances=advances,
                french=french,
                font=font,
                simulation=simulation,
                recipe=reviewed_choice_layout_recipes[event_id],
            )
            if reviewed_row_repairs:
                choice_row_layout_repairs_by_event[event_id] = reviewed_row_repairs
            if reviewed_decoration_repairs:
                adaptive_choice_decoration_repairs_by_event[event_id] = reviewed_decoration_repairs
            if reviewed_compact_repairs:
                reviewed_choice_compact_repairs_by_event[event_id] = reviewed_compact_repairs
        unpaused_scroll_repairs: list[dict] = []
        cross_mapping_sentence_repairs: list[dict] = []
        blocking_issues = [
            issue
            for issue in simulation.issues
            if issue.severity in {"error", "warning"}
        ]
        implicit_wraps = sum(
            line.implicit_wrap
            for box in simulation.boxes
            for page in box.pages
            for line in page.lines
        )
        if blocking_issues or implicit_wraps:
            (
                event_translations,
                event_reports,
                simulation,
                choice_row_layout_repairs,
            ) = _try_restore_stock_choice_row_prefix(
                base_rom=base_rom,
                event=event,
                translations=event_translations,
                reports=event_reports,
                font=font,
                simulation=simulation,
            )
            if choice_row_layout_repairs:
                choice_row_layout_repairs_by_event[event_id] = choice_row_layout_repairs
                blocking_issues = [
                    issue for issue in simulation.issues
                    if issue.severity in {"error", "warning"}
                ]
                implicit_wraps = sum(
                    line.implicit_wrap
                    for box in simulation.boxes
                    for page in box.pages
                    for line in page.lines
                )
        if blocking_issues or implicit_wraps:
            (
                anchor_simulation,
                anchor_overrides,
                anchor_repairs,
            ) = _try_adaptive_choice_anchor_positions(
                base_rom=base_rom,
                event=event,
                translations=event_translations,
                advances=advances,
                font=font,
                simulation=simulation,
            )
            if anchor_repairs:
                simulation = anchor_simulation
                choice_option_position_overrides_by_event[event_id] = anchor_overrides
                adaptive_choice_anchor_repairs_by_event[event_id] = anchor_repairs
                blocking_issues = []
                implicit_wraps = 0
        if blocking_issues or implicit_wraps:
            (
                event_translations,
                event_reports,
                simulation,
                choice_decoration_repairs,
            ) = _try_adaptive_choice_decoration(
                base_rom=base_rom,
                event=event,
                translations=event_translations,
                reports=event_reports,
                font=font,
                simulation=simulation,
            )
            if choice_decoration_repairs:
                adaptive_choice_decoration_repairs_by_event[event_id] = choice_decoration_repairs
                blocking_issues = []
                implicit_wraps = 0
        if blocking_issues or implicit_wraps:
            (
                decorated_translations,
                decorated_reports,
                decorated_simulation,
                choice_decoration_repairs,
                decorated_anchor_overrides,
                decorated_anchor_repairs,
            ) = _try_adaptive_choice_decoration_with_anchor_positions(
                base_rom=base_rom,
                event=event,
                translations=event_translations,
                reports=event_reports,
                advances=advances,
                font=font,
                simulation=simulation,
            )
            if choice_decoration_repairs and decorated_anchor_repairs:
                event_translations = decorated_translations
                event_reports = decorated_reports
                simulation = decorated_simulation
                adaptive_choice_decoration_repairs_by_event[event_id] = choice_decoration_repairs
                choice_option_position_overrides_by_event[event_id] = decorated_anchor_overrides
                adaptive_choice_anchor_repairs_by_event[event_id] = decorated_anchor_repairs
                blocking_issues = []
                implicit_wraps = 0
        if blocking_issues or implicit_wraps:
            # Semantic wrapping is a presentation preference, never a reason to
            # lose an otherwise safe translated event. Retry the whole event
            # with the compact validated wrapper; accept that fallback only if
            # the independent simulator is completely clean.
            compact_translations: dict[str, str] = {}
            compact_reports: list[dict] = []
            compact_errors: list[dict] = []
            for mapping in event_mappings:
                try:
                    values, mapping_report = _format_mass_mapping(
                        source_document,
                        mapping,
                        advances,
                        base_rom=base_rom,
                        french=french,
                        prefer_semantic_line_breaks=False,
                    )
                except ValueError as exc:
                    compact_errors.append({"message": str(exc)})
                    break
                duplicate = sorted(set(values) & set(compact_translations))
                if duplicate:
                    compact_errors.append({"message": f"compact fallback duplicate IDs: {duplicate}"})
                    break
                compact_translations.update(values)
                mapping_report["semantic_layout_fallback"] = True
                compact_reports.append(mapping_report)

            if not compact_errors:
                _apply_targeted_wait00_fresh_page_clear(event_id, compact_translations)
                _apply_explicit_post_wait_newlines(
                    event_id, compact_translations, source_text_by_id=source_text_by_id
                )
                compact_translations, compact_simulation, compact_wait00_repairs = _repair_wait00_page_overlaps(
                    base_rom=base_rom,
                    event=event,
                    translations=compact_translations,
                    font=font,
                )
                (
                    compact_translations,
                    compact_simulation,
                    compact_post_wait_sentence_repairs,
                ) = _repair_unique_post_wait_sentence_newline(
                    base_rom=base_rom,
                    event=event,
                    translations=compact_translations,
                    font=font,
                    simulation=compact_simulation,
                )
                compact_blocking = [
                    issue for issue in compact_simulation.issues
                    if issue.severity in {"error", "warning"}
                ]
                compact_wraps = sum(
                    line.implicit_wrap
                    for box in compact_simulation.boxes
                    for page in box.pages
                    for line in page.lines
                )
                if compact_blocking or compact_wraps:
                    (
                        compact_translations,
                        compact_reports,
                        compact_simulation,
                        compact_choice_row_layout_repairs,
                    ) = _try_restore_stock_choice_row_prefix(
                        base_rom=base_rom,
                        event=event,
                        translations=compact_translations,
                        reports=compact_reports,
                        font=font,
                        simulation=compact_simulation,
                    )
                    if compact_choice_row_layout_repairs:
                        choice_row_layout_repairs_by_event[event_id] = compact_choice_row_layout_repairs
                        compact_blocking = [
                            issue for issue in compact_simulation.issues
                            if issue.severity in {"error", "warning"}
                        ]
                        compact_wraps = sum(
                            line.implicit_wrap
                            for box in compact_simulation.boxes
                            for page in box.pages
                            for line in page.lines
                        )
                if compact_blocking or compact_wraps:
                    (
                        compact_anchor_simulation,
                        compact_anchor_overrides,
                        compact_anchor_repairs,
                    ) = _try_adaptive_choice_anchor_positions(
                        base_rom=base_rom,
                        event=event,
                        translations=compact_translations,
                        advances=advances,
                        font=font,
                        simulation=compact_simulation,
                    )
                    if compact_anchor_repairs:
                        compact_simulation = compact_anchor_simulation
                        choice_option_position_overrides_by_event[event_id] = compact_anchor_overrides
                        adaptive_choice_anchor_repairs_by_event[event_id] = compact_anchor_repairs
                        compact_blocking = []
                        compact_wraps = 0
                if compact_blocking or compact_wraps:
                    (
                        compact_translations,
                        compact_reports,
                        compact_simulation,
                        compact_choice_decoration_repairs,
                    ) = _try_adaptive_choice_decoration(
                        base_rom=base_rom,
                        event=event,
                        translations=compact_translations,
                        reports=compact_reports,
                        font=font,
                        simulation=compact_simulation,
                    )
                    if compact_choice_decoration_repairs:
                        adaptive_choice_decoration_repairs_by_event[event_id] = compact_choice_decoration_repairs
                        compact_blocking = []
                        compact_wraps = 0
                if compact_blocking or compact_wraps:
                    (
                        compact_decorated_translations,
                        compact_decorated_reports,
                        compact_decorated_simulation,
                        compact_choice_decoration_repairs,
                        compact_decorated_anchor_overrides,
                        compact_decorated_anchor_repairs,
                    ) = _try_adaptive_choice_decoration_with_anchor_positions(
                        base_rom=base_rom,
                        event=event,
                        translations=compact_translations,
                        reports=compact_reports,
                        advances=advances,
                        font=font,
                        simulation=compact_simulation,
                    )
                    if compact_choice_decoration_repairs and compact_decorated_anchor_repairs:
                        compact_translations = compact_decorated_translations
                        compact_reports = compact_decorated_reports
                        compact_simulation = compact_decorated_simulation
                        adaptive_choice_decoration_repairs_by_event[event_id] = compact_choice_decoration_repairs
                        choice_option_position_overrides_by_event[event_id] = compact_decorated_anchor_overrides
                        adaptive_choice_anchor_repairs_by_event[event_id] = compact_decorated_anchor_repairs
                        compact_blocking = []
                        compact_wraps = 0
                if not compact_blocking and not compact_wraps:
                    accepted_events.append(event_id)
                    translations_by_event[event_id] = compact_translations
                    reports_by_event[event_id] = compact_reports
                    wait00_repairs_by_event[event_id] = compact_wait00_repairs
                    if compact_post_wait_sentence_repairs:
                        explicit_post_wait_newline_repairs_by_event.setdefault(event_id, []).extend(
                            compact_post_wait_sentence_repairs
                        )
                    unpaused_scroll_repairs_by_event[event_id] = []
                    cross_mapping_sentence_repairs_by_event[event_id] = []
                    continue

            # Preserve every event that the historical compact fallback can
            # already save byte-for-byte. Only after that path fails may a
            # pure four-line rolling-window overflow receive one additional
            # semantic page break.
            (
                repaired_translations,
                repaired_reports,
                repaired_simulation,
                unpaused_scroll_repairs,
            ) = _repair_pure_unpaused_scroll(
                base_rom=base_rom,
                source_document=source_document,
                event=event,
                event_mappings=event_mappings,
                translations=event_translations,
                reports=event_reports,
                advances=advances,
                font=font,
                simulation=simulation,
            )
            if unpaused_scroll_repairs:
                accepted_events.append(event_id)
                translations_by_event[event_id] = repaired_translations
                reports_by_event[event_id] = repaired_reports
                wait00_repairs_by_event[event_id] = wait00_repairs
                unpaused_scroll_repairs_by_event[event_id] = unpaused_scroll_repairs
                cross_mapping_sentence_repairs_by_event[event_id] = []
                continue

            (
                repaired_translations,
                repaired_reports,
                repaired_simulation,
                cross_mapping_sentence_repairs,
            ) = _repair_cross_mapping_sentence_overflow(
                base_rom=base_rom,
                source_document=source_document,
                event=event,
                event_mappings=event_mappings,
                translations=event_translations,
                reports=event_reports,
                advances=advances,
                font=font,
                simulation=simulation,
            )
            if cross_mapping_sentence_repairs:
                accepted_events.append(event_id)
                translations_by_event[event_id] = repaired_translations
                reports_by_event[event_id] = repaired_reports
                wait00_repairs_by_event[event_id] = wait00_repairs
                unpaused_scroll_repairs_by_event[event_id] = []
                cross_mapping_sentence_repairs_by_event[event_id] = (
                    cross_mapping_sentence_repairs
                )
                structural_reaction_page_repairs_by_event[event_id] = []
                continue

            (
                reaction_translations,
                reaction_reports,
                reaction_simulation,
                reaction_repairs,
            ) = _repair_structural_reaction_page_boundary(
                base_rom=base_rom,
                source_document=source_document,
                event=event,
                event_mappings=event_mappings,
                translations=event_translations,
                reports=event_reports,
                advances=advances,
                font=font,
                simulation=simulation,
            )
            if reaction_repairs:
                accepted_events.append(event_id)
                translations_by_event[event_id] = reaction_translations
                reports_by_event[event_id] = reaction_reports
                wait00_repairs_by_event[event_id] = wait00_repairs
                unpaused_scroll_repairs_by_event[event_id] = []
                cross_mapping_sentence_repairs_by_event[event_id] = []
                structural_reaction_page_repairs_by_event[event_id] = reaction_repairs
                continue

            (
                boundary_translations,
                boundary_simulation,
                boundary_repairs,
            ) = _try_single_carrier_boundary_newline(
                base_rom=base_rom,
                event=event,
                translations=event_translations,
                font=font,
                structural_command_overrides=structural_command_overrides_by_event.get(event_id),
            )
            if boundary_repairs:
                accepted_events.append(event_id)
                translations_by_event[event_id] = boundary_translations
                reports_by_event[event_id] = event_reports
                wait00_repairs_by_event[event_id] = wait00_repairs
                unpaused_scroll_repairs_by_event[event_id] = []
                cross_mapping_sentence_repairs_by_event[event_id] = []
                structural_reaction_page_repairs_by_event[event_id] = []
                carrier_boundary_newline_repairs_by_event[event_id] = boundary_repairs
                continue

            reviewed_translations, reviewed_simulation, reviewed_repairs = _apply_reviewed_layout_search_recipe(
                base_rom=base_rom,
                event=event,
                translations=event_translations,
                font=font,
                structural_command_overrides=structural_command_overrides_by_event.get(event_id),
            )
            if reviewed_repairs:
                accepted_events.append(event_id)
                translations_by_event[event_id] = reviewed_translations
                reports_by_event[event_id] = event_reports
                wait00_repairs_by_event[event_id] = wait00_repairs
                unpaused_scroll_repairs_by_event[event_id] = []
                cross_mapping_sentence_repairs_by_event[event_id] = []
                structural_reaction_page_repairs_by_event[event_id] = []
                source_derived_layout_search_repairs_by_event[event_id] = reviewed_repairs
                continue

            searched_translations, searched_simulation, search_repairs = _try_source_derived_layout_search(
                base_rom=base_rom,
                event=event,
                translations=event_translations,
                font=font,
                structural_command_overrides=structural_command_overrides_by_event.get(event_id),
            )
            if search_repairs:
                accepted_events.append(event_id)
                translations_by_event[event_id] = searched_translations
                reports_by_event[event_id] = event_reports
                wait00_repairs_by_event[event_id] = wait00_repairs
                unpaused_scroll_repairs_by_event[event_id] = []
                cross_mapping_sentence_repairs_by_event[event_id] = []
                structural_reaction_page_repairs_by_event[event_id] = []
                source_derived_layout_search_repairs_by_event[event_id] = search_repairs
                continue

            page_translations, page_simulation, page_repairs = _try_unpaused_scroll_page_repairs(
                base_rom=base_rom,
                event=event,
                translations=event_translations,
                font=font,
                structural_command_overrides=structural_command_overrides_by_event.get(event_id),
            )
            if page_repairs:
                accepted_events.append(event_id)
                translations_by_event[event_id] = page_translations
                reports_by_event[event_id] = event_reports
                wait00_repairs_by_event[event_id] = wait00_repairs
                unpaused_scroll_repairs_by_event[event_id] = []
                cross_mapping_sentence_repairs_by_event[event_id] = []
                structural_reaction_page_repairs_by_event[event_id] = []
                source_derived_layout_search_repairs_by_event[event_id] = page_repairs
                continue

            (
                subset_translations,
                subset_reports,
                subset_simulation,
                subset_deferred_reports,
            ) = _try_direct_simulator_safe_subset(
                base_rom=base_rom,
                event=event,
                event_mappings=event_mappings,
                translations=direct_subset_translations,
                reports=direct_subset_reports,
                font=font,
                structural_command_overrides=structural_command_overrides_by_event.get(event_id),
                max_deferred_mappings=3,
            )
            if subset_deferred_reports:
                deferred_ids = sorted({
                    text_id
                    for report in subset_deferred_reports
                    for text_id in report.get("snes_ids", [])
                })
                accepted_events.append(event_id)
                partial_accepted_events.append(event_id)
                partial_unresolved_semantic_ids_by_event[event_id] = deferred_ids
                partial_layout_deferred_semantic_ids_by_event[event_id] = deferred_ids
                partial_suppression_reason_by_event[event_id] = "mapped_but_direct_simulator_deferred"
                translations_by_event[event_id] = subset_translations
                reports_by_event[event_id] = subset_reports
                wait00_repairs_by_event[event_id] = []
                unpaused_scroll_repairs_by_event[event_id] = []
                cross_mapping_sentence_repairs_by_event[event_id] = []
                structural_reaction_page_repairs_by_event[event_id] = []
                continue

            # If newly reviewed structural mappings are correct semantically but
            # still cannot be laid out safely, preserve the previous French-only
            # PARTIEL behavior instead of losing the whole event. Only mappings
            # that predate the current structural reviews are rendered; every newly
            # reviewed semantic token is explicitly suppressed and the direct result
            # must simulate cleanly.
            structural_review = [
                m for m in event_mappings
                if m.get("provenance") in {"round6", "round7", "round8", "round11", "round18", "round20", "round21", "round22", "round25"}
            ]
            baseline = [
                m for m in event_mappings
                if m.get("provenance") not in {"round6", "round7", "round8", "round11", "round18", "round20", "round21", "round22", "round25"}
            ]
            if structural_review and baseline:
                partial_translations: dict[str, str] = {}
                partial_reports: list[dict] = []
                partial_failed = False
                for baseline_mapping in baseline:
                    try:
                        values, mapping_report = _format_mass_mapping(
                            source_document,
                            baseline_mapping,
                            advances,
                            base_rom=base_rom,
                            french=french,
                            prefer_semantic_line_breaks=True,
                        )
                    except ValueError:
                        partial_failed = True
                        break
                    if set(values) & set(partial_translations):
                        partial_failed = True
                        break
                    partial_translations.update(values)
                    mapping_report = dict(mapping_report)
                    mapping_report["partial_event"] = True
                    partial_reports.append(mapping_report)
                suppressed = sorted({
                    text_id
                    for structural_mapping in structural_review
                    for text_id in structural_mapping.get("snes_ids", [])
                })
                # Keep layout-deferred mapped carriers absent from the sparse
                # French translation map so their stock SNES English remains
                # visible in a PARTIEL event.
                targeted_wait00_fresh_page_repairs_by_event[event_id] = _apply_targeted_wait00_fresh_page_clear(
                    event_id, partial_translations
                )
                explicit_post_wait_newline_repairs_by_event[event_id] = _apply_explicit_post_wait_newlines(
                    event_id, partial_translations, source_text_by_id=source_text_by_id
                )
                if not partial_failed and partial_reports:
                    try:
                        partial_simulation = simulate_event(
                            base_rom,
                            event,
                            partial_translations,
                            font=font,
                            player_names={0: "000000000", 1: "000000000", 2: "000000000"},
                        )
                    except ValueError:
                        partial_simulation = None
                    if partial_simulation is not None:
                        partial_blocking = [
                            i for i in partial_simulation.issues
                            if i.severity in {"error", "warning"}
                        ]
                        partial_wraps = sum(
                            line.implicit_wrap
                            for box in partial_simulation.boxes
                            for page in box.pages
                            for line in page.lines
                        )
                        if not partial_blocking and not partial_wraps:
                            accepted_events.append(event_id)
                            partial_accepted_events.append(event_id)
                            partial_unresolved_semantic_ids_by_event[event_id] = suppressed
                            partial_suppression_reason_by_event[event_id] = "mapped_but_layout_deferred"
                            translations_by_event[event_id] = partial_translations
                            reports_by_event[event_id] = partial_reports
                            wait00_repairs_by_event[event_id] = []
                            unpaused_scroll_repairs_by_event[event_id] = []
                            cross_mapping_sentence_repairs_by_event[event_id] = []
                            structural_reaction_page_repairs_by_event[event_id] = []
                            continue

            details = [
                {
                    "severity": issue.severity,
                    "code": issue.code,
                    "message": issue.message,
                    "box": issue.box,
                    "page": issue.page,
                    "line": issue.line,
                }
                for issue in blocking_issues
            ]
            if implicit_wraps and not any(
                detail.get("code") in {"IMPLICIT_RUNTIME_WRAP", "IMPLICIT_RUNTIME_HARD_WRAP"}
                for detail in details
            ):
                details.append(
                    {
                        "severity": "error",
                        "code": "IMPLICIT_RUNTIME_WRAP_SUMMARY",
                        "message": f"simulator recorded {implicit_wraps} implicit runtime wrap(s)",
                    }
                )
            excluded_events.append(
                {
                    "event_id": event_id,
                    "stage": "simulator_rejected",
                    "semantic_ids": semantic_ids,
                    "missing_semantic_ids": [],
                    "details": details,
                }
            )
            continue

        # Round 67: C9:40D7 belongs to a fully aligned Android-848 mapping, but
        # official Android FR intentionally omits this Western-only second sentence
        # and the SNES-JP event has no distinct counterpart. The user validated
        # suppressing the standalone final page. Apply that exact mapped-carrier
        # suppression only after the ordinary complete-event layout is proven clean,
        # then re-simulate with the immediately following WAIT $00 omitted.
        if event_id == "013A":
            manual_entry = manual_supplements_by_event.get("013A", {}).get("C9:40D7")
            if manual_entry is None or manual_entry.get("status") != "suppressed":
                raise AssertionError("Round-67 $013A/C9:40D7 validated suppression metadata missing")
            if event_translations.get("C9:40D7") not in {None, ""}:
                raise AssertionError("Round-67 $013A/C9:40D7 would overwrite visible translated text")
            event_translations["C9:40D7"] = ""
            suppression_report = {
                "event_id": "013A",
                "snes_ids": ["C9:40D7"],
                "android_ids": [848],
                "confidence": "user_validated_snes_jp_absent_android_fr_adaptation_suppression",
                "manual_supplement": True,
                "manual_status": "suppressed",
                "manual_reason": manual_entry["reason"],
                "android_identity_unchanged": True,
                "formatted_entries": [{"id": "C9:40D7", "text": ""}],
                "payload_policy": "validated_empty_mapped_carrier_with_adjacent_wait_omission",
            }
            event_reports.append(suppression_report)
            manual_supplement_reports_by_event.setdefault("013A", []).append(suppression_report)
            try:
                suppression_simulation = simulate_event(
                    base_rom,
                    event,
                    event_translations,
                    font=font,
                    player_names={0: "000000000", 1: "000000000", 2: "000000000"},
                    omitted_command_token_indexes=structural_omission_indexes_by_event.get(event_id),
                    structural_command_overrides=structural_command_overrides_by_event.get(event_id),
                )
            except ValueError as exc:
                excluded_events.append({
                    "event_id": event_id,
                    "stage": "simulator_rejected",
                    "semantic_ids": semantic_ids,
                    "missing_semantic_ids": [],
                    "details": [{"message": f"Round-67 validated $013A suppression failed serialization: {exc}"}],
                })
                continue
            suppression_blocking = [
                issue for issue in suppression_simulation.issues
                if issue.severity in {"error", "warning"}
            ]
            suppression_wraps = sum(
                line.implicit_wrap
                for box in suppression_simulation.boxes
                for page in box.pages
                for line in page.lines
            )
            if suppression_blocking or suppression_wraps:
                excluded_events.append({
                    "event_id": event_id,
                    "stage": "simulator_rejected",
                    "semantic_ids": semantic_ids,
                    "missing_semantic_ids": [],
                    "details": [
                        {
                            "severity": issue.severity,
                            "code": issue.code,
                            "message": issue.message,
                            "box": issue.box,
                            "page": issue.page,
                            "line": issue.line,
                        }
                        for issue in suppression_blocking
                    ] + ([{
                        "severity": "error",
                        "code": "IMPLICIT_RUNTIME_WRAP_SUMMARY",
                        "message": f"Round-67 validated $013A suppression recorded {suppression_wraps} implicit wrap(s)",
                    }] if suppression_wraps else []),
                })
                continue
            simulation = suppression_simulation

        accepted_events.append(event_id)
        if complete_layout_deferred_ids:
            partial_accepted_events.append(event_id)
            deferred_ids = sorted(set(complete_layout_deferred_ids))
            partial_unresolved_semantic_ids_by_event[event_id] = deferred_ids
            partial_layout_deferred_semantic_ids_by_event[event_id] = deferred_ids
            partial_suppression_reason_by_event[event_id] = "mapped_but_layout_deferred"
        translations_by_event[event_id] = event_translations
        reports_by_event[event_id] = event_reports
        wait00_repairs_by_event[event_id] = wait00_repairs
        unpaused_scroll_repairs_by_event[event_id] = unpaused_scroll_repairs
        cross_mapping_sentence_repairs_by_event[event_id] = cross_mapping_sentence_repairs

    # Second, conservative partial-event pass. Every alignment-incomplete event
    # is reconsidered on each run. Already accepted high-confidence mappings are
    # rendered in French; genuinely unresolved semantic carriers are deliberately
    # left untranslated so their stock SNES English remains visible during
    # playtesting. Structural commands/layout remain canonical. Unlike complete
    # events, partial events receive no compact/event-level repair: the directly
    # formatted mixed FR/EN event must already simulate with no errors, warnings
    # or implicit wraps.
    incomplete_by_event = {
        entry["event_id"]: entry
        for entry in excluded_events
        if entry.get("stage") == "alignment_incomplete"
    }
    for event in source_document["events"]:
        event_id = event["event_id"]
        incomplete = incomplete_by_event.get(event_id)
        if incomplete is None:
            continue
        event_mappings = mappings_by_event.get(event_id, [])
        manual_only_ids = DIALOGUE_MANUAL_ONLY_RESEGMENTED_PARTIAL_IDS.get(event_id)
        if manual_only_ids:
            manual_entries_for_policy = manual_supplements_by_event.get(event_id, {})
            if set(manual_entries_for_policy) != set(manual_only_ids):
                raise AssertionError(
                    f"manual-only resegmented PARTIEL ${event_id} supplement set changed: "
                    f"{sorted(manual_entries_for_policy)}"
                )
            if any(
                manual_entries_for_policy[text_id].get("status") != "translated"
                for text_id in manual_only_ids
            ):
                # Until the user explicitly approves the exact manual carrier,
                # preserve the historical Round-64/65 exclusion unchanged.
                manual_only_ids = None
            else:
                # Exact Round-66 policy: do not let the presence of one approved
                # manual carrier reopen any Android mapping in this resegmented
                # event. Everything except the manual carrier stays stock USA.
                event_mappings = []
        # A user-validated Android-absent manual supplement may intentionally be
        # the only French payload in an otherwise alignment-incomplete event
        # (Round 43 Dryad). Keep it outside semantic alignment but still let the
        # normal PARTIEL simulator gate decide whether the translation is safe.
        if (
            not event_mappings
            and event_id not in manual_supplements_by_event
            and event_id not in DIALOGUE_REVIEWED_UNMAPPED_LAYOUT_RESEGMENTATIONS
        ):
            continue
        # The complete-event pass already removes a trailing PLAYER_NAME that
        # was borrowed only as duplicate alignment context by the preceding
        # mapping. PARTIEL must apply the same ownership rule before deciding
        # whether proven French can coexist with unresolved stock carriers.
        event_mappings, duplicated_player_context_repairs = (
            _strip_duplicated_trailing_player_context(
                event, event_mappings, base_rom=base_rom
            )
        )
        if duplicated_player_context_repairs:
            duplicated_player_context_repairs_by_event[event_id] = (
                duplicated_player_context_repairs
            )
        missing_ids = list(incomplete.get("missing_semantic_ids", []))
        missing_set = set(missing_ids)
        event_mappings, reviewed_hole_player_context_repairs = (
            _strip_trailing_player_context_owned_by_reviewed_hole(
                event,
                event_mappings,
                missing_ids=missing_set,
                unmapped_by_id=unmapped_by_id,
            )
        )
        reviewed_hole_player_context_repairs_by_event[event_id] = (
            reviewed_hole_player_context_repairs
        )
        frozen_suppressions = set(
            DIALOGUE_USER_VALIDATED_VISUALLY_COMPLETE_SUPPRESSIONS.get(event_id, ())
        )
        partial_user_suppressions = set(
            DIALOGUE_USER_VALIDATED_PARTIAL_SUPPRESSIONS.get(event_id, ())
        )
        if not partial_user_suppressions <= missing_set:
            raise AssertionError(
                f"partial event ${event_id}: user suppression is not an unresolved semantic hole: "
                f"{sorted(partial_user_suppressions - missing_set)}"
            )
        effective_suppressed_ids = sorted(
            missing_set | frozen_suppressions | partial_user_suppressions
        )
        validated_android_omission_hole = any(
            unmapped_by_id.get(missing_id, {}).get("reason") == "validated_android_omission"
            for missing_id in missing_ids
        )
        event_translations: dict[str, str] = {}
        event_reports: list[dict] = []
        partial_errors: list[dict] = []
        layout_deferred_ids: list[str] = []
        generic_layout_deferred_ids: list[str] = []
        layout_deferred_reports: list[dict] = []
        round67_resolved_missing_ids: set[str] = set()
        for mapping in event_mappings:
            mapping_semantic_ids = set(mapping.get("snes_ids", []))
            frozen_overlap = mapping_semantic_ids & frozen_suppressions
            if frozen_overlap:
                if frozen_overlap != mapping_semantic_ids:
                    raise AssertionError(
                        f"partial event ${event_id}: mapping mixes frozen validated omissions "
                        f"with visible semantic IDs: {sorted(mapping_semantic_ids)}"
                    )
                continue
            try:
                values, mapping_report = _format_mass_mapping(
                    source_document,
                    mapping,
                    advances,
                    base_rom=base_rom,
                    french=french,
                    prefer_semantic_line_breaks=True,
                )
            except ValueError as exc:
                message = str(exc)
                reviewed_defer_note = _reviewed_partial_layout_defer(
                    event_id, mapping, message
                )
                generic_defer = (
                    event_id not in DIALOGUE_GENERIC_PARTIAL_LAYOUT_DEFERRAL_BLOCKLIST
                    and _partial_layout_deferable_formatter_error(message)
                )
                if (
                    (validated_android_omission_hole and _partial_layout_deferable_formatter_error(message))
                    or reviewed_defer_note is not None
                    or generic_defer
                ):
                    deferred = list(mapping.get("snes_ids", []))
                    layout_deferred_ids.extend(deferred)
                    if generic_defer and reviewed_defer_note is None and not validated_android_omission_hole:
                        generic_layout_deferred_ids.extend(deferred)
                        generic_layout_deferred_semantic_ids_by_event.setdefault(event_id, []).extend(deferred)
                    layout_deferred_reports.append({
                        "event_id": event_id,
                        "snes_ids": deferred,
                        "android_ids": mapping.get("android_ids", []),
                        "confidence": mapping.get("confidence"),
                        "partial_event": True,
                        "layout_deferred": True,
                        "layout_deferred_formatter_error": message,
                        "layout_deferred_policy": (
                            "reviewed_exact"
                            if reviewed_defer_note is not None
                            else (
                                "validated_android_omission"
                                if validated_android_omission_hole
                                else "generic_structural_safe_subset"
                            )
                        ),
                        "reviewed_partial_layout_defer_note": reviewed_defer_note,
                        "formatted_entries": [],
                    })
                    continue
                partial_errors.append({
                    "snes_ids": mapping.get("snes_ids", []),
                    "android_ids": mapping.get("android_ids", []),
                    "message": message,
                })
                continue
            duplicate = sorted(set(values) & set(event_translations))
            if duplicate:
                partial_errors.append({
                    "snes_ids": mapping.get("snes_ids", []),
                    "android_ids": mapping.get("android_ids", []),
                    "message": f"partial formatter generated duplicate translated source IDs: {duplicate}",
                })
                continue
            forbidden = sorted(set(values) & missing_set)
            if forbidden:
                raise AssertionError(
                    f"partial event ${event_id} attempted to translate unmapped semantic IDs: {forbidden}"
                )
            event_translations.update(values)
            mapping_report["partial_event"] = True
            event_reports.append(mapping_report)
        # User-validated Android-absent carriers may be supplied explicitly by
        # the small manual supplement file.  They stay outside Android identity
        # coverage and keep the event PARTIEL until a separate policy changes
        # that status.
        manual_entries = manual_supplements_by_event.get(event_id, {})
        post_repair_manual_ids = set(
            DIALOGUE_PARTIAL_MANUAL_POST_REPAIR_IDS.get(event_id, frozenset())
        )
        active_manual_entries = {
            text_id: entry for text_id, entry in manual_entries.items()
            if entry.get("status") != "needs_manual_translation"
            and text_id not in post_repair_manual_ids
        }
        deferred_manual_entries: dict[str, dict] = {}
        manual_reports: list[dict] = []
        for missing_id in list(missing_ids):
            manual_entry = manual_entries.get(missing_id)
            if manual_entry is None:
                continue
            # A pending manual supplement is provenance/review data only. Keep
            # the canonical USA carrier completely untouched: do not feed its
            # English through the French formatter, because reflowing identical
            # prose could change simulation/admission despite the user not yet
            # approving any payload. This is the strict meaning of “pending
            # serializes original_en”: `french_dialogues` falls back to the source ROM
            # bytes exactly.
            if manual_entry.get("status") == "suppressed":
                if (event_id, missing_id) != ("013A", "C9:40D7"):
                    raise AssertionError(f"unexpected unresolved manual suppression ${event_id}/{missing_id}")
                if missing_id not in frozen_suppressions:
                    raise AssertionError(
                        f"manual suppression ${event_id}/{missing_id} must be a visually-complete frozen omission"
                    )
                event_translations[missing_id] = ""
                manual_reports.append({
                    "event_id": event_id,
                    "snes_ids": [missing_id],
                    "android_ids": [],
                    "confidence": "user_validated_snes_jp_absent_suppression",
                    "manual_supplement": True,
                    "manual_status": "suppressed",
                    "manual_reason": manual_entry["reason"],
                    "formatted_entries": [{"id": missing_id, "text": ""}],
                    "payload_policy": "validated_empty_carrier_with_adjacent_wait_omission",
                })
                continue
            if manual_entry.get("status") == "needs_manual_translation":
                manual_reports.append({
                    "event_id": event_id,
                    "snes_ids": [missing_id],
                    "android_ids": [],
                    "confidence": (
                        "user_requested_unmapped_manual_review"
                        if manual_entry.get("reason") == "user_requested_unmapped_carrier_review"
                        else "user_validated_android_absent_manual"
                    ),
                    "source_display": manual_entry.get("original_en", ""),
                    "french_display": manual_entry.get("original_en", ""),
                    "manual_supplement": True,
                    "manual_status": "needs_manual_translation",
                    "manual_reason": manual_entry.get("reason", ""),
                    "manual_translation_proposal": manual_entry.get("translation_fr", ""),
                    "formatted_entries": [],
                    "payload_policy": "canonical_usa_source_bytes_unchanged_until_approval",
                })
                continue
            if missing_id in post_repair_manual_ids:
                if manual_entry.get("status") != "translated":
                    raise AssertionError(
                        f"post-repair manual ${event_id}/{missing_id} must be translated"
                    )
                deferred_manual_entries[missing_id] = manual_entry
                continue
            value, manual_report = _format_manual_supplement(
                source_document, manual_entry, advances
            )
            if manual_only_ids and missing_id in manual_only_ids:
                manual_report["payload_policy"] = "manual_only_on_resegmented_partial_event"
            # $0278's two controller instructions are separated by WAIT $00 but
            # no stock NEWLINE/TEXT_CLEAR. WAIT does not advance the live cursor;
            # add an explicit formatting-only newline before the second manual
            # supplement so the two validated SNES-only instructions cannot rely
            # on an implicit runtime wrap.
            if event_id == "0278" and missing_id == "C9:A74E":
                value = "\n" + value.lstrip(" ")
                manual_report["layout_adjustment"] = "explicit_newline_after_wait00"
            event_translations[missing_id] = value
            manual_reports.append(manual_report)
        # A mapped carrier may also be explicitly suppressed after human review when
        # regional resegmentation proves that the standalone USA page does not exist
        # as a distinct SNES-JP unit. This is intentionally exact and currently only
        # applies to the mapped suppression $04E1/CA:2C84. Unmapped $013A/C9:40D7
        # is handled in the missing-carrier branch above. The mapped carrier must already be layout-deferred; the
        # adjacent WAIT omission is independently guarded by the structural-omission table.
        for manual_id, manual_entry in manual_entries.items():
            if manual_entry.get("status") != "suppressed":
                continue
            if (event_id, manual_id) != ("04E1", "CA:2C84"):
                raise AssertionError(f"unexpected mapped manual suppression ${event_id}/{manual_id}")
            if manual_id not in layout_deferred_ids:
                raise AssertionError(
                    f"mapped manual suppression ${event_id}/{manual_id} is no longer layout-deferred"
                )
            event_translations[manual_id] = ""
            layout_deferred_ids = [text_id for text_id in layout_deferred_ids if text_id != manual_id]
            manual_reports.append({
                "event_id": event_id,
                "snes_ids": [manual_id],
                "android_ids": [],
                "confidence": "user_validated_snes_jp_resegmentation_suppression",
                "manual_supplement": True,
                "manual_status": "suppressed",
                "manual_reason": manual_entry["reason"],
                "formatted_entries": [{"id": manual_id, "text": ""}],
            })
        if manual_reports:
            manual_supplement_reports_by_event[event_id] = manual_reports
            event_reports.extend(manual_reports)

        if event_id == "04E1":
            round67_reports, round67_resolved_missing_ids = _apply_reviewed_scene_redistributions(
                event, event_translations, english=english, redistribution_values=redistribution_values,
                layout_deferred_ids=layout_deferred_ids, missing_ids=missing_ids,
            )
            event_reports = [
                report for report in event_reports
                if not (report.get("layout_deferred") and "CA:2C93" in report.get("snes_ids", []))
            ]
            event_reports.extend(round67_reports)

        layout_resegmentations = DIALOGUE_REVIEWED_UNMAPPED_LAYOUT_RESEGMENTATIONS.get(event_id, {})
        for missing_id in missing_ids:
            entry = layout_resegmentations.get(missing_id)
            if entry is None:
                continue
            by_id_check, _ = event_text_index(source_document)
            if by_id_check[missing_id].get("event_id") != event_id:
                raise AssertionError(f"reviewed unresolved layout ${event_id}/{missing_id} moved")
            event_translations[missing_id] = entry["text"]
            event_reports.append({
                "event_id": event_id,
                "snes_ids": [missing_id],
                "android_ids": [],
                "confidence": "very_high_structural_review_without_android_identity",
                "unresolved_layout_resegmentation": True,
                "reason": entry["reason"],
                "formatted_entries": [{"id": missing_id, "text": entry["text"]}],
            })

        # $0278 resumes the Android sequence after its two SNES-only controller
        # instructions. Android 1349 is a mobile-specific extra page absent from
        # SNES; insert it before the already aligned 1350 page, then continue to
        # 1351 on the stock next carrier.
        if event_id == "0278":
            if set(manual_entries) != {"C9:A730", "C9:A74E"}:
                raise AssertionError("$0278 manual supplement set changed unexpectedly")
            if "C9:A76B" not in event_translations:
                raise AssertionError("$0278 expected aligned carrier C9:A76B")
            extra_text, extra_report = _format_android_extra_page(
                source_document, event_id=event_id, carrier_id="C9:A76B",
                android_id=1349, french=french, advances=advances
            )
            event_translations["C9:A76B"] = extra_text + "\f" + event_translations["C9:A76B"]
            extra_report["distributed_before_android_ids"] = [1350]
            android_extra_reports_by_event[event_id] = [extra_report]
            event_reports.append(extra_report)

        # The common inn prompt is parameterized rather than manually translated.
        # Android EN/FR 110 proves the full 5-GP sentence; the stock caller emits
        # the numeric price between $0330 and $0331, so $0331 receives only the
        # French suffix after that number.
        if event_id == "0331":
            event_translations["C9:CEB3"] = inn_template["suffix_translation"]

        # Mixed-language PARTIEL presentation: genuinely unresolved IDs are not
        # emitted into the sparse French JSON. Their stock SNES English therefore
        # remains byte-for-byte intact and visible in-game, making missing
        # alignment easy to spot during tests. Frozen user-validated omissions are
        # the only unresolved carriers that may still be explicitly suppressed.
        for missing_id in effective_suppressed_ids:
            if missing_id in event_translations:
                continue
            if missing_id not in frozen_suppressions:
                continue
            preservation = next((
                entry
                for entry in DIALOGUE_USER_VALIDATED_PARTIAL_LAYOUT_PRESERVATIONS
                if entry["event_id"] == event_id
                and entry["suppressed_semantic_id"] == missing_id
            ), None)
            if preservation is None:
                event_translations[missing_id] = ""
                continue
            preserved_text = preservation["preserved_text"]
            if preserved_text.strip():
                raise AssertionError(
                    f"partial event ${event_id}: layout preservation for {missing_id} contains visible text"
                )
            source_text = source_text_by_id.get(missing_id, "")
            if preserved_text.count("\n") > source_text.count("\n"):
                raise AssertionError(
                    f"partial event ${event_id}: layout preservation for {missing_id} invents NEWLINEs"
                )
            event_translations[missing_id] = preserved_text
        if layout_deferred_reports:
            event_reports.extend(layout_deferred_reports)
        if partial_errors or not event_translations:
            incomplete["partial_attempt"] = {
                "status": "formatter_rejected",
                "details": partial_errors,
            }
            continue
        targeted_wait00_fresh_page_repairs_by_event[event_id] = _apply_targeted_wait00_fresh_page_clear(
            event_id, event_translations
        )
        explicit_post_wait_newline_repairs_by_event[event_id] = _apply_explicit_post_wait_newlines(
            event_id, event_translations, source_text_by_id=source_text_by_id
        )
        # Alignment-incomplete/locked reviewed scenes use the same calibrated
        # presentation wrapper as complete events before their independent
        # mixed-event simulation. This changes layout only; unresolved carriers
        # remain absent and reviewed Android-FR payload remains source-derived.
        event_translations, partial_automatic_reflow = _auto_reflow_fixed_translation_carriers(
            event_translations, advances
        )
        if partial_automatic_reflow:
            automatic_216px_reflows_by_event.setdefault(event_id, []).extend(partial_automatic_reflow)
        try:
            simulation = simulate_event(
                base_rom,
                event,
                event_translations,
                font=font,
                player_names={0: "000000000", 1: "000000000", 2: "000000000"},
                omitted_command_token_indexes=structural_omission_indexes_by_event.get(event_id),
                structural_command_overrides=structural_command_overrides_by_event.get(event_id),
            )
        except ValueError as exc:
            incomplete["partial_attempt"] = {
                "status": "serialization_rejected",
                "details": [{"message": str(exc)}],
            }
            continue
        blocking_issues = [
            issue for issue in simulation.issues
            if issue.severity in {"error", "warning"}
        ]
        implicit_wraps = sum(
            line.implicit_wrap
            for box in simulation.boxes
            for page in box.pages
            for line in page.lines
        )
        if generic_layout_deferred_ids and (blocking_issues or implicit_wraps):
            # The generic safe-subset rule is intentionally stricter than the
            # reviewed omission families below: if the direct mixed event is
            # not already clean, do not add pagination/choice/compact repairs.
            incomplete["partial_attempt"] = {
                "status": "simulator_rejected",
                "details": [
                    {
                        "severity": issue.severity,
                        "code": issue.code,
                        "message": issue.message,
                        "box": issue.box,
                        "page": issue.page,
                        "line": issue.line,
                    }
                    for issue in blocking_issues
                ],
                "implicit_wraps": implicit_wraps,
            }
            continue

        # A validated-no-equivalent carrier is a deliberate identity hole, not
        # a reason to reject all surrounding proven French.  For that exact
        # PARTIEL family, reuse the same whole-event compact wrapper already
        # accepted for complete events when the direct semantic wrapper alone
        # causes a simulator failure.  Compact mode only removes formatter-added
        # presentation breaks; it does not add/move/remove any SNES command and
        # the unresolved carrier remains absent from the sparse translation map.
        if (
            (blocking_issues or implicit_wraps)
            and any(
                unmapped_by_id.get(missing_id, {}).get("reason")
                in {"validated_no_equivalent", "validated_android_omission"}
                for missing_id in missing_ids
            )
            and not active_manual_entries
            and not frozen_suppressions
        ):
            compact_translations: dict[str, str] = {}
            compact_reports: list[dict] = list(layout_deferred_reports)
            compact_failed = False
            for mapping in event_mappings:
                try:
                    values, mapping_report = _format_mass_mapping(
                        source_document,
                        mapping,
                        advances,
                        base_rom=base_rom,
                        french=french,
                        prefer_semantic_line_breaks=False,
                    )
                except ValueError as exc:
                    compact_message = str(exc)
                    if (
                        (validated_android_omission_hole and _partial_layout_deferable_formatter_error(compact_message))
                        or _reviewed_partial_layout_defer(event_id, mapping, compact_message) is not None
                    ):
                        continue
                    compact_failed = True
                    break
                if set(values) & set(compact_translations):
                    compact_failed = True
                    break
                if set(values) & missing_set:
                    raise AssertionError(
                        f"partial compact event ${event_id} attempted to translate unmapped semantic IDs"
                    )
                compact_translations.update(values)
                mapping_report = dict(mapping_report)
                mapping_report["partial_event"] = True
                mapping_report["semantic_layout_fallback"] = True
                compact_reports.append(mapping_report)
            if not compact_failed and compact_translations:
                _apply_targeted_wait00_fresh_page_clear(event_id, compact_translations)
                _apply_explicit_post_wait_newlines(
                    event_id, compact_translations, source_text_by_id=source_text_by_id
                )
                try:
                    compact_simulation = simulate_event(
                        base_rom,
                        event,
                        compact_translations,
                        font=font,
                        player_names={0: "000000000", 1: "000000000", 2: "000000000"},
                        omitted_command_token_indexes=structural_omission_indexes_by_event.get(event_id),
                    )
                except ValueError:
                    compact_simulation = None
                if compact_simulation is not None:
                    compact_blocking = [
                        issue for issue in compact_simulation.issues
                        if issue.severity in {"error", "warning"}
                    ]
                    compact_wraps = sum(
                        line.implicit_wrap
                        for box in compact_simulation.boxes
                        for page in box.pages
                        for line in page.lines
                    )
                    if not compact_blocking and not compact_wraps:
                        event_translations = compact_translations
                        event_reports = compact_reports
                        simulation = compact_simulation
                        blocking_issues = []
                        implicit_wraps = 0

        # A reviewed omission/no-equivalent hole may leave otherwise proven
        # French in a four-line rolling-window state. Reuse the same generic
        # semantic extra-page repair as complete events, but only when the
        # simulator defect is pure UNPAUSED_SCROLL and the repair touches
        # mapped carriers only. The unresolved stock-English carrier remains
        # absent from the sparse translation map.
        if (
            (blocking_issues or implicit_wraps)
            and (
                bool(layout_deferred_ids)
                and event_id in DIALOGUE_REVIEWED_PARTIAL_LAYOUT_DEFERRALS
                or any(
                    unmapped_by_id.get(missing_id, {}).get("reason")
                    in {"validated_no_equivalent", "validated_android_omission"}
                    for missing_id in missing_ids
                )
            )
            and not active_manual_entries
            and not frozen_suppressions
        ):
            (
                repaired_translations,
                repaired_reports,
                repaired_simulation,
                partial_unpaused_scroll_repairs,
            ) = _repair_pure_unpaused_scroll(
                base_rom=base_rom,
                source_document=source_document,
                event=event,
                event_mappings=event_mappings,
                translations=event_translations,
                reports=event_reports,
                advances=advances,
                font=font,
                simulation=simulation,
            )
            if partial_unpaused_scroll_repairs:
                if set(repaired_translations) & missing_set:
                    raise AssertionError(
                        f"partial event ${event_id}: unpaused-scroll repair translated a reviewed hole"
                    )
                event_translations = repaired_translations
                event_reports = repaired_reports
                simulation = repaired_simulation
                unpaused_scroll_repairs_by_event[event_id] = partial_unpaused_scroll_repairs
                blocking_issues = [
                    issue for issue in simulation.issues
                    if issue.severity in {"error", "warning"}
                ]
                implicit_wraps = sum(
                    line.implicit_wrap
                    for box in simulation.boxes
                    for page in box.pages
                    for line in page.lines
                )

        if blocking_issues or implicit_wraps:
            (
                anchor_simulation,
                anchor_overrides,
                anchor_repairs,
            ) = _try_adaptive_choice_anchor_positions(
                base_rom=base_rom,
                event=event,
                translations=event_translations,
                advances=advances,
                font=font,
                simulation=simulation,
            )
            if anchor_repairs:
                simulation = anchor_simulation
                choice_option_position_overrides_by_event[event_id] = anchor_overrides
                adaptive_choice_anchor_repairs_by_event[event_id] = anchor_repairs
                blocking_issues = []
                implicit_wraps = 0
        if blocking_issues or implicit_wraps:
            (
                event_translations,
                event_reports,
                simulation,
                choice_decoration_repairs,
            ) = _try_adaptive_choice_decoration(
                base_rom=base_rom,
                event=event,
                translations=event_translations,
                reports=event_reports,
                font=font,
                simulation=simulation,
            )
            if choice_decoration_repairs:
                adaptive_choice_decoration_repairs_by_event[event_id] = choice_decoration_repairs
                blocking_issues = []
                implicit_wraps = 0
        if blocking_issues or implicit_wraps:
            (
                decorated_translations,
                decorated_reports,
                decorated_simulation,
                choice_decoration_repairs,
                decorated_anchor_overrides,
                decorated_anchor_repairs,
            ) = _try_adaptive_choice_decoration_with_anchor_positions(
                base_rom=base_rom,
                event=event,
                translations=event_translations,
                reports=event_reports,
                advances=advances,
                font=font,
                simulation=simulation,
            )
            if choice_decoration_repairs and decorated_anchor_repairs:
                event_translations = decorated_translations
                event_reports = decorated_reports
                simulation = decorated_simulation
                adaptive_choice_decoration_repairs_by_event[event_id] = choice_decoration_repairs
                choice_option_position_overrides_by_event[event_id] = decorated_anchor_overrides
                adaptive_choice_anchor_repairs_by_event[event_id] = decorated_anchor_repairs
                blocking_issues = []
                implicit_wraps = 0
        # Round 65 exact post-repair manual approval. $04E8 already required
        # ordinary PARTIEL formatting repairs while CA:437D was stock English.
        # Preserve those repairs first, then add the approved Japanese-led laugh
        # and re-simulate the complete mixed event. This is deliberately limited
        # by DIALOGUE_PARTIAL_MANUAL_POST_REPAIR_IDS.
        if not blocking_issues and not implicit_wraps and deferred_manual_entries:
            late_reports: list[dict] = []
            for manual_id, manual_entry in sorted(deferred_manual_entries.items()):
                if manual_id in event_translations:
                    raise AssertionError(
                        f"post-repair manual ${event_id}/{manual_id} already has payload"
                    )
                value, manual_report = _format_manual_supplement(
                    source_document, manual_entry, advances
                )
                event_translations[manual_id] = value
                manual_report["payload_policy"] = "apply_after_validated_partial_repairs"
                late_reports.append(manual_report)
            if late_reports:
                manual_supplement_reports_by_event.setdefault(event_id, []).extend(late_reports)
                event_reports.extend(late_reports)
            simulation = simulate_event(
                base_rom,
                event,
                event_translations,
                font=font,
                player_names={0: "000000000", 1: "000000000", 2: "000000000"},
                omitted_command_token_indexes=structural_omission_indexes_by_event.get(event_id),
                structural_command_overrides=structural_command_overrides_by_event.get(event_id),
            )
            blocking_issues = [
                issue for issue in simulation.issues
                if issue.severity in {"error", "warning"}
            ]
            implicit_wraps = sum(
                line.implicit_wrap
                for box in simulation.boxes
                for page in box.pages
                for line in page.lines
            )

        # A user-approved omission inside an event that remains PARTIEL for
        # unrelated reasons is applied only after the ordinary mixed-event
        # formatter/simulator repairs have succeeded. This preserves the exact
        # previously validated layout strategy, then proves that removing the
        # selected stock phrase does not introduce a new runtime defect.
        if not blocking_issues and not implicit_wraps and partial_user_suppressions:
            for suppressed_id in sorted(partial_user_suppressions):
                if suppressed_id in event_translations:
                    raise AssertionError(
                        f"partial event ${event_id}: user-suppressed hole {suppressed_id} "
                        "was unexpectedly translated"
                    )
                event_translations[suppressed_id] = ""
            simulation = simulate_event(
                base_rom,
                event,
                event_translations,
                font=font,
                player_names={0: "000000000", 1: "000000000", 2: "000000000"},
                omitted_command_token_indexes=structural_omission_indexes_by_event.get(event_id),
                structural_command_overrides=structural_command_overrides_by_event.get(event_id),
            )
            blocking_issues = [
                issue for issue in simulation.issues
                if issue.severity in {"error", "warning"}
            ]
            implicit_wraps = sum(
                line.implicit_wrap
                for box in simulation.boxes
                for page in box.pages
                for line in page.lines
            )

        if blocking_issues or implicit_wraps:
            incomplete["partial_attempt"] = {
                "status": "simulator_rejected",
                "details": [
                    {
                        "severity": issue.severity,
                        "code": issue.code,
                        "message": issue.message,
                        "box": issue.box,
                        "page": issue.page,
                        "line": issue.line,
                    }
                    for issue in blocking_issues
                ],
                "implicit_wraps": implicit_wraps,
            }
            continue
        accepted_events.append(event_id)
        if event_id == "0331":
            parameterized_inn_events.add(event_id)
        else:
            partial_accepted_events.append(event_id)
            partial_unresolved_semantic_ids_by_event[event_id] = sorted(
                set(effective_suppressed_ids) - round67_resolved_missing_ids
            )
            partial_layout_deferred_semantic_ids_by_event[event_id] = sorted(set(layout_deferred_ids))
            if manual_entries:
                statuses = {entry.get("status") for entry in manual_entries.values()}
                if "needs_manual_translation" in statuses:
                    partial_suppression_reason_by_event[event_id] = "manual_translation_pending"
                elif "suppressed" in statuses:
                    partial_suppression_reason_by_event[event_id] = "manual_resegmented_page_suppression"
                else:
                    partial_suppression_reason_by_event[event_id] = "manual_translation_without_android_identity"
            elif event_id in DIALOGUE_REVIEWED_UNMAPPED_LAYOUT_RESEGMENTATIONS:
                partial_suppression_reason_by_event[event_id] = "android_resegmented_shared_prefix_without_single_identity"
            elif partial_user_suppressions:
                partial_suppression_reason_by_event[event_id] = "user_validated_snes_jp_absent_suppression"
            elif layout_deferred_ids:
                partial_suppression_reason_by_event[event_id] = (
                    "validated_android_omission_with_layout_deferred"
                    if validated_android_omission_hole
                    else "alignment_unresolved_with_layout_deferred"
                )
            else:
                partial_suppression_reason_by_event[event_id] = "alignment_unresolved"
        translations_by_event[event_id] = event_translations
        reports_by_event[event_id] = event_reports
        wait00_repairs_by_event[event_id] = []
        unpaused_scroll_repairs_by_event.setdefault(event_id, [])
        cross_mapping_sentence_repairs_by_event[event_id] = []
        duplicated_player_context_repairs_by_event.setdefault(event_id, [])
        fragment_spacing_repairs_by_event.setdefault(event_id, [])

    # Materialize the other half of the parameterized inn chain.  The nine
    # caller events contain language-neutral numeric parameters; $0330's English
    # prefix is suppressed so the number becomes the first visible French token.
    inn_price_events = {
        "0320": ("C9:CE3D", "5"),
        "0321": ("C9:CE46", "10"),
        "0322": ("C9:CE50", "15"),
        "0323": ("C9:CE5A", "30"),
        "0324": ("C9:CE64", "50"),
        "0325": ("C9:CE6E", "100"),
        "0326": ("C9:CE79", "120"),
        "0327": ("C9:CE84", "150"),
        "0328": ("C9:CE8F", "200"),
    }
    by_event_id = {event["event_id"]: event for event in source_document["events"]}
    for event_id, (text_id, price) in inn_price_events.items():
        event = by_event_id[event_id]
        text_token = next(token for token in event["tokens"] if token.get("id") == text_id)
        if text_token.get("source") != price:
            raise ValueError(f"Parameterized inn ${event_id}: stock price carrier changed")
        signatures = [
            (token.get("name"), token.get("args"))
            for token in event["tokens"] if token.get("type") == "command"
        ]
        if signatures != [("OP_30", f"F9 {int(event_id,16)-0x320:02X}"), ("OP_23", "30"), ("OP_13", "31"), ("END", None)]:
            raise ValueError(f"Parameterized inn ${event_id}: caller structure changed")
        translations_by_event[event_id] = {text_id: price}
        reports_by_event[event_id] = [{
            "event_id": event_id,
            "snes_ids": [text_id],
            "android_ids": [inn_template["android_id"]],
            "confidence": "user_validated_parameterized_android_template",
            "parameter_value": price,
            "formatted_entries": [{"id": text_id, "text": price}],
        }]
        if event_id not in accepted_events:
            accepted_events.append(event_id)
        parameterized_inn_events.add(event_id)

    prefix_event_id = "0330"
    prefix_event = by_event_id[prefix_event_id]
    prefix_token = next(token for token in prefix_event["tokens"] if token.get("id") == inn_template["prefix_id"])
    if prefix_token.get("source") != " One night is ":
        raise ValueError("Parameterized inn $0330: stock prefix changed")
    translations_by_event[prefix_event_id] = {inn_template["prefix_id"]: inn_template["prefix_translation"]}
    reports_by_event[prefix_event_id] = [{
        "event_id": prefix_event_id,
        "snes_ids": [inn_template["prefix_id"]],
        "android_ids": [inn_template["android_id"]],
        "confidence": "user_validated_parameterized_android_template",
        "suppressed_stock_prefix": True,
        "formatted_entries": [{"id": inn_template["prefix_id"], "text": ""}],
    }]
    if prefix_event_id not in accepted_events:
        accepted_events.append(prefix_event_id)
    parameterized_inn_events.add(prefix_event_id)

    # Round 54 may serialize every official Android-FR word available for a
    # mapped unit while still leaving a stock SNES sentence whose Android-FR
    # counterpart is genuinely absent. Keep those events visibly PARTIEL so
    # the remaining English carrier is easy to find later rather than being
    # mistaken for a fully localized event.
    for event_id, omitted_ids in DIALOGUE_ANDROID_FR_OMISSION_PARTIALS.items():
        if event_id not in accepted_events:
            raise ValueError(f"Round-54 FR-omission PARTIEL ${event_id} was not accepted")
        if event_id not in partial_accepted_events:
            partial_accepted_events.append(event_id)
        partial_unresolved_semantic_ids_by_event[event_id] = list(omitted_ids)
        partial_layout_deferred_semantic_ids_by_event[event_id] = []
        partial_suppression_reason_by_event[event_id] = "official_android_fr_omission"

    resolved_special_events = set(parameterized_inn_events)
    if partial_accepted_events or resolved_special_events:
        accepted_partial = set(partial_accepted_events) | resolved_special_events
        excluded_events = [
            entry for entry in excluded_events
            if entry.get("event_id") not in accepted_partial
        ]
        accepted_events.sort(key=lambda value: int(value, 16))

    translations: dict[str, str] = {}
    formatted: list[dict] = []
    for event_id in accepted_events:
        for text_id, value in translations_by_event[event_id].items():
            if text_id in translations:
                raise ValueError(f"Mass formatter generated duplicate translation ID {text_id}")
            translations[text_id] = value
        formatted.extend(reports_by_event[event_id])

    source_order = {
        token["id"]: order
        for order, token in enumerate(
            token
            for event in source_document["events"]
            for token in event["tokens"]
            if token.get("type") == "text"
        )
    }
    ordered_entries = sorted(translations.items(), key=lambda item: source_order[item[0]])
    translation_document = make_dialogue_translation_document(
        ordered_entries,
        group="dialogues.android_format_mass_simulator_filtered",
    )
    visually_complete_events = (
        DIALOGUE_USER_VALIDATED_VISUALLY_COMPLETE_EVENTS
        | DIALOGUE_USER_VALIDATED_VISUALLY_COMPLETE_STATUS_OVERRIDES
    )
    visible_partial_events = [
        event_id for event_id in partial_accepted_events
        if event_id not in visually_complete_events
    ]
    user_validated_complete_events = [
        event_id for event_id in partial_accepted_events
        if event_id in visually_complete_events
    ]
    def partial_metadata(event_id: str) -> dict:
        reason = partial_suppression_reason_by_event[event_id]
        ids = partial_unresolved_semantic_ids_by_event[event_id]
        layout_deferred_ids = partial_layout_deferred_semantic_ids_by_event.get(event_id, [])
        result = {"event_id": event_id, "partial_reason": reason}
        if reason == "manual_translation_pending":
            result["manual_pending_semantic_ids"] = sorted(
                text_id for text_id, entry in manual_supplements_by_event.get(event_id, {}).items()
                if entry.get("status") == "needs_manual_translation"
            )
            suppressed = sorted(set(ids) - set(result["manual_pending_semantic_ids"]))
            if suppressed:
                result["suppressed_semantic_ids"] = suppressed
            if layout_deferred_ids:
                result["layout_deferred_semantic_ids"] = layout_deferred_ids
        elif reason == "manual_translation_without_android_identity":
            result["manual_translated_semantic_ids"] = sorted(
                text_id for text_id, entry in manual_supplements_by_event.get(event_id, {}).items()
                if entry.get("status") == "translated"
            )
            suppressed = sorted(set(ids) - set(result["manual_translated_semantic_ids"]))
            if suppressed:
                result["suppressed_semantic_ids"] = suppressed
        elif reason == "manual_resegmented_page_suppression":
            result["manual_suppressed_semantic_ids"] = sorted(
                text_id for text_id, entry in manual_supplements_by_event.get(event_id, {}).items()
                if entry.get("status") == "suppressed"
            )
            if ids:
                result["unresolved_semantic_ids"] = ids
            if layout_deferred_ids:
                result["layout_deferred_semantic_ids"] = layout_deferred_ids
        elif reason == "mapped_but_layout_deferred":
            result["layout_deferred_semantic_ids"] = ids
        elif reason == "user_validated_snes_jp_absent_suppression":
            result["suppressed_semantic_ids"] = ids
        else:
            result["unresolved_semantic_ids"] = ids
            if layout_deferred_ids:
                result["layout_deferred_semantic_ids"] = layout_deferred_ids
        return result

    translation_document["partial_events"] = [
        partial_metadata(event_id) for event_id in visible_partial_events
    ]
    def complete_event_metadata(event_id: str) -> dict:
        ids = partial_unresolved_semantic_ids_by_event[event_id]
        if event_id in DIALOGUE_USER_VALIDATED_VISUALLY_COMPLETE_STATUS_OVERRIDES:
            return {
                "event_id": event_id,
                "unresolved_semantic_ids": ids,
                "reason": "user_validated_runtime_complete_with_unresolved_alignment",
            }
        reason = partial_suppression_reason_by_event.get(event_id)
        result = {"event_id": event_id}
        if reason == "manual_translation_without_android_identity":
            result["manual_translated_semantic_ids"] = sorted(
                text_id for text_id, entry in manual_supplements_by_event.get(event_id, {}).items()
                if entry.get("status") == "translated"
            )
            suppressed = sorted(set(ids) - set(result["manual_translated_semantic_ids"]))
            if suppressed:
                result["suppressed_semantic_ids"] = suppressed
            result["reason"] = "user_validated_complete_with_manual_jp_supplement"
        elif reason == "manual_resegmented_page_suppression":
            result["manual_suppressed_semantic_ids"] = sorted(
                text_id for text_id, entry in manual_supplements_by_event.get(event_id, {}).items()
                if entry.get("status") == "suppressed"
            )
            result["reason"] = "user_validated_complete_with_manual_resegmentation"
        elif reason == "android_resegmented_shared_prefix_without_single_identity":
            result["unresolved_semantic_ids"] = ids
            result["reason"] = "user_validated_complete_shared_prefix_resegmentation"
        elif reason == "user_validated_snes_jp_absent_suppression":
            result["suppressed_semantic_ids"] = ids
            result["reason"] = "user_validated_complete_snes_jp_absent_suppression"
        else:
            result["suppressed_semantic_ids"] = ids
            result["reason"] = "user_validated_android_adaptation_complete"
        return result

    translation_document["user_validated_visually_complete_events"] = [
        complete_event_metadata(event_id) for event_id in user_validated_complete_events
    ]
    accepted_event_set = set(accepted_events)
    translation_document["user_validated_structural_omissions"] = [
        entry for entry in DIALOGUE_USER_VALIDATED_STRUCTURAL_OMISSIONS
        if entry.get("event_id") in accepted_event_set
    ]
    translation_document["user_validated_structural_command_overrides"] = [
        entry for entry in DIALOGUE_USER_VALIDATED_STRUCTURAL_COMMAND_OVERRIDES
        if entry.get("event_id") in accepted_event_set
    ]
    translation_document["user_validated_partial_layout_preservations"] = []
    translation_document["manual_dialogue_supplements"] = [
        {
            "event_id": event_id,
            "id": text_id,
            "status": entry["status"],
            "reason": entry["reason"],
        }
        for event_id in sorted(manual_supplements_by_event)
        for text_id, entry in sorted(manual_supplements_by_event[event_id].items())
    ]
    translation_document["migrated_manual_dialogue_supplements"] = [
        {
            "event_id": "0204",
            "id": "C9:902F",
            "status": "migrated_to_android_redistribution",
            "reason": "same_scene_android_fr_843_844_round69_redistribution",
            "active_manual_supplement": False,
        }
    ]
    translation_document["user_validated_stock_english_overrides"] = [
        {
            "event_id": report["event_id"],
            "id": report["snes_ids"][0],
            "android_id": report["android_ids"][0],
            "reason": report["override_reason"],
        }
        for report in formatted
        if report.get("user_validated_stock_english_override")
    ]
    translation_document["parameterized_android_templates"] = [{
        "kind": "inn_price_prompt",
        "android_id": inn_template["android_id"],
        "android_english": inn_template["android_english"],
        "android_french": inn_template["android_french"],
        "prefix_id": inn_template["prefix_id"],
        "suffix_id": inn_template["suffix_id"],
        "price_event_ids": sorted(
            [event_id for event_id in parameterized_inn_events if event_id not in {"0330", "0331"}],
            key=lambda value: int(value, 16),
        ),
        "reason": "user_validated_dynamic_price_generalization",
    }]
    translation_document["choice_option_position_overrides"] = [
        {"event_id": event_id, **repair}
        for event_id in accepted_events
        for repair in adaptive_choice_anchor_repairs_by_event.get(event_id, [])
    ]

    stage_counts: dict[str, int] = {}
    for entry in excluded_events:
        stage_counts[entry["stage"]] = stage_counts.get(entry["stage"], 0) + 1
    accepted_semantic_ids = sum(
        1
        for event_id in accepted_events
        for token in next(
            event for event in source_document["events"] if event["event_id"] == event_id
        )["tokens"]
        if (
            token.get("type") == "text"
            and _auto_semantic(token.get("source", ""))
            and token.get("id") in translations_by_event[event_id]
            and translations_by_event[event_id][token.get("id")] != ""
            and not any(
                preservation["event_id"] == event_id
                and preservation["suppressed_semantic_id"] == token.get("id")
                for preservation in DIALOGUE_USER_VALIDATED_PARTIAL_LAYOUT_PRESERVATIONS
            )
        )
    )
    report_document = {
        "format_version": 1,
        "status": "simulator_filtered_partial_runtime_candidate",
        "source_alignment": "mappings/android/dialogues_auto.json (regenerated from Android EN/FR)",
        "policy": {
            "event_selection": "complete semantic events plus simulator-clean partial events",
            "alignment_must_already_be_accepted": True,
            "all_semantic_ids_in_complete_event_must_be_mapped": True,
            "partial_event_policy": "reconsider every alignment-incomplete event on every run; translate every accepted Android mapping, leave unresolved semantic carriers untouched so stock SNES English remains visible, keep the event explicitly PARTIEL, preserve structural commands/layout, and require a clean independent simulation. A structurally incompatible mapped carrier may remain wholly stock under the generic safe-subset rule only when the formatter failure is an already-recognized command/PLAYER_NAME binding refusal, at least one independent French mapping remains, and the direct mixed event passes with zero errors/warnings/wraps and no adaptive repair; $015A/$0204 are explicitly excluded because their handoff records semantic resegmentation hazards. Reviewed Android-omission/no-equivalent families retain their narrower existing fallbacks. Future alignment/formatter improvements are therefore picked up automatically",
            "generic_structural_safe_subset_policy": "for a semantically accepted mapping, a recognized unsupported command/PLAYER_NAME boundary or an unserializable generated trailing page break may defer the whole mapping to stock; no command or identity changes, zero-gain events are rejected, and generic candidates receive no adaptive/compact repair before the independent clean simulation gate",
            "direct_simulator_safe_subset_policy": "second-stage fallback only after ordinary formatting or the generic structural safe-subset still fails direct simulation: the clean stock event must itself simulate without defects; at most three whole mapped carriers may be deferred; each candidate must individually reduce the direct simulator defect score; the deterministic smallest subset is accepted only when the remaining mixed event directly reaches zero errors, zero warnings and zero implicit wraps. No command, identity, layout bridge or adaptive repair is changed by this helper",
            "user_validated_visual_complete_policy": "events explicitly validated by the user as complete Android adaptations keep their simulator-clean French-only bytes and are removed from the PARTIEL badge without inventing mappings for omitted SNES-only fragments",
            "user_validated_structural_omission_policy": "a stock command may be omitted only when the user explicitly validates the omission and the command is proven by exact adjacency to an explicitly suppressed semantic ID; Round 63 additionally suppresses the standalone $04E1/CA:2C84 page and its immediately following WAIT $00 because SNES-JP resegments that meaning into the following unit; Round 67 suppresses the Western-only $013A/C9:40D7 instruction and its immediately following WAIT $00 because no distinct SNES-JP line exists and Android FR omits it; Round 57 removes PLAYER_NAME(0)+post-line WAIT with $02FC/C9:CB28 and PLAYER_NAME(2) with $0558/CA:6629, while $010C/C9:30F5 remains text-only",
            "manual_supplement_policy": "only exact allow-listed carriers may appear in translations/dialogues_manual_supplements.json: reviewed Android omissions, user-requested no-unique-equivalent carriers, plus the exact Round-62/63 mapped suppression carrier; pending entries may carry a review-only translation_fr proposal but never alter the visible payload until explicitly approved; manual entries never create Android identity",
            "user_validated_stock_english_override_policy": "when Android English identity is proven but the corresponding Android French is user-validated as a localization error, keep the semantic mapping accepted but serialize the exact canonical USA source text through the ordinary `french_dialogues` pipeline; this is non-cascading evidence and does not count as an unresolved/manual translation",
            "parameterized_inn_policy": "Android EN/FR 110 is the reviewed template for the common inn prompt: keep each stock numeric caller as the dynamic price, suppress stock C9:CEA3 before it, and render the normalized Android-FR suffix through C9:CEB3; this resolves all shared inn price variants without per-price manual translation",
            "event_0278_android_extra_policy": "after Android 1347/1348 and the two user-validated SNES-only manual controller supplements, insert Android FR 1349 as an extra page before already aligned 1350, then continue with 1351; an explicit newline before C9:A74E materializes the real WAIT!=NEWLINE cursor behavior and avoids an implicit wrap",
            "reviewed_fragment_spacing_policy": "event $0106 may insert only the two user-reported literal spaces between proven adjacent text fragments; no command or layout boundary changes",
            "physical_page_capacity_lines": DIALOGUE_PAGE_LINES,
            "source_english_line_count_is_not_a_layout_limit": True,
            "snes_vwf_wrap_pixels": DIALOGUE_WRAP_PIXELS,
            "snes_parser_max_decoded_characters": DIALOGUE_WRAP_CHARS,
            "dynamic_player_name_width_assumption": "9 characters at worst-case validated glyph advance",
            "dynamic_player_name_character_assumption": "9 visible characters plus 1 conservative parser-safety unit per PLAYER_NAME",
            "maximum_generated_extra_pages_per_mapping": 2,
            "two_extra_pages_policy": "only two complete-sentence boundaries producing three independently <=3-line pages",
            "generated_page_break_encoding": "WAIT $00 + TEXT_CLEAR",
            "simulator_player_name": "000000000",
            "simulator_rejects_errors": True,
            "simulator_rejects_warnings": True,
            "simulator_rejects_implicit_wraps": True,
            "simulator_unsupported_structures_are_rejected": True,
            "semantic_line_break_preferences": "sentence boundaries strong; commas weak when materially better balanced",
            "semantic_layout_simulator_fallback": "retry whole event with compact wrapper before excluding",
            "line_start_text_x_formatter_reservation": "proven fresh-line TEXT_X padding reduces only the first formatted line's pixel/parser capacity",
            "android_leading_player_label_policy": "drop only an exact leading %S(n,0) speaker label when the mapped SNES source has no PLAYER_NAME; localized prose is otherwise unchanged",
            "adjacent_nonsemantic_player_carrier_policy": "a punctuation/whitespace-only SNES text token immediately outside an existing PLAYER_NAME binding may carry localized literal text; no PLAYER_NAME command is moved or created",
            "adjacent_player_through_carrier_policy": "one existing PLAYER_NAME immediately before a punctuation/whitespace carrier may join a binding only when Android French proves that exact extra leading placeholder",
            "duplicated_player_context_policy": "a trailing PLAYER_NAME duplicated as the next mapping's leading alignment context may be ignored only across a proven linear bridge; any called clean-ROM event must be text-free, branch-free and returning, and the SNES PLAYER_NAME remains with the following mapping",
            "reviewed_hole_player_context_policy": "in a PARTIEL event, a trailing PLAYER_NAME borrowed only as alignment context may be returned to the immediately following reviewed no-equivalent/Android-omission stock carrier when that exact PLAYER_NAME command and hole are adjacent in the canonical SNES stream; no command or carrier moves",
            "static_speaker_dynamic_addressee_policy": "when SNES and Android EN both prove STATIC_SPEAKER:%S(n)!/? but Android FR omits only the dynamic addressee, preserve the existing SNES PLAYER_NAME in its original slot and attach only the proven punctuation after the localized static speaker label; no command is created, removed, moved or reordered",
            "existing_wait_sentence_distribution_policy": "multi-slot mappings may be redistributed at complete French sentence boundaries across one existing WAIT $00, optional TEXT_CLEAR, and optionally an already-validated pure actor-action OP_32/OP_34 + COMPLETE_ACTIONS bridge; timed WAITs and PLAYER_NAME at/across a boundary remain excluded, while one identical leading PLAYER_NAME is allowed only when it sits immediately before the first mapped carrier; every stock command stays unchanged",
            "existing_timed_wait_sentence_distribution_policy": "exactly one existing WAIT $04/$08 may separate two complete source/French sentences; the timed WAIT is preserved byte-for-byte and no other boundary command is accepted",
            "reviewed_wait10_resegmentation_policy": "a structurally reviewed two-SNES/one-Android unit may split official French at a complete sentence boundary across one exact stock WAIT $10; the timed WAIT stays byte-for-byte, a proven leading PLAYER_NAME stays in place, and cursor movement preserves the canonical newline owner ($02AE before WAIT, $042D after WAIT)",
            "single_text_x_distribution_policy": "one Android anchor may distribute over exactly two SNES text carriers separated solely by one stock TEXT_X when the first stock carrier already ends in NEWLINE and Android French itself has exactly two non-empty lines; preserve the newline and TEXT_X byte-for-byte and require both localized lines to fit independently",
            "existing_wait_weak_clause_policy": "for one two-slot WAIT $00 mapping whose source slots are each complete sentences, a French comma may be the split only before an explicit discourse connector such as alors/mais/donc/pourtant/cependant",
            "existing_action_boundary_policy": "two text slots from one Android unit may be redistributed only at a complete sentence boundary across proven OP_32 walk / OP_34 loop-action / COMPLETE_ACTIONS commands, with a complete source sentence before the action; choice events remain excluded and commands remain unchanged",
            "nonsemantic_action_carrier_policy": "one three-slot semantic/layout-only/semantic mapping may preserve the stock middle carrier while distributing two complete French sentences across action-only boundaries and clean-ROM text-free returning calls",
            "shake_effect_boundary_policy": "one two-slot mapping may cross only the proven sound-call + OP_2D $02 + timed WAIT + OP_2D $04 + sound-call sequence; both sound callees must be sound-only returning scripts and every stock effect byte stays unchanged",
            "sound_effect_action_boundary_policy": "one two-slot mapping may cross only an exact proven sound-only returning OP_20..OP_27 call + one unchanged OP_2D effect + COMPLETE_ACTIONS bridge; SNES and Android EN must contain no PLAYER_NAME, Android FR may contribute exactly one comma vocative that is removed because no SNES PLAYER_NAME exists to carry it, the remaining FR is split only at a complete sentence boundary, and one newline may be materialized only when the unchanged bridge would otherwise exceed the same-line parser/pixel budget",
            "reviewed_sequence_block_policy": "a user-validated sequence_block_with_android_extra mapping may redistribute four Android French anchors over three semantic SNES slots only in the exact reviewed semantic/layout/action/semantic/WAIT+clear shape; the stock layout carrier remains untouched",
            "cross_mapping_action_sentence_overflow_policy": "one leading newline plus semantic pagination may repair a soft or decoded-capacity parser wrap only across an adjacent OP_32/OP_34 + COMPLETE_ACTIONS boundary after a complete localized sentence; accept only after clean resimulation",
            "pure_unpaused_scroll_policy": "after compact fallback fails, one semantic-boundary extra page may be tried only when UNPAUSED_SCROLL is the sole simulator defect; accept only after clean resimulation",
            "cross_mapping_sentence_overflow_policy": "after all earlier fallbacks fail, a parser-wrap + unpaused-scroll event may add one newline at a proven adjacent sentence boundary and one semantic page break; accept only after clean resimulation",
            "wait00_exact_overlap_policy": "no generic WAIT $00 carry-over cleanup; presentation changes require explicit per-event runtime validation; timed WAITs unchanged",
            "targeted_wait00_fresh_page_policy": "keep stock WAIT $00 bytes unchanged; $0106/C9:2994 is runtime-validated and the eight round13 detector matches are explicitly converted from newline-only carriers to TEXT_CLEAR as a single user-requested runtime-test batch; no generic WAIT carry-over cleanup",
            "wait_semantics_policy": "runtime-validated: WAIT pauses without advancing the text cursor; only explicit $7F NEWLINE or TEXT_CLEAR changes the physical line/page",
            "explicit_post_wait_newline_policy": "materialize reviewed formatter line boundaries that older simulation had implicitly attributed to WAIT; after compact formatting, a sole decoded-capacity wrap may additionally receive one leading NEWLINE only at an immediate text -> WAIT $00 -> text complete-sentence boundary when exactly one such candidate makes the whole event simulator-clean; keep WAIT bytes unchanged; use TEXT_CLEAR instead of NEWLINE when a three-line window would otherwise scroll before the next pause",
            "choice_row_prefix_restore_policy": "when Android prose reflow removes the stock final NEWLINE + optional spaces + '(' immediately before CHOICE_BEGIN and the first stock CHOICE_OPTION would rewind over translated prompt text, restore only that stock row suffix; for a standalone decorative '(' carrier after dynamic stock output, one explicit NEWLINE may be prefixed for the same first-anchor condition; no option coordinate changes are made by this repair and unrelated new simulator defects reject it",
            "adaptive_choice_anchor_policy": "keep the first CHOICE_OPTION stock; when a later stock coordinate would overwrite the preceding localized label in the decoded row, move only that later coordinate right to the minimum cell immediately after the label; accept only a rightward <32 coordinate whose whole event passes the independent zero-error/zero-warning/zero-wrap simulation; runtime validated by the $03/$11 -> $03/$12 Temple de l'Eau/Pandora diagnostic",
            "adaptive_choice_decoration_policy": "preserve the canonical outer ( ... ) decoration whenever the normal choice event is simulator-clean; only after a width/layout rejection, retry by removing the proven opening/closing parenthesis pair plus its adjacent horizontal padding; when stripping alone is insufficient, it may be composed with the already validated later-anchor-only right shift, while the first CHOICE_OPTION remains stock; accept only if the whole event passes the same zero-error/zero-warning/zero-wrap gate",
            "reviewed_choice_layout_recipe_policy": "Round-72 reviewed decoration removals are stored as structural event/carrier recipes with no French prose. They are reapplied deterministically after Android-FR formatting; if restoring the choice-row newline would otherwise force a fresh page, only the owning Android-backed prompt is retried with the existing compact wrapper before the reviewed decoration is stripped.",
        },
        "coverage": {
            "semantic_source_event_count": sum(
                1
                for event in source_document["events"]
                if any(
                    token.get("type") == "text" and _auto_semantic(token.get("source", ""))
                    for token in event["tokens"]
                )
            ),
            "complete_aligned_event_count": complete_aligned_count,
            "formatter_candidate_event_count": formatter_candidate_count,
            "accepted_event_count": len(accepted_events),
            "complete_accepted_event_count": len(accepted_events) - len(visible_partial_events),
            "partial_accepted_event_count": len(visible_partial_events),
            "user_validated_visually_complete_event_count": len(user_validated_complete_events),
            "user_validated_structural_omission_event_count": len(structural_omission_indexes_by_event),
            "user_validated_structural_omitted_command_count": sum(
                len(indexes) for indexes in structural_omission_indexes_by_event.values()
            ),
            "manual_supplement_entry_count": sum(len(entries) for entries in manual_supplements_by_event.values()),
            "parameterized_inn_event_count": len(parameterized_inn_events),
            "partial_unresolved_or_manual_id_count": sum(
                len(partial_unresolved_semantic_ids_by_event[event_id]) for event_id in visible_partial_events
            ),
            "partial_layout_deferred_id_count": sum(
                len(partial_layout_deferred_semantic_ids_by_event.get(event_id, []))
                for event_id in visible_partial_events
            ),
            "generic_structural_safe_subset_event_count": sum(
                event_id in generic_layout_deferred_semantic_ids_by_event
                for event_id in visible_partial_events
            ),
            "generic_structural_safe_subset_deferred_id_count": sum(
                len(set(generic_layout_deferred_semantic_ids_by_event.get(event_id, [])))
                for event_id in visible_partial_events
            ),
            "direct_simulator_safe_subset_event_count": len({
                report.get("event_id")
                for report in formatted
                if report.get("layout_deferred_policy") == "direct_simulator_safe_subset"
            }),
            "direct_simulator_safe_subset_deferred_id_count": sum(
                1
                for report in formatted
                if report.get("layout_deferred_policy") == "direct_simulator_safe_subset"
            ),
            "accepted_semantic_source_id_count": accepted_semantic_ids,
            "translation_entry_count": len(ordered_entries),
            "fragment_spacing_repaired_event_count": sum(bool(value) for value in fragment_spacing_repairs_by_event.values()),
            "fragment_spacing_repair_count": sum(len(value) for value in fragment_spacing_repairs_by_event.values()),
            "explicit_post_wait_newline_repaired_event_count": sum(bool(value) for value in explicit_post_wait_newline_repairs_by_event.values()),
            "explicit_post_wait_newline_repair_count": sum(len(value) for value in explicit_post_wait_newline_repairs_by_event.values()),
            "round48_pagination_repaired_event_count": sum(bool(value) for value in round48_pagination_repairs_by_event.values()),
            "round48_pagination_repair_count": sum(len(value) for value in round48_pagination_repairs_by_event.values()),
            "round49_04e9_wait00_clear_repaired_event_count": sum(bool(value) for value in round49_04e9_wait00_clear_repairs_by_event.values()),
            "round49_04e9_wait00_clear_repair_count": sum(len(value) for value in round49_04e9_wait00_clear_repairs_by_event.values()),
            "round50_01ce_choice_page_clear_repaired_event_count": sum(bool(value) for value in round50_01ce_choice_page_clear_repairs_by_event.values()),
            "round50_01ce_choice_page_clear_repair_count": sum(len(value) for value in round50_01ce_choice_page_clear_repairs_by_event.values()),
            "wait00_overlap_repaired_event_count": sum(bool(value) for value in wait00_repairs_by_event.values()),
            "wait00_overlap_repair_count": sum(len(value) for value in wait00_repairs_by_event.values()),
            "unpaused_scroll_repaired_event_count": sum(bool(value) for value in unpaused_scroll_repairs_by_event.values()),
            "unpaused_scroll_repair_count": sum(len(value) for value in unpaused_scroll_repairs_by_event.values()),
            "live_line_compact_repaired_event_count": sum(bool(value) for value in live_line_compact_repairs_by_event.values()),
            "live_line_compact_repair_count": sum(len(value) for value in live_line_compact_repairs_by_event.values()),
            "cross_mapping_sentence_repaired_event_count": sum(bool(value) for value in cross_mapping_sentence_repairs_by_event.values()),
            "cross_mapping_sentence_repair_count": sum(len(value) for value in cross_mapping_sentence_repairs_by_event.values()),
            "structural_reaction_page_repaired_event_count": sum(bool(value) for value in structural_reaction_page_repairs_by_event.values()),
            "structural_reaction_page_repair_count": sum(len(value) for value in structural_reaction_page_repairs_by_event.values()),
            "android_leading_player_label_removed_mapping_count": sum(
                any("%S(" in marker for marker in (entry.get("structural_markers_removed") or []))
                for entry in formatted
            ),
            "adjacent_nonsemantic_player_carrier_mapping_count": sum(
                bool(entry.get("adjacent_nonsemantic_carrier_ids")) for entry in formatted
            ),
            "adjacent_nonsemantic_player_carrier_entry_count": sum(
                len(entry.get("adjacent_nonsemantic_carrier_ids") or []) for entry in formatted
            ),
            "adjacent_player_through_carrier_mapping_count": sum(
                bool(entry.get("adjacent_player_carrier_indexes")) for entry in formatted
            ),
            "duplicated_player_context_repaired_event_count": sum(
                bool(duplicated_player_context_repairs_by_event.get(event_id))
                for event_id in accepted_events
            ),
            "duplicated_player_context_repair_count": sum(
                len(duplicated_player_context_repairs_by_event.get(event_id, []))
                for event_id in accepted_events
            ),
            "reviewed_hole_player_context_repaired_event_count": sum(
                bool(reviewed_hole_player_context_repairs_by_event.get(event_id))
                for event_id in accepted_events
            ),
            "reviewed_hole_player_context_repair_count": sum(
                len(reviewed_hole_player_context_repairs_by_event.get(event_id, []))
                for event_id in accepted_events
            ),
            "preserved_static_speaker_dynamic_addressee_mapping_count": sum(
                bool(entry.get("preserved_static_speaker_dynamic_addressee"))
                for entry in formatted
            ),
            "existing_wait_sentence_distribution_mapping_count": sum(
                bool(entry.get("existing_wait_sentence_distribution")) for entry in formatted
            ),
            "existing_wait_leading_player_mapping_count": sum(
                entry.get("existing_wait_leading_player_index") is not None for entry in formatted
            ),
            "partial_semantic_layout_fallback_event_count": sum(
                any(report.get("semantic_layout_fallback") for report in reports_by_event.get(event_id, []))
                for event_id in visible_partial_events
            ),
            "existing_timed_wait_sentence_distribution_mapping_count": sum(
                bool(entry.get("existing_timed_wait_sentence_distribution")) for entry in formatted
            ),
            "reviewed_wait10_resegmentation_mapping_count": sum(
                bool(entry.get("structural_timed_wait10_resegmentation")) for entry in formatted
            ),
            "single_text_x_distribution_mapping_count": sum(
                bool(entry.get("structural_single_text_x_distribution")) for entry in formatted
            ),
            "existing_wait_weak_clause_boundary_mapping_count": sum(
                bool(entry.get("existing_wait_weak_clause_boundary")) for entry in formatted
            ),
            "existing_action_sentence_split_mapping_count": sum(
                bool(entry.get("existing_action_sentence_split")) for entry in formatted
            ),
            "nonsemantic_action_carrier_mapping_count": sum(
                bool(entry.get("nonsemantic_action_carrier_distribution")) for entry in formatted
            ),
            "shake_effect_sentence_distribution_mapping_count": sum(
                bool(entry.get("existing_shake_effect_sentence_distribution")) for entry in formatted
            ),
            "sound_effect_action_sentence_distribution_mapping_count": sum(
                bool(entry.get("sound_effect_action_sentence_distribution")) for entry in formatted
            ),
            "reviewed_sequence_block_distribution_mapping_count": sum(
                bool(entry.get("reviewed_sequence_block_distribution")) for entry in formatted
            ),
            "action_boundary_line_break_count": sum(
                bool(entry.get("inserted_action_boundary_line_break")) for entry in formatted
            ),
            "choice_row_layout_repaired_event_count": sum(
                bool(choice_row_layout_repairs_by_event.get(event_id))
                for event_id in accepted_events
            ),
            "choice_row_layout_repair_count": sum(
                len(choice_row_layout_repairs_by_event.get(event_id, []))
                for event_id in accepted_events
            ),
            "adaptive_choice_anchor_shifted_event_count": sum(
                bool(adaptive_choice_anchor_repairs_by_event.get(event_id))
                for event_id in accepted_events
            ),
            "adaptive_choice_anchor_shift_count": sum(
                len(adaptive_choice_anchor_repairs_by_event.get(event_id, []))
                for event_id in accepted_events
            ),
            "adaptive_choice_decoration_stripped_event_count": sum(
                bool(adaptive_choice_decoration_repairs_by_event.get(event_id))
                for event_id in accepted_events
            ),
            "adaptive_choice_decoration_stripped_count": sum(
                len(adaptive_choice_decoration_repairs_by_event.get(event_id, []))
                for event_id in accepted_events
            ),
            "reviewed_choice_layout_recipe_event_count": len(reviewed_choice_layout_recipes),
            "reviewed_choice_compact_reflow_event_count": sum(
                bool(reviewed_choice_compact_repairs_by_event.get(event_id))
                for event_id in accepted_events
            ),
            "excluded_event_count": len(excluded_events),
            "excluded_stage_counts": stage_counts,
        },
        "accepted_events": accepted_events,
        "user_validated_visually_complete_events": [
            complete_event_metadata(event_id) for event_id in user_validated_complete_events
        ],
        "user_validated_structural_omissions": list(DIALOGUE_USER_VALIDATED_STRUCTURAL_OMISSIONS),
        "user_validated_structural_command_overrides": list(DIALOGUE_USER_VALIDATED_STRUCTURAL_COMMAND_OVERRIDES),
        "manual_dialogue_supplements": translation_document["manual_dialogue_supplements"],
        "user_validated_stock_english_overrides": translation_document["user_validated_stock_english_overrides"],
        "parameterized_android_templates": translation_document["parameterized_android_templates"],
        "partial_accepted_events": [
            partial_metadata(event_id) for event_id in visible_partial_events
        ],
        "formatted_mappings": formatted,
        "choice_row_layout_repairs": [
            {"event_id": event_id, **repair}
            for event_id in accepted_events
            for repair in choice_row_layout_repairs_by_event.get(event_id, [])
        ],
        "adaptive_choice_anchor_repairs": [
            {"event_id": event_id, **repair}
            for event_id in accepted_events
            for repair in adaptive_choice_anchor_repairs_by_event.get(event_id, [])
        ],
        "adaptive_choice_decoration_repairs": [
            {"event_id": event_id, **repair}
            for event_id in accepted_events
            for repair in adaptive_choice_decoration_repairs_by_event.get(event_id, [])
        ],
        "reviewed_choice_layout_recipes": [
            reviewed_choice_layout_recipes[event_id]
            for event_id in sorted(reviewed_choice_layout_recipes, key=lambda value: int(value, 16))
        ],
        "reviewed_choice_compact_repairs": [
            {"event_id": event_id, **repair}
            for event_id in accepted_events
            for repair in reviewed_choice_compact_repairs_by_event.get(event_id, [])
        ],
        "wait00_overlap_repairs": [
            {"event_id": event_id, **repair}
            for event_id in accepted_events
            for repair in wait00_repairs_by_event.get(event_id, [])
        ],
        "round48_pagination_repairs": [
            {"event_id": event_id, **repair}
            for event_id in accepted_events
            for repair in round48_pagination_repairs_by_event.get(event_id, [])
        ],
        "round49_04e9_wait00_clear_repairs": [
            {"event_id": event_id, **repair}
            for event_id in accepted_events
            for repair in round49_04e9_wait00_clear_repairs_by_event.get(event_id, [])
        ],
        "round50_01ce_choice_page_clear_repairs": [
            {"event_id": event_id, **repair}
            for event_id in accepted_events
            for repair in round50_01ce_choice_page_clear_repairs_by_event.get(event_id, [])
        ],
        "automatic_216px_reflows": [
            {"event_id": event_id, "reflows": repairs}
            for event_id, repairs in automatic_216px_reflows_by_event.items()
            if repairs
        ],
        "carrier_boundary_newline_repairs": [
            {"event_id": event_id, "repairs": repairs}
            for event_id, repairs in carrier_boundary_newline_repairs_by_event.items()
            if repairs
        ],
        "carrier_repack_repairs": [
            {"event_id": event_id, "repairs": repairs}
            for event_id, repairs in carrier_repack_repairs_by_event.items()
            if repairs
        ],
        "live_player_prefix_reflow_repairs": [
            {"event_id": event_id, "repairs": repairs}
            for event_id, repairs in live_player_prefix_reflow_repairs_by_event.items()
            if repairs
        ],
        "source_derived_layout_search_repairs": [
            {"event_id": event_id, "repairs": repairs}
            for event_id, repairs in source_derived_layout_search_repairs_by_event.items()
            if repairs
        ],
        "unpaused_scroll_repairs": [
            {"event_id": event_id, **repair}
            for event_id in accepted_events
            for repair in unpaused_scroll_repairs_by_event.get(event_id, [])
        ],
        "live_line_compact_repairs": [
            {"event_id": event_id, **repair}
            for event_id in accepted_events
            for repair in live_line_compact_repairs_by_event.get(event_id, [])
        ],
        "cross_mapping_sentence_repairs": [
            {"event_id": event_id, **repair}
            for event_id in accepted_events
            for repair in cross_mapping_sentence_repairs_by_event.get(event_id, [])
        ],
        "structural_reaction_page_repairs": [
            {"event_id": event_id, **repair}
            for event_id in accepted_events
            for repair in structural_reaction_page_repairs_by_event.get(event_id, [])
        ],
        "fragment_spacing_repairs": [
            {"event_id": event_id, **repair}
            for event_id, repairs in fragment_spacing_repairs_by_event.items()
            for repair in repairs
        ],
        "explicit_post_wait_newline_repairs": [
            {"event_id": event_id, **repair}
            for event_id in accepted_events
            for repair in explicit_post_wait_newline_repairs_by_event.get(event_id, [])
        ],
        "duplicated_player_context_repairs": [
            {"event_id": event_id, **repair}
            for event_id in accepted_events
            for repair in duplicated_player_context_repairs_by_event.get(event_id, [])
        ],
        "reviewed_hole_player_context_repairs": [
            {"event_id": event_id, **repair}
            for event_id in accepted_events
            for repair in reviewed_hole_player_context_repairs_by_event.get(event_id, [])
        ],
        "excluded_events": excluded_events,
    }
    return translation_document, report_document


def dialogue_format_mass_excluded_csv(report: dict, source_document: dict) -> str:
    """Render one row per semantic source phrase in an event excluded from mass output."""
    import csv
    import io

    by_event = {event["event_id"]: event for event in source_document["events"]}
    output = io.StringIO(newline="")
    fields = [
        "event_id",
        "stage",
        "snes_id",
        "texte_source_snes_usa",
        "est_non_mappe_alignement",
        "raison_evenement_exclu",
        "commentaire_utilisateur",
    ]
    writer = csv.DictWriter(output, fieldnames=fields, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writeheader()
    for excluded in report.get("excluded_events", []):
        event_id = excluded["event_id"]
        event = by_event[event_id]
        missing = set(excluded.get("missing_semantic_ids", []))
        detail_messages: list[str] = []
        for detail in excluded.get("details", []):
            if "message" in detail:
                prefix = detail.get("code") or "+".join(detail.get("snes_ids", []))
                detail_messages.append(f"{prefix}: {detail['message']}" if prefix else detail["message"])
            elif "reason" in detail:
                text_id = detail.get("snes_id", "")
                detail_messages.append(f"{text_id}: {detail['reason']}")
        reason = " | ".join(detail_messages)
        semantic = [
            token
            for token in event["tokens"]
            if token.get("type") == "text" and _auto_semantic(token.get("source", ""))
        ]
        for token in semantic:
            writer.writerow(
                {
                    "event_id": event_id,
                    "stage": excluded["stage"],
                    "snes_id": token["id"],
                    "texte_source_snes_usa": token["source"].replace("\r", "").replace("\n", " ⏎ ").strip(),
                    "est_non_mappe_alignement": "oui" if token["id"] in missing else "non",
                    "raison_evenement_exclu": reason,
                    "commentaire_utilisateur": "",
                }
            )
    return output.getvalue()


def dialogue_unmapped_csv(document: dict) -> str:
    """Render the automatic alignment's unresolved semantic source phrases."""
    import csv
    import io

    output = io.StringIO(newline="")
    fieldnames = [
        "event_id",
        "snes_id",
        "texte_source_snes_usa",
        "raison",
        "note",
        "meilleur_id_android_anglais",
        "meilleur_texte_anglais_android",
        "meilleur_score_lexical",
        "meilleure_couverture_source",
        "meilleur_texte_francais_candidat",
        "deuxieme_id_android_anglais",
        "deuxieme_score_lexical",
        "commentaire_utilisateur",
    ]
    writer = csv.DictWriter(
        output,
        fieldnames=fieldnames,
        delimiter=";",
        quoting=csv.QUOTE_MINIMAL,
        lineterminator="\n",
    )
    writer.writeheader()
    for entry in document["unmapped"]:
        candidates = entry.get("top_candidates", [])
        first = candidates[0] if candidates else {}
        second = candidates[1] if len(candidates) > 1 else {}
        writer.writerow(
            {
                "event_id": entry["event_id"],
                "snes_id": entry["snes_id"],
                "texte_source_snes_usa": entry["source"].replace("\r", "").replace("\n", " ⏎ ").strip(),
                "raison": entry["reason"],
                "note": entry["note"],
                "meilleur_id_android_anglais": first.get("android_id", ""),
                "meilleur_texte_anglais_android": first.get("android_english", "").replace("\r", "").replace("\n", " ⏎ ").strip(),
                "meilleur_score_lexical": first.get("lexical_score", ""),
                "meilleure_couverture_source": first.get("source_token_coverage", ""),
                "meilleur_texte_francais_candidat": first.get("french_display", "").replace("\r", "").replace("\n", " ⏎ ").strip(),
                "deuxieme_id_android_anglais": second.get("android_id", ""),
                "deuxieme_score_lexical": second.get("lexical_score", ""),
                "commentaire_utilisateur": "",
            }
        )
    # UTF-8 BOM is added when the caller writes bytes/text to disk.
    return output.getvalue()


def serialized(document: dict) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def write_or_check(output: Path, text: str, *, check: bool, source_label: str) -> None:
    if check:
        try:
            existing = output.read_text(encoding="utf-8")
        except OSError as exc:
            raise SystemExit(f"Cannot read {output}: {exc}") from exc
        if existing != text:
            raise SystemExit(f"{output} is not up to date with {source_label}")
        print(f"Android import/alignment check OK: {output}")
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    print(f"Generated {output} from {source_label}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--only",
        choices=("intro", "dialogue-auto", "dialogue-format-mass"),
        default="intro",
        help=(
            "generate the intro translation, the canonical dialogue alignment, "
            "or the complete simulator-validated dialogue translation"
        ),
    )
    parser.add_argument(
        "--scrtxt",
        type=Path,
        default=DEFAULT_SCRTXT_FR,
        help="Android French scrtxt binary",
    )
    parser.add_argument(
        "--scrtxt-en",
        type=Path,
        default=DEFAULT_SCRTXT_EN,
        help="Android English scrtxt binary (required for dialogue generation)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="destination JSON; defaults depend on --only",
    )
    parser.add_argument(
        "--unmapped-csv",
        type=Path,
        help="dialogue-auto unresolved CSV destination (default: mappings/android/dialogues_unmapped.csv)",
    )
    parser.add_argument(
        "--rom",
        type=Path,
        help="clean unheadered USA ROM; required for dialogue-format-mass VWF metrics",
    )
    parser.add_argument(
        "--format-report",
        type=Path,
        help="dialogue-format-mass report destination",
    )
    parser.add_argument(
        "--excluded-csv",
        type=Path,
        help="dialogue-format-mass exclusion CSV destination",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify that the destination already equals generated output",
    )
    args = parser.parse_args()

    french_path = args.scrtxt.resolve()
    try:
        french = read_scrtxt(french_path)
        if args.only == "intro":
            document = make_intro_translation(french)
            output = (args.output or DEFAULT_INTRO_OUTPUT).resolve()
            source_label = str(french_path)
            format_report = None
        else:
            english_path = args.scrtxt_en.resolve()
            english = read_scrtxt(english_path)
            source_label = f"{english_path} + {french_path} + assets/dialogues.json"
            if args.only == "dialogue-auto":
                document = make_dialogue_auto_alignment(
                    english,
                    french,
                    english_path=english_path,
                    french_path=french_path,
                )
                output = (args.output or DEFAULT_DIALOGUE_AUTO_OUTPUT).resolve()
                format_report = None
            else:
                if args.rom is None:
                    raise ValueError("--rom is required for dialogue-format-mass")
                base_rom = args.rom.resolve().read_bytes()
                document, format_report = make_dialogue_format_mass(
                    english,
                    french,
                    english_path=english_path,
                    french_path=french_path,
                    base_rom=base_rom,
                )
                output = (args.output or DEFAULT_DIALOGUE_FORMAT_MASS_OUTPUT).resolve()
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc

    write_or_check(output, serialized(document), check=args.check, source_label=source_label)

    if args.only == "dialogue-auto":
        csv_output = (args.unmapped_csv or DEFAULT_DIALOGUE_UNMAPPED_CSV).resolve()
        csv_bytes = ("\ufeff" + dialogue_unmapped_csv(document)).encode("utf-8")
        if args.check:
            try:
                existing_csv = csv_output.read_bytes()
            except OSError as exc:
                raise SystemExit(f"Cannot read {csv_output}: {exc}") from exc
            if existing_csv != csv_bytes:
                raise SystemExit(f"{csv_output} is not up to date with automatic dialogue alignment")
            print(f"Android alignment CSV check OK: {csv_output}")
        else:
            csv_output.parent.mkdir(parents=True, exist_ok=True)
            csv_output.write_bytes(csv_bytes)
            print(f"Generated {csv_output} from automatic dialogue alignment")

    if args.only == "dialogue-format-mass":
        assert format_report is not None
        report_output = (args.format_report or DEFAULT_DIALOGUE_FORMAT_MASS_REPORT).resolve()
        write_or_check(
            report_output,
            serialized(format_report),
            check=args.check,
            source_label=source_label + " + clean USA ROM VWF metrics",
        )
        excluded_csv_output = (args.excluded_csv or DEFAULT_DIALOGUE_FORMAT_MASS_EXCLUDED_CSV).resolve()
        source_document = json.loads(DIALOGUE_SOURCE.read_text(encoding="utf-8"))
        excluded_csv_bytes = (
            "\ufeff" + dialogue_format_mass_excluded_csv(format_report, source_document)
        ).encode("utf-8")
        if args.check:
            try:
                existing_csv = excluded_csv_output.read_bytes()
            except OSError as exc:
                raise SystemExit(f"Cannot read {excluded_csv_output}: {exc}") from exc
            if existing_csv != excluded_csv_bytes:
                raise SystemExit(f"{excluded_csv_output} is not up to date with mass dialogue formatting")
            print(f"Dialogue mass exclusion CSV check OK: {excluded_csv_output}")
        else:
            excluded_csv_output.parent.mkdir(parents=True, exist_ok=True)
            excluded_csv_output.write_bytes(excluded_csv_bytes)
            print(f"Generated {excluded_csv_output} from mass dialogue formatting")

    if not args.check:
        if args.only == "intro":
            print(f"Imported {len(INTRO_ANDROID_IDS)} validated intro entries")
        elif args.only == "dialogue-auto":
            coverage = document["coverage"]
            print(
                "Dialogue automatic alignment: "
                f"{coverage['mapped_semantic_source_id_count']}/{coverage['semantic_source_id_count']} "
                f"semantic source IDs mapped ({coverage['mapped_semantic_percent']}%); "
                f"{coverage['unmapped_semantic_source_id_count']} unresolved; no translation JSON changed"
            )
        else:
            assert format_report is not None
            coverage = format_report["coverage"]
            print(
                "Dialogue format mass: "
                f"{coverage['accepted_event_count']} simulator-clean event(s), "
                f"{coverage['translation_entry_count']} translated source token(s); "
                f"{coverage['excluded_event_count']} event(s) excluded"
            )


if __name__ == "__main__":
    main()
