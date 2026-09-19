#!/usr/bin/env python3
"""Review-only pagination/layout cleanup for the Round-85.42 dialogue candidate.

Policy, in order:
1. Existing page/TEXT_CLEAR markers are authoritative and untouched when every
   local segment already uses <=3 lines.
2. For a carrier-local 4-line segment, first try to rebalance the exact same
   printable payload into 3 lines under the validated 216px / 38-unit limits.
3. Only when no valid 3-line wrap exists, replace the newline before line 4 by
   the canonical generated page marker (WAIT $00 + TEXT_CLEAR, ``\f``).
4. Every changed event is independently resimulated; the full candidate is then
   resimulated across the complete corpus.

Round 85.43 is intentionally superseded: it used event-global live-line risk as
an insertion trigger and could split a valid 3+2 page layout into 2+1+2.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from html import escape
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shared.extracted.assets import load_or_extract_dialogues  # noqa: E402
from shared.dialogue.simulator import make_dialogue_font, simulate_event  # noqa: E402
from shared.dialogue.structure import (  # noqa: E402
    resolve_choice_option_position_overrides,
    resolve_structural_command_overrides,
    resolve_structural_omission_token_indexes,
)
from shared.dialogue.translation import (  # noqa: E402
    DIALOGUE_WRAP_CHARS,
    DIALOGUE_WRAP_PIXELS,
    _balanced_wrap_markup,
    _markup_chars,
    make_dialogue_advances,
    markup_width,
)

PAGE_LINES = 3
SENTINEL_ID = "C9:27E4"
SENTINEL_TEXT = ": Bon, il faut que je\nrentre au village !\n"


def entry_map(document: dict) -> dict[str, str]:
    return {e["id"]: e["text"] for g in document.get("groups", []) for e in g.get("entries", [])}


def carrier_to_event(source_document: dict) -> dict[str, str]:
    out = {}
    for event in source_document["events"]:
        for token in event.get("tokens", []):
            if token.get("type") in {"text", "ending_text"} and token.get("id"):
                out[token["id"]] = event["event_id"]
    return out


def event_translations(source_document: dict, translations: dict[str, str]) -> dict[str, dict[str, str]]:
    result = {}
    for event in source_document["events"]:
        values = {
            t["id"]: translations[t["id"]]
            for t in event.get("tokens", [])
            if t.get("type") in {"text", "ending_text"} and t.get("id") in translations
        }
        if values:
            result[event["event_id"]] = values
    return result


def split_controls(value: str) -> list[str]:
    return re.split(r"([\v\f])", value)


def lines(segment: str) -> list[str]:
    return [line for line in segment.split("\n") if line]


def printable_payload(value: str) -> str:
    # Layout separators are whitespace for semantic-payload comparison.
    return re.sub(r"\s+", " ", value.replace("\v", " ").replace("\f", " ")).strip()


def local_overflows(value: str) -> list[str]:
    return [part for part in split_controls(value) if part not in {"\v", "\f"} and len(lines(part)) > PAGE_LINES]


def three_line_rebalance(segment: str, advances: dict[str, int]) -> tuple[str, list[int], list[int]] | None:
    source_lines = lines(segment)
    if len(source_lines) != 4:
        return None
    # Dynamic PLAYER_NAME expansion is wider than the markup placeholder and
    # must not be judged by static balancing metrics alone. Keep its reviewed
    # hard lines and paginate instead.
    if "%S(" in segment:
        return None
    logical = " ".join(source_lines)
    try:
        wrapped, widths, _chars, units = _balanced_wrap_markup(
            logical, advances, line_count=3, page_line_counts=(3,)
        )
    except ValueError:
        return None
    if any(width > DIALOGUE_WRAP_PIXELS for width in widths):
        return None
    if any(unit > DIALOGUE_WRAP_CHARS for unit in units):
        return None
    # Keep a trailing newline only if the segment had one; no control semantics
    # are otherwise changed by this wrapping path.
    if segment.endswith("\n") and not wrapped.endswith("\n"):
        wrapped += "\n"
    return wrapped, widths, units


def two_by_two_pages(segment: str, advances: dict[str, int]) -> tuple[str, list[int], list[int]]:
    """Return two balanced 2-line pages for an irreducible 4-line segment.

    Dynamic PLAYER_NAME markup is left on the reviewed hard lines because the
    static placeholder understates its runtime width; in that case only the
    middle newline becomes a page marker.
    """
    source_lines = lines(segment)
    if len(source_lines) != 4:
        raise ValueError("2+2 pagination expects exactly four source lines")
    if "%S(" in segment or segment.lstrip().startswith(":"):
        # Preserve exact line geometry for dynamic/binding-prefix carriers;
        # static metrics may omit a PLAYER_NAME emitted by the previous token.
        # Replace boundary 2->3 only.
        positions = [m.start() for m in re.finditer(r"\n", segment)]
        if len(positions) < 2:
            raise ValueError("Cannot find middle newline for 2+2 pagination")
        pos = positions[1]
        return segment[:pos] + "\f" + segment[pos + 1:], [], []
    logical = " ".join(source_lines)
    wrapped, widths, _chars, units = _balanced_wrap_markup(
        logical, advances, line_count=4, page_line_counts=(2, 2)
    )
    if any(width > DIALOGUE_WRAP_PIXELS for width in widths):
        raise ValueError("Balanced 2+2 page exceeds 216px")
    if any(unit > DIALOGUE_WRAP_CHARS for unit in units):
        raise ValueError("Balanced 2+2 page exceeds 38 parser units")
    if segment.endswith("\n") and not wrapped.endswith("\n"):
        wrapped += "\n"
    return wrapped, widths, units


def transform_value(value: str, advances: dict[str, int]) -> tuple[str, list[dict]]:
    parts = split_controls(value)
    changes = []
    seg_index = 0
    for i, part in enumerate(parts):
        if part in {"\v", "\f"}:
            continue
        source_lines = lines(part)
        if len(source_lines) <= PAGE_LINES:
            seg_index += 1
            continue
        if len(source_lines) != 4:
            raise ValueError(f"Unexpected local segment with {len(source_lines)} lines")
        balanced = three_line_rebalance(part, advances)
        if balanced is not None:
            after, widths, units = balanced
            strategy = "rebalance_4_to_3_lines"
            detail = {"widths_pixels": widths, "parser_units": units}
        else:
            after, widths, units = two_by_two_pages(part, advances)
            strategy = "balanced_two_by_two_pages"
            detail = {"widths_pixels": widths, "parser_units": units}
        if printable_payload(part) != printable_payload(after):
            raise ValueError("Printable payload changed")
        parts[i] = after
        changes.append({
            "segment": seg_index,
            "strategy": strategy,
            "before_segment": part,
            "after_segment": after,
            "semantic_payload_changed": False,
            **detail,
        })
        seg_index += 1
    return "".join(parts), changes


def metrics(value: str, advances: dict[str, int]) -> list[dict]:
    rows = []
    page = 1
    line_no = 0
    for part in split_controls(value):
        if part in {"\v", "\f"}:
            page += 1
            line_no = 0
            continue
        for text in part.split("\n"):
            if not text:
                continue
            line_no += 1
            rows.append({"page": page, "line": line_no, "text": text,
                         "pixels": markup_width(text, advances, 0), "glyphs": _markup_chars(text)})
    return rows


def display(value: str) -> str:
    return escape(value.replace("\v", "⟦TEXT_CLEAR⟧\n").replace("\f", "⟦WAIT $00 + TEXT_CLEAR⟧\n"))


def metrics_html(rows: list[dict]) -> str:
    return "".join(
        f"<tr><td>{r['page']}</td><td>{r['line']}</td><td><code>{escape(r['text'])}</code></td>"
        f"<td>{r['pixels']} px</td><td>{r['glyphs']}</td></tr>" for r in rows
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", type=Path, required=True)
    ap.add_argument("--baseline", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--html", type=Path, required=True)
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()

    rom = args.rom.read_bytes()
    source = load_or_extract_dialogues(rom)
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    before_map = entry_map(baseline)
    if before_map.get(SENTINEL_ID) != SENTINEL_TEXT:
        raise SystemExit("Baseline sentinel drifted")
    candidate = deepcopy(baseline)
    advances = make_dialogue_advances(rom)
    font = make_dialogue_font(rom)
    carrier_event = carrier_to_event(source)

    changed = []
    for group in candidate.get("groups", []):
        for entry in group.get("entries", []):
            if not local_overflows(entry["text"]):
                continue
            before = entry["text"]
            after, edits = transform_value(before, advances)
            if before == after:
                continue
            # If every original local segment was already safe, this carrier
            # would never have entered the transform path. Existing page/clear
            # markers are preserved byte-for-byte unless the affected segment
            # itself must be paginated because it cannot fit in 3 lines.
            if [c for c in before if c in "\v"] != [c for c in after if c in "\v"]:
                raise SystemExit(f"TEXT_CLEAR marker drift in {entry['id']}")
            if printable_payload(before) != printable_payload(after):
                raise SystemExit(f"Printable payload drift in {entry['id']}")
            entry["text"] = after
            changed.append({
                "event_id": carrier_event.get(entry["id"], "????"), "text_id": entry["id"],
                "before": before, "after": after, "edits": edits,
                "before_metrics": metrics(before, advances), "after_metrics": metrics(after, advances),
            })

    after_map = entry_map(candidate)
    if after_map.get(SENTINEL_ID) != SENTINEL_TEXT:
        raise SystemExit("Candidate regressed C9:27E4 sentinel")
    remaining = {tid: local_overflows(value) for tid, value in after_map.items() if local_overflows(value)}
    if remaining:
        raise SystemExit(f"Local >3-line segments remain: {list(remaining)[:8]}")

    overrides = resolve_structural_command_overrides(candidate, source)
    omissions = resolve_structural_omission_token_indexes(candidate, source, translations=after_map)
    choices = resolve_choice_option_position_overrides(candidate, source)
    per_event = event_translations(source, after_map)
    failures = []
    implicit_total = 0
    live_risks = []
    for event in source["events"]:
        eid = event["event_id"]
        if eid not in per_event:
            continue
        sim = simulate_event(
            rom, event, per_event[eid], font=font,
            player_names={0:"000000000",1:"000000000",2:"000000000"},
            structural_command_overrides=overrides.get(eid),
            omitted_command_token_indexes=omissions.get(eid),
            choice_option_position_overrides=choices.get(eid),
        )
        blocking = [i.code for i in sim.issues if i.severity in {"error", "warning"}]
        wraps = sum(line.implicit_wrap for box in sim.boxes for page in box.pages for line in page.lines)
        implicit_total += wraps
        if blocking or wraps:
            failures.append({"event_id": eid, "blocking": blocking, "implicit_wraps": wraps})
        risks = sum(i.code == "UNPAUSED_LIVE_LINE_SCROLL_RISK" for i in sim.issues)
        if risks:
            live_risks.append({"event_id": eid, "count": risks})
    if failures:
        raise SystemExit(f"Simulator failures: {failures[:8]}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    strategy_counts = {}
    for item in changed:
        for edit in item["edits"]:
            strategy_counts[edit["strategy"]] = strategy_counts.get(edit["strategy"], 0) + 1
    cards = []
    for item in changed:
        reasons = []
        for edit in item["edits"]:
            if edit["strategy"] == "rebalance_4_to_3_lines":
                reasons.append("4 lignes → 3 lignes par rééquilibrage des mêmes mots; aucune pagination ajoutée")
            else:
                reasons.append("4 lignes irréductibles en une page → deux pages équilibrées de 2 lignes (WAIT $00 + TEXT_CLEAR au milieu)")
        cards.append(f"""
<section class=card><h2>${item['event_id']} / {item['text_id']}</h2><p>{'<br>'.join(map(escape,reasons))}</p>
<div class=cols><div><h3>Avant — Round 85.42</h3><pre>{display(item['before'])}</pre>
<table><thead><tr><th>Page</th><th>Ligne</th><th>Texte</th><th>Largeur</th><th>Glyphes</th></tr></thead><tbody>{metrics_html(item['before_metrics'])}</tbody></table></div>
<div><h3>Après — candidat Round 85.44</h3><pre>{display(item['after'])}</pre>
<table><thead><tr><th>Page</th><th>Ligne</th><th>Texte</th><th>Largeur</th><th>Glyphes</th></tr></thead><tbody>{metrics_html(item['after_metrics'])}</tbody></table></div></div></section>""")
    html = f"""<!doctype html><html lang=fr><head><meta charset=utf-8><title>Secret of Mana FR — pagination Round 85.44</title>
<style>body{{font-family:system-ui,sans-serif;margin:24px;background:#f5f5f5;color:#171717}}.summary,.card{{background:#fff;border:1px solid #ddd;border-radius:10px;padding:18px;margin:0 0 18px}}.cols{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}pre{{white-space:pre-wrap;background:#f7f7f7;padding:12px;border-radius:6px}}table{{border-collapse:collapse;width:100%;font-size:13px}}th,td{{border:1px solid #ddd;padding:5px;text-align:left}}code{{white-space:pre-wrap}}@media(max-width:1000px){{.cols{{grid-template-columns:1fr}}}}</style></head><body>
<div class=summary><h1>Corrected-only — meilleur découpage Round 85.44</h1>
<p>Base : Round 85.42. Round 85.43 est rejeté et n'est pas utilisé.</p>
<p><strong>{len(changed)} carriers modifiés</strong> : {strategy_counts.get('rebalance_4_to_3_lines',0)} segments tiennent finalement en 3 lignes et sont simplement rééquilibrés ; {strategy_counts.get('balanced_two_by_two_pages',0)} segments seulement nécessitent une nouvelle frontière WAIT $00 + TEXT_CLEAR.</p>
<p>Les blocs déjà sûrs (notamment Jach en 3 lignes + WAIT/CLEAR + 2 lignes) restent strictement inchangés. Corpus complet : 0 erreur / 0 warning / 0 wrap implicite. Sentinelle <code>$0103 / C9:27E4</code> inchangée.</p>
<p>Les diagnostics événement-globaux <code>UNPAUSED_LIVE_LINE_SCROLL_RISK</code> restent visibles pour audit, mais ne pilotent plus automatiquement une insertion de page : ils ont produit les faux positifs du 85.43.</p></div>{''.join(cards)}</body></html>"""
    args.html.parent.mkdir(parents=True, exist_ok=True)
    args.html.write_text(html, encoding="utf-8")

    report = {
        "round": "85.44", "baseline": "85.42", "rejected_round": "85.43",
        "changed_carriers": len(changed), "changed_events": len({x['event_id'] for x in changed}),
        "strategy_counts": strategy_counts, "remaining_local_overflows": 0,
        "simulator_failures": len(failures), "implicit_wraps": implicit_total,
        "remaining_global_live_risk_events": len(live_risks),
        "remaining_global_live_risk_count": sum(x['count'] for x in live_risks),
        "global_live_risks_review_only": live_risks, "changes": changed,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k not in {"changes","global_live_risks_review_only"}}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
