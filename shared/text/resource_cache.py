"""Persistent local cache for generated French $CA text resources.

The cached translation JSON is an optimization only. Canonical provenance remains
in the clean USA ROM extraction, Android systxt EN/FR sources, the reviewed layout
recipe and generator code. A cache entry is reused only when its fingerprint and
payload hash both match.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TRANSLATION_CACHE = ROOT / "translations" / "text_resources_french.json"
DEFAULT_CACHE_META = ROOT / "build" / "cache" / "text_resources_french.meta.json"
CACHE_VERSION = 1


def _input_paths() -> list[Path]:
    from shared.text.android_resources import LAYOUT, SYSTXT_EN, SYSTXT_FR

    return [
        LAYOUT,
        SYSTXT_EN,
        SYSTXT_FR,
        ROOT / "shared" / "text" / "android_resources.py",
        ROOT / "shared" / "text" / "android_strings.py",
    ]


def fingerprint(base_rom: bytes, source_document: dict) -> str:
    digest = hashlib.sha256()
    digest.update(f"text-resources-french-cache-v{CACHE_VERSION}\0".encode())
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
        document = json.loads(payload.decode("utf-8"))
        if document.get("format_version") != 1 or document.get("language") != "fr":
            return None
        return document
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
