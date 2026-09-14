from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SCRTXT_EN = ROOT / "sources" / "android" / "scrtxt_en.bin"
DEFAULT_SCRTXT_FR = ROOT / "sources" / "android" / "scrtxt_fr.bin"
DEFAULT_SYSTXT_EN = ROOT / "sources" / "android" / "systxt_en.bin"
DEFAULT_SYSTXT_FR = ROOT / "sources" / "android" / "systxt_fr.bin"
DIALOGUE_REVIEWED_ALIGNMENT_RECIPES = ROOT / "recipes" / "android" / "dialogues_reviewed_alignment.json"

from shared.dialogue.translation import normalize_android_french
from shared.text.android_strings import read_string_table

def _load_recipe_document(path: Path, *, label: str, expected: dict) -> dict:
    """Load a structural recipe document and validate its schema markers."""
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError(f"{label}: recipe root must be an object")
    for key, value in expected.items():
        if document.get(key) != value:
            raise ValueError(f"{label}: expected {key}={value!r}")
    return document


def _load_recipe_section(path: Path, section: str, *, label: str, expected: dict) -> dict:
    """Load one named section from a consolidated structural recipe document."""
    container = _load_recipe_document(
        path, label=f"{label} container", expected={"format_version": 1}
    )
    sections = container.get("sections")
    if not isinstance(sections, dict) or section not in sections:
        raise ValueError(f"{label}: missing recipe section {section!r}")
    document = sections[section]
    if not isinstance(document, dict):
        raise ValueError(f"{label}: section {section!r} must be an object")
    for key, value in expected.items():
        if document.get(key) != value:
            raise ValueError(f"{label}: expected {key}={value!r}")
    return document


def read_scrtxt(path: Path) -> dict[int, str]:
    """Read an Android scrtxt/systxt table."""
    return read_string_table(path)

def require_parallel_scrtxt(english: dict[int, str], french: dict[int, str]) -> None:
    """Require English/French containers to expose the same Android ID namespace."""
    if set(english) != set(french):
        missing_fr = sorted(set(english) - set(french))
        missing_en = sorted(set(french) - set(english))
        details = []
        if missing_fr:
            details.append("missing in French: " + ", ".join(map(str, missing_fr[:10])))
        if missing_en:
            details.append("missing in English: " + ", ".join(map(str, missing_en[:10])))
        raise ValueError("Android scrtxt ID sets differ (" + "; ".join(details) + ")")


def normalize_android_prose(text: str) -> str:
    """Remove source-layout whitespace while preserving the translated prose."""
    return " ".join(text.replace("\r", " ").replace("\n", " ").split())


@lru_cache(maxsize=None)
def normalize_alignment_text(text: str) -> str:
    """Normalize English text for cross-version comparison, not for translation output."""
    text = re.sub(r"%S\([^)]*\)", " playername ", text, flags=re.IGNORECASE)
    text = text.replace("_", " ")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.casefold()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def dialogue_text_entries(document: dict) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for event in document.get("events", []):
        event_id = event.get("event_id")
        for token_index, token in enumerate(event.get("tokens", [])):
            if token.get("type") != "text":
                continue
            text_id = token.get("id")
            source = token.get("source")
            if not isinstance(text_id, str) or not isinstance(source, str):
                raise ValueError(f"Malformed dialogue text token in event {event_id}")
            if text_id in result:
                raise ValueError(f"Duplicate dialogue text ID {text_id}")
            result[text_id] = {
                "event_id": event_id,
                "token_index": token_index,
                "source": source,
            }
    return result


def english_anchor_interval(anchor_id: int, english: dict[int, str]) -> list[int]:
    """Return an English non-empty ID plus following empty slots up to the next anchor."""
    if anchor_id not in english or not english[anchor_id]:
        raise ValueError(f"Android English ID {anchor_id} is not a non-empty anchor")
    ids = [anchor_id]
    next_id = anchor_id + 1
    while next_id in english and english[next_id] == "":
        ids.append(next_id)
        next_id += 1
    return ids


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_snes_review_parts(parts: tuple, source: dict[str, dict], *, event_id: str) -> tuple[list[str], str]:
    """Render canonical SNES source parts plus explicit dynamic-name placeholders."""
    snes_ids: list[str] = []
    chunks: list[str] = []
    for part in parts:
        if isinstance(part, str):
            if part not in source:
                raise ValueError(f"Dialogue review source ID {part} is absent from assets/dialogues.json")
            if source[part]["event_id"] != event_id:
                raise ValueError(
                    f"Dialogue review source ID {part} moved from event {event_id} "
                    f"to {source[part]['event_id']}"
                )
            snes_ids.append(part)
            chunks.append(source[part]["source"])
        elif (
            isinstance(part, tuple)
            and len(part) == 2
            and part[0] == "player_name"
            and isinstance(part[1], int)
        ):
            chunks.append(f"%S({part[1]},0)")
        else:
            raise ValueError(f"Unsupported dialogue review SNES part: {part!r}")
    return snes_ids, "".join(chunks)


def android_anchor_units(anchor_ids: tuple[int, ...], english: dict[int, str]) -> list[int]:
    """Expand one or more English anchors to include their localization slots."""
    result: list[int] = []
    for anchor_id in anchor_ids:
        for text_id in english_anchor_interval(anchor_id, english):
            if text_id not in result:
                result.append(text_id)
    return result




def sentence_break_positions(text: str) -> list[tuple[int, int]]:
    """Return complete-sentence boundary spans followed by layout whitespace."""
    out = []
    for match in re.finditer(r"(?:\.{3}|[.!?…]+)(?:[”\"»')\]]*)[ \t\r\n]+", text):
        out.append((match.start(), match.end()))
    return out
