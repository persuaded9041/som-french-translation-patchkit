#!/usr/bin/env python3
"""Generate a standalone HTML preview/audit of final encoded SNES dialogue boxes."""
from __future__ import annotations

import argparse
import base64
import csv
import json
from html import escape
from io import BytesIO
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT))

from PIL import Image, ImageDraw  # noqa: E402
from shared.dialogue.codec import load_document  # noqa: E402
from shared.dialogue.simulator import (  # noqa: E402
    DialogueFont,
    EventSimulation,
    Glyph,
    Issue,
    SimLine,
    make_dialogue_font,
    simulate_event,
)
from shared.core.rom import validate_base_rom  # noqa: E402
from shared.dialogue.structure import (  # noqa: E402
    load_structural_omission_token_indexes,
    load_structural_command_overrides,
    load_choice_option_position_overrides,
)
from shared.text.translation_json import load_translation  # noqa: E402

DIALOGUES = PROJECT_ROOT / "assets" / "dialogues.json"
TRANSLATIONS = PROJECT_ROOT / "translations" / "dialogues_french.json"


WAIT00_FRESH_PAGE_BATCH_TEST_EVENTS = frozenset({
    "00FB", "0134", "016D", "01CA", "029C", "03EE", "04A1", "04EA",
})

EXPLICIT_POST_WAIT_NEWLINE_BATCH_TEST_EVENTS = frozenset({
    "0103", "0106", "0136", "0167", "016D", "016E", "01C3", "0228",
    "0259", "026A", "055E", "059B",
})


def render_page_png(lines: list[SimLine], font: DialogueFont, *, scale: int = 2) -> str:
    logical_w, logical_h = 272, 48
    image = Image.new("RGB", (logical_w * scale, logical_h * scale), (25, 67, 150))
    draw = ImageDraw.Draw(image)
    # Border, 256-pixel renderer strip, and runtime-validated 216-pixel safe text limit.
    draw.rectangle((1 * scale, 1 * scale, (logical_w - 2) * scale, (logical_h - 2) * scale), outline=(226, 226, 226), width=scale)
    draw.line((8 * scale, 0, 8 * scale, logical_h * scale), fill=(82, 120, 190), width=1)
    draw.line(((8 + 216) * scale, 0, (8 + 216) * scale, logical_h * scale), fill=(255, 196, 80), width=1)
    draw.line(((8 + 256) * scale, 0, (8 + 256) * scale, logical_h * scale), fill=(82, 120, 190), width=1)

    for line_index, line in enumerate(lines[:4]):
        base_x = 8
        base_y = 3 + line_index * 14
        cursor = 0
        ink_pixels: list[tuple[int, int]] = []
        fixed_cells = bool(line.glyphs) and all(glyph.fixed_cell for glyph in line.glyphs)
        for slot, glyph in enumerate(line.glyphs):
            rows = font.rows[glyph.code]
            glyph_cursor = slot * 8 if fixed_cells else cursor
            for y, row in enumerate(rows):
                for x in range(8):
                    if row & (0x80 >> x):
                        ink_pixels.append((base_x + glyph_cursor + x, base_y + y))
            cursor = (slot + 1) * 8 if fixed_cells else cursor + font.advances[glyph.code]
        # Approximate the game's black outline first, then white ink.
        outline = set()
        for x, y in ink_pixels:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx or dy:
                        outline.add((x + dx, y + dy))
        for x, y in outline:
            if 0 <= x < logical_w and 0 <= y < logical_h:
                draw.rectangle((x * scale, y * scale, (x + 1) * scale - 1, (y + 1) * scale - 1), fill=(0, 0, 0))
        for x, y in ink_pixels:
            if 0 <= x < logical_w and 0 <= y < logical_h:
                draw.rectangle((x * scale, y * scale, (x + 1) * scale - 1, (y + 1) * scale - 1), fill=(255, 255, 255))

    buf = BytesIO()
    image.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def issue_badge(issue: Issue) -> str:
    return f'<span class="badge {issue.severity}">{escape(issue.severity.upper())}</span> <code>{escape(issue.code)}</code> — {escape(issue.message)}'


def source_event_html(event: dict, *, player_name: str) -> str:
    """Render canonical USA event text without applying VWF simulation.

    This column is intentionally a readable source transcript, not a second
    renderer. Canonical SNES hard line breaks are preserved and the few text
    control commands that matter to page flow are shown between chunks.
    """
    structural = {"CE": "▽", "CF": "←", "D0": "→"}
    parts: list[str] = []
    for token in event.get("tokens", []):
        kind = token.get("type")
        if kind in {"text", "ending_text"}:
            text_id = token.get("id", "")
            label = f'<div class="source-id">{escape(text_id)}</div>' if text_id else ""
            parts.append(f'<div class="source-chunk">{label}<pre>{escape(token.get("source", ""))}</pre></div>')
            continue
        if kind == "glyph":
            code = token.get("code", "")
            glyph = structural.get(code.upper(), f"‹${code}›")
            parts.append(f'<span class="source-inline">{escape(glyph)}</span>')
            continue
        if kind != "command":
            continue
        name = token.get("name", "")
        if name == "PLAYER_NAME":
            args = token.get("args", "00").split()
            index = int(args[0], 16) if args else 0
            parts.append(f'<span class="source-inline player">{escape(player_name)} <small>(PLAYER_NAME {index})</small></span>')
        elif name in {"TEXT_OPEN", "TEXT_CLOSE", "TEXT_CLEAR", "WAIT"}:
            suffix = f' ${token.get("args", "")}' if name == "WAIT" and token.get("args") else ""
            parts.append(f'<div class="source-control">{escape(name + suffix)}</div>')
    return "".join(parts) or '<div class="muted">Aucun texte source.</div>'


def make_html(
    simulations: list[EventSimulation],
    font: DialogueFont,
    *,
    player_name: str,
    source_path: Path,
    source_events: dict[str, dict],
    partial_events: set[str] | None = None,
    baseline_simulations: dict[str, EventSimulation] | None = None,
    baseline_translations: dict[str, str] | None = None,
    current_translations: dict[str, str] | None = None,
    preserved_tags: dict[str, set[str]] | None = None,
) -> str:
    partial_events = partial_events or set()
    baseline_simulations = baseline_simulations or {}
    baseline_translations = baseline_translations or {}
    current_translations = current_translations or {}
    preserved_tags = preserved_tags or {"new": set(), "modified": set(), "review": set()}
    total_boxes = sum(len(sim.boxes) for sim in simulations)
    total_pages = sum(len(box.pages) for sim in simulations for box in sim.boxes)
    errors = sum(issue.severity == "error" for sim in simulations for issue in sim.issues)
    warnings = sum(issue.severity == "warning" for sim in simulations for issue in sim.issues)
    implicit = sum(line.implicit_wrap for sim in simulations for box in sim.boxes for page in box.pages for line in page.lines)

    cards: list[str] = []
    for sim in simulations:
        issue_html = "".join(f"<li>{issue_badge(issue)}</li>" for issue in sim.issues)
        if not issue_html:
            issue_html = '<li><span class="badge ok">OK</span> Aucun problème simulé.</li>'
        boxes_html: list[str] = []
        for box_index, box in enumerate(sim.boxes, 1):
            pages_html: list[str] = []
            for page_index, page in enumerate(box.pages, 1):
                if not page.lines and not page.waits:
                    continue
                png = render_page_png(page.lines, font)
                transcript = []
                metrics = []
                for line_index, line in enumerate(page.lines, 1):
                    transcript.append(f"{line_index}. {escape(line.text) if line.text else '&nbsp;'}")
                    metrics.append(
                        f"L{line_index}: {line.advance_pixels}px avance / {line.visible_extent_pixels}px encre / "
                        f"{line.decoded_count} glyphes / {line.parser_units} unités"
                        + (" / WRAP IMPLICITE" if line.implicit_wrap else "")
                    )
                waits = " · ".join(page.waits)
                pages_html.append(f"""
                <div class="page">
                  <div class="page-head"><strong>Boîte {box_index} · Page {page_index}</strong>{' <span class="muted">(ouverture implicite)</span>' if box.implicit_open else ''}</div>
                  <img class="preview" src="data:image/png;base64,{png}" alt="Aperçu simulé événement {sim.event_id} page {page_index}">
                  <pre>{chr(10).join(transcript)}</pre>
                  <div class="metrics">{escape(' | '.join(metrics))}</div>
                  {f'<div class="wait">{escape(waits)}</div>' if waits else ''}
                  {f'<div class="transition">Transition : {escape(page.transition)}</div>' if page.transition else ''}
                </div>""")
            boxes_html.append("".join(pages_html))
        partial = sim.event_id in partial_events
        partial_badge = '<span class="badge partial">PARTIEL · FR/EN incomplet</span>' if partial else ''
        current_ids = set(sim.translated_ids)
        # A previously empty translation becoming visible is NEW too. PARTIEL
        # events now deliberately leave unresolved carriers absent from the sparse
        # French JSON so their stock SNES English stays visible in-game.
        new_ids = (
            sorted(
                text_id
                for text_id in current_ids
                if current_translations.get(text_id, "").strip("\n\r\t \v\f")
                and not baseline_translations.get(text_id, "").strip("\n\r\t \v\f")
            )
            if baseline_translations
            else []
        )
        baseline_sim = baseline_simulations.get(sim.event_id)
        modified = (baseline_sim is not None and baseline_sim.encoded != sim.encoded) or sim.event_id in preserved_tags["modified"]
        is_new = bool(new_ids) or sim.event_id in preserved_tags["new"]
        review_issue_codes = {"WAIT00_THIRD_LINE_SCROLL_RISK", "UNPAUSED_LIVE_LINE_SCROLL_RISK"}
        to_review = (
            partial
            or sim.status != "ok"
            or sim.event_id in WAIT00_FRESH_PAGE_BATCH_TEST_EVENTS
            or sim.event_id in EXPLICIT_POST_WAIT_NEWLINE_BATCH_TEST_EVENTS
            or sim.event_id in preserved_tags["review"]
            or any(issue.code in review_issue_codes for issue in sim.issues)
        )
        tag_badges = []
        if is_new:
            tag_badges.append('<span class="badge new">NEW</span>')
        if modified:
            tag_badges.append('<span class="badge modified">MODIFIED</span>')
        if to_review:
            tag_badges.append('<span class="badge review">TO REVIEW</span>')
        tag_title = f' title="Nouveaux IDs: {escape(", ".join(new_ids))}"' if new_ids else ''
        cards.append(f"""
        <details class="event {sim.status}" data-status="{sim.status}" data-event="{sim.event_id}" data-new="{int(is_new)}" data-modified="{int(modified)}" data-review="{int(to_review)}" open>
          <summary{tag_title}><span class="event-id">${sim.event_id}</span> <span class="status {sim.status}">{sim.status.upper()}</span> {partial_badge} {' '.join(tag_badges)} <span class="muted">{len(sim.translated_ids)} token(s) traduit(s), {len(sim.encoded)} octets encodés</span></summary>
          <ul class="issues">{issue_html}</ul>
          <div class="comparison">
            <section class="translated-column"><h3>Français généré · simulation VWF</h3>{''.join(boxes_html)}</section>
            <section class="source-column"><h3>Source SNES USA · sans VWF</h3>{source_event_html(source_events[sim.event_id], player_name=player_name)}</section>
          </div>
          <details class="raw"><summary>Octets événement encodés</summary><code>{sim.encoded.hex(' ').upper()}</code></details>
        </details>""")

    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Secret of Mana — simulateur de dialogues</title>
<style>
:root {{ color-scheme: dark; --bg:#10131a; --panel:#181d28; --line:#2d3547; --text:#edf2ff; --muted:#9ea9bf; --ok:#59d98e; --warn:#ffc857; --err:#ff6b6b; }}
* {{ box-sizing:border-box }}
body {{ margin:0; font-family:system-ui,-apple-system,Segoe UI,sans-serif; background:var(--bg); color:var(--text); }}
main {{ max-width:1540px; margin:auto; padding:28px 20px 80px; }}
h1 {{ margin:0 0 8px; font-size:28px }}
p {{ line-height:1.5 }}
.toolbar {{ position:sticky; top:0; z-index:5; background:rgba(16,19,26,.94); backdrop-filter:blur(8px); padding:12px 0; display:flex; gap:10px; flex-wrap:wrap; border-bottom:1px solid var(--line); }}
input,button {{ background:#202737; color:var(--text); border:1px solid #39445c; border-radius:7px; padding:9px 11px; }}
button {{ cursor:pointer }}
.stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(135px,1fr)); gap:10px; margin:18px 0 24px; }}
.stat {{ background:var(--panel); border:1px solid var(--line); padding:13px; border-radius:9px; }}
.stat strong {{ display:block; font-size:22px }}
.event {{ background:var(--panel); border:1px solid var(--line); border-left:5px solid var(--ok); border-radius:10px; margin:12px 0; overflow:hidden; }}
.event.warning {{ border-left-color:var(--warn) }} .event.error {{ border-left-color:var(--err) }}
summary {{ cursor:pointer; padding:13px 15px }}
.event-id {{ font:700 16px ui-monospace,SFMono-Regular,Consolas,monospace }}
.status,.badge {{ display:inline-block; font-size:11px; font-weight:800; border-radius:999px; padding:3px 7px; margin:0 5px; }}
.status.ok,.badge.ok {{ background:#193d2b;color:#80efad }} .status.warning,.badge.warning {{ background:#4a3812;color:#ffd878 }} .status.error,.badge.error {{ background:#4c2024;color:#ff9b9b }} .badge.info {{ background:#263750;color:#a8ccff }} .badge.partial {{ background:#4a3518;color:#ffd08a }}
.muted {{ color:var(--muted) }}
.issues {{ margin:0 18px 8px; padding-left:20px; color:#d7deee }} .issues li {{ margin:5px 0 }}
.comparison {{ display:grid; grid-template-columns:minmax(0,1.18fr) minmax(330px,.82fr); gap:14px; padding:0 18px 18px; align-items:start; }}
.translated-column,.source-column {{ min-width:0; }}
.translated-column h3,.source-column h3 {{ margin:4px 0 10px; font-size:14px; color:#c9d5ec; }}
.page {{ margin:12px 0 18px; padding:14px; border:1px solid var(--line); border-radius:9px; background:#121722; }}
.source-column {{ position:sticky; top:72px; max-height:calc(100vh - 92px); overflow:auto; padding:12px; border:1px solid var(--line); border-radius:9px; background:#121722; }}
.source-chunk {{ padding:8px 0; border-bottom:1px solid #242c3b; }} .source-chunk:last-child {{ border-bottom:0 }}
.source-id {{ color:#8292ad; font:11px ui-monospace,SFMono-Regular,Consolas,monospace; margin-bottom:3px; }}
.source-chunk pre {{ margin:0; color:#d7deee; }}
.source-control {{ display:inline-block; margin:6px 6px 6px 0; padding:3px 6px; border-radius:5px; background:#263750; color:#a8ccff; font:11px ui-monospace,SFMono-Regular,Consolas,monospace; }}
.source-inline {{ display:inline-block; margin:4px 4px 4px 0; padding:2px 5px; border-radius:4px; background:#202737; font-family:ui-monospace,SFMono-Regular,Consolas,monospace; }} .source-inline small {{ color:#8292ad }}
@media (max-width:1000px) {{ .comparison {{ grid-template-columns:1fr; }} .source-column {{ position:static; max-height:none; }} }}
.page-head {{ margin-bottom:9px }}
.preview {{ display:block; width:min(544px,100%); image-rendering:pixelated; border-radius:4px; background:#194396; }}
pre {{ white-space:pre-wrap; margin:10px 0 5px; font:14px ui-monospace,SFMono-Regular,Consolas,monospace; color:#eef4ff }}
.metrics {{ color:#aab6cd; font-size:12px; line-height:1.45 }}
.wait {{ margin-top:7px;color:#ffd878;font-size:12px }} .transition {{ margin-top:4px;color:#9fcbff;font-size:12px }}
.raw {{ margin:0 18px 15px; color:var(--muted) }} .raw summary {{ padding:8px 0 }} .raw code {{ display:block; word-break:break-all; font-size:11px; line-height:1.5 }}
.note {{ background:#17202d;border:1px solid #2c3d55;border-radius:9px;padding:13px 15px;margin:15px 0 }}
.hidden {{ display:none!important }}
</style>
</head>
<body><main>
<h1>Simulateur de boîtes de dialogue — `vwf_dialogues` / `french_dialogues`</h1>
<p>Ce rapport repart des <strong>octets événement réellement sérialisés</strong>, puis redécode le flux avec le profil dialogue <code>$E8</code> et les métriques VWF validées. Chaque événement compare maintenant le <strong>français simulé à gauche</strong> et la <strong>source SNES USA canonique à droite</strong>, conservée sans VWF.</p>
<div class="note"><strong>Nom dynamique de test :</strong> <code>{escape(player_name)}</code>. Le défaut est volontairement un nom de 9 caractères larges pour tester le pire cas. Le simulateur vérifie 38 glyphes, la marge empirique de source <code>PLAYER_NAME</code>, le bitmap physique 256 px, la largeur sûre runtime-validée de 216 px, les retours implicites et les 3 lignes physiques par page. Il ne remplace pas un test runtime pour les timings, animations ou artefacts de compositor.</div>
<div class="stats">
<div class="stat"><strong>{len(simulations)}</strong>événements</div><div class="stat"><strong>{total_boxes}</strong>boîtes</div><div class="stat"><strong>{total_pages}</strong>pages</div><div class="stat"><strong>{errors}</strong>erreurs</div><div class="stat"><strong>{warnings}</strong>avertissements</div><div class="stat"><strong>{implicit}</strong>wraps implicites</div>
</div>
<div class="toolbar"><input id="search" placeholder="Filtrer par ID, texte, erreur…"><button id="issues">Afficher seulement les problèmes</button><button class="tag-filter" data-filter="new">NEW</button><button class="tag-filter" data-filter="modified">MODIFIED</button><button class="tag-filter" data-filter="review">TO REVIEW</button><button id="collapse">Tout replier</button><button id="expand">Tout ouvrir</button></div>
<section id="events">{''.join(cards)}</section>
<p class="muted">Source : {escape(str(source_path))}</p>
<script>
const search=document.getElementById('search'); const cards=[...document.querySelectorAll('.event')]; let issuesOnly=false;
function apply(){{ const q=search.value.toLowerCase(); cards.forEach(c=>{{ const match=!q||c.innerText.toLowerCase().includes(q); const issue=!issuesOnly||c.dataset.status!=='ok'; c.classList.toggle('hidden',!(match&&issue)); }}); }}
search.addEventListener('input',apply); document.getElementById('issues').onclick=e=>{{issuesOnly=!issuesOnly;e.target.textContent=issuesOnly?'Afficher tout':'Afficher seulement les problèmes';apply();}};
document.getElementById('collapse').onclick=()=>cards.forEach(c=>c.open=false); document.getElementById('expand').onclick=()=>cards.forEach(c=>c.open=true);
</script>
</main></body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path, help="clean unheadered Secret of Mana (USA) ROM")
    parser.add_argument("-o", "--output", type=Path, default=PROJECT_ROOT / "dialogue_preview.html")
    parser.add_argument("--dialogues", type=Path, default=DIALOGUES)
    parser.add_argument("--translation", type=Path, default=TRANSLATIONS)
    parser.add_argument("--event", action="append", default=[], help="optional event ID (hex), repeatable")
    parser.add_argument("--player-name", default="000000000", help="simulated PLAYER_NAME value; default is 9 wide digits")
    parser.add_argument("--issues-csv", type=Path, help="optional machine-readable issue report")
    parser.add_argument("--baseline-translation", type=Path, help="optional previous translation JSON used to tag NEW/MODIFIED events")
    parser.add_argument("--preserve-tags", type=Path, help="optional JSON snapshot of NEW/MODIFIED/TO REVIEW event IDs to preserve until user review")
    args = parser.parse_args()

    base = args.rom.resolve().read_bytes()
    validate_base_rom(base)
    document = load_document(args.dialogues.resolve())
    translations = load_translation(args.translation.resolve(), document, source_asset="dialogues.json")
    structural_omissions = load_structural_omission_token_indexes(
        args.translation.resolve(), document, translations=translations
    )
    structural_command_overrides = load_structural_command_overrides(
        args.translation.resolve(), document
    )
    choice_option_overrides = load_choice_option_position_overrides(
        args.translation.resolve(), document
    )
    translation_document = json.loads(args.translation.resolve().read_text(encoding="utf-8"))
    partial_events = {
        entry.get("event_id")
        for entry in translation_document.get("partial_events", [])
        if isinstance(entry, dict) and isinstance(entry.get("event_id"), str)
    }
    selected_ids = {value.upper().replace("$", "").zfill(4) for value in args.event}

    events = []
    for event in document["events"]:
        translated = any(token.get("id") in translations for token in event["tokens"] if token.get("id"))
        if selected_ids:
            if event["event_id"] not in selected_ids:
                continue
        elif not translated:
            continue
        events.append(event)
    if selected_ids - {event["event_id"] for event in events}:
        missing = ", ".join(sorted(selected_ids - {event["event_id"] for event in events}))
        raise SystemExit(f"Requested event(s) not found in dialogue asset: {missing}")
    if not events:
        raise SystemExit("No events selected for simulation")

    font = make_dialogue_font(base)
    player_names = {0: args.player_name, 1: args.player_name, 2: args.player_name}
    simulations = [
        simulate_event(
            base,
            event,
            translations,
            font=font,
            player_names=player_names,
            omitted_command_token_indexes=structural_omissions.get(event["event_id"]),
            structural_command_overrides=structural_command_overrides.get(event["event_id"]),
            choice_option_position_overrides=choice_option_overrides.get(event["event_id"]),
        )
        for event in events
    ]

    source_events = {event["event_id"]: event for event in events}
    preserved_tags = {"new": set(), "modified": set(), "review": set()}
    if args.preserve_tags:
        raw_preserved = json.loads(args.preserve_tags.resolve().read_text(encoding="utf-8"))
        for key in preserved_tags:
            values = raw_preserved.get(key, [])
            if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
                raise SystemExit(f"Invalid preserve-tags field: {key}")
            preserved_tags[key] = {v.upper().replace("$", "").zfill(4) for v in values}
    baseline_translations: dict[str, str] = {}
    baseline_simulations: dict[str, EventSimulation] = {}
    if args.baseline_translation:
        baseline_path = args.baseline_translation.resolve()
        baseline_translations = load_translation(baseline_path, document, source_asset="dialogues.json")
        baseline_structural_omissions = load_structural_omission_token_indexes(
            baseline_path, document, translations=baseline_translations
        )
        baseline_structural_command_overrides = load_structural_command_overrides(
            baseline_path, document
        )
        baseline_choice_option_overrides = load_choice_option_position_overrides(
            baseline_path, document
        )
        baseline_simulations = {
            event["event_id"]: simulate_event(
                base,
                event,
                baseline_translations,
                font=font,
                player_names=player_names,
                omitted_command_token_indexes=baseline_structural_omissions.get(event["event_id"]),
                structural_command_overrides=baseline_structural_command_overrides.get(event["event_id"]),
                choice_option_position_overrides=baseline_choice_option_overrides.get(event["event_id"]),
            )
            for event in events
            if any(token.get("id") in baseline_translations for token in event["tokens"] if token.get("id"))
        }
    html = make_html(
        simulations,
        font,
        player_name=args.player_name,
        source_path=args.translation.resolve(),
        source_events=source_events,
        partial_events=partial_events,
        baseline_simulations=baseline_simulations,
        baseline_translations=baseline_translations,
        current_translations=translations,
        preserved_tags=preserved_tags,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")

    issues = [issue for sim in simulations for issue in sim.issues]
    if args.issues_csv:
        args.issues_csv.parent.mkdir(parents=True, exist_ok=True)
        with args.issues_csv.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(["event_id", "severity", "code", "box", "page", "line", "message"])
            for issue in issues:
                writer.writerow([issue.event_id, issue.severity, issue.code, issue.box or "", issue.page or "", issue.line or "", issue.message])

    errors = sum(issue.severity == "error" for issue in issues)
    warnings = sum(issue.severity == "warning" for issue in issues)
    implicit = sum(line.implicit_wrap for sim in simulations for box in sim.boxes for page in box.pages for line in page.lines)
    wait_scroll_review = sum(issue.code == "WAIT00_THIRD_LINE_SCROLL_RISK" for issue in issues)
    print(f"Simulated translated events: {len(simulations)}")
    print(f"Errors: {errors}; warnings: {warnings}; implicit runtime wraps: {implicit}")
    print(f"WAIT $00 third-line scroll review risks: {wait_scroll_review}")
    print(f"HTML: {args.output}")
    if args.issues_csv:
        print(f"Issues CSV: {args.issues_csv}")


if __name__ == "__main__":
    main()
