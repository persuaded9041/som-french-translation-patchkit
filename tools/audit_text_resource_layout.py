#!/usr/bin/env python3
"""Audit Android-FR CA text resources before ROM insertion.

This tool is deliberately insertion-free.  It measures the generated French payload
against conservative envelopes observed in the clean USA ROM, checks editable charset
coverage, and performs an in-memory same-bank serialization dry run after deterministic
encoding-only normalization.

The observed stock envelopes are *not* claimed as proven UI hard limits.  They are
reported as conservative review thresholds until the corresponding renderer/menu
geometry is runtime-validated.
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared.text.stock import TEXT_TO_CODE, encode_text_with_stock_dte  # noqa: E402
from shared.text.resources import (  # noqa: E402
    FIRST_RESOURCE_POINTER,
    load_document,
    serialize_table_and_blob,
)
from shared.core.rom import validate_base_rom  # noqa: E402
from shared.text.resource_translation import normalize_for_snes  # noqa: E402

ASSET = ROOT / "assets" / "text_resources.json"
TRANSLATION = ROOT / "translations" / "text_resources_french.json"
DEFAULT_JSON = ROOT / "reports" / "android" / "text_resources_layout_audit.json"
DEFAULT_HTML = ROOT / "reports" / "android" / "text_resources_layout_audit.html"


def load_translations(path: Path) -> dict[str, str]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for group in doc.get("groups", []):
        for entry in group.get("entries", []):
            key = entry["id"]
            if key in out:
                raise ValueError(f"Duplicate translation ID: {key}")
            out[key] = entry["text"]
    return out


def line_metrics(text: str) -> tuple[int, int, list[int]]:
    lines = text.split("\n")
    lengths = [len(line) for line in lines]
    return max(lengths, default=0), len(lines), lengths


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("rom", type=Path, help="Clean unheadered USA ROM")
    ap.add_argument("--json", type=Path, default=DEFAULT_JSON)
    ap.add_argument("--html", type=Path, default=DEFAULT_HTML)
    ap.add_argument("--check", action="store_true", help="Verify existing generated reports")
    args = ap.parse_args()

    rom = args.rom.read_bytes()
    validate_base_rom(rom)
    source_doc = load_document(ASSET)
    translations = load_translations(TRANSLATION)

    stock_by_category: dict[str, list[dict]] = defaultdict(list)
    for resource in source_doc["resources"]:
        stock_by_category[resource["category"]].append(resource)

    envelopes: dict[str, dict] = {}
    for category, resources in stock_by_category.items():
        widths = []
        line_counts = []
        for r in resources:
            width, count, _ = line_metrics(r["source"])
            widths.append(width)
            line_counts.append(count)
        envelopes[category] = {
            "observed_stock_max_line_chars": max(widths, default=0),
            "observed_stock_max_lines": max(line_counts, default=0),
            "note": "observed stock envelope; not a proven renderer hard limit",
        }

    rows: list[dict] = []
    normalized_translations: dict[str, str] = {}
    status_counts = Counter()
    unsupported_chars = Counter()

    by_id = {r["id"]: r for r in source_doc["resources"]}
    for snes_id, text in translations.items():
        resource = by_id[snes_id]
        normalized, normalization_notes = normalize_for_snes(text)
        bad = sorted({
            ch for ch in normalized
            if ch != "\n" and (ch not in TEXT_TO_CODE or TEXT_TO_CODE[ch] >= 0xE6)
        })
        for ch in bad:
            unsupported_chars[ch] += normalized.count(ch)

        stock_width, stock_lines, _ = line_metrics(resource["source"])
        fr_width, fr_lines, fr_line_lengths = line_metrics(normalized)
        envelope = envelopes[resource["category"]]
        over_width = fr_width > envelope["observed_stock_max_line_chars"]
        over_lines = fr_lines > envelope["observed_stock_max_lines"]
        if bad:
            status = "encoding_blocked"
        elif over_width or over_lines:
            status = "geometry_review"
        else:
            status = "inside_stock_envelope"
        status_counts[status] += 1

        encoded_bytes = None
        if not bad:
            encoded_bytes = len(encode_text_with_stock_dte(rom, normalized, upper_dte_threshold=0xE6))
            normalized_translations[snes_id] = normalized

        rows.append(
            {
                "resource_id": resource["resource_id"],
                "snes_id": snes_id,
                "category": resource["category"],
                "stock_en": resource["source"],
                "android_fr": text,
                "normalized_fr": normalized,
                "normalization": normalization_notes,
                "stock_max_line_chars": stock_width,
                "fr_max_line_chars": fr_width,
                "fr_line_lengths": fr_line_lengths,
                "fr_lines": fr_lines,
                "category_stock_envelope_chars": envelope["observed_stock_max_line_chars"],
                "category_stock_envelope_lines": envelope["observed_stock_max_lines"],
                "encoded_bytes": encoded_bytes,
                "unsupported_chars": bad,
                "status": status,
            }
        )

    dry_run = {
        "possible_for_all_translations": not unsupported_chars,
        "profile_safe_translation_count": len(normalized_translations),
        "stock_blob_bytes": 7315,
        "translated_blob_bytes": None,
        "delta_bytes": None,
        "first_pointer": f"{FIRST_RESOURCE_POINTER:04X}",
        "end_pointer": None,
        "remaining_ca_bank_bytes": None,
    }
    table, blob = serialize_table_and_blob(
        rom, source_doc, translations=normalized_translations, compress_translations=True
    )
    end_pointer = FIRST_RESOURCE_POINTER + len(blob)
    dry_run.update(
        {
            "translated_blob_bytes": len(blob),
            "delta_bytes": len(blob) - 7315,
            "end_pointer": f"{end_pointer:04X}",
            "remaining_ca_bank_bytes": 0x10000 - end_pointer,
            "pointer_table_bytes": len(table),
        }
    )

    result = {
        "format_version": 1,
        "purpose": "pre-insertion geometry/encoding audit; no ROM writes",
        "source_asset": "assets/text_resources.json",
        "translation": "translations/text_resources_french.json",
        "stock_envelopes": envelopes,
        "summary": {
            "translated_entries": len(rows),
            **status_counts,
            "unsupported_character_kinds": len(unsupported_chars),
            "unsupported_characters": dict(unsupported_chars),
        },
        "same_bank_serialization_dry_run": dry_run,
        "records": rows,
    }

    json_text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"

    def e(v: object) -> str:
        return html.escape(str(v))

    categories = Counter(r["category"] for r in rows)
    cat_rows = []
    for cat in sorted(categories):
        subset = [r for r in rows if r["category"] == cat]
        env = envelopes[cat]
        inside = sum(r["status"] == "inside_stock_envelope" for r in subset)
        review = sum(r["status"] == "geometry_review" for r in subset)
        blocked = sum(r["status"] == "encoding_blocked" for r in subset)
        cat_rows.append(
            f"<tr><td>{e(cat)}</td><td>{len(subset)}</td>"
            f"<td>{env['observed_stock_max_line_chars']} chars / {env['observed_stock_max_lines']} line(s)</td>"
            f"<td>{inside}</td><td>{review}</td><td>{blocked}</td></tr>"
        )

    record_rows = []
    for r in rows:
        cls = r["status"]
        notes = ", ".join(r["normalization"]) or "—"
        bad = " ".join(repr(ch) for ch in r["unsupported_chars"]) or "—"
        record_rows.append(
            f'<tr class="{cls}"><td>${e(r["resource_id"])}<br><small>{e(r["snes_id"])}</small></td>'
            f'<td>{e(r["category"])}</td><td><pre>{e(r["stock_en"])}</pre></td>'
            f'<td><pre>{e(r["android_fr"])}</pre></td>'
            f'<td>{r["fr_max_line_chars"]} / {r["category_stock_envelope_chars"]}<br>'
            f'{r["fr_lines"]} / {r["category_stock_envelope_lines"]} line(s)</td>'
            f'<td>{e(r["status"])}</td><td>{e(notes)}</td><td>{e(bad)}</td></tr>'
        )

    dr = dry_run
    html_text = f"""<!doctype html><html lang=fr><head><meta charset=utf-8>
<title>Secret of Mana — audit géométrie ressources $CA</title>
<style>
body{{font:14px/1.45 system-ui,sans-serif;margin:24px;background:#f6f4ef;color:#222}}main{{max-width:1500px;margin:auto}}
h1,h2{{margin-bottom:.35em}}.notice{{padding:12px 14px;border:1px solid #d9c989;background:#fff8d7;border-radius:9px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin:16px 0}}.card{{background:white;border:1px solid #ddd5c8;border-radius:9px;padding:12px}}
.card b{{font-size:20px;display:block}}table{{border-collapse:collapse;width:100%;background:white}}th,td{{border:1px solid #ddd;padding:7px;vertical-align:top}}th{{background:#ebe7de;position:sticky;top:0}}
pre{{margin:0;white-space:pre-wrap;font:12px/1.3 ui-monospace,monospace}}.inside_stock_envelope{{background:#f0fbf3}}.geometry_review{{background:#fff7dd}}.encoding_blocked{{background:#fdebec}}small{{color:#666}}
</style></head><body><main>
<h1>Audit pré-insertion des ressources texte $CA</h1>
<p class=notice><b>Aucune ROM n'est modifiée.</b> Les seuils ci-dessous sont les maxima observés dans la ROM US, utilisés comme enveloppe conservatrice de review. Ils ne sont pas encore des limites d'affichage démontrées.</p>
<div class=cards>
<div class=card><b>{len(rows)}</b>traductions Android FR mappées</div>
<div class=card><b>{status_counts['inside_stock_envelope']}</b>dans l'enveloppe stock</div>
<div class=card><b>{status_counts['geometry_review']}</b>à revoir côté géométrie</div>
<div class=card><b>{status_counts['encoding_blocked']}</b>bloquées par l'encodage</div>
</div>
<h2>Sérialisation même banque — dry run</h2>
<p>Pour les traductions compatibles avec le profil direct/DTE actuel, après normalisation purement typographique (U+3000 → espace ; guillemets droits → “…”), le blob passerait de <b>{dr['stock_blob_bytes']}</b> à <b>{dr['translated_blob_bytes']}</b> octets ({dr['delta_bytes']:+d}). Fin théorique : <code>CA:{dr['end_pointer']}</code>, laissant <b>{dr['remaining_ca_bank_bytes']}</b> octets dans la banque. <b>Le stockage n'est donc pas le facteur limitant.</b></p>
<h2>Résumé par catégorie</h2><table><thead><tr><th>Catégorie</th><th>Trad.</th><th>Enveloppe US observée</th><th>OK enveloppe</th><th>Review géométrie</th><th>Encodage</th></tr></thead><tbody>{''.join(cat_rows)}</tbody></table>
<h2>Détail</h2><table><thead><tr><th>ID</th><th>Catégorie</th><th>SNES USA</th><th>Android FR</th><th>FR / enveloppe</th><th>Statut</th><th>Normalisation</th><th>Caractères non pris en charge</th></tr></thead><tbody>{''.join(record_rows)}</tbody></table>
</main></body></html>"""

    if args.check:
        if not args.json.exists() or args.json.read_text(encoding="utf-8") != json_text:
            raise SystemExit(f"Out of date: {args.json}")
        if not args.html.exists() or args.html.read_text(encoding="utf-8") != html_text:
            raise SystemExit(f"Out of date: {args.html}")
        print("Text-resource layout audit is reproducible.")
        return

    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.html.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json_text, encoding="utf-8")
    args.html.write_text(html_text, encoding="utf-8")
    print(
        f"Audit: {len(rows)} translated; {status_counts['inside_stock_envelope']} inside stock envelope; "
        f"{status_counts['geometry_review']} geometry review; {status_counts['encoding_blocked']} encoding-blocked"
    )
    print(
        f"Dry run: {dry_run['translated_blob_bytes']} bytes, end CA:{dry_run['end_pointer']}, "
        f"spare {dry_run['remaining_ca_bank_bytes']} bytes"
    )
    print(f"JSON -> {args.json}")
    print(f"HTML -> {args.html}")


if __name__ == "__main__":
    main()
