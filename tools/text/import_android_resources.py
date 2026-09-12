#!/usr/bin/env python3
"""Materialize/review deterministic Android-FR text-resource mappings.

The reusable mapping/translation generator lives in ``shared.text.android_resources``;
this module is intentionally only a CLI/reporting frontend.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import html
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shared.text.android_resources import (
    DEFAULT_MAPPING, DEFAULT_TRANSLATION, build_mapping, build_translation, load_inputs,
)

def render_html(mapping: dict) -> str:
    counts = defaultdict(int)
    for r in mapping["records"]:
        counts[r["status"]] += 1
    rows = []
    for r in mapping["records"]:
        if r["status"] == "excluded" and r["category"] == "unused":
            continue
        aid = r.get("android_id", "")
        note = r.get("evidence") or r.get("reason", "")
        rows.append("<tr>" + "".join([
            f"<td>{html.escape(r['resource_id'])}<br><small>{html.escape(r['snes_id'])}</small></td>",
            f"<td>{html.escape(r['category'])}</td>",
            f"<td>{html.escape(r['snes_en']).replace(chr(10), '<br>')}</td>",
            f"<td>{html.escape(str(aid))}</td>",
            f"<td>{html.escape(r.get('android_en','')).replace(chr(10), '<br>')}</td>",
            f"<td>{html.escape(r.get('android_fr','')).replace(chr(10), '<br>')}</td>",
            f"<td><b>{html.escape(r['status'])}</b><br><small>{html.escape(note)}</small></td>",
        ]) + "</tr>")
    return f"""<!doctype html><html lang=fr><meta charset=utf-8><title>Android FR → ressources SNES CA</title>
<style>body{{font:14px system-ui;margin:24px;background:#f6f5f2;color:#222}}table{{border-collapse:collapse;width:100%;background:white}}th,td{{border:1px solid #ddd;padding:7px;vertical-align:top}}th{{position:sticky;top:0;background:#eee}}small{{color:#666}}.stats{{display:flex;gap:12px;margin:12px 0 20px}}.stats span{{background:white;border:1px solid #ddd;border-radius:8px;padding:8px 12px}}</style>
<h1>Android FR → ressources texte SNES $CA</h1><p>Review générée sans modifier la ROM. Les destinations SNES sont les IDs/adresses canoniques de <code>assets/text_resources.json</code>.</p>
<div class=stats><span><b>{counts['mapped']}</b> mappées</span><span><b>{counts['unresolved']}</b> non résolues</span><span><b>{counts['excluded']}</b> exclues</span></div>
<table><thead><tr><th>Ressource SNES</th><th>Catégorie</th><th>SNES USA</th><th>ID Android</th><th>Android EN</th><th>Android FR</th><th>État / preuve</th></tr></thead><tbody>{''.join(rows)}</tbody></table></html>"""


def write_or_check(path: Path, content: str, check: bool) -> None:
    if check:
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            raise SystemExit(f"OUT OF DATE: {path.relative_to(ROOT)}")
        print(f"OK: {path.relative_to(ROOT)}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"Wrote {path.relative_to(ROOT)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="verify materialized generated JSON files")
    ap.add_argument("--html", type=Path, help="write a human-readable mapping review")
    args = ap.parse_args()
    source, layout, en, fr = load_inputs()
    mapping = build_mapping(source, layout, en, fr)
    translation = build_translation(mapping)
    mapping_text = json.dumps(mapping, ensure_ascii=False, indent=2) + "\n"
    translation_text = json.dumps(translation, ensure_ascii=False, indent=2) + "\n"
    write_or_check(DEFAULT_MAPPING, mapping_text, args.check)
    write_or_check(DEFAULT_TRANSLATION, translation_text, args.check)
    if args.html:
        args.html.parent.mkdir(parents=True, exist_ok=True)
        args.html.write_text(render_html(mapping), encoding="utf-8")
        print(f"Wrote {args.html}")
    status = defaultdict(int)
    cats = defaultdict(lambda: defaultdict(int))
    for r in mapping["records"]:
        status[r["status"]] += 1
        cats[r["category"]][r["status"]] += 1
    print("Summary:", dict(status))
    for cat in sorted(cats):
        print(f"  {cat}: {dict(cats[cat])}")


if __name__ == "__main__":
    main()
