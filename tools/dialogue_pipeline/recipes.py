from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
import re

from .common import ROOT, _load_recipe_document, normalize_android_prose, sentence_break_positions
from .policies import *
from shared.dialogue.translation import event_text_index, normalize_android_french, semantic_wrap_markup, format_mapping as format_dialogue_mapping

DIALOGUE_REDISTRIBUTION_RECIPES = ROOT / "recipes" / "android" / "dialogues_redistribution.json"
DIALOGUE_MAPPING_LAYOUT_RECIPES = ROOT / "recipes" / "android" / "dialogues_mapping_layout.json"
DIALOGUE_CHOICE_LAYOUT_RECIPES = ROOT / "recipes" / "android" / "dialogues_choice_layout.json"
DIALOGUE_COVERAGE_REPAIR_RECIPES = ROOT / "recipes" / "android" / "dialogues_coverage_repair.json"
DIALOGUE_MANUAL_SUPPLEMENTS = ROOT / "translations" / "dialogues_manual_supplements.json"

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
    boundaries = sentence_break_positions(suffix)
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


