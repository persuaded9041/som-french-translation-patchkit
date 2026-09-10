#!/usr/bin/env python3
"""Lock the exact user-reviewed Round-62 dialogue redistributions and review surcharge."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRANSLATIONS = ROOT / "translations" / "dialogues_french.json"
MASS = ROOT / "mappings" / "android" / "dialogues_format_mass.json"
SUPPLEMENTS = ROOT / "translations" / "dialogues_manual_supplements.json"

EXPECTED_TRANSLATIONS = {
    "C9:DAF5": "Scorpion : Quoi ! Encore vous ?\n",
    "C9:DB09": "Et toi, imbécile, tu ne les as pas\nreconnus ?! Sbire : Désolé, chef...",
    "C9:F04C": "♪ Mon cœur, mon amour (la la la),\fma gorge se noue quand je te vois\n(la la la),\f",
    "C9:F07D": "et tout bouillonne dans ma tête... ♪",
    "CA:31EE": " : Papy !\f",
    "CA:3218": "Cette voix... C'est toi, mon petit ?",
    "CA:36C7": "Truffaut : Vous voilà enfin !\nLes héros de la légende !\fNous vous attendions !\f",
    "CA:36F6": " : Pardon ?",
}


def load_translation_map() -> dict[str, str]:
    doc = json.loads(TRANSLATIONS.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for group in doc["groups"]:
        for entry in group["entries"]:
            out[entry["id"]] = entry["text"]
    return out


def main() -> int:
    translations = load_translation_map()
    for text_id, expected in EXPECTED_TRANSLATIONS.items():
        actual = translations.get(text_id)
        if actual != expected:
            raise SystemExit(
                f"Round-62 translation drift for {text_id}: {actual!r} != {expected!r}"
            )

    mass = json.loads(MASS.read_text(encoding="utf-8"))
    partial_by_event = {item["event_id"]: item for item in mass["partial_accepted_events"]}
    for resolved in ("038D", "03EA", "04E3"):
        if resolved in partial_by_event:
            raise SystemExit(f"Round-62 resolved event ${resolved} unexpectedly remains PARTIEL")

    e04e2 = partial_by_event.get("04E2")
    if not e04e2:
        raise SystemExit("Round-62 event $04E2 must remain PARTIEL")
    deferred = set(e04e2.get("layout_deferred_semantic_ids", []))
    if {"CA:31EE", "CA:3218"} & deferred:
        raise SystemExit("Round-62 recovered $04E2 carriers became deferred again")

    # Round 62 still observed $013A/C9:40D7 as a visible Android-FR omission.
    # Round 67 legitimately supersedes that mutable state after direct SNES-JP review
    # and explicit user approval of a local suppression. Keep this historical checker
    # focused on the eight Round-62 redistribution payloads above.

    # Round 62 introduced $04E1/CA:2C84 as a pending review surcharge.
    # Round 63 may legitimately supersede that mutable current status after user review;
    # this historical checker only keeps the Round-62 redistribution payload locked.

    supplements = json.loads(SUPPLEMENTS.read_text(encoding="utf-8"))
    entries = supplements["entries"]
    target = next((e for e in entries if e["event_id"] == "04E1" and e["id"] == "CA:2C84"), None)
    if target is None:
        raise SystemExit("Missing Round-62 $04E1/CA:2C84 supplement")
    expected_fields = {
        "original_en": " It is time!",
        "original_fr": "Le moment est venu !",
        "translation_fr": "Le moment est venu !",
        "original_jp_event_id": "0070",
        "original_jp_carrier_id": "C9:1539",
    }
    for key, expected in expected_fields.items():
        if target.get(key) != expected:
            raise SystemExit(f"Round-62 supplement drift for {key}: {target.get(key)!r} != {expected!r}")

    print(
        "Round-62 targeted dialogue review verified: 8 redistributed translation entries, "
        "$038D/$03EA/$04E3 complete, $04E2 partial; later $013A/$04E1 review states may be superseded"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
