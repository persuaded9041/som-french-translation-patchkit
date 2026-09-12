#!/usr/bin/env python3
"""Generate/check the current manual supplement review sheet."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "translations" / "dialogues_manual_supplements.json"
OUTPUT = ROOT / "reports" / "android" / "dialogues_manual_supplements.html"


def esc(value: object) -> str:
    if value is None:
        return '<span class="muted">Non transcrit avec certitude</span>'
    return html.escape(str(value)).replace("\n", "<br>")


def render() -> str:
    doc = json.loads(SOURCE.read_text(encoding="utf-8"))
    rows: list[str] = []
    pending = 0
    translated = 0
    suppressed = 0
    for entry in doc.get("entries", []):
        status = entry["status"]
        pending += status == "needs_manual_translation"
        translated += status == "translated"
        suppressed += status == "suppressed"
        jp_extra = ""
        raw = entry.get("original_jp_raw_hex")
        state = entry.get("original_jp_status", "")
        jp_event = entry.get("original_jp_event_id")
        jp_carrier = entry.get("original_jp_carrier_id")
        bits = []
        if state:
            bits.append(f"<b>État JP :</b> {html.escape(state)}")
        if jp_event or jp_carrier:
            location = []
            if jp_event:
                location.append(f"événement <code>${html.escape(str(jp_event))}</code>")
            if jp_carrier:
                location.append(f"carrier <code>{html.escape(str(jp_carrier))}</code>")
            bits.append("<b>Localisation JP :</b> " + " · ".join(location))
        if raw:
            bits.append(f"<b>Octets JP conservés :</b> <code>{html.escape(raw)}</code>")
        jp_context = entry.get("original_jp_context")
        if jp_context:
            ctx_loc = []
            if entry.get("original_jp_context_event_id"):
                ctx_loc.append(f"événement <code>${html.escape(str(entry['original_jp_context_event_id']))}</code>")
            if entry.get("original_jp_context_carrier_id"):
                ctx_loc.append(f"carrier <code>{html.escape(str(entry['original_jp_context_carrier_id']))}</code>")
            bits.append(
                "<b>Contexte JP attesté" + (" (" + " · ".join(ctx_loc) + ")" if ctx_loc else "") +
                ":</b><div class=\"text\">" + esc(jp_context) + "</div>"
            )
        if entry.get("original_jp_context_raw_hex"):
            bits.append(f"<b>Octets du contexte JP :</b> <code>{html.escape(str(entry['original_jp_context_raw_hex']))}</code>")
        if entry.get("original_fr_carrier_ids"):
            bits.append(
                "<b>Bloc FR Rev1 resegmenté :</b> " + ", ".join(
                    f"<code>{html.escape(str(v))}</code>" for v in entry["original_fr_carrier_ids"]
                )
            )
        if bits:
            jp_extra = '<div class="evidence">' + "<br>".join(bits) + "</div>"
        if status == "needs_manual_translation":
            badge, status_label = "pending", "À VALIDER"
        elif status == "suppressed":
            badge, status_label = "suppressed", "SUPPRIMÉ"
        else:
            badge, status_label = "done", "VALIDÉ"
        if status == "suppressed":
            proposal_html = '<span class="muted">Aucun texte affiché dans le patch.</span>'
        elif status == "needs_manual_translation" and entry.get("proposal_action") == "suppress":
            proposal_html = '<b>SUPPRESSION PROPOSÉE</b><br><span class="muted">Aucun texte japonais distinct ne correspond à ce carrier occidental.</span>'
        else:
            proposal_html = esc(entry.get('translation_fr'))
        rows.append(f"""
<details class="card" data-status="{html.escape(status)}" open>
  <summary><code>${html.escape(entry['event_id'])}</code> · <code>{html.escape(entry['id'])}</code>
    <span class="badge {badge}">{status_label}</span></summary>
  <div class="grid">
    <section><h3>SNES japonais original</h3><div class="text">{esc(entry.get('original_jp'))}</div>{jp_extra}</section>
    <section><h3>SNES USA original</h3><div class="text">{esc(entry.get('original_en'))}</div></section>
    <section><h3>SNES France Rev 1</h3><div class="text">{esc(entry.get('original_fr'))}</div></section>
    <section class="proposal"><h3>Proposition du patch</h3><div class="text">{proposal_html}</div></section>
  </div>
  <div class="meta"><b>Base de proposition :</b> {html.escape(entry.get('proposal_basis',''))}<br>
  <b>Note :</b> {html.escape(entry.get('review_note',''))}</div>
</details>""")

    refs = doc.get("reference_roms", {})
    jp_hash = refs.get("snes_jp", {}).get("sha256", "")
    us_hash = refs.get("snes_us", {}).get("sha256", "")
    fr_hash = refs.get("snes_fr_rev1", {}).get("sha256", "")
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Secret of Mana — surcharges manuelles</title>
<style>
:root{{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#202530;background:#f5f6f8}}
body{{max-width:1280px;margin:0 auto;padding:28px 18px 60px}}h1{{margin-bottom:6px}}.lead{{color:#5b6472;max-width:950px}}
.banner{{background:#fff8dc;border:1px solid #e5cf72;border-radius:12px;padding:14px 16px;margin:20px 0}}
.stats{{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0}}.stat{{background:white;border:1px solid #dce1e8;border-radius:10px;padding:9px 12px}}
.card{{background:white;border:1px solid #dce1e8;border-radius:12px;margin:14px 0;box-shadow:0 1px 2px #00000008}}summary{{padding:14px 16px;font-weight:700;cursor:pointer}}
.badge{{font-size:.75rem;margin-left:8px;padding:3px 7px;border-radius:999px}}.pending{{background:#fff0c8;color:#775000}}.done{{background:#daf4e2;color:#196633}}.suppressed{{background:#eceff3;color:#4d5968}}
.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;padding:0 16px 14px}}section{{border:1px solid #e5e8ed;border-radius:10px;padding:12px;background:#fbfcfd}}section.proposal{{background:#eef6ff;border-color:#bed8f5}}h3{{font-size:.88rem;margin:0 0 8px;color:#536071;text-transform:uppercase;letter-spacing:.03em}}
.text{{white-space:normal;font-family:ui-monospace,SFMono-Regular,Consolas,monospace;line-height:1.45}}.meta{{border-top:1px solid #e5e8ed;padding:12px 16px;color:#56606e;font-size:.9rem;line-height:1.45}}.evidence{{margin-top:9px;color:#67717f;font-size:.82rem}}.muted{{color:#8a929e;font-style:italic}}
.hashes{{font-size:.78rem;color:#687281;word-break:break-all}}code{{font-family:ui-monospace,SFMono-Regular,Consolas,monospace}}@media(max-width:760px){{.grid{{grid-template-columns:1fr}}}}
</style></head><body>
<h1>Surcharges manuelles</h1>
<p class="lead">Comparaison destinée à la validation humaine. Le sens du SNES japonais est prioritaire ; la localisation française officielle sert de référence de terminologie et de ton. Une proposition marquée « À valider » n'est jamais injectée : le build conserve le texte USA tant que <code>status=needs_manual_translation</code>. Une entrée « SUPPRIMÉ » conserve ses trois sources pour provenance mais n'affiche aucun texte.</p>
<div class="banner"><b>Règle de provenance :</b> <code>original_jp</code> ne contient que du japonais attribué au SNES original avec suffisamment de certitude. Un champ JP non encore transcrit reste volontairement vide ; Android JP n'est jamais substitué à l'original SNES.</div>
<div class="stats"><div class="stat"><b>{len(rows)}</b> carriers manuels</div><div class="stat"><b>{pending}</b> proposition(s) à valider</div><div class="stat"><b>{translated}</b> traduction(s) validée(s)</div><div class="stat"><b>{suppressed}</b> suppression(s) validée(s)</div></div>
<div class="hashes">SNES JP SHA-256 : <code>{html.escape(jp_hash)}</code><br>SNES USA SHA-256 : <code>{html.escape(us_hash)}</code><br>SNES FR Rev 1 SHA-256 : <code>{html.escape(fr_hash)}</code></div>
{''.join(rows)}
</body></html>"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    text = render()
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != text:
            raise SystemExit(f"stale generated file: {OUTPUT.relative_to(ROOT)}")
        print("Manual supplement HTML is up to date")
        return
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(text, encoding="utf-8")
    print(f"Generated {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
