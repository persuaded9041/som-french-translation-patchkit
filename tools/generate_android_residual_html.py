#!/usr/bin/env python3
"""Generate a focused HTML index for the exhausted Android dialogue residuals.

The report is intentionally identity-only: it does not alter translations.  It
presents every residual semantic SNES carrier by its final audited state, with
nearby SNES and already-owned Android context, plus the remaining Android-FR-only
records whose Android-English slot is empty.
"""
from __future__ import annotations

import argparse
from html import escape
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REVIEW = ROOT / "mappings" / "android" / "dialogues_review_round53.json"
DEFAULT_OUTPUT = ROOT / "mappings" / "android" / "dialogues_review_round53_context.html"

STATE_LABELS = {
    "ANDROID_ABSENT_VALIDATED": "ANDROID ABSENT — VALIDÉ",
    "NO_UNIQUE_ANDROID_EQUIVALENT": "AUCUN ÉQUIVALENT UNIQUE",
    "CONTEXTUAL_TEMPLATE_NO_SINGLE_ID": "GABARIT CONTEXTUEL",
    "VISUALLY_COMPLETE_ANDROID_ADAPTATION": "ADAPTATION VISUELLE VALIDÉE",
    "EXPLICIT_HANDOFF_LOCK": "VERROUILLÉ",
}


def load_scrtxt_reader():
    path = ROOT / "tools" / "import_android_text.py"
    spec = importlib.util.spec_from_file_location("import_android_text_for_residual_html", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load import_android_text.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.read_scrtxt


def fmt_text(value: str) -> str:
    return escape(value).replace("\n", "<br>")


def mapping_context(mapping: dict) -> str:
    ids = ", ".join(str(x) for x in mapping.get("android_ids", [])) or "—"
    snes = ", ".join(mapping.get("snes_ids", []))
    en = mapping.get("android_english_display", "")
    fr = mapping.get("french_display") or mapping.get("identity_french_display", "")
    return (
        f'<div class="anchor"><div><b>{escape(snes)}</b> → Android {escape(ids)}</div>'
        f'<div class="pair"><span>EN</span>{fmt_text(en)}</div>'
        f'<div class="pair"><span>FR</span>{fmt_text(fr)}</div></div>'
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="verify the existing HTML is byte-for-byte current")
    args = parser.parse_args()

    review = json.loads(args.review.resolve().read_text(encoding="utf-8"))
    if review.get("status") != "round53_android_fr_residual_exhaustion_audit":
        raise SystemExit("Expected the Round-53 Android-FR exhaustion audit")

    source = json.loads((ROOT / "assets" / "dialogues.json").read_text(encoding="utf-8"))
    events = {event["event_id"]: event for event in source["events"]}
    auto = json.loads((ROOT / "mappings" / "android" / "dialogues_auto.json").read_text(encoding="utf-8"))
    mappings_by_event: dict[str, list[dict]] = {}
    for mapping in auto["mappings"]:
        mappings_by_event.setdefault(mapping["event_id"], []).append(mapping)

    read_scrtxt = load_scrtxt_reader()
    android_en = read_scrtxt(ROOT / "sources" / "android" / "scrtxt_en.bin")
    android_fr = read_scrtxt(ROOT / "sources" / "android" / "scrtxt_fr.bin")

    cards: list[str] = []
    for entry in review["residual_semantic_audit"]["entries"]:
        event_id = entry["event_id"]
        snes_id = entry["snes_id"]
        event = events[event_id]
        text_tokens = [token for token in event["tokens"] if token.get("type") == "text"]
        text_pos = next(i for i, token in enumerate(text_tokens) if token["id"] == snes_id)
        start, stop = max(0, text_pos - 2), min(len(text_tokens), text_pos + 3)
        snes_context = []
        for idx in range(start, stop):
            token = text_tokens[idx]
            cls = " current" if token["id"] == snes_id else ""
            snes_context.append(
                f'<div class="snes-line{cls}"><code>{escape(token["id"])}</code> {fmt_text(token["source"])}</div>'
            )

        token_index = next(i for i, token in enumerate(event["tokens"]) if token.get("id") == snes_id)
        nearby = []
        for mapping in mappings_by_event.get(event_id, []):
            positions = [
                i for i, token in enumerate(event["tokens"])
                if token.get("type") == "text" and token.get("id") in mapping.get("snes_ids", [])
            ]
            if not positions:
                continue
            distance = min(abs(pos - token_index) for pos in positions)
            nearby.append((distance, min(positions), mapping))
        nearby.sort(key=lambda item: (item[0], item[1]))
        anchor_html = "".join(mapping_context(item[2]) for item in nearby[:2]) or '<div class="muted">Aucune ancre Android possédée dans cet événement.</div>'

        best_id = entry.get("best_android_english_id")
        best_html = '<div class="muted">Aucun candidat automatique.</div>'
        if best_id is not None:
            best_html = (
                f'<div class="candidate"><b>Meilleur candidat automatique : Android {best_id}</b>'
                f'<div class="pair"><span>EN</span>{fmt_text(android_en.get(best_id, entry.get("best_android_english", "")))}</div>'
                f'<div class="pair"><span>FR</span>{fmt_text(android_fr.get(best_id, entry.get("best_android_french_candidate", "")))}</div></div>'
            )

        state = entry["final_state"]
        search_blob = " ".join([
            event_id, snes_id, entry["source"], state, entry["note"],
            entry.get("best_android_english", ""), entry.get("best_android_french_candidate", ""),
        ]).lower()
        cards.append(f'''
<details class="card" data-state="{escape(state)}" data-search="{escape(search_blob)}" open>
  <summary><code>${escape(event_id)}</code> · <code>{escape(snes_id)}</code> <span class="badge {escape(state.lower())}">{escape(STATE_LABELS[state])}</span></summary>
  <div class="grid">
    <section><h3>Carrier SNES USA</h3><div class="focus">{fmt_text(entry["source"])}</div><h4>Contexte SNES</h4>{''.join(snes_context)}</section>
    <section><h3>État final</h3><p>{escape(entry["note"])}</p>{best_html}<h4>Ancres Android possédées les plus proches</h4>{anchor_html}</section>
  </div>
</details>''')

    fr_only_cards = []
    for item in review["android_fr_only_audit"]["entries"]:
        if item["owned"]:
            continue
        aid = item["android_id"]
        lo, hi = max(min(android_en), aid - 2), min(max(android_en), aid + 2)
        rows = []
        for idx in range(lo, hi + 1):
            if idx not in android_en:
                continue
            rows.append(
                f'<tr><td>{idx}</td><td>{fmt_text(android_en[idx])}</td><td>{fmt_text(android_fr[idx])}</td></tr>'
            )
        fr_only_cards.append(f'''
<details class="fronly" open>
  <summary>Android {aid} · <span class="badge fronlybadge">FR-ONLY NON ATTRIBUÉ</span></summary>
  <p><b>FR :</b> {fmt_text(item["french"])}</p>
  <p>{escape(item.get("note", ""))}</p>
  <table><thead><tr><th>ID</th><th>Android EN</th><th>Android FR</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
</details>''')

    counts = review["residual_semantic_audit"]["counts"]
    buttons = ['<button class="state active" data-state="all">Tous · 40</button>']
    for key in STATE_LABELS:
        buttons.append(f'<button class="state" data-state="{escape(key)}">{escape(STATE_LABELS[key])} · {counts[key]}</button>')

    html = f'''<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Secret of Mana — Round 53 · résidu Android FR</title>
<style>
:root{{--bg:#111318;--panel:#1b1f27;--panel2:#242a34;--text:#eef2f6;--muted:#aeb7c4;--line:#3a4351;--accent:#8ec5ff}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--text);font:15px/1.45 system-ui,sans-serif}} main{{max-width:1320px;margin:auto;padding:24px}}
h1{{margin:.2em 0}} .lead{{color:var(--muted);max-width:1000px}} .summary{{display:flex;gap:12px;flex-wrap:wrap;margin:18px 0}} .stat{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 16px}}
.toolbar{{position:sticky;top:0;z-index:5;background:rgba(17,19,24,.96);padding:12px 0;display:flex;gap:8px;flex-wrap:wrap;border-bottom:1px solid var(--line)}} input{{flex:1;min-width:260px;background:var(--panel);color:var(--text);border:1px solid var(--line);padding:10px;border-radius:8px}} button{{background:var(--panel);color:var(--text);border:1px solid var(--line);padding:9px 11px;border-radius:8px;cursor:pointer}} button.active{{outline:2px solid var(--accent)}}
.card,.fronly{{background:var(--panel);border:1px solid var(--line);border-radius:10px;margin:12px 0;overflow:hidden}} summary{{padding:13px 15px;cursor:pointer;background:var(--panel2)}} .grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px;padding:15px}} @media(max-width:850px){{.grid{{grid-template-columns:1fr}}}}
section h3,section h4{{margin:.3em 0 .7em}} .focus{{font-size:1.08em;border-left:4px solid var(--accent);padding:10px 12px;background:#151922}} .snes-line{{padding:5px 8px;border-bottom:1px solid #2f3641}} .snes-line.current{{background:#2b3543}} code{{color:#c8e1ff}} .muted{{color:var(--muted)}}
.badge{{display:inline-block;padding:3px 7px;border:1px solid #5a6574;border-radius:999px;font-size:11px;margin-left:8px}} .android_absent_validated{{border-color:#7397bd}} .no_unique_android_equivalent{{border-color:#b6956c}} .contextual_template_no_single_id{{border-color:#9b8bc4}} .visually_complete_android_adaptation{{border-color:#78aa89}} .explicit_handoff_lock{{border-color:#c57d7d}} .fronlybadge{{border-color:#d1a75c}}
.pair{{display:grid;grid-template-columns:36px 1fr;gap:8px;margin:5px 0}} .pair span{{color:var(--muted);font-weight:700}} .anchor,.candidate{{border:1px solid var(--line);border-radius:7px;padding:9px;margin:8px 0;background:#151922}} table{{width:100%;border-collapse:collapse;margin-top:10px}} th,td{{border:1px solid var(--line);padding:7px;text-align:left;vertical-align:top}} .hidden{{display:none!important}}
</style></head><body><main>
<h1>Round 53 · résidu Android FR épuisé</h1>
<p class="lead">Audit identité uniquement. Android EN reste la couche de preuve. Round 51 avait fermé le reliquat EN ; Round 53 examine toutes les entrées <code>scrtxt</code> où EN est vide mais FR non vide et classe les 40 carriers SNES encore hors identité. Aucun mapping ni payload de traduction n'est ajouté.</p>
<div class="summary"><div class="stat"><b>1798 / 1838</b><br>identités établies</div><div class="stat"><b>40</b><br>carriers résiduels</div><div class="stat"><b>62</b><br>IDs FR-only (EN vide)</div><div class="stat"><b>58</b><br>déjà possédés</div><div class="stat"><b>4</b><br>FR-only non attribués, tous expliqués</div></div>
<div class="toolbar"><input id="search" placeholder="Filtrer par événement, carrier, texte ou raison…">{''.join(buttons)}</div>
<h2>40 carriers résiduels</h2>
{''.join(cards)}
<h2>4 entrées Android FR-only encore non attribuées</h2>
<p class="lead">Elles sont conservées comme preuve d’audit, mais aucune ne fournit une nouvelle identité SNES sûre sous la règle « Android EN = identité ».</p>
{''.join(fr_only_cards)}
</main>
<script>
const cards=[...document.querySelectorAll('.card')]; const search=document.getElementById('search'); let state='all';
function apply(){{const q=search.value.toLowerCase().trim(); cards.forEach(c=>{{const okState=state==='all'||c.dataset.state===state; const okText=!q||c.dataset.search.includes(q); c.classList.toggle('hidden',!(okState&&okText));}})}}
search.addEventListener('input',apply); document.querySelectorAll('button.state').forEach(b=>b.addEventListener('click',()=>{{document.querySelectorAll('button.state').forEach(x=>x.classList.remove('active'));b.classList.add('active');state=b.dataset.state;apply();}}));
</script></body></html>'''
    out = args.output.resolve()
    if args.check:
        if not out.exists():
            raise SystemExit(f"Missing generated HTML: {out}")
        if out.read_text(encoding="utf-8") != html:
            raise SystemExit(f"Generated HTML is out of date: {out}")
        print(f"Verified {out} ({len(review['residual_semantic_audit']['entries'])} residual carriers, {len(fr_only_cards)} unowned FR-only entries)")
    else:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
        print(f"Generated {out} ({len(review['residual_semantic_audit']['entries'])} residual carriers, {len(fr_only_cards)} unowned FR-only entries)")


if __name__ == "__main__":
    main()
