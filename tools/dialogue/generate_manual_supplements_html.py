#!/usr/bin/env python3
"""Generate/check the current minimal manual-supplement review sheet."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "translations" / "dialogues_manual_supplements.json"
DIALOGUES = ROOT / "assets" / "dialogues.json"
OUTPUT = ROOT / "reports" / "android" / "dialogues_manual_supplements.html"


def esc(value: object) -> str:
    return html.escape(str(value)).replace("\n", "<br>")


def render() -> str:
    doc = json.loads(SOURCE.read_text(encoding="utf-8"))
    source = json.loads(DIALOGUES.read_text(encoding="utf-8"))
    by_id = {
        token["id"]: (event["event_id"], token.get("source", ""))
        for event in source["events"]
        for token in event.get("tokens", [])
        if token.get("type") == "text" and token.get("id")
    }
    rows: list[str] = []
    suppressed = 0
    for entry in doc.get("entries", []):
        text_id = entry["id"]
        event_id, original_en = by_id[text_id]
        is_suppressed = entry.get("suppress") is True
        suppressed += is_suppressed
        if is_suppressed:
            badge, proposal = "suppressed", '<span class="muted">Carrier supprimé du payload final.</span>'
        else:
            badge, proposal = "done", esc(entry["text"])
        rows.append(f"""
<details class="card" open>
  <summary><code>${html.escape(event_id)}</code> · <code>{html.escape(text_id)}</code>
    <span class="badge {badge}">{'SUPPRIMÉ' if is_suppressed else 'VALIDÉ'}</span></summary>
  <div class="grid">
    <section><h3>SNES USA canonique</h3><div class="text">{esc(original_en)}</div></section>
    <section class="proposal"><h3>Payload manuel</h3><div class="text">{proposal}</div></section>
  </div>
</details>""")
    translated = len(rows) - suppressed
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Secret of Mana — surcharges manuelles</title>
<style>
:root{{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#202530;background:#f5f6f8}}
body{{max-width:1100px;margin:0 auto;padding:28px 18px 60px}}h1{{margin-bottom:6px}}.lead{{color:#5b6472;max-width:900px}}
.stats{{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0}}.stat{{background:white;border:1px solid #dce1e8;border-radius:10px;padding:9px 12px}}
.card{{background:white;border:1px solid #dce1e8;border-radius:12px;margin:14px 0;box-shadow:0 1px 2px #00000008}}summary{{padding:14px 16px;font-weight:700;cursor:pointer}}
.badge{{font-size:.75rem;margin-left:8px;padding:3px 7px;border-radius:999px}}.done{{background:#daf4e2;color:#196633}}.suppressed{{background:#eceff3;color:#4d5968}}
.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;padding:0 16px 14px}}section{{border:1px solid #e5e8ed;border-radius:10px;padding:12px;background:#fbfcfd}}section.proposal{{background:#eef6ff;border-color:#bed8f5}}h3{{font-size:.88rem;margin:0 0 8px;color:#536071;text-transform:uppercase;letter-spacing:.03em}}
.text{{white-space:normal;font-family:ui-monospace,SFMono-Regular,Consolas,monospace;line-height:1.45}}.muted{{color:#8a929e;font-style:italic}}code{{font-family:ui-monospace,SFMono-Regular,Consolas,monospace}}@media(max-width:760px){{.grid{{grid-template-columns:1fr}}}}
</style></head><body>
<h1>Surcharges manuelles</h1>
<p class="lead">Vue générée depuis le manifeste minimal. L'événement et le texte USA sont reconstruits depuis <code>assets/dialogues.json</code>; le manifeste ne versionne que la décision manuelle finale.</p>
<div class="stats"><div class="stat"><b>{len(rows)}</b> carriers</div><div class="stat"><b>{translated}</b> traduction(s)</div><div class="stat"><b>{suppressed}</b> suppression(s)</div></div>
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
