#!/usr/bin/env python3
"""Build deterministic Android-FR mappings for canonical SNES CA text resources.

This tool does not patch a ROM.  It binds Android ``systxt`` records to the
position-based IDs in ``assets/text_resources.json`` and emits:

* ``mappings/android/text_resources_android.json``: identity/provenance trace;
* ``translations/text_resources_french.json``: sparse French payload suitable
  for a future resource-reinsertion component;
* optional HTML review output.

Identity is deliberately conservative.  Reviewed ordered blocks may survive
English wording changes because their sequence is structural evidence.  Irregular
families use exact Android-English identity inside a bounded family; ambiguous or
missing entries remain unresolved rather than being guessed.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import html
import json
from pathlib import Path
import re
import struct
import unicodedata

ROOT = Path(__file__).resolve().parent.parent
SOURCE_ASSET = ROOT / "assets" / "text_resources.json"
LAYOUT = ROOT / "mappings" / "android" / "text_resources_layout.json"
SYSTXT_EN = ROOT / "sources" / "android" / "systxt_en.bin"
SYSTXT_FR = ROOT / "sources" / "android" / "systxt_fr.bin"
DEFAULT_MAPPING = ROOT / "mappings" / "android" / "text_resources_android.json"
DEFAULT_TRANSLATION = ROOT / "translations" / "text_resources_french.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_scrtxt(path: Path) -> dict[int, str]:
    data = path.read_bytes()
    if len(data) < 8:
        raise ValueError(f"{path}: file too small")
    count, pool_size = struct.unpack_from("<II", data, 0)
    table_end = 8 + count * 8
    if table_end + pool_size != len(data):
        raise ValueError(f"{path}: inconsistent scrtxt size")
    pool = data[table_end:]
    out: dict[int, str] = {}
    for index in range(count):
        text_id, offset = struct.unpack_from("<II", data, 8 + index * 8)
        if text_id in out or offset >= len(pool):
            raise ValueError(f"{path}: invalid table record {index}")
        end = pool.find(b"\0", offset)
        if end < 0:
            raise ValueError(f"{path}: unterminated text {text_id}")
        out[text_id] = pool[offset:end].decode("utf-8")
    return out


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace("’", "'").replace("#", "x")
    return re.sub(r"\s+", " ", text).strip().casefold()


def parse_hex(value: str) -> int:
    return int(value, 16)


def in_range(resource: dict, start: str, end: str) -> bool:
    rid = parse_hex(resource["resource_id"])
    return parse_hex(start) <= rid <= parse_hex(end)


def load_inputs():
    source = json.loads(SOURCE_ASSET.read_text(encoding="utf-8"))
    if source.get("format_version") != 2 or len(source.get("resources", [])) != 0x201:
        raise ValueError("assets/text_resources.json is not the canonical v2 513-resource asset")
    layout = json.loads(LAYOUT.read_text(encoding="utf-8"))
    if layout.get("format_version") != 1:
        raise ValueError("Unsupported text-resource Android layout format")
    en = read_scrtxt(SYSTXT_EN)
    fr = read_scrtxt(SYSTXT_FR)
    if set(en) != set(fr):
        raise ValueError("Android systxt EN/FR ID sets differ")
    return source, layout, en, fr


def build_mapping(source: dict, layout: dict, en: dict[int, str], fr: dict[int, str]) -> dict:
    resources = source["resources"]
    by_rid = {parse_hex(r["resource_id"]): r for r in resources}
    mapped: dict[int, dict] = {}

    for block in layout["ordered_blocks"]:
        s0, s1 = parse_hex(block["snes_start"]), parse_hex(block["snes_end"])
        a0, a1 = block["android_start"], block["android_end"]
        if s1 - s0 != a1 - a0:
            raise ValueError(f"Ordered block length mismatch for {block['category']}")
        for offset, rid in enumerate(range(s0, s1 + 1)):
            resource = by_rid[rid]
            if resource["category"] != block["category"]:
                raise ValueError(f"${rid:03X}: category mismatch in ordered recipe")
            aid = a0 + offset
            if aid not in en:
                raise ValueError(f"Android systxt ID {aid} missing")
            mapped[rid] = {
                "status": "mapped",
                "evidence": block["evidence"],
                "android_id": aid,
                "android_en": en[aid],
                "android_fr": fr[aid],
                "english_exact": norm(resource["source"]) == norm(en[aid]),
            }

    for family in layout["bounded_exact_families"]:
        subset = [r for r in resources if in_range(r, family["snes_start"], family["snes_end"])]
        candidates: dict[str, list[int]] = defaultdict(list)
        for aid in range(family["android_start"], family["android_end"] + 1):
            candidates[norm(en.get(aid, ""))].append(aid)
        ordered_dupes = {norm(x) for x in family.get("ordered_duplicate_names", [])}
        dupe_cursor: dict[str, int] = defaultdict(int)
        for resource in subset:
            rid = parse_hex(resource["resource_id"])
            key = norm(resource["source"])
            hits = candidates.get(key, []) if key else []
            if len(hits) == 1:
                aid = hits[0]
                mapped[rid] = {"status": "mapped", "evidence": family["evidence"], "android_id": aid,
                               "android_en": en[aid], "android_fr": fr[aid], "english_exact": True}
            elif len(hits) > 1 and key in ordered_dupes:
                idx = dupe_cursor[key]
                dupe_cursor[key] += 1
                if idx < len(hits):
                    aid = hits[idx]
                    mapped[rid] = {"status": "mapped", "evidence": "bounded_exact_ordered_duplicate",
                                   "android_id": aid, "android_en": en[aid], "android_fr": fr[aid],
                                   "english_exact": True, "candidate_android_ids": hits}
                else:
                    mapped[rid] = {"status": "unresolved", "reason": "more SNES duplicate occurrences than Android candidates", "candidate_android_ids": hits}
            elif len(hits) > 1:
                fr_values = {fr[x] for x in hits}
                if len(fr_values) == 1:
                    aid = hits[0]
                    mapped[rid] = {"status": "mapped", "evidence": "bounded_exact_duplicate_equivalent_french",
                                   "android_id": aid, "android_en": en[aid], "android_fr": fr[aid],
                                   "english_exact": True, "candidate_android_ids": hits}
                else:
                    mapped[rid] = {"status": "unresolved", "reason": "multiple exact Android-English candidates with different French payloads", "candidate_android_ids": hits}
            else:
                mapped[rid] = {"status": "unresolved", "reason": "no exact Android-English identity inside reviewed family"}

    excluded = layout.get("excluded_resource_ids", {})
    for resource in resources:
        rid = parse_hex(resource["resource_id"])
        if rid in mapped:
            continue
        reason = None
        for spec, why in excluded.items():
            if "-" in spec:
                lo, hi = map(parse_hex, spec.split("-", 1))
                if lo <= rid <= hi:
                    reason = why
                    break
            elif rid == parse_hex(spec):
                reason = why
                break
        mapped[rid] = {"status": "excluded" if reason else "unresolved", "reason": reason or "No reviewed Android identity recipe yet."}

    records = []
    for resource in resources:
        rid = parse_hex(resource["resource_id"])
        record = {
            "resource_id": resource["resource_id"],
            "snes_id": resource["id"],
            "category": resource["category"],
            "snes_en": resource["source"],
            **mapped[rid],
        }
        records.append(record)

    return {
        "format_version": 1,
        "source_asset": "assets/text_resources.json",
        "android_namespace": "systxt",
        "android_sources": {
            "en": {"path": "sources/android/systxt_en.bin", "sha256": sha256(SYSTXT_EN)},
            "fr": {"path": "sources/android/systxt_fr.bin", "sha256": sha256(SYSTXT_FR)},
        },
        "layout_recipe": "mappings/android/text_resources_layout.json",
        "records": records,
    }


def build_translation(mapping: dict) -> dict:
    groups: dict[str, list[dict]] = defaultdict(list)
    for record in mapping["records"]:
        if record["status"] != "mapped":
            continue
        text = record.get("android_fr")
        if not isinstance(text, str):
            continue
        # Android padding/newline sentinels represent blank stock resources; preserve
        # an actual empty payload rather than introducing U+3000 into the SNES asset.
        if not record["snes_en"] and not text.strip(" \t\r\n\u3000"):
            text = ""
        groups[record["category"]].append({"id": record["snes_id"], "text": text})
    return {
        "format_version": 1,
        "language": "fr",
        "source_asset": "text_resources.json",
        "generated_from": "sources/android/systxt_fr.bin",
        "mapping": "mappings/android/text_resources_android.json",
        "groups": [{"group": f"resources.{cat}", "entries": entries} for cat, entries in groups.items()],
    }


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
    ap.add_argument("--check", action="store_true", help="verify committed generated JSON files")
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
