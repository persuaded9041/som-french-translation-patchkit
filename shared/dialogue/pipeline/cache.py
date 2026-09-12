"""Persistent local cache for the generated French dialogue document.

The cache is an optimization only. Canonical provenance remains the clean USA ROM,
Android EN/FR sources, reviewed recipes and manual supplements. A cache entry is
accepted only when its fingerprint matches all inputs that can affect formatter
output and the cached payload hash still matches the JSON on disk.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TRANSLATION_CACHE = ROOT / "translations" / "dialogues_french.json"
DEFAULT_CACHE_META = ROOT / "build" / "cache" / "dialogues_french.meta.json"
CACHE_VERSION = 1


def _input_paths() -> list[Path]:
    from shared.dialogue.pipeline.common import DEFAULT_SCRTXT_EN, DEFAULT_SCRTXT_FR

    paths = [
        DEFAULT_SCRTXT_EN,
        DEFAULT_SCRTXT_FR,
        ROOT / "translations" / "dialogues_manual_supplements.json",
    ]
    paths.extend(sorted((ROOT / "recipes" / "android").glob("dialogues_*.json")))
    for directory in (
        ROOT / "shared" / "dialogue",
        ROOT / "shared" / "vwf",
        ROOT / "shared" / "charset",
    ):
        paths.extend(
            sorted(
                path
                for path in directory.rglob("*")
                if path.is_file() and path.suffix in {".py", ".json"}
            )
        )
    return paths


def fingerprint(base_rom: bytes, source_document: dict) -> str:
    digest = hashlib.sha256()
    digest.update(f"dialogues-french-cache-v{CACHE_VERSION}\0".encode())
    digest.update(hashlib.sha256(base_rom).digest())
    source_bytes = json.dumps(
        source_document, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    digest.update(hashlib.sha256(source_bytes).digest())
    for path in _input_paths():
        digest.update(str(path.relative_to(ROOT)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(payload)
    tmp.replace(path)


def load(
    base_rom: bytes,
    source_document: dict,
    *,
    translation_path: Path = DEFAULT_TRANSLATION_CACHE,
    meta_path: Path = DEFAULT_CACHE_META,
) -> dict | None:
    if not translation_path.is_file() or not meta_path.is_file():
        return None
    expected_fingerprint = fingerprint(base_rom, source_document)
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        payload = translation_path.read_bytes()
        if meta.get("version") != CACHE_VERSION:
            return None
        if meta.get("fingerprint") != expected_fingerprint:
            return None
        if meta.get("payload_sha256") != hashlib.sha256(payload).hexdigest():
            return None
        return json.loads(payload.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def store(
    document: dict,
    base_rom: bytes,
    source_document: dict,
    *,
    translation_path: Path = DEFAULT_TRANSLATION_CACHE,
    meta_path: Path = DEFAULT_CACHE_META,
) -> None:
    payload = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    _atomic_write(translation_path, payload)
    meta = {
        "version": CACHE_VERSION,
        "fingerprint": fingerprint(base_rom, source_document),
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
    }
    _atomic_write(
        meta_path,
        (json.dumps(meta, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    )
