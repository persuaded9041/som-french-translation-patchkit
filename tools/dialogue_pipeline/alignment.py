from __future__ import annotations

from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
import json
import math
import re

from shared.dialogue_translation import normalize_android_french
from .common import (DEFAULT_SYSTXT_EN, DEFAULT_SYSTXT_FR, DIALOGUE_REVIEWED_ALIGNMENT_RECIPES, DIALOGUE_SOURCE, _load_recipe_document, read_scrtxt, require_parallel_scrtxt, normalize_alignment_text, load_dialogue_text_entries, english_anchor_interval, sha256, render_snes_review_parts, android_anchor_units)
from .policies import DIALOGUE_FORCED_UNMAPPED, DIALOGUE_VALIDATED_ANDROID_OMISSIONS, DIALOGUE_VALIDATED_CONTEXTUAL_TEMPLATES, DIALOGUE_REVIEWED_AUTO_OVERRIDES, DIALOGUE_VALIDATED_ALTERNATIVE_GROUPS

@lru_cache(maxsize=None)
def _auto_metric_tokens(normalized: str) -> tuple[tuple[str, ...], frozenset[str]]:
    """Token views shared across lexical comparisons of the same normalized text."""
    tokens = tuple(normalized.split())
    return tokens, frozenset(tokens)


@lru_cache(maxsize=None)
def _auto_metrics_normalized(source_norm: str, candidate_norm: str) -> dict[str, float]:
    """Lexical metrics keyed by the normalized forms that actually define them."""
    try:
        from rapidfuzz import fuzz
    except ImportError as exc:  # pragma: no cover - user environment diagnostic
        raise ValueError(
            "Automatic dialogue alignment requires RapidFuzz; install requirements.txt"
        ) from exc

    if not source_norm or not candidate_norm:
        return {
            "character_similarity": 0.0,
            "source_token_coverage": 0.0,
            "lexical_score": 0.0,
        }
    character_similarity = float(fuzz.ratio(source_norm, candidate_norm))
    source_tokens, _ = _auto_metric_tokens(source_norm)
    _, candidate_tokens = _auto_metric_tokens(candidate_norm)
    covered = sum(token in candidate_tokens for token in source_tokens)
    source_token_coverage = 100.0 * covered / len(source_tokens)
    lexical_score = character_similarity * 0.75 + source_token_coverage * 0.25
    return {
        "character_similarity": round(character_similarity, 1),
        "source_token_coverage": round(source_token_coverage, 1),
        "lexical_score": round(lexical_score, 1),
    }


def _auto_metrics(source: str, candidate: str) -> dict[str, float]:
    """Fast deterministic lexical metrics used only by the automatic aligner."""
    return _auto_metrics_normalized(
        normalize_alignment_text(source),
        normalize_alignment_text(candidate),
    )


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
        self._rank_cache: dict[tuple[str, int], tuple[dict, ...]] = {}

    def rank(self, source: str, *, limit: int = 20) -> list[dict]:
        from rapidfuzz import fuzz

        normalized = normalize_alignment_text(source)
        if not normalized:
            return []
        cache_key = (normalized, limit)
        cached = self._rank_cache.get(cache_key)
        if cached is not None:
            return [dict(item) for item in cached]
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
            ranked.append({
                "android_id": text_id,
                **_auto_metrics_normalized(normalized, self.choices[text_id]),
            })
        ranked.sort(
            key=lambda item: (item["lexical_score"], item["character_similarity"]),
            reverse=True,
        )
        self._rank_cache[cache_key] = tuple(dict(item) for item in ranked)
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
    # These short comparison spans are reused throughout the dynamic-programming
    # grid. Build each structural span once per session instead of repeatedly
    # rendering/joining it for every opposite-side position.
    source_spans = {
        (source_index, width): _auto_render_span(
            session, source_index, source_index + width - 1
        )
        for source_index in range(source_count)
        for width in range(1, min(3, source_count - source_index) + 1)
    }
    android_spans = {
        (android_index, width): " ".join(
            english[text_id]
            for text_id in android_ids[android_index : android_index + width]
        )
        for android_index in range(android_count)
        for width in range(1, min(3, android_count - android_index) + 1)
    }
    normalized_source_spans = {
        key: normalize_alignment_text(value) for key, value in source_spans.items()
    }
    normalized_android_spans = {
        key: normalize_alignment_text(value) for key, value in android_spans.items()
    }

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
                source = source_spans[(source_index, source_width)]
                for android_width in range(1, min(3, android_count - android_index) + 1):
                    candidate_ids = android_ids[android_index : android_index + android_width]
                    evidence = _auto_metrics_normalized(
                        normalized_source_spans[(source_index, source_width)],
                        normalized_android_spans[(android_index, android_width)],
                    )
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


def _auto_position_context_occurrences(
    context_records: list[dict],
    source: dict[str, dict],
    index: _AutoCandidateIndex,
) -> list[dict]:
    """Flatten immutable positional evidence once for repeated target probes."""
    occurrences: list[dict] = []
    for record in context_records:
        if not record.get("android_ids"):
            continue
        android_positions = [
            index.anchor_pos[text_id]
            for text_id in record["android_ids"]
            if text_id in index.anchor_pos
        ]
        if not android_positions:
            continue
        android_min = min(android_positions)
        android_max = max(android_positions)
        for neighbor_id in record.get("snes_ids", []):
            neighbor_position = _auto_source_rom_position(neighbor_id)
            if neighbor_position is None or neighbor_id not in source:
                continue
            occurrences.append(
                {
                    "snes_id": neighbor_id,
                    "event_id": source[neighbor_id]["event_id"],
                    "snes_position": neighbor_position,
                    "android_ids": list(record["android_ids"]),
                    "android_min": android_min,
                    "android_max": android_max,
                }
            )
    return occurrences


def _auto_equivalent_group_position_prediction(
    snes_ids: list[str] | tuple[str, ...],
    android_groups: list[list[int]] | tuple[tuple[int, ...], ...],
    context_records: list[dict],
    source: dict[str, dict],
    index: _AutoCandidateIndex,
    *,
    context_occurrences: list[dict] | None = None,
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

    prepared = context_occurrences
    if prepared is None:
        prepared = _auto_position_context_occurrences(context_records, source, index)
    occurrences: list[dict] = []
    for occurrence in prepared:
        if occurrence["snes_id"] in target_set:
            continue
        snes_distance = min(
            abs(occurrence["snes_position"] - target) for target in target_positions
        )
        if snes_distance > 0x300:
            continue
        occurrences.append(
            {
                "snes_id": occurrence["snes_id"],
                "event_id": occurrence["event_id"],
                "snes_distance": snes_distance,
                "android_ids": occurrence["android_ids"],
                "android_min": occurrence["android_min"],
                "android_max": occurrence["android_max"],
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
    position_context = _auto_position_context_occurrences(frozen_context, source, index)

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
            [snes_id], android_groups, frozen_context, source, index, context_occurrences=position_context
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
            record.get("snes_ids", []), alternatives, frozen_context, source, index, context_occurrences=position_context
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
    position_context = _auto_position_context_occurrences(frozen_context, source, index)
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
            [snes_id], [[android_id]], frozen_context, source, index, context_occurrences=position_context
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
    position_context = _auto_position_context_occurrences(frozen_context, source, index)
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
            [snes_id], [[android_id]], frozen_context, source, index, context_occurrences=position_context
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


