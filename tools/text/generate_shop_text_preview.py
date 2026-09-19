#!/usr/bin/env python3
"""Generate a compact review HTML for the French D9 shop/forge response family."""
from __future__ import annotations

import argparse
from html import escape
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shared.extracted.assets import load_or_extract_shop
from shared.text.android_strings import read_string_table
from shared.text.stock import encode_text_with_stock_dte
from shared.charset import DIALOGUE_DTE_THRESHOLD
from shared.text.translation_json import load_translation

DIRECT = ROOT / "translations" / "shop_text_french.json"
OVERRIDES = ROOT / "translations" / "shop_text_reviewed_overrides.json"
RECIPE = ROOT / "recipes" / "android" / "shop_text_mapping.json"
ASSET = ROOT / "assets" / "shop_text.json"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("rom", type=Path)
    ap.add_argument("-o", "--output", type=Path, required=True)
    args = ap.parse_args()

    rom = args.rom.read_bytes()
    source = load_or_extract_shop(rom, ASSET)
    direct = load_translation(DIRECT, source, source_asset="shop_text.json")
    override_doc = json.loads(OVERRIDES.read_text(encoding="utf-8"))
    overrides = {entry["id"]: entry for entry in override_doc["entries"]}
    recipe = json.loads(RECIPE.read_text(encoding="utf-8"))
    provenance = {record["snes_id"]: record for record in recipe["records"]}
    tables: dict[str, tuple[dict[int, str], dict[int, str]]] = {}

    rows = []
    for source_record in source["records"]:
        text_id = source_record["id"]
        meta = provenance[text_id]
        status = meta["status"]
        namespace = meta.get("android_namespace")
        ids = meta.get("android_ids", [])
        android_en = android_fr = "—"
        if namespace:
            if namespace not in tables:
                tables[namespace] = (
                    read_string_table(ROOT / "sources" / "android" / f"{namespace}_en.bin"),
                    read_string_table(ROOT / "sources" / "android" / f"{namespace}_fr.bin"),
                )
            en, fr = tables[namespace]
            android_en = " / ".join(en[value].strip() for value in ids)
            android_fr = " / ".join(fr[value].strip() for value in ids)
        final = direct.get(text_id) or overrides[text_id]["text"]
        encoded = encode_text_with_stock_dte(rom, final, upper_dte_threshold=DIALOGUE_DTE_THRESHOLD)
        label = {
            "direct": "Android FR directe",
            "adaptation_basis": "Adaptation SNES validée",
            "reviewed_without_android_equivalent": "Sans équivalent Android exact — validé",
        }[status]
        reason = overrides.get(text_id, {}).get("reason", "")
        rows.append((text_id, source_record["source"], namespace, ids, android_en, android_fr,
                     final, label, len(final), len(final) * 8, len(encoded), reason))

    body = []
    for row in rows:
        text_id, usa, namespace, ids, aen, afr, final, label, chars, px, enc, reason = row
        source_label = "—" if namespace is None else f"{namespace} " + ", ".join(map(str, ids))
        body.append(
            "<tr>"
            f"<td><code>{escape(text_id)}</code></td>"
            f"<td>{escape(usa)}</td>"
            f"<td>{escape(source_label)}<br><small>EN: {escape(aen)}<br>FR: {escape(afr)}</small></td>"
            f"<td><strong>{escape(final)}</strong><br><small>{escape(label)}</small></td>"
            f"<td>{chars}/28 caractères<br>{enc} octets DTE</td>"
            f"<td>{escape(reason) if reason else '—'}</td>"
            "</tr>"
        )

    html = f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><title>Secret of Mana FR — Shop / Forge</title>
<style>
body{{font-family:system-ui,sans-serif;margin:24px;background:#111;color:#eee}}
h1{{margin-bottom:6px}} p{{color:#bbb}} table{{border-collapse:collapse;width:100%;background:#181818}}
th,td{{border:1px solid #444;padding:9px;vertical-align:top;text-align:left}} th{{background:#282828}}
code{{color:#9dd}} small{{color:#bbb}} strong{{color:#fff}} .ok{{color:#9f9}}
</style></head><body>
<h1>Shop / Forge — lot validé</h1>
<p>Limite du parseur stock vérifiée par le builder : <strong>28 caractères visibles</strong>. Dans le build complet, ces lignes sont ensuite rendues en VWF par le tag Shop dédié <code>$A9</code>, sans augmenter la capacité du parseur. Le pool D9 est reconstruit avec DTE et reste dans son allocation stock.</p>
<table><thead><tr><th>ID source</th><th>USA</th><th>Android</th><th>Français retenu</th><th>Budget / encodage</th><th>Note</th></tr></thead>
<tbody>{''.join(body)}</tbody></table>
</body></html>"""
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")
    print(f"HTML: {args.output}")


if __name__ == "__main__":
    main()
