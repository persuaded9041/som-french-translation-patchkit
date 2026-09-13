#!/usr/bin/env python3
"""Audit dialogue reflow quality without changing canonical formatter behavior.

The audit consumes one freshly generated dialogue translation document and its
format report, attributes candidate short-line defects to the 216px reflow
stage (and notes overlap with later layout-search repairs), then tests a narrow
balanced two-line alternative.  Candidates are accepted into the review output
only when the complete event remains simulator-clean with the validated
216px/38-unit runtime contract.

This tool is intentionally review-only.  It does not modify recipes or the
canonical formatter; the resulting candidate JSON/HTML exists so the balancing
policy can be reviewed before any generalization is accepted.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from copy import deepcopy
from html import escape
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shared.extracted.assets import load_or_extract_dialogues  # noqa: E402
from shared.dialogue.simulator import make_dialogue_font, simulate_event  # noqa: E402
from shared.dialogue.structure import resolve_structural_command_overrides  # noqa: E402
from shared.dialogue.translation import (  # noqa: E402
    DIALOGUE_WRAP_CHARS,
    DIALOGUE_WRAP_PIXELS,
    _balanced_wrap_markup,
    _markup_chars,
    make_dialogue_advances,
    markup_width,
    semantic_wrap_markup,
)

SENTINEL_ID = "C9:27E4"
SENTINEL_TEXT = ": Bon, il faut que je\nrentre au village !\n"
DEFAULT_SHORT_LINE_PIXELS = 72


def _entry_map(document: dict) -> dict[str, str]:
    return {
        entry["id"]: entry["text"]
        for group in document.get("groups", [])
        for entry in group.get("entries", [])
    }


def _event_translations(source_document: dict, translations: dict[str, str]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for event in source_document["events"]:
        values = {
            token["id"]: translations[token["id"]]
            for token in event.get("tokens", [])
            if token.get("type") in {"text", "ending_text"}
            and token.get("id") in translations
        }
        if values:
            result[event["event_id"]] = values
    return result


def _reflow_records(format_report: dict) -> dict[tuple[str, str], list[dict]]:
    result: dict[tuple[str, str], list[dict]] = defaultdict(list)
    seen: set[tuple[str, str, str, str]] = set()

    def add(event_id: str, carrier: dict) -> None:
        text_id = carrier["id"]
        for line in carrier.get("reflowed_lines", []):
            key = (event_id, text_id, line["source_line"], line["wrapped"])
            if key in seen:
                continue
            seen.add(key)
            result[(event_id, text_id)].append(line)

    for mapping in format_report.get("formatted_mappings", []):
        event_id = mapping.get("event_id")
        for carrier in mapping.get("automatic_216px_reflow", []) or []:
            add(event_id, carrier)
    for event in format_report.get("automatic_216px_reflows", []):
        for carrier in event.get("reflows", []):
            add(event["event_id"], carrier)
    return result


def _layout_search_by_carrier(format_report: dict) -> dict[tuple[str, str], list[dict]]:
    result: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for event in format_report.get("source_derived_layout_search_repairs", []):
        for repair in event.get("repairs", []):
            result[(event["event_id"], repair["text_id"])].append(repair)
    return result


def _line_metrics(value: str, advances: dict[str, int]) -> list[dict]:
    rows: list[dict] = []
    page = 1
    line_no = 0
    for segment_index, segment in enumerate(value.replace("\v", "\f").split("\f")):
        if segment_index:
            page += 1
            line_no = 0
        for line in segment.split("\n"):
            if not line:
                continue
            line_no += 1
            rows.append({
                "page": page,
                "line": line_no,
                "text": line,
                "pixels": markup_width(line, advances, 0),
                "glyphs": _markup_chars(line),
            })
    return rows


def _clean_simulation(base_rom: bytes, event: dict, translations: dict[str, str], font, overrides) -> tuple[bool, list[str]]:
    simulation = simulate_event(
        base_rom,
        event,
        translations,
        font=font,
        player_names={0: "000000000", 1: "000000000", 2: "000000000"},
        structural_command_overrides=overrides,
    )
    problems = [issue.code for issue in simulation.issues if issue.severity in {"error", "warning"}]
    implicit = sum(
        line.implicit_wrap
        for box in simulation.boxes
        for page in box.pages
        for line in page.lines
    )
    if implicit:
        problems.append(f"IMPLICIT_RUNTIME_WRAP x{implicit}")
    return not problems, problems


def _candidate_changes(
    *,
    reflows: dict[tuple[str, str], list[dict]],
    layout_repairs: dict[tuple[str, str], list[dict]],
    advances: dict[str, int],
    short_line_pixels: int,
) -> dict[str, list[dict]]:
    candidates: dict[str, list[dict]] = defaultdict(list)
    for (event_id, text_id), records in sorted(reflows.items()):
        for record in records:
            before_widths = record.get("widths_pixels", [])
            if len(before_widths) != 2 or min(before_widths) >= short_line_pixels:
                continue
            try:
                balanced, widths, chars, units = _balanced_wrap_markup(
                    record["source_line"],
                    advances,
                    line_count=2,
                    page_line_counts=(2,),
                )
            except ValueError:
                continue
            if min(widths) <= min(before_widths):
                continue
            if any(width > DIALOGUE_WRAP_PIXELS for width in widths):
                continue
            if any(unit > DIALOGUE_WRAP_CHARS for unit in units):
                continue
            overlap = layout_repairs.get((event_id, text_id), [])
            candidates[event_id].append({
                "text_id": text_id,
                "source_line": record["source_line"],
                "before": record["wrapped"],
                "after": balanced,
                "before_widths": before_widths,
                "after_widths": widths,
                "before_glyphs": record.get("decoded_characters", []),
                "after_glyphs": chars,
                "after_parser_units": units,
                "category": "reflow_plus_layout_search" if overlap else "greedy_orphan_balance",
                "newline_provenance": [
                    "automatic_216px_reflow",
                    *(["source_derived_layout_search"] if overlap else []),
                ],
                "layout_search_repairs": overlap,
            })
    return candidates


def _collision_repack_value(value: str, advances: dict[str, int]) -> str:
    """Rewrap visible page segments after a proven reflow/layout-search overlap.

    This may only be considered after provenance has proved that both formatter
    stages touched the carrier. Page/TEXT_CLEAR controls remain fixed; only hard
    NEWLINEs inside each visible segment are normalized back to spaces before the
    ordinary semantic wrapper is reapplied. Whole-event simulation remains the
    acceptance gate.
    """
    import re

    parts = re.split(r"([\v\f])", value)
    rebuilt: list[str] = []
    for part in parts:
        if part in {"\v", "\f"} or not part:
            rebuilt.append(part)
            continue
        logical = re.sub(r"[ \t]*\n[ \t]*", " ", part)
        logical = re.sub(r"[ \t]+", " ", logical)
        if not logical.strip():
            rebuilt.append(logical)
            continue
        wrapped, _widths, _chars, _units = semantic_wrap_markup(logical, advances)
        rebuilt.append(wrapped)
    return "".join(rebuilt)


def _apply_review_candidates(
    *,
    source_document: dict,
    baseline_document: dict,
    candidates: dict[str, list[dict]],
    base_rom: bytes,
    advances: dict[str, int],
    font,
) -> tuple[dict, list[dict]]:
    event_by_id = {event["event_id"]: event for event in source_document["events"]}
    baseline_map = _entry_map(baseline_document)
    per_event = _event_translations(source_document, baseline_map)
    overrides = resolve_structural_command_overrides(baseline_document, source_document)
    accepted: list[dict] = []
    replacements: dict[str, str] = {}

    for event_id, event_candidates in sorted(candidates.items(), key=lambda item: int(item[0], 16)):
        current = dict(per_event[event_id])
        applied: list[dict] = []
        for candidate in event_candidates:
            text_id = candidate["text_id"]
            old_value = current.get(text_id, "")
            if candidate["before"] not in old_value:
                continue
            current[text_id] = old_value.replace(candidate["before"], candidate["after"], 1)
            applied.append(candidate)
        if not applied:
            continue
        clean, problems = _clean_simulation(
            base_rom,
            event_by_id[event_id],
            current,
            font,
            overrides.get(event_id),
        )
        if not clean:
            continue

        # Collision cleanup is deliberately separate from generic orphan
        # balancing.  Only carriers explicitly touched by both reflow and a
        # later layout-search repair are eligible.  Keep page controls fixed,
        # repack the visible page segments, and accept each carrier only when
        # the complete event remains simulator-clean.
        for text_id in sorted({
            candidate["text_id"]
            for candidate in applied
            if candidate["category"] == "reflow_plus_layout_search"
        }):
            old_value = current[text_id]
            try:
                repacked = _collision_repack_value(old_value, advances)
            except ValueError:
                continue
            if repacked == old_value:
                continue
            repack_candidate = dict(current)
            repack_candidate[text_id] = repacked
            repack_clean, _repack_problems = _clean_simulation(
                base_rom,
                event_by_id[event_id],
                repack_candidate,
                font,
                overrides.get(event_id),
            )
            if not repack_clean:
                continue
            current = repack_candidate
            applied.append({
                "text_id": text_id,
                "source_line": None,
                "before": old_value,
                "after": repacked,
                "before_widths": [],
                "after_widths": [],
                "before_glyphs": [],
                "after_glyphs": [],
                "after_parser_units": [],
                "category": "collision_segment_repack",
                "newline_provenance": [
                    "automatic_216px_reflow",
                    "source_derived_layout_search",
                ],
                "layout_search_repairs": [],
            })

        changed_ids = sorted({candidate["text_id"] for candidate in applied})
        for text_id in changed_ids:
            replacements[text_id] = current[text_id]
        for text_id in changed_ids:
            accepted.append({
                "event_id": event_id,
                "text_id": text_id,
                "before_text": per_event[event_id][text_id],
                "after_text": current[text_id],
                "before_metrics": _line_metrics(per_event[event_id][text_id], advances),
                "after_metrics": _line_metrics(current[text_id], advances),
                "changes": [c for c in applied if c["text_id"] == text_id],
                "simulation": "clean",
                "problems": problems,
            })

    candidate_document = deepcopy(baseline_document)
    for group in candidate_document.get("groups", []):
        for entry in group.get("entries", []):
            if entry["id"] in replacements:
                entry["text"] = replacements[entry["id"]]
    return candidate_document, accepted


def _display_text(value: str) -> str:
    return escape(value.replace("\v", "⟦TEXT_CLEAR⟧\n").replace("\f", "⟦PAGE⟧\n"))


def _metrics_html(rows: list[dict]) -> str:
    return "".join(
        f"<tr><td>{row['page']}</td><td>{row['line']}</td><td><code>{escape(row['text'])}</code></td>"
        f"<td>{row['pixels']} px</td><td>{row['glyphs']}</td></tr>"
        for row in rows
    )


def _write_html(path: Path, accepted: list[dict], *, threshold: int, overlap_count: int, reflow_count: int) -> None:
    cards = []
    for item in accepted:
        categories = sorted({change["category"] for change in item["changes"]})
        reasons = []
        for change in item["changes"]:
            if change["before_widths"] and change["after_widths"]:
                before_min = min(change["before_widths"])
                after_min = min(change["after_widths"])
                detail = f"queue {before_min}px → {after_min}px"
            else:
                detail = "repack du segment de page après collision de provenance"
            reasons.append(
                f"{escape(change['category'])}: {detail}; "
                f"provenance {escape(' + '.join(change['newline_provenance']))}"
            )
        cards.append(f"""
<section class="card">
  <h2>${item['event_id']} / {item['text_id']}</h2>
  <p class="reason">{'<br>'.join(reasons)}</p>
  <div class="cols">
    <div><h3>Avant — Round 85.40</h3><pre>{_display_text(item['before_text'])}</pre>
      <table><thead><tr><th>Page</th><th>Ligne</th><th>Texte</th><th>Largeur</th><th>Glyphes</th></tr></thead><tbody>{_metrics_html(item['before_metrics'])}</tbody></table>
    </div>
    <div><h3>Après — candidat audit</h3><pre>{_display_text(item['after_text'])}</pre>
      <table><thead><tr><th>Page</th><th>Ligne</th><th>Texte</th><th>Largeur</th><th>Glyphes</th></tr></thead><tbody>{_metrics_html(item['after_metrics'])}</tbody></table>
    </div>
  </div>
</section>""")
    html = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>Secret of Mana FR — audit layout corrected-only</title>
<style>
body{{font-family:system-ui,sans-serif;margin:24px;background:#f5f5f5;color:#171717}} .summary,.card{{background:white;border:1px solid #ddd;border-radius:10px;padding:18px;margin:0 0 18px}} .cols{{display:grid;grid-template-columns:1fr 1fr;gap:18px}} pre{{white-space:pre-wrap;background:#f7f7f7;padding:12px;border-radius:6px}} table{{border-collapse:collapse;width:100%;font-size:13px}} th,td{{border:1px solid #ddd;padding:5px;text-align:left}} code{{white-space:pre-wrap}} .reason{{font-size:14px}} @media(max-width:1000px){{.cols{{grid-template-columns:1fr}}}}
</style></head><body>
<div class="summary"><h1>Audit global de mise en page — corrected-only</h1>
<p>Baseline Round 85.40/85.41. Aucun texte Android FR n'est modifié : seuls des mots entiers sont redistribués entre deux lignes déjà issues du reflow 216 px.</p>
<p><strong>{len(accepted)} carriers modifiés</strong> ; seuil de détection d'une queue courte : &lt; {threshold}px. Le corpus contient {reflow_count} lignes de reflow tracées et {overlap_count} carriers où reflow et layout-search se chevauchent. Tous les événements présentés ci-dessous restent simulator-clean (0 erreur, 0 warning, 0 wrap implicite).</p>
<p>La sentinelle <code>$0103 / C9:27E4</code> reste exactement <code>Randy: Bon, il faut que je / rentre au village !</code> sur deux lignes.</p></div>
{''.join(cards)}
</body></html>"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--dialogues", type=Path, required=True)
    parser.add_argument("--format-report", type=Path, required=True)
    parser.add_argument("--html", type=Path, required=True)
    parser.add_argument("--candidate-output", type=Path)
    parser.add_argument("--short-line-pixels", type=int, default=DEFAULT_SHORT_LINE_PIXELS)
    args = parser.parse_args()

    base_rom = args.rom.read_bytes()
    baseline_document = json.loads(args.dialogues.read_text(encoding="utf-8"))
    format_report = json.loads(args.format_report.read_text(encoding="utf-8"))
    translations = _entry_map(baseline_document)
    if translations.get(SENTINEL_ID) != SENTINEL_TEXT:
        raise SystemExit(
            f"Round-85.40 sentinel drifted: {SENTINEL_ID}={translations.get(SENTINEL_ID)!r}"
        )
    source_document = load_or_extract_dialogues(base_rom)
    advances = make_dialogue_advances(base_rom)
    font = make_dialogue_font(base_rom)
    reflows = _reflow_records(format_report)
    layout_repairs = _layout_search_by_carrier(format_report)
    overlap_count = len(set(reflows) & set(layout_repairs))
    reflow_count = sum(len(records) for records in reflows.values())
    candidates = _candidate_changes(
        reflows=reflows,
        layout_repairs=layout_repairs,
        advances=advances,
        short_line_pixels=args.short_line_pixels,
    )
    candidate_document, accepted = _apply_review_candidates(
        source_document=source_document,
        baseline_document=baseline_document,
        candidates=candidates,
        base_rom=base_rom,
        advances=advances,
        font=font,
    )
    if _entry_map(candidate_document).get(SENTINEL_ID) != SENTINEL_TEXT:
        raise SystemExit("Audit candidate regressed the $0103 / C9:27E4 sentinel")
    _write_html(
        args.html,
        accepted,
        threshold=args.short_line_pixels,
        overlap_count=overlap_count,
        reflow_count=reflow_count,
    )
    if args.candidate_output:
        args.candidate_output.parent.mkdir(parents=True, exist_ok=True)
        args.candidate_output.write_text(
            json.dumps(candidate_document, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    events = len({item["event_id"] for item in accepted})
    collision_carriers = sum(
        any(change["category"] == "reflow_plus_layout_search" for change in item["changes"])
        for item in accepted
    )
    print(
        f"Layout audit: {len(accepted)} changed carrier(s) across {events} event(s); "
        f"{collision_carriers} overlap carrier(s); sentinel preserved; all displayed candidates simulator-clean"
    )


if __name__ == "__main__":
    main()
