#!/usr/bin/env python3
"""CLI facade for Android-derived Secret of Mana text generation.

Dialogue generation internals live in ``shared.dialogue.pipeline``.  This module intentionally
keeps the historical command line entry point stable while exposing only the active
intro/alignment/mass-generation workflows.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shared.text.intro_event import load_document as load_intro_source  # noqa: E402
from shared.dialogue.pipeline.common import (  # noqa: E402
    DEFAULT_SCRTXT_EN, DEFAULT_SCRTXT_FR, DIALOGUE_SOURCE,
    read_scrtxt, normalize_android_prose,
)
from shared.dialogue.pipeline.alignment import make_dialogue_auto_alignment, is_semantic_text  # noqa: E402
from shared.dialogue.pipeline.formatter import make_dialogue_format_mass  # noqa: E402

DEFAULT_INTRO_OUTPUT = ROOT / "translations" / "intro_event_french.json"


INTRO_ANDROID_IDS = tuple(range(3445, 3453))
INTRO_TARGET_IDS = (
    "CA:0C0D",
    "CA:0C59",
    "CA:0CB3",
    "CA:0D0C",
    "CA:0D5C",
    "CA:0DAB",
    "CA:0DFF",
    "CA:0E21",
)


# ---- Android text decoding and structural recipe rendering -----------------


def make_intro_translation(scrtxt: dict[int, str]) -> dict:
    source = load_intro_source(ROOT / "assets" / "intro_event.json")
    source_ids = tuple(entry["id"] for entry in source["entries"])
    if source_ids != INTRO_TARGET_IDS:
        raise ValueError(
            "assets/intro_event.json IDs/order no longer match the validated Android intro mapping"
        )

    missing = [text_id for text_id in INTRO_ANDROID_IDS if text_id not in scrtxt]
    if missing:
        raise ValueError("Missing Android intro text ID(s): " + ", ".join(map(str, missing)))

    entries = [
        {
            "id": target_id,
            "text": normalize_android_prose(scrtxt[android_id]),
        }
        for android_id, target_id in zip(INTRO_ANDROID_IDS, INTRO_TARGET_IDS, strict=True)
    ]
    return {
        "format_version": 1,
        "language": "fr",
        "source_asset": "intro_event.json",
        "groups": [
            {
                "group": "intro.event_0400",
                "entries": entries,
            }
        ],
    }


# ---- Conservative whole-dialogue Android alignment -------------------------

DEFAULT_DIALOGUE_AUTO_OUTPUT = ROOT / "reports" / "android" / "dialogues_auto.json"
DEFAULT_DIALOGUE_UNMAPPED_CSV = ROOT / "reports" / "android" / "dialogues_unmapped.csv"
DEFAULT_DIALOGUE_FORMAT_MASS_OUTPUT = ROOT / "translations" / "dialogues_french.json"
DEFAULT_DIALOGUE_FORMAT_MASS_REPORT = ROOT / "reports" / "android" / "dialogues_format_mass.json"
DEFAULT_DIALOGUE_FORMAT_MASS_EXCLUDED_CSV = ROOT / "reports" / "android" / "dialogues_format_mass_excluded.csv"
# These two stress-test sources were explicitly reviewed and have no confident
# standalone Android-English equivalent. Automatic passes must never force them.

# A stronger omission proof: an already accepted neighboring mapping explicitly
# documents that Android EN drops this standalone SNES fragment rather than
# translating/resegmenting it elsewhere.  Keep the carrier unmapped, but this
# status may admit a conservative PARTIEL event around it.

# Round 57 compares the reviewed Android omissions against the original
# Japanese SNES ROM supplied by the user. This is provenance/serialization
# evidence only; it never creates Android identity.


# These semantic carriers are real stock prose fragments, but they are shared
# subroutine templates whose Android identity is determined by the numeric
# caller.  No single Android scrtxt record owns them independently: executions
# correspond to the reviewed per-price prompt family (110/229/502/1365/1907/
# 1961/2319/2498, with equivalent duplicates).  Keep them unresolved in the
# 1798/1838 one-carrier identity count while recording that this is deliberate,
# not an unreviewed lexical hole.

# Reviewed structural corrections that intentionally replace an automatic
# lexical choice. The generic calibration guard remains active for every other
# reviewed source ID.

# The pilot proved that these duplicated Android locations carry equivalent
# English/French content even though provenance cannot select one copy. Keep the
# alternatives explicit instead of inventing a single Android ID.

# These events were explicitly reviewed by the user as visually complete even
# though the Android adaptation intentionally omits some stock SNES semantic
# fragments. Keep their exact simulator-clean French-only bytes, but do not
# count them as PARTIEL in the preview/report. Alignment may later prove an
# identity for an omitted source fragment; that new identity must not silently
# change the already runtime-validated translated serialization.

# User-approved Android omissions that are safe to suppress locally even though
# the containing event remains PARTIEL for unrelated mapped/layout-deferred
# carriers.  These IDs do not make the whole event visually complete.
# Round 69: after scene-level semantic review, the following former PARTIEL
# events are considered fully translated/complete. They remain traceable below
# through user_validated_visually_complete_events, preserving whether completion
# came from a manual supplement, a shared-prefix resegmentation, or a validated
# SNES/JP-absent suppression.

# These events remain semantically alignment-incomplete and keep their exact
# mixed/stock serialization, but runtime review confirmed that no missing or
# English content is visibly exposed to the player. They therefore remain
# traceable as unresolved alignment without carrying the PARTIEL badge.

# $01DC has one Android-adaptation omission that includes a structural speaker
# carrier, not just semantic text. The user explicitly validated dropping the
# final stock PLAYER_NAME(0) together with C9:804A because Android 729 begins
# the following Niccolo scene directly after Android 728. The source asset stays
# canonical; this exact command is omitted only in translated serialization.


# Round 67: Android FR $04E2 assigns the complete reaction to PLAYER_NAME(2),
# while stock SNES splits the same region between PLAYER_NAME(1) and
# PLAYER_NAME(2). The user explicitly approved redistributing Android 1281 over
# CA:32C5/CA:32D7. Keep the canonical source untouched; translated serialization
# changes only the first adjacent PLAYER_NAME index and omits the now-redundant
# second identical speaker command.


# $0331 remains semantically PARTIEL because the generic inn prompt carrier
# C9:CEB3 has no single proven Android identity. Suppressing its visible stock
# English must nevertheless preserve its two stock NEWLINEs: runtime testing
# proved that the choice row must stay on its original third physical line for
# the stock selection/highlight geometry to target the rendered Oui/Non row.
# This is layout-only metadata, never localized prose.

# Reviewed PARTIEL-only layout deferrals. These do not weaken Android-English
# identity: the listed mapping remains accepted, but its stock SNES carrier is
# deliberately left untranslated because official Android French cannot be
# serialized without changing the canonical PLAYER_NAME/text ownership. The
# event remains visibly PARTIEL/TO REVIEW, and admission still requires a clean
# independent simulation.

# Generic structural safe-subset PARTIEL is deliberately disabled for the two
# alignment-incomplete scenes whose handoff already records a semantic/resegmentation
# hazard. Their problem is not merely layout, so leaving a few mapped carriers stock
# would give a misleadingly usable mixed scene.


# Manual supplements never create Android identity. Most are exact SNES carriers
# whose complete absence from Android was explicitly reviewed; Round 62 also
# allows one exact already-mapped carrier as a provenance-rich layout-review
# surcharge. Pending entries always keep the stock USA payload active.

# Round 64 stages the remaining user-facing "NON TROUVÉ — PAS D’ÉQUIVALENT
# UNIQUE" carriers in the same provenance-rich manual-review schema. These
# entries never create Android identity. Round 65 explicitly approves four of
# the five JP-led proposals; Round 66 explicitly approves the final $0204
# carrier too, while preserving the event's broader resegmentation block.

# $04E8 already needed an ordinary PARTIEL layout repair before its unresolved
# stock carrier was manually approved. Apply that one validated manual carrier
# only *after* the existing mixed-event repair pipeline has succeeded, then
# re-simulate. This exact deferral prevents the new approval from disabling or
# replacing unrelated, already-proven PARTIEL formatting repairs.

# Round 66: $0204 remains deliberately blocked from the generic PARTIEL
# formatter because its Android-FR material is semantically resegmented and
# two mapped carriers still cross unsupported PLAYER_NAME ownership. The user
# nevertheless approved the exact JP-led manual carrier C9:902F. Admit only
# that carrier on top of the otherwise stock USA event, then require a clean
# whole-event simulation. Do not use this as permission to release any of the
# other $0204 Android mappings.

# Round 62 also uses the same provenance-rich review schema for one already
# identified Android carrier whose official French cannot be serialized through
# the canonical USA WAIT split. This is a review surcharge, not an Android
# omission. Round 63 subsequently validated suppressing the standalone page.

# Exact unresolved shared-prefix redistributions. These preserve Android identity
# honesty: no Android ID is assigned, but a redundant SNES-English prefix may be
# reduced to layout-only bytes when every already-proven Android destination owns
# the localized subject itself. The event remains PARTIEL/alignment-unresolved.

# Exact payload exceptions where Android English identity is accepted but the
# user has explicitly rejected the corresponding Android French localization.
# Keep this allow-list exact: this is not a generic preference for stock English.

# Every alignment-incomplete event is reconsidered on each mass pass. Accepted
# mappings are rendered in French while unresolved semantic carriers remain
# untouched, so their stock SNES English stays visible in-game. The event is
# admitted only when that mixed FR/EN serialization is simulator-clean and is
# always marked PARTIEL. User-validated visually complete adaptations keep their
# separate frozen-omission policy.


# User-validated alignment identities are data, not executable round-specific code.


# WAIT $00 rolling-window cleanup is presentation-sensitive.  Keep automatic
# repairs restricted to the checkpoint that predates the round-8 partial-block
# review; newly exposed overlaps must be reviewed explicitly before changing
# stock persistence semantics.
# Do not rewrite stock WAIT $00 presentation automatically.  Exact visible
# carry-over after an interactive WAIT is a legitimate rolling-window state,
# not proof of duplicated dialogue.  Any future presentation change must be
# reviewed and implemented explicitly for that event.


# Runtime-validated WAIT semantics: WAIT pauses without advancing the text
# cursor.  Earlier formatter/simulator revisions implicitly treated WAIT as a
# line terminator, so a small set of already-formatted scenes relied on a line
# break that was never serialized.  Materialize those intended boundaries as
# explicit dialogue NEWLINE bytes ($7F) while leaving every WAIT command intact.
#
# These are layout-only repairs: no Android/SNES semantic mapping is changed.
# ``prepend`` places NEWLINE at the start of the following text carrier;
# ``append`` places it at the end of the preceding carrier when the following
# visible object is PLAYER_NAME and there is no text carrier before it.


# Exact Android-FR-only vocatives reviewed as localization embellishments.
# The allow-list stores only structural identities and a removal policy; the
# localized sentence itself is always derived from the current Android FR slot.


# Round 49 exact formatter-only recoveries. These do not change Android-English
# identity and are intentionally event-specific: one Android-FR-only speaker
# label can be removed where the SNES event has no PLAYER_NAME command at all,
# and one three-part machine-noise line can be distributed across its exact
# stock PLAY_SOUND/WAIT bridge without moving or inventing commands.


# Round 54 exact recoveries from already-proven Android identities. These are
# event-specific serialization rules only; no generic matcher/formatter is widened.


def dialogue_format_mass_excluded_csv(report: dict, source_document: dict) -> str:
    """Render one row per semantic source phrase in an event excluded from mass output."""
    import csv
    import io

    by_event = {event["event_id"]: event for event in source_document["events"]}
    output = io.StringIO(newline="")
    fields = [
        "event_id",
        "stage",
        "snes_id",
        "texte_source_snes_usa",
        "est_non_mappe_alignement",
        "raison_evenement_exclu",
        "commentaire_utilisateur",
    ]
    writer = csv.DictWriter(output, fieldnames=fields, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writeheader()
    for excluded in report.get("excluded_events", []):
        event_id = excluded["event_id"]
        event = by_event[event_id]
        missing = set(excluded.get("missing_semantic_ids", []))
        detail_messages: list[str] = []
        for detail in excluded.get("details", []):
            if "message" in detail:
                prefix = detail.get("code") or "+".join(detail.get("snes_ids", []))
                detail_messages.append(f"{prefix}: {detail['message']}" if prefix else detail["message"])
            elif "reason" in detail:
                text_id = detail.get("snes_id", "")
                detail_messages.append(f"{text_id}: {detail['reason']}")
        reason = " | ".join(detail_messages)
        semantic = [
            token
            for token in event["tokens"]
            if token.get("type") == "text" and is_semantic_text(token.get("source", ""))
        ]
        for token in semantic:
            writer.writerow(
                {
                    "event_id": event_id,
                    "stage": excluded["stage"],
                    "snes_id": token["id"],
                    "texte_source_snes_usa": token["source"].replace("\r", "").replace("\n", " ⏎ ").strip(),
                    "est_non_mappe_alignement": "oui" if token["id"] in missing else "non",
                    "raison_evenement_exclu": reason,
                    "commentaire_utilisateur": "",
                }
            )
    return output.getvalue()


def dialogue_unmapped_csv(document: dict) -> str:
    """Render the automatic alignment's unresolved semantic source phrases."""
    import csv
    import io

    output = io.StringIO(newline="")
    fieldnames = [
        "event_id",
        "snes_id",
        "texte_source_snes_usa",
        "raison",
        "note",
        "meilleur_id_android_anglais",
        "meilleur_texte_anglais_android",
        "meilleur_score_lexical",
        "meilleure_couverture_source",
        "meilleur_texte_francais_candidat",
        "deuxieme_id_android_anglais",
        "deuxieme_score_lexical",
        "commentaire_utilisateur",
    ]
    writer = csv.DictWriter(
        output,
        fieldnames=fieldnames,
        delimiter=";",
        quoting=csv.QUOTE_MINIMAL,
        lineterminator="\n",
    )
    writer.writeheader()
    for entry in document["unmapped"]:
        candidates = entry.get("top_candidates", [])
        first = candidates[0] if candidates else {}
        second = candidates[1] if len(candidates) > 1 else {}
        writer.writerow(
            {
                "event_id": entry["event_id"],
                "snes_id": entry["snes_id"],
                "texte_source_snes_usa": entry["source"].replace("\r", "").replace("\n", " ⏎ ").strip(),
                "raison": entry["reason"],
                "note": entry["note"],
                "meilleur_id_android_anglais": first.get("android_id", ""),
                "meilleur_texte_anglais_android": first.get("android_english", "").replace("\r", "").replace("\n", " ⏎ ").strip(),
                "meilleur_score_lexical": first.get("lexical_score", ""),
                "meilleure_couverture_source": first.get("source_token_coverage", ""),
                "meilleur_texte_francais_candidat": first.get("french_display", "").replace("\r", "").replace("\n", " ⏎ ").strip(),
                "deuxieme_id_android_anglais": second.get("android_id", ""),
                "deuxieme_score_lexical": second.get("lexical_score", ""),
                "commentaire_utilisateur": "",
            }
        )
    # UTF-8 BOM is added when the caller writes bytes/text to disk.
    return output.getvalue()


def serialized(document: dict) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def write_or_check(output: Path, text: str, *, check: bool, source_label: str) -> None:
    if check:
        try:
            existing = output.read_text(encoding="utf-8")
        except OSError as exc:
            raise SystemExit(f"Cannot read {output}: {exc}") from exc
        if existing != text:
            raise SystemExit(f"{output} is not up to date with {source_label}")
        print(f"Android import/alignment check OK: {output}")
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    print(f"Generated {output} from {source_label}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--only",
        choices=("intro", "dialogue-auto", "dialogue-format-mass"),
        default="intro",
        help=(
            "generate the intro translation, the canonical dialogue alignment, "
            "or the complete simulator-validated dialogue translation"
        ),
    )
    parser.add_argument(
        "--scrtxt",
        type=Path,
        default=DEFAULT_SCRTXT_FR,
        help="Android French scrtxt binary",
    )
    parser.add_argument(
        "--scrtxt-en",
        type=Path,
        default=DEFAULT_SCRTXT_EN,
        help="Android English scrtxt binary (required for dialogue generation)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="destination JSON; defaults depend on --only",
    )
    parser.add_argument(
        "--unmapped-csv",
        type=Path,
        help="dialogue-auto unresolved CSV destination (default: reports/android/dialogues_unmapped.csv)",
    )
    parser.add_argument(
        "--rom",
        type=Path,
        help="clean unheadered USA ROM; required for dialogue-format-mass VWF metrics",
    )
    parser.add_argument(
        "--format-report",
        type=Path,
        help="dialogue-format-mass report destination",
    )
    parser.add_argument(
        "--excluded-csv",
        type=Path,
        help="dialogue-format-mass exclusion CSV destination",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify that the destination already equals generated output",
    )
    args = parser.parse_args()

    french_path = args.scrtxt.resolve()
    try:
        french = read_scrtxt(french_path)
        if args.only == "intro":
            document = make_intro_translation(french)
            output = (args.output or DEFAULT_INTRO_OUTPUT).resolve()
            source_label = str(french_path)
            format_report = None
        else:
            english_path = args.scrtxt_en.resolve()
            english = read_scrtxt(english_path)
            source_label = f"{english_path} + {french_path} + assets/dialogues.json"
            if args.only == "dialogue-auto":
                document = make_dialogue_auto_alignment(
                    english,
                    french,
                    english_path=english_path,
                    french_path=french_path,
                )
                output = (args.output or DEFAULT_DIALOGUE_AUTO_OUTPUT).resolve()
                format_report = None
            else:
                if args.rom is None:
                    raise ValueError("--rom is required for dialogue-format-mass")
                base_rom = args.rom.resolve().read_bytes()
                document, format_report = make_dialogue_format_mass(
                    english,
                    french,
                    english_path=english_path,
                    french_path=french_path,
                    base_rom=base_rom,
                )
                output = (args.output or DEFAULT_DIALOGUE_FORMAT_MASS_OUTPUT).resolve()
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc

    write_or_check(output, serialized(document), check=args.check, source_label=source_label)

    if args.only == "dialogue-auto":
        csv_output = (args.unmapped_csv or DEFAULT_DIALOGUE_UNMAPPED_CSV).resolve()
        csv_bytes = ("\ufeff" + dialogue_unmapped_csv(document)).encode("utf-8")
        if args.check:
            try:
                existing_csv = csv_output.read_bytes()
            except OSError as exc:
                raise SystemExit(f"Cannot read {csv_output}: {exc}") from exc
            if existing_csv != csv_bytes:
                raise SystemExit(f"{csv_output} is not up to date with automatic dialogue alignment")
            print(f"Android alignment CSV check OK: {csv_output}")
        else:
            csv_output.parent.mkdir(parents=True, exist_ok=True)
            csv_output.write_bytes(csv_bytes)
            print(f"Generated {csv_output} from automatic dialogue alignment")

    if args.only == "dialogue-format-mass":
        assert format_report is not None
        report_output = (args.format_report or DEFAULT_DIALOGUE_FORMAT_MASS_REPORT).resolve()
        write_or_check(
            report_output,
            serialized(format_report),
            check=args.check,
            source_label=source_label + " + clean USA ROM VWF metrics",
        )
        excluded_csv_output = (args.excluded_csv or DEFAULT_DIALOGUE_FORMAT_MASS_EXCLUDED_CSV).resolve()
        source_document = json.loads(DIALOGUE_SOURCE.read_text(encoding="utf-8"))
        excluded_csv_bytes = (
            "\ufeff" + dialogue_format_mass_excluded_csv(format_report, source_document)
        ).encode("utf-8")
        if args.check:
            try:
                existing_csv = excluded_csv_output.read_bytes()
            except OSError as exc:
                raise SystemExit(f"Cannot read {excluded_csv_output}: {exc}") from exc
            if existing_csv != excluded_csv_bytes:
                raise SystemExit(f"{excluded_csv_output} is not up to date with mass dialogue formatting")
            print(f"Dialogue mass exclusion CSV check OK: {excluded_csv_output}")
        else:
            excluded_csv_output.parent.mkdir(parents=True, exist_ok=True)
            excluded_csv_output.write_bytes(excluded_csv_bytes)
            print(f"Generated {excluded_csv_output} from mass dialogue formatting")

    if not args.check:
        if args.only == "intro":
            print(f"Imported {len(INTRO_ANDROID_IDS)} validated intro entries")
        elif args.only == "dialogue-auto":
            coverage = document["coverage"]
            print(
                "Dialogue automatic alignment: "
                f"{coverage['mapped_semantic_source_id_count']}/{coverage['semantic_source_id_count']} "
                f"semantic source IDs mapped ({coverage['mapped_semantic_percent']}%); "
                f"{coverage['unmapped_semantic_source_id_count']} unresolved; no translation JSON changed"
            )
        else:
            assert format_report is not None
            coverage = format_report["coverage"]
            print(
                "Dialogue format mass: "
                f"{coverage['accepted_event_count']} simulator-clean event(s), "
                f"{coverage['translation_entry_count']} translated source token(s); "
                f"{coverage['excluded_event_count']} event(s) excluded"
            )


if __name__ == "__main__":
    main()
