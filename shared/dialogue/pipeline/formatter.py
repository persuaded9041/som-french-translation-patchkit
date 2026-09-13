from __future__ import annotations

from functools import lru_cache
from itertools import combinations
import json
import math
from pathlib import Path
import re

from shared.dialogue.translation import (
    DIALOGUE_PAGE_LINES, DIALOGUE_WRAP_CHARS, DIALOGUE_WRAP_PIXELS,
    format_mapping as format_dialogue_mapping,
    format_mapping_across_existing_wait_boundaries, format_mapping_across_existing_timed_wait_boundary,
    format_mapping_across_existing_action_boundary, event_text_index, format_event_text_index, normalize_android_french,
    sentence_boundary_positions, markup_width, semantic_wrap_markup, make_dialogue_advances,
    player_placeholder_width, MAX_PLAYER_NAME_CHARS, make_translation_document as make_dialogue_translation_document,
)
from shared.dialogue.codec import TRANSLATION_CLEAR, TRANSLATION_TRAILING_PAGE_BREAK_ALLOWLIST, parse_event
from shared.dialogue.structure import (resolve_structural_omission_token_indexes, resolve_structural_command_overrides,
    resolve_structural_command_insertions)
from shared.core.rom import validate_base_rom
from .common import ROOT, _load_recipe_document, normalize_android_prose, normalize_alignment_text, sentence_break_positions
from .policies import *
from .alignment import make_dialogue_auto_alignment, is_semantic_text
from .final_layout import apply_validated_final_layout
from .final_structure import apply_validated_final_structure
from .post_structure_layout import apply_validated_post_structure_layout
from .review_delta import (apply_round85_review_delta, reviewed_structural_command_overrides,
    reviewed_choice_option_position_overrides, reviewed_appended_entry_order)
from .recipes import (
    load_dialogue_redistribution_recipes, reviewed_live_prefix_layout_lock_ids, _render_mapping_layout_recipe,
    _load_dialogue_coverage_repair_recipes, _apply_dialogue_coverage_repairs,
    _load_reviewed_choice_layout_recipes, _load_manual_dialogue_supplements,
    _format_manual_supplement, _format_android_extra_page, _parameterized_inn_prompt,
)

DIALOGUE_LAYOUT_SEARCH_RECIPES = ROOT / "recipes" / "android" / "dialogues_layout_search.json"

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
            if is_semantic_text(source):
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
    from shared.dialogue.simulator import simulate_event

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
    from shared.dialogue.simulator import simulate_event

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
    from shared.dialogue.simulator import simulate_event

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
    from shared.dialogue.simulator import simulate_event

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
    from shared.dialogue.simulator import simulate_event

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
        by_id, by_event = format_event_text_index(source_document)
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

    by_id, by_event = format_event_text_index(source_document)
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

    boundaries = sentence_boundary_positions(french_without_vocative)
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
        or markup_width(combined, advances) > DIALOGUE_WRAP_PIXELS
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

    by_id, by_event = format_event_text_index(source_document)
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
    boundaries = sentence_boundary_positions(french)
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

    by_id, by_event = format_event_text_index(source_document)
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

    by_id, by_event = format_event_text_index(source_document)
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
    boundaries = sentence_boundary_positions(french)
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

    by_id, by_event = format_event_text_index(source_document)
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

    by_id, _ = format_event_text_index(source_document)
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

    by_id, by_event = format_event_text_index(source_document)
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

    by_id, by_event = format_event_text_index(source_document)
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

    boundaries = sentence_boundary_positions(french_full)
    if not boundaries:
        raise ValueError("WAIT $10 resegmentation requires a complete-sentence split")

    second_owns_leading_newline = by_id[snes_ids[1]]["source"].startswith("\n")

    def sentence_count(text: str) -> int:
        compact = re.sub(r"\s+", " ", text.strip())
        return 0 if not compact else len(sentence_boundary_positions(compact)) + 1

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

    by_id, by_event = format_event_text_index(source_document)
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

    by_id, by_event = format_event_text_index(source_document)
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
    by_id, _ = format_event_text_index(source_document)
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

    by_id, by_event = format_event_text_index(source_document)
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
    by_id, by_event = format_event_text_index(source_document)
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
    by_id, _ = format_event_text_index(source_document)
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
    by_id, by_event = format_event_text_index(source_document)
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
            "source": "recipes/android/dialogues_redistribution.json + sources/android/scrtxt_fr.bin",
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
            "source": "recipes/android/dialogues_redistribution.json + sources/android/scrtxt_fr.bin",
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
    from shared.dialogue.simulator import simulate_event

    blocking = [i for i in simulation.issues if i.severity in {"error", "warning"}]
    codes = {i.code for i in blocking}

    by_id, _ = format_event_text_index(source_document)
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
                first_line_prefix_pixels=markup_width(reaction_text, advances, 0),
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


def _replace_boundary_whitespace_with_page_break(text: str, *, first: bool) -> str | None:
    boundaries = sentence_break_positions(text)
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
    from shared.dialogue.simulator import simulate_event

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
    from shared.dialogue.simulator import simulate_event

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
    from shared.dialogue.simulator import simulate_event

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
        if markup_width(previous_text, advances, 0) > span_pixels:
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
    from shared.dialogue.simulator import simulate_event

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
    from shared.dialogue.simulator import simulate_event

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
    from shared.dialogue.simulator import simulate_event

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
    from shared.dialogue.simulator import simulate_event

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
    from shared.dialogue.simulator import simulate_event

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
    from shared.dialogue.simulator import simulate_event

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
    from shared.dialogue.simulator import simulate_event

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
                width = markup_width(line, advances, 0)
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
    from shared.dialogue.simulator import simulate_event

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
        if text_id in reviewed_live_prefix_layout_lock_ids():
            continue
        previous = tokens[index - 1]
        if previous.get("type") != "command" or previous.get("name") != "PLAYER_NAME":
            continue
        value = candidate[text_id]
        # A leading page/clear control resets the live prefix before prose.
        if not value or value.startswith(("\v", "\f")):
            continue
        # Reflow only inside the current visible page segment.  A form-feed
        # (WAIT $00 + TEXT_CLEAR) or clear marker is a hard runtime boundary and
        # must never be swallowed while joining earlier soft NEWLINEs.
        control_match = re.search(r"[\v\f]", value)
        if control_match:
            prefix_segment = value[:control_match.start()]
            control_suffix = value[control_match.start():]
        else:
            prefix_segment = value
            control_suffix = ""
        parts = prefix_segment.split("\n")
        first = parts[0]
        if not first.strip():
            continue

        # Earlier formatting may already have inserted a soft wrap inside the
        # same sentence.  Reflowing only ``parts[0]`` can then create an
        # orphan word before the preserved next line (for example
        # ``... ou il`` / ``va`` / ``s'en prendre ...``).  Extend the live
        # prefix reflow through consecutive soft lines until a genuine
        # sentence boundary, but never across the hard control boundary above.
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
        replacement = "\n".join([wrapped, *parts[consumed_parts:]]) + control_suffix
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
    alignment: dict | None = None,
    source_document: dict,
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
    from shared.dialogue.simulator import make_dialogue_font, simulate_event

    validate_base_rom(base_rom)
    if alignment is None:
        alignment = make_dialogue_auto_alignment(
            english,
            french,
            english_path=english_path,
            french_path=french_path,
            source_document=source_document,
        )
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
    final_structural_command_override_entries = reviewed_structural_command_overrides()
    final_structural_command_overrides_by_event = resolve_structural_command_overrides(
        {"user_validated_structural_command_overrides": final_structural_command_override_entries},
        source_document,
    )
    structural_command_insertions_by_event = resolve_structural_command_insertions(
        {"user_validated_structural_command_insertions": list(DIALOGUE_USER_VALIDATED_STRUCTURAL_COMMAND_INSERTIONS)},
        source_document,
    )
    redistribution_values, redistribution_meta = load_dialogue_redistribution_recipes(french)
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
            "recipes/android/dialogues_coverage_repair.json."
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
            if token.get("type") == "text" and is_semantic_text(token.get("source", ""))
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
            if (blocking or wraps) and event_id in _reviewed_layout_search_recipe_index():
                # Some reviewed plans (currently $05F8) are defined after the
                # validated live PLAYER_NAME-prefix reflow. Reproduce that cheap
                # structural prerequisite first, then try the reviewed plan. If
                # either step no longer applies, fall through to the historical
                # generic repair sequence unchanged.
                fast_values = values
                fast_simulation = simulation
                prefix_values, prefix_simulation, prefix_repairs = _try_live_player_prefix_reflow(
                    base_rom=base_rom, event=event, translations=fast_values, advances=advances, font=font
                )
                if prefix_repairs:
                    fast_values = prefix_values
                    fast_simulation = prefix_simulation
                reviewed_values, reviewed_simulation, reviewed_repairs = _apply_reviewed_layout_search_recipe(
                    base_rom=base_rom, event=event, translations=fast_values, font=font
                )
                if reviewed_repairs:
                    values = reviewed_values
                    simulation = reviewed_simulation
                    blocking = []
                    wraps = 0
                    if prefix_repairs:
                        live_player_prefix_reflow_repairs_by_event[event_id] = prefix_repairs
                    source_derived_layout_search_repairs_by_event[event_id] = reviewed_repairs
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

            # Reviewed layout recipes are deterministic structural plans discovered
            # by the historical fallback search. Try them before rescanning the
            # generic carrier-boundary neighborhood; if a recipe has drifted, the
            # original generic fallback remains immediately below.
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

    # Round 85.53A: replay the complete user-validated Round-85.52 layout
    # only after every canonical semantic/structural formatter stage has run.
    # The recipe contains no translated prose: semantic fingerprints must match
    # the freshly generated carriers before any spaces/newlines/page separators
    # are changed. Every changed event is independently resimulated with
    # 9-character player names before the layout is accepted.
    validated_final_layout_repairs_by_event: dict[str, list[dict]] = {}
    source_event_by_id = {event["event_id"]: event for event in source_document["events"]}
    for event_id in accepted_events:
        candidate, repairs = apply_validated_final_layout(
            event_id, translations_by_event[event_id]
        )
        if not repairs:
            continue
        simulation = simulate_event(
            base_rom,
            source_event_by_id[event_id],
            candidate,
            font=font,
            player_names={0: "000000000", 1: "000000000", 2: "000000000"},
            omitted_command_token_indexes=structural_omission_indexes_by_event.get(event_id),
            structural_command_overrides=structural_command_overrides_by_event.get(event_id),
            choice_option_position_overrides=choice_option_position_overrides_by_event.get(event_id),
        )
        if _simulation_blocking_score(simulation)[0] != 0:
            raise ValueError(
                f"Final reviewed layout for ${event_id} no longer simulates cleanly"
            )
        translations_by_event[event_id] = candidate
        validated_final_layout_repairs_by_event[event_id] = repairs

    # Round 85.56: apply the separately reviewed Round-85.54/85.55-v2
    # speaker-structure delta only after the established Round-85.52 layout has
    # been reproduced. Structural recipes contain no French prose: they may
    # inline an omitted stock PLAYER_NAME placeholder, move a clear-only marker,
    # or preserve punctuation proved by the clean-USA source. A second layout
    # recipe then replays only spaces/newlines/page separators.
    validated_final_structure_repairs_by_event: dict[str, list[dict]] = {}
    validated_post_structure_layout_repairs_by_event: dict[str, list[dict]] = {}
    validated_round85_review_repairs_by_event: dict[str, list[dict]] = {}

    # Round 85.57-85.67: replay the complete user-validated choice geometry
    # before the final review-delta simulation. The recipe contains only source
    # IDs, command coordinates and structural metadata, never localized prose.
    reviewed_choice_entries = reviewed_choice_option_position_overrides()
    choice_option_position_overrides_by_event = {}
    for entry in reviewed_choice_entries:
        event_id = str(entry["event_id"])
        choice_option_position_overrides_by_event.setdefault(event_id, {})[int(entry["token_index"])] = int(entry["translated_position"])

    for event_id in accepted_events:
        event = source_event_by_id[event_id]
        candidate, structure_repairs = apply_validated_final_structure(
            event,
            translations_by_event[event_id],
            structural_command_overrides=final_structural_command_overrides_by_event.get(event_id),
        )
        candidate, layout_repairs = apply_validated_post_structure_layout(event_id, candidate)
        candidate, review_repairs = apply_round85_review_delta(event_id, candidate, french)
        if not structure_repairs and not layout_repairs and not review_repairs:
            continue
        simulation = simulate_event(
            base_rom,
            event,
            candidate,
            font=font,
            player_names={0: "000000000", 1: "000000000", 2: "000000000"},
            omitted_command_token_indexes=structural_omission_indexes_by_event.get(event_id),
            structural_command_overrides=final_structural_command_overrides_by_event.get(event_id),
            structural_command_insertions_before=structural_command_insertions_by_event.get(event_id),
            choice_option_position_overrides=choice_option_position_overrides_by_event.get(event_id),
        )
        if _simulation_blocking_score(simulation)[0] != 0:
            raise ValueError(
                f"Round-85.56 reviewed final structure/layout for ${event_id} no longer simulates cleanly"
            )
        translations_by_event[event_id] = candidate
        if structure_repairs:
            validated_final_structure_repairs_by_event[event_id] = structure_repairs
        if layout_repairs:
            validated_post_structure_layout_repairs_by_event[event_id] = layout_repairs
        if review_repairs:
            validated_round85_review_repairs_by_event[event_id] = review_repairs

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
    reviewed_appended_ids = reviewed_appended_entry_order()
    reviewed_appended_rank = {text_id: index for index, text_id in enumerate(reviewed_appended_ids)}
    ordered_entries = sorted(
        translations.items(),
        key=lambda item: (
            1 if item[0] in reviewed_appended_rank else 0,
            reviewed_appended_rank.get(item[0], source_order.get(item[0], 1 << 30)),
        ),
    )
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
        entry for entry in final_structural_command_override_entries
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
    translation_document["choice_option_position_overrides"] = reviewed_choice_entries
    translation_document["user_validated_structural_command_insertions"] = [
        entry for entry in DIALOGUE_USER_VALIDATED_STRUCTURAL_COMMAND_INSERTIONS
        if entry.get("event_id") in accepted_event_set
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
            and is_semantic_text(token.get("source", ""))
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
        "source_alignment": "reports/android/dialogues_auto.json (regenerated from Android EN/FR)",
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
                    token.get("type") == "text" and is_semantic_text(token.get("source", ""))
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
        "user_validated_structural_command_overrides": list(final_structural_command_override_entries),
        "user_validated_structural_command_insertions": list(DIALOGUE_USER_VALIDATED_STRUCTURAL_COMMAND_INSERTIONS),
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
        "validated_final_layout_repairs": [
            {"event_id": event_id, "repairs": repairs}
            for event_id, repairs in validated_final_layout_repairs_by_event.items()
            if repairs
        ],
        "validated_round85_review_repairs": [
            {"event_id": event_id, "repairs": repairs}
            for event_id, repairs in validated_round85_review_repairs_by_event.items()
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


