#!/usr/bin/env python3
"""Generate the focused Round-67 full Android-FR review sheet for event $04E2."""
from __future__ import annotations
import html
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tools.import_android_text import read_scrtxt  # noqa: E402

OUT = ROOT / "mappings" / "android" / "dialogue_04E2_android_fr_round67.html"
EVENT_ID = "04E2"
ANDROID_IDS = range(1274, 1309)
DEFERRED = {
    1285: "CA:3335 + CA:3359",
    1286: "CA:3362",
    1288: "CA:33E4",
    1289: "CA:33E4",
    1290: "CA:3423",
    1291: "CA:3423",
}

def esc(v: object) -> str:
    return html.escape(str(v)).replace("\n", "<br>").replace("_", "<span class='wait'>_</span>")

def render() -> str:
    en = read_scrtxt(ROOT / "sources/android/scrtxt_en.bin")
    fr = read_scrtxt(ROOT / "sources/android/scrtxt_fr.bin")
    source = json.loads((ROOT / "assets/dialogues.json").read_text(encoding="utf-8"))
    trans = json.loads((ROOT / "translations/dialogues_french.json").read_text(encoding="utf-8"))
    active = {e["id"]: e["text"] for g in trans["groups"] for e in g["entries"]}
    ev = next(e for e in source["events"] if e["event_id"] == EVENT_ID)

    android_rows = []
    for i in ANDROID_IDS:
        if i == 1280:
            state = "omis"
            state_label = "OMIS SUR DEMANDE"
            carrier = "CA:32C5 (carrier réutilisé pour Android 1281)"
        elif i == 1281:
            state = "resolved"
            state_label = "REDISTRIBUÉ"
            carrier = "CA:32C5 + CA:32D7 · PLAYER_NAME(2)"
        elif i in DEFERRED:
            state = "deferred"
            state_label = "À RÉORGANISER"
            carrier = DEFERRED[i]
        elif i in {1295}:
            state = "extra"
            state_label = "ANDROID FR-ONLY"
            carrier = "à lire dans la séquence complète"
        elif not en.get(i, "") and not fr.get(i, ""):
            state = "empty"
            state_label = "VIDE"
            carrier = "—"
        else:
            state = "normal"
            state_label = "CONTEXTE / DÉJÀ TRAITÉ"
            carrier = ""
        android_rows.append(f"""
<tr class="{state}"><td class="id">{i}</td><td><span class="badge">{state_label}</span>{('<div class="carrier">'+esc(carrier)+'</div>') if carrier else ''}</td><td class="mono">{esc(en.get(i,'')) or '<span class="muted">vide</span>'}</td><td class="mono fr">{esc(fr.get(i,'')) or '<span class="muted">vide</span>'}</td></tr>""")

    token_rows=[]
    for idx,t in enumerate(ev["tokens"]):
        if t.get("type") == "text":
            tid=t["id"]
            cur=active.get(tid)
            status="translated" if cur is not None else "stock"
            marker="À RÉORGANISER" if tid in {"CA:3335","CA:3359","CA:3362","CA:33E4","CA:3423"} else ("FR ACTIF" if cur is not None else "STOCK")
            token_rows.append(f"<tr class='{status}'><td>{idx}</td><td><code>{esc(tid)}</code></td><td>{marker}</td><td class='mono'>{esc(t.get('source',''))}</td><td class='mono fr'>{esc(cur) if cur is not None else '<span class="muted">stock USA</span>'}</td></tr>")
        elif t.get("type") == "command" and t.get("name") in {"PLAYER_NAME","WAIT","TEXT_CLEAR","TEXT_OPEN","COMPLETE_ACTIONS"}:
            args=(" "+t.get("args","")) if t.get("args") else ""
            note=""
            if idx==35: note=" → traduit comme PLAYER_NAME 02"
            if idx==37: note=" → omis dans la version traduite"
            token_rows.append(f"<tr class='command'><td>{idx}</td><td colspan='2'><code>{esc(t['name']+args)}</code>{esc(note)}</td><td colspan='2'></td></tr>")

    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>$04E2 — vue complète Android FR Round 67</title>
<style>
:root{{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#20242c;background:#f4f6f8}}body{{max-width:1500px;margin:auto;padding:24px}}h1{{margin-bottom:4px}}h2{{margin-top:28px}}.lead{{color:#596373;max-width:1100px;line-height:1.45}}.box{{background:white;border:1px solid #dce2e8;border-radius:12px;padding:14px 16px;margin:16px 0}}table{{width:100%;border-collapse:collapse;background:white;border:1px solid #dce2e8}}th,td{{border-bottom:1px solid #e6e9ed;padding:9px;vertical-align:top;text-align:left}}th{{position:sticky;top:0;background:#eef1f5;z-index:1}}.mono{{white-space:normal;font:13px/1.45 ui-monospace,SFMono-Regular,Consolas,monospace}}.fr{{background:#f8fbff}}.id{{font-weight:700;width:55px}}.badge{{font-size:11px;font-weight:700;padding:3px 6px;border-radius:999px;background:#edf0f4}}.carrier{{font-size:12px;color:#657080;margin-top:5px}}tr.deferred td{{background:#fff6dd}}tr.omis td{{background:#f0f1f3;color:#67717d}}tr.resolved td{{background:#eaf8ee}}tr.extra td{{background:#f3edff}}tr.command td{{background:#f2f3f5;color:#606a76}}.muted{{color:#949ba5;font-style:italic}}.wait{{background:#ffe9a8;padding:0 2px;border-radius:3px}}code{{font-family:ui-monospace,SFMono-Regular,Consolas,monospace}}ul{{line-height:1.5}}@media(max-width:900px){{body{{padding:12px}}table{{font-size:12px}}th,td{{padding:6px}}}}
</style></head><body>
<h1>$04E2 — dialogue Android FR complet</h1><p class="lead">Round 67 · vue de travail destinée à la réorganisation manuelle des blocs SNES. La colonne Android FR reproduit tous les slots <b>1274 à 1308</b>, y compris les slots vides et Android-only. Les lignes jaunes sont les seules zones encore différées dans le payload SNES actuel.</p>
<div class="box"><b>Déjà résolu dans ce Round :</b> Android 1281 est réparti sur <code>CA:32C5</code> + <code>CA:32D7</code> et appartient entièrement à <code>PLAYER_NAME(2)</code>. Le stock <code>PLAYER_NAME(1)</code> devant <code>CA:32C5</code> est rebindi en 2 et le second <code>PLAYER_NAME(2)</code> redondant est omis. Android 1280 (« Quelle horreur ! C'est terrible ! ») est volontairement omis conformément à ta redistribution.</div>
<div class="box"><b>Reste à organiser :</b><ul><li><code>CA:3335 + CA:3359</code> ↔ Android 1285, séparés par WAIT/TEXT_CLEAR/actions.</li><li><code>CA:3362</code> ↔ Android 1286.</li><li><code>CA:33E4</code> ↔ Android 1288 + 1289, avec un <code>PLAYER_NAME(2)</code> ajouté par Android FR dans 1289.</li><li><code>CA:3423</code> ↔ Android 1290 + 1291.</li></ul></div>
<h2>1. Séquence Android complète</h2><table><thead><tr><th>ID</th><th>État</th><th>Android EN</th><th>Android FR officiel</th></tr></thead><tbody>{''.join(android_rows)}</tbody></table>
<h2>2. Structure SNES $04E2 actuelle</h2><p class="lead">Les commandes de contrôle utiles sont montrées entre les carriers. « STOCK » signifie que le carrier reste volontairement en anglais pour l'instant.</p><table><thead><tr><th>#</th><th>Carrier / commande</th><th>État</th><th>SNES USA</th><th>Payload FR actuel</th></tr></thead><tbody>{''.join(token_rows)}</tbody></table>
</body></html>"""

def main() -> None:
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(render(),encoding="utf-8")
    print(f"Generated {OUT.relative_to(ROOT)}")

if __name__ == "__main__": main()
