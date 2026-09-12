#!/usr/bin/env python3
"""Validate the minimal manual-dialogue supplement manifest."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shared.dialogue.codec import encode_translated_dialogue_text  # noqa: E402
from shared.extracted.assets import load_or_extract_dialogues  # noqa: E402
from shared.dialogue.pipeline.policies import (  # noqa: E402
    DIALOGUE_USER_REQUESTED_MAPPED_MANUAL_REVIEW_IDS,
    DIALOGUE_USER_REQUESTED_UNMAPPED_MANUAL_REVIEW_IDS,
    DIALOGUE_USER_VALIDATED_ANDROID_ABSENT_MANUAL_IDS,
)

MANUAL = ROOT / "translations" / "dialogues_manual_supplements.json"
SOURCE = ROOT / "assets" / "dialogues.json"
EXPECTED_IDS = {
    "C9:1057", "C9:2179", "C9:2208", "C9:2268", "C9:40D7",
    "C9:916F", "C9:9193", "C9:9F88", "C9:A730", "C9:A74E",
    "C9:C56C", "C9:CAA6", "C9:CAC2", "C9:CB0C", "C9:D1B8",
    "CA:2C84", "CA:437D",
}
SUPPRESSED_IDS = {"C9:40D7", "CA:2C84"}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rom", type=Path, help="clean unheadered USA ROM; required if the optional dialogue cache is absent")
    args = ap.parse_args()
    doc = json.loads(MANUAL.read_text(encoding="utf-8"))
    if set(doc) != {"format_version", "entries"} or doc.get("format_version") != 3:
        raise SystemExit("manual supplements must use minimal format v3")

    if args.rom is None and not SOURCE.exists():
        raise SystemExit("--rom is required when assets/dialogues.json is absent")
    rom = args.rom.resolve().read_bytes() if args.rom is not None else b""
    source = load_or_extract_dialogues(rom, SOURCE)
    by_id = {
        tok["id"]: {"event_id": ev["event_id"], "source": tok.get("source", "")}
        for ev in source["events"]
        for tok in ev.get("tokens", [])
        if tok.get("type") == "text" and tok.get("id")
    }
    entries = doc.get("entries", [])
    ids = [e.get("id") for e in entries if isinstance(e, dict)]
    if set(ids) != EXPECTED_IDS or len(ids) != len(EXPECTED_IDS):
        raise SystemExit(f"manual supplement set changed: {sorted(set(ids))}")
    if len(ids) != len(set(ids)):
        raise SystemExit("manual supplement IDs must be unique")

    allowed_by_event: dict[str, set[str]] = {}
    for allow_map in (
        DIALOGUE_USER_VALIDATED_ANDROID_ABSENT_MANUAL_IDS,
        DIALOGUE_USER_REQUESTED_UNMAPPED_MANUAL_REVIEW_IDS,
        DIALOGUE_USER_REQUESTED_MAPPED_MANUAL_REVIEW_IDS,
    ):
        for event_id, allowed in allow_map.items():
            allowed_by_event.setdefault(event_id, set()).update(allowed)

    for e in entries:
        if not isinstance(e, dict):
            raise SystemExit("manual supplement entries must be objects")
        if set(e) - {"id", "text", "suppress"}:
            raise SystemExit(f"{e.get('id')}: unexpected field(s) {sorted(set(e) - {'id', 'text', 'suppress'})}")
        text_id = e.get("id")
        meta = by_id.get(text_id)
        if meta is None:
            raise SystemExit(f"{text_id}: unknown source carrier")
        event_id = meta["event_id"]
        if text_id not in allowed_by_event.get(event_id, set()):
            raise SystemExit(f"${event_id}/{text_id}: carrier left the exact manual allow-list")
        suppress = e.get("suppress", False)
        if not isinstance(suppress, bool):
            raise SystemExit(f"{text_id}: suppress must be boolean")
        if suppress:
            if text_id not in SUPPRESSED_IDS or set(e) != {"id", "suppress"}:
                raise SystemExit(f"{text_id}: invalid validated suppression record")
        else:
            if set(e) != {"id", "text"} or not isinstance(e.get("text"), str) or not e["text"]:
                raise SystemExit(f"{text_id}: translated records must contain only id + non-empty text")
            try:
                encode_translated_dialogue_text(e["text"])
            except ValueError as exc:
                raise SystemExit(f"{text_id}: text is not dialogue-codec encodable: {exc}") from exc

    by_manual_id = {e["id"]: e for e in entries}
    if by_manual_id["C9:D1B8"] != {"id": "C9:D1B8", "text": "Dryade"}:
        raise SystemExit("$035F must remain the validated minimal Dryade surcharge")
    if by_manual_id["C9:40D7"] != {"id": "C9:40D7", "suppress": True}:
        raise SystemExit("$013A/C9:40D7 validated suppression changed")
    if by_manual_id["CA:2C84"] != {"id": "CA:2C84", "suppress": True}:
        raise SystemExit("$04E1/CA:2C84 validated suppression changed")
    print("Manual supplement schema verified: v3 minimal; 17 carriers; 15 translations + 2 suppressions")


if __name__ == "__main__":
    main()
