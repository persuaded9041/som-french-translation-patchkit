#!/usr/bin/env python3
"""Lock the Round-64 provenance records; later explicit approvals may advance status."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANUAL = ROOT / "translations" / "dialogues_manual_supplements.json"

EXPECTED = {
    "C9:2179": ("00EE", "「パンドーラ行き、しゅっぱーつ！", "Embarquement pour Pandore !\n", "Départ pour Pandora !"),
    "C9:2208": ("00F1", "「パンドーラ行き\n", "Pour Pandore !\n", "Pour Pandora !"),
    "C9:2268": ("00F3", "「氷の国！いってらっしゃい！\n", "Polaira ? D'accord. Salut !\n", "Pays de glace ! Bon voyage !"),
    "C9:902F": ("0204", "「これで世界のどこにおっても、\n　その聖剣には種子からのパワーが　とどくはずじゃ。", "Où que tu sois, tu pourras\nrecevoir le pouvoir de la\ngraine Mana.", "Où que tu sois, le pouvoir de la Graine atteindra ton Épée."),
    "CA:437D": ("04E8", "「ケケケケ！", "… Hiiiiiiii !", "Héhéhéhé !"),
}


def die(message: str) -> None:
    raise SystemExit(f"Round-64 provenance check failed: {message}")


def main() -> None:
    manual = json.loads(MANUAL.read_text(encoding="utf-8"))
    entries = {entry["id"]: entry for entry in manual["entries"]}
    for sid, (event_id, jp, fr, proposal) in EXPECTED.items():
        entry = entries.get(sid)
        if not entry:
            die(f"missing {sid}")
        expected_fields = {
            "event_id": event_id,
            "reason": "user_requested_unmapped_carrier_review",
            "original_jp": jp,
            "original_fr": fr,
            "translation_fr": proposal,
        }
        for key, value in expected_fields.items():
            if entry.get(key) != value:
                die(f"{sid} {key} drifted: {entry.get(key)!r} != {value!r}")
        if entry.get("status") not in {"needs_manual_translation", "translated"}:
            die(f"{sid} unexpected later status: {entry.get('status')!r}")
        if not entry.get("original_en"):
            die(f"{sid} lost canonical USA source")
    print("Round-64 provenance verified: 5 no-equivalent JP/USA/FR records preserved")


if __name__ == "__main__":
    main()
