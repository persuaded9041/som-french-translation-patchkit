#!/usr/bin/env python3
"""Validate the current manual-dialogue supplement review schema."""
from __future__ import annotations
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from shared.dialogue_codec import encode_translated_dialogue_text  # noqa: E402
MANUAL = ROOT / "translations" / "dialogues_manual_supplements.json"
SOURCE = ROOT / "assets" / "dialogues.json"
EXPECTED_IDS = {
    "C9:1057", "C9:2179", "C9:2208", "C9:2268", "C9:40D7",
    "C9:916F", "C9:9193", "C9:9F88", "C9:A730", "C9:A74E",
    "C9:C56C", "C9:CAA6", "C9:CAC2", "C9:CB0C", "C9:D1B8",
    "CA:2C84", "CA:437D",
}
PENDING_IDS = set()


def main() -> None:
    doc = json.loads(MANUAL.read_text(encoding="utf-8"))
    if doc.get("format_version") != 2 or doc.get("language") != "fr":
        raise SystemExit("manual supplements must be Round-58 format v2 / fr")
    refs = doc.get("reference_roms", {})
    if refs.get("snes_jp", {}).get("sha256") != "7fd1747eb4333f502d5fe6df7267342e4b4a399ab65b57f0a139e5f9fc02ab9d":
        raise SystemExit("SNES-JP provenance hash changed")
    if refs.get("snes_fr_rev1", {}).get("sha256") != "b730adcbb34a19f8fd1c2abe27455cc3256329a9b8a021291e3009ea33004127":
        raise SystemExit("SNES-FR Rev1 provenance hash changed")

    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    by_id = {
        tok["id"]: tok.get("source", "")
        for ev in source["events"]
        for tok in ev.get("tokens", [])
        if tok.get("type") == "text" and tok.get("id")
    }
    entries = doc.get("entries", [])
    ids = {e.get("id") for e in entries}
    if ids != EXPECTED_IDS or len(entries) != len(EXPECTED_IDS):
        raise SystemExit(f"manual supplement set changed: {sorted(ids)}")
    for e in entries:
        text_id = e["id"]
        for key in ("original_jp", "original_en", "original_fr", "translation_fr"):
            if key not in e:
                raise SystemExit(f"{text_id}: missing {key}")
        if e["original_en"] != by_id.get(text_id):
            raise SystemExit(f"{text_id}: original_en drifted from canonical source")
        if e["original_jp"] is not None and not isinstance(e["original_jp"], str):
            raise SystemExit(f"{text_id}: original_jp must be string/null")
        if not isinstance(e["original_fr"], str) or not e["original_fr"]:
            raise SystemExit(f"{text_id}: original_fr missing")
        if not isinstance(e["translation_fr"], str):
            raise SystemExit(f"{text_id}: translation_fr must be a string")
        is_empty_validated_suppression = (
            e.get("status") == "suppressed" and e["translation_fr"] == ""
        )
        if not e["translation_fr"] and not is_empty_validated_suppression:
            raise SystemExit(f"{text_id}: translation_fr proposal/reference missing")
        if e["translation_fr"]:
            try:
                encode_translated_dialogue_text(e["translation_fr"])
            except ValueError as exc:
                raise SystemExit(f"{text_id}: translation_fr is not dialogue-codec encodable: {exc}") from exc
        if e["status"] == "needs_manual_translation" and e["translation_fr"] == e["original_en"]:
            raise SystemExit(f"{text_id}: pending entry has no distinct French proposal")
        if e["status"] not in {"needs_manual_translation", "translated", "suppressed"}:
            raise SystemExit(f"{text_id}: invalid status")
    pending = [e for e in entries if e["status"] == "needs_manual_translation"]
    translated = [e for e in entries if e["status"] == "translated"]
    suppressed = [e for e in entries if e["status"] == "suppressed"]
    if (
        {e["id"] for e in pending} != PENDING_IDS
        or len(translated) != 15
        or {e["id"] for e in suppressed} != {"CA:2C84", "C9:40D7"}
    ):
        raise SystemExit("current manual supplement approval/suppression state changed")
    mapped_review = next(e for e in suppressed if e["id"] == "CA:2C84")
    if (
        mapped_review["event_id"] != "04E1"
        or mapped_review["reason"] != "user_validated_resegmented_snes_jp_suppression"
        or mapped_review["original_en"] != " It is time!"
        or mapped_review["original_fr"] != "Le moment est venu !"
        or mapped_review["translation_fr"] != "Le moment est venu !"
        or mapped_review["original_jp_event_id"] != "0070"
        or mapped_review["original_jp_carrier_id"] != "C9:1539"
        or "あたらしく生まれ変わった体" not in mapped_review["original_jp"]
    ):
        raise SystemExit("$04E1/CA:2C84 resegmented-page suppression changed")
    dryad = next(e for e in entries if e["id"] == "C9:D1B8")
    if (
        dryad["translation_fr"] != "Dryade"
        or dryad["original_jp"] != "ドリアード"
        or dryad["original_en"] != "Dryad"
        or dryad["status"] != "translated"
    ):
        raise SystemExit("$035F must remain the validated minimal Dryade surcharge")
    western = next(e for e in entries if e["id"] == "C9:40D7")
    if (
        western["event_id"] != "013A"
        or western["status"] != "suppressed"
        or western.get("reason") != "user_validated_snes_jp_absent_suppression"
        or western["translation_fr"] != ""
        or western["original_jp"] is not None
        or western.get("original_jp_status") != "no_distinct_snes_jp_counterpart_confirmed"
        or western.get("original_jp_context_carrier_id") != "C9:4F39"
        or "聖剣とともに使えば" not in western.get("original_jp_context", "")
        or "D'autres armes sont" not in western["original_fr"]
    ):
        raise SystemExit("$013A/C9:40D7 validated JP-absent suppression changed")
    print("Manual supplement schema verified: 17 carriers; 15 translated + 0 pending + 2 validated suppressions")

if __name__ == "__main__":
    main()
