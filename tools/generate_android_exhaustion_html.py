#!/usr/bin/env python3
"""Generate one searchable HTML dashboard for the exhausted Android dialogue source.

The dashboard is deliberately diagnostic only.  It combines:
- the Round-53 identity residual audit (what Android cannot safely identify),
- the current PARTIEL list (Android-owned material still deferred for structure/layout),
- the Round-54 exact recoveries (already-owned Android FR serialized conservatively).
"""
from __future__ import annotations

import argparse
from html import escape
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "mappings" / "android" / "dialogues_android_exhaustion_status.html"

STATE_LABELS = {
    "ANDROID_ABSENT_VALIDATED": "ANDROID ABSENT — VALIDÉ",
    "NO_UNIQUE_ANDROID_EQUIVALENT": "AUCUN ÉQUIVALENT UNIQUE",
    "CONTEXTUAL_TEMPLATE_NO_SINGLE_ID": "GABARIT CONTEXTUEL",
    "VISUALLY_COMPLETE_ANDROID_ADAPTATION": "ADAPTATION VISUELLE VALIDÉE",
    "EXPLICIT_HANDOFF_LOCK": "VERROUILLÉ",
}


def fmt(value: object) -> str:
    return escape(str(value or "")).replace("\n", "<br>")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def translation_ids(document: dict) -> set[str]:
    return {
        entry["id"]
        for group in document.get("groups", [])
        for entry in group.get("entries", [])
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    r53 = load_json(ROOT / "mappings" / "android" / "dialogues_review_round53.json")
    r54 = load_json(ROOT / "mappings" / "android" / "dialogues_review_round54.json")
    auto = load_json(ROOT / "mappings" / "android" / "dialogues_auto.json")
    mass = load_json(ROOT / "mappings" / "android" / "dialogues_format_mass.json")
    tr = load_json(ROOT / "translations" / "dialogues_french.json")
    source = load_json(ROOT / "assets" / "dialogues.json")

    if r53.get("status") != "round53_android_fr_residual_exhaustion_audit":
        raise SystemExit("Round-53 exhaustion review is not current")
    if r54.get("status") != "round54_exact_partial_recovery_runtime_candidate":
        raise SystemExit("Round-54 recovery review is not current")

    events = {e["event_id"]: e for e in source["events"]}
    auto_by_event: dict[str, list[dict]] = {}
    for m in auto["mappings"]:
        auto_by_event.setdefault(m["event_id"], []).append(m)
    translated = translation_ids(tr)

    # Round-54 recoveries.
    recovery_cards = []
    for scene in r54["scenes"]:
        rows = "".join(
            f'<tr><td><code>{fmt(x["id"])}</code></td><td>{fmt(x["text"])}</td></tr>'
            for x in scene.get("serialized_entries", [])
        )
        stock_rows = "".join(
            f'<tr><td>{fmt(kind)}</td><td><code>{fmt(name)}</code></td><td>{fmt(value)}</td></tr>'
            for kind, name, value in scene.get("stock_window", [])
        )
        recovery_cards.append(f'''<details class="card" data-kind="recovered" data-search="{fmt(scene['event_id'] + ' ' + scene.get('note','') + ' ' + scene.get('android_french',''))}" open>
<summary><code>${fmt(scene['event_id'])}</code> · Android {fmt(', '.join(map(str, scene.get('android_ids', []))))} <span class="badge good">RÉCUPÉRÉ — TEST RUNTIME</span></summary>
<div class="grid"><section><h3>Structure SNES USA canonique</h3><table><tbody>{stock_rows}</tbody></table><h3>Android EN</h3><p>{fmt(scene.get('android_english'))}</p><h3>Android FR</h3><p class="focus">{fmt(scene.get('android_french'))}</p></section>
<section><h3>Sérialisation candidate</h3><table><tbody>{rows}</tbody></table><h3>Pourquoi c’est sûr</h3><p>{fmt(scene.get('note'))}</p><p class="muted">Stratégie : {fmt(scene.get('strategy'))}</p></section></div></details>''')

    # Current PARTIEL events.  Mappings touching the listed deferred/unresolved
    # carriers expose whether Android is already found versus truly absent.
    partial_cards = []
    for part in tr.get("partial_events", []):
        event_id = part["event_id"]
        ids = (
            part.get("layout_deferred_semantic_ids")
            or part.get("unresolved_semantic_ids")
            or part.get("manual_pending_semantic_ids")
            or part.get("manual_translated_semantic_ids")
            or []
        )
        ids_set = set(ids)
        mappings = []
        for m in auto_by_event.get(event_id, []):
            if ids_set.intersection(m.get("snes_ids", [])):
                mappings.append(m)
        found_ids = {sid for m in mappings for sid in m.get("snes_ids", []) if sid in ids_set}
        missing_ids = [sid for sid in ids if sid not in found_ids]
        mapping_html = []
        for m in mappings:
            still_stock = [sid for sid in m.get("snes_ids", []) if sid not in translated]
            mapping_html.append(
                '<div class="mapping">'
                f'<b>SNES {fmt(", ".join(m.get("snes_ids", [])))}</b> → Android {fmt(", ".join(map(str,m.get("android_ids",[]))))}'
                f'<div class="pair"><span>EN</span><div>{fmt(m.get("android_english_display"))}</div></div>'
                f'<div class="pair"><span>FR</span><div>{fmt(m.get("french_display") or m.get("identity_french_display"))}</div></div>'
                f'<div class="muted">Encore stock : {fmt(", ".join(still_stock) or "—")}</div></div>'
            )
        source_rows = []
        for token in events[event_id]["tokens"]:
            if token.get("type") == "text" and token.get("id") in ids_set:
                source_rows.append(f'<tr><td><code>{fmt(token["id"])}</code></td><td>{fmt(token.get("source"))}</td></tr>')
        if mappings and not missing_ids:
            label, kind = "ANDROID TROUVÉ — DIFFÉRÉ", "found-deferred"
        elif mappings:
            label, kind = "MIXTE — TROUVÉ + NON TROUVÉ", "mixed"
        else:
            label, kind = "PAS D’IDENTITÉ ANDROID SÉRIALISABLE", "not-found"
        search = " ".join([event_id, part.get("partial_reason", ""), *ids, *missing_ids]).lower()
        partial_cards.append(f'''<details class="card" data-kind="{kind}" data-search="{fmt(search)}" open>
<summary><code>${fmt(event_id)}</code> <span class="badge">{label}</span> <span class="muted">{fmt(part.get('partial_reason'))}</span></summary>
<div class="grid"><section><h3>Carriers encore à traiter</h3><table><tbody>{''.join(source_rows)}</tbody></table><p class="muted">Sans mapping Android dans ce sous-ensemble : {fmt(', '.join(missing_ids) or '—')}</p></section>
<section><h3>Identités Android déjà établies</h3>{''.join(mapping_html) or '<p class="muted">Aucune.</p>'}</section></div></details>''')

    # Final 40 identity residuals, compact but fully searchable and with reason.
    residual_rows = []
    for entry in r53["residual_semantic_audit"]["entries"]:
        state = entry["final_state"]
        residual_rows.append(
            f'<tr data-kind="residual" data-search="{fmt((entry["event_id"]+" "+entry["snes_id"]+" "+entry["source"]+" "+entry["note"]+" "+state).lower())}">'
            f'<td><code>${fmt(entry["event_id"])}</code></td><td><code>{fmt(entry["snes_id"])}</code></td><td>{fmt(entry["source"])}</td>'
            f'<td><span class="badge">{fmt(STATE_LABELS[state])}</span></td><td>{fmt(entry["note"])}</td></tr>'
        )

    coverage = mass["coverage"]
    counts = r53["residual_semantic_audit"]["counts"]
    html = f'''<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Secret of Mana — état final de la source Android</title>
<style>
:root{{--bg:#111318;--panel:#1b1f27;--panel2:#242a34;--text:#eef2f6;--muted:#aeb7c4;--line:#3a4351;--accent:#8ec5ff}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 system-ui,sans-serif}}main{{max-width:1400px;margin:auto;padding:24px}}h1,h2{{margin-top:1.1em}}.lead,.muted{{color:var(--muted)}}.summary{{display:flex;gap:10px;flex-wrap:wrap}}.stat,.card{{background:var(--panel);border:1px solid var(--line);border-radius:10px}}.stat{{padding:10px 14px}}.card{{margin:10px 0;overflow:hidden}}summary{{padding:12px 14px;background:var(--panel2);cursor:pointer}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:14px}}@media(max-width:850px){{.grid{{grid-template-columns:1fr}}}}.focus,.mapping{{background:#151922;border-left:3px solid var(--accent);padding:9px;margin:8px 0}}.mapping{{border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:7px}}.badge{{display:inline-block;border:1px solid #667384;border-radius:999px;padding:2px 7px;font-size:11px;margin:0 4px}}.good{{border-color:#6ca87e}}code{{color:#c8e1ff}}table{{width:100%;border-collapse:collapse}}th,td{{border:1px solid var(--line);padding:6px;vertical-align:top;text-align:left}}.pair{{display:grid;grid-template-columns:30px 1fr;gap:6px;margin-top:5px}}.pair span{{font-weight:700;color:var(--muted)}}.toolbar{{position:sticky;top:0;background:rgba(17,19,24,.97);z-index:4;padding:10px 0;border-bottom:1px solid var(--line)}}input{{width:100%;padding:10px;background:var(--panel);color:var(--text);border:1px solid var(--line);border-radius:8px}}.hidden{{display:none!important}}
</style></head><body><main>
<h1>État final de la source Android · Round 54</h1>
<p class="lead">Android EN reste la preuve d’identité. Le Round 53 a épuisé la recherche d’identité EN + les slots FR-only ; Round 54 ne crée aucune identité et sérialise seulement du FR déjà possédé quand la structure SNES le permet exactement. Ce tableau sépare volontairement ce qui est <b>introuvable dans Android</b> de ce qui est <b>trouvé mais différé</b>.</p>
<div class="summary"><div class="stat"><b>1798 / 1838</b><br>identités établies</div><div class="stat"><b>40</b><br>résidu d’identité classé</div><div class="stat"><b>{coverage['accepted_event_count']}</b><br>événements simulator-clean</div><div class="stat"><b>{coverage['complete_accepted_event_count']} + {coverage['partial_accepted_event_count']}</b><br>complets + PARTIEL</div><div class="stat"><b>{coverage['translation_entry_count']}</b><br>entrées JSON</div></div>
<div class="toolbar"><input id="search" placeholder="Filtrer événement, carrier, Android ID, texte ou raison…"></div>
<h2>Round 54 · récupérations exactes à valider runtime</h2>{''.join(recovery_cards)}
<h2>PARTIEL · Android trouvé mais structure/layout encore à traiter</h2><p class="lead">Cette section est la file de travail à reprendre plus tard. Un badge « Android trouvé — différé » signifie que la recherche source est terminée : le problème restant est structurel, pas lexical.</p>{''.join(partial_cards)}
<h2>40 carriers sans nouvelle identité Android sûre</h2><p class="lead">Ces états sont issus de l’audit Round 53 et restent l’index autoritaire des éléments « non trouvés ». Répartition : {', '.join(f'{STATE_LABELS[k]} {counts[k]}' for k in STATE_LABELS)}.</p>
<table id="residual"><thead><tr><th>Événement</th><th>Carrier</th><th>SNES USA</th><th>État</th><th>Raison</th></tr></thead><tbody>{''.join(residual_rows)}</tbody></table>
</main><script>const q=document.getElementById('search');function apply(){{const s=q.value.toLowerCase().trim();document.querySelectorAll('[data-search]').forEach(x=>x.classList.toggle('hidden',!!s&&!x.dataset.search.includes(s)));}}q.addEventListener('input',apply);</script></body></html>'''

    out = args.output.resolve()
    if args.check:
        if not out.exists() or out.read_text(encoding="utf-8") != html:
            raise SystemExit(f"Generated HTML is out of date: {out}")
        print(f"Verified {out}: {len(recovery_cards)} recoveries, {len(partial_cards)} PARTIEL, 40 residual carriers")
    else:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
        print(f"Generated {out}: {len(recovery_cards)} recoveries, {len(partial_cards)} PARTIEL, 40 residual carriers")


if __name__ == "__main__":
    main()
