#!/usr/bin/env python3
"""Validate locked dialogue decisions and current playable-dialogue coverage."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shared.dialogue.pipeline.alignment import make_dialogue_auto_alignment  # noqa: E402
from shared.dialogue.pipeline.common import DEFAULT_SCRTXT_EN, DEFAULT_SCRTXT_FR, read_scrtxt, normalize_android_prose  # noqa: E402
from shared.dialogue.pipeline.formatter import make_dialogue_format_mass  # noqa: E402
from shared.extracted.assets import load_or_extract_dialogues

MANUAL = ROOT / "translations/dialogues_manual_supplements.json"
RECIPES = ROOT / "recipes/android/dialogues_redistribution.json"
FORMATTING_RECIPES = ROOT / "recipes/android/dialogues_formatting.json"

ROUND69_EVENTS = {
    "010C", "015A", "01C5", "0204", "0205", "0227", "04E2", "04E5", "04E6",
    "04E9", "04FD", "0559", "0592", "05B4",
}
ORPHANS = {"0269": "C9:A49C", "02DE": "C9:C4FB", "0603": "CA:85FC"}


def die(msg: str) -> None:
    raise SystemExit(f"Dialogue regression check failed: {msg}")


def active_entries(document: dict) -> dict[str, str]:
    return {e["id"]: e["text"] for group in document.get("groups", []) for e in group.get("entries", [])}


def semantic_layout_normalized(text: str) -> str:
    return " ".join(text.replace("\n", " ").replace("\f", " ").replace("\v", " ").split())


def check_targeted_reviews(manual: dict, french: dict, mass: dict) -> None:
    entries = {e["id"]: e for e in manual["entries"]}
    c40d7 = entries.get("C9:40D7")
    if c40d7 != {"id": "C9:40D7", "suppress": True}:
        die("$013A/C9:40D7 validated suppression drifted")

    active = active_entries(french)
    if active.get("C9:40D7") != "":
        die("$013A/C9:40D7 must serialize as empty text")
    expected_omission = {
        "event_id": "013A",
        "suppressed_semantic_ids": ["C9:40D7"],
        "suppressed_commands": [{"name": "WAIT", "args": "00", "immediately_after_text_id": "C9:40D7"}],
        "reason": "round67_user_validated_snes_jp_absent_android_fr_adaptation_suppression",
    }
    omission = next((x for x in french.get("user_validated_structural_omissions", []) if x.get("event_id") == "013A"), None)
    if omission != expected_omission:
        die(f"$013A structural suppression drifted: {omission!r}")

    expected_04e1 = {
        "CA:2BED": "Mon corps actuel est sur le point de\nse corrompre.\nIl me faut un nouveau corps...",
        "CA:2C3A": "Un être humain ordinaire est incapable\nde contenir longtemps mon énergie.\fIl me faut donc le corps d'un être\nd'exception.\fOr, une ou deux fois par siècle, un\nhumain naît avec le Sang des ténèbres\ndans les veines.",
        "CA:2C84": "",
    }
    for sid, text in expected_04e1.items():
        if semantic_layout_normalized(active.get(sid, "")) != semantic_layout_normalized(text):
            die(f"$04E1 {sid} semantic payload drifted")

    # Round 85.66/85.67 validated coverage must be sourced from Android FR,
    # never frozen as localized prose in this regression.
    android_fr = read_scrtxt(DEFAULT_SCRTXT_FR)
    for sid, android_ids in {
        "CA:2C93": [3260, 3261],
        "CA:2DF2": [3278],
        "C9:DE89": [1897],
        "CA:3A05": [1373],
        "CA:5A7F": [1988],
    }.items():
        rendered = semantic_layout_normalized(active.get(sid, ""))
        for android_id in android_ids:
            expected = semantic_layout_normalized(normalize_android_prose(android_fr[android_id]).replace("_", "").strip())
            if expected not in rendered:
                die(f"Round-85 validated Android-FR coverage missing: {sid} <- {android_id}")

    expected_04e2 = {
        "CA:32C5": ": Quelle horreur !\nC'est terrible !",
        "CA:32D7": ": Non !\nC'est pas possible !\nIls se sont sûrement échappés !",
    }
    for sid, text in expected_04e2.items():
        if semantic_layout_normalized(active.get(sid, "")) != semantic_layout_normalized(text):
            die(f"$04E2 {sid} semantic payload drifted")

    if any(entry.get("event_id") == "04E2" for entry in french.get("user_validated_structural_command_overrides", [])):
        die("$04E2 must preserve both stock PLAYER_NAME commands after Android-FR 1280 restoration")

    # Round 85.54/85.55-v2 locked visual/speaker sentinels. These are exact
    # layout checks because the bugs were caused by rolling-window speaker
    # fragments rather than semantic mistranslation.
    if active.get("C9:6CDD") != "\vLutin : Bah, ma mémoire finira\nbien par revenir ! ":
        die("$01B9 first speaker carrier layout drifted")
    if active.get("C9:6D0D") != "Faut être\npositif dans la vie, hé hé hé !":
        die("$01B9 continuation carrier layout drifted")
    if active.get("C9:7D47") != " : Ah bon ?!\nComment ça ?":
        die("$01DA Android-FR player reply drifted")
    if active.get("C9:7E72") != ".\fHum... Drôle de nom.\nMoi, c'est... ":
        die("$01DA girl-speaker exception/page boundary drifted")
    if active.get("C9:D1B8") != "Dryade fera réagir l'orbe !":
        die("$035F full Dryade orb-message surcharge drifted")
    if active.get("C9:D1C0") != "\n" or active.get("C9:D1CB") != "":
        die("$0360 shared suffix must remain neutralized after full $035F surcharge")
    # Lot-5 validated pagination/layout sentinels.  These exact checks lock the
    # user-reviewed WAIT-only rolling-window layouts and the cross-carrier
    # three-line regrouping without changing Android-FR semantic payloads.
    expected_lot5 = {
        "C9:7C5B": "Je vous sens ému jusqu'aux larmes,\ncher spectateur... Voulez-vous\nfaire un geste pour ce malheureux\r\nenfant frappé par l'injustice ?\fUn simple don de 100 pièces\nferait déjà beaucoup pour ce\npauvre petit !\f  (",
        "C9:8512": "Elinice : Thanatos est un chevalier\nmage au service de l'Empire\nVandole, qui va détruire\r\nvotre petit royaume de l'intérieur !",
        "C9:8F73": "Rusalka : Ton Épée s'est alignée\nsur la puissance\nde la Graine de Mana,\r\net résonne désormais à l'unisson\r\navec elle !",
        "C9:8FE0": "\ndésormais le pouvoir de la Graine\nde Mana.",
        "C9:9076": "Rusalka : %S(0,0),\nsi l'Empire réussit à réactiver\nla Forteresse,\r\nle pouvoir de Mana\r\ndisparaîtra à tout\r\njamais de ce monde.",
        "C9:910D": "\nou tout sera perdu !",
        "C9:924F": "\vL'Épée ne pourra être\nravivée si les sceaux sont\nbrisés avant qu'elle n'entre\r\nen symbiose avec les Graines !",
        "C9:97D6": "Notre fils Durac a tant\nde travail qu'il n'a jamais\nle temps de venir nous voir,\r\nalors que Pandora est si près !",
    }
    for sid, expected in expected_lot5.items():
        if active.get(sid) != expected:
            die(f"Lot-5 validated layout drifted: {sid}")

    # Exhaustive dialogue-audit late-layout sentinels. These lock the reviewed
    # rolling-scroll and final-lot speaker/pagination fixes so earlier formatting
    # recipes cannot silently restore obsolete page clears or label breaks.
    expected_audit_late_layout = {
        "C9:1573": "Sous le récif de corail\nau nord-est de cette île dort\nun continent englouti abritant\r\nune civilisation ancienne.",
        "C9:33AC": "\vVoyageur : D'après la légende,\nl'Épée doit être retirée par\nun brave lorsqu'un grand\r\ndanger menace notre monde.",
        "C9:5686": "Ils sont dans un état second\net se dirigent tous vers\nles ruines au sud de Pandora,\r\ncomme vidés de leur énergie.",
        "C9:6D1D": "\vChef : Si le Flagellateur\nqui était enfermé dans le temple\ns'est échappé, c'est qu'il doit\r\nêtre possible d'y pénétrer.",
        "CA:752E": "J'accepte de te tenir compagnie\njusque-là...\nalors sois reconnaissant, hein ?",
        "CA:757E": "%S(0,0) : Zut !\nIl ne se passe rien !",
        "CA:76B2": "\nComme vous voudrez,\nVotre Majesté...\n",
        "CA:7E4B": "Bientôt les bénévodons du monde\nentier se rassembleront et\nfusionneront en un être unique et\r\nimmense...",
        "CA:8010": "Pour vaincre définitivement\nl'Empereur ressuscité, il usa de ses\ndernières forces pour venir\r\nchercher l'Épée.",
        "CA:8471": " : Je suis de la tribu de\nMana... Je vais accomplir\nle destin de mes parents\r\net protéger ce monde si merveilleux !",
        "CA:889F": "%S(0,0) : Aïe !\nOn ne pourra pas traverser ces\nflammes !",
        "CA:892F": "%S(0,0) : Ah... Il y a un\nbouclier ! On n'arrivera pas à\nentrer ! Partons...",
        "CA:8D4B": "\vJ'ai retenu la leçon : si le pouvoir\nde Mana est utilisé à mauvais\nescient, cela peut devenir très\r\ndangereux !",
        "CA:986B": "%S(0,0) : Oh là là,\nqu'est-ce qui m'est\narrivé... ?",
    }
    for sid, expected in expected_audit_late_layout.items():
        if active.get(sid) != expected:
            die(f"Exhaustive-audit validated layout drifted: {sid}")

    for sid in ("C9:09A7", "C9:09F8", "C9:0A8E"):
        if " :\n" in active.get(sid, ""):
            die(f"Lot-1 dynamic speaker label newline regressed: {sid}")

    lot12_colon_carriers = (
        "CA:7A0C", "CA:7A43", "CA:7A7D", "CA:7AB0", "CA:7B38", "CA:7B69",
        "CA:7C98", "CA:7CBA", "CA:7D32", "CA:7D5E", "CA:7DA9", "CA:80B4",
        "CA:8300", "CA:8381", "CA:838A", "CA:839E", "CA:843F", "CA:8471",
        "CA:84B9", "CA:84DE", "CA:8528",
    )
    for sid in lot12_colon_carriers:
        if not active.get(sid, "").startswith(" :"):
            die(f"$05F8 French speaker-colon spacing drifted: {sid}")

    lot5_020f = [x for x in french.get("choice_option_position_overrides", []) if x.get("event_id") == "020F"]
    if len(lot5_020f) != 1 or lot5_020f[0].get("translated_position") != 21:
        die("$020F validated visible choice gap drifted")

    structural_insertions = french.get("user_validated_structural_command_insertions", [])
    expected_structural_insertion_events = {
        "0020", "0021", "0023", "0112", "01DD", "02B7", "02EE", "036F", "038C", "038D",
        "03AA", "04A1", "04E2", "0592", "05F8",
    }
    if {entry.get("event_id") for entry in structural_insertions} != expected_structural_insertion_events:
        die("validated structural-command insertion event set drifted")

    # Full dialogue-audit dynamic-name restoration sentinels.  All prose is
    # derived from Android FR at check time; only IDs/carriers are locked here.
    android_fr = read_scrtxt(DEFAULT_SCRTXT_FR)
    audited_android_replacements = {
        "C9:09A7": [2460], "C9:09F8": [2452], "C9:0A8E": [2457],
        "C9:37AF": [109], "C9:3AC3": [914], "C9:68BA": [574],
        "C9:9B74": [951], "C9:9CB8": [973], "C9:9D38": [991],
        "C9:9E14": [1168], "C9:9F44": [1203], "C9:A02A": [1264],
        "C9:AA04": [1524], "C9:ABFB": [1480], "C9:BE42": [1735, 1736],
        "C9:DA79": [1800], "CA:40AF": [87], "CA:4126": [91],
        "C9:B2BD": [1560], "C9:BDD6": [1705],
        "C9:BDFE": [1701], "C9:BE80": [1734], "C9:BEC3": [2579],
        "C9:CA73": [2298], "C9:D3EE": [489], "C9:D515": [1142],
        "C9:DA8C": [1801], "C9:E0D9": [1891, 1892], "C9:E0FA": [1889],
        "C9:F0C2": [2369], "C9:F0E4": [2372], "CA:17B9": [2891],
        "CA:1E1B": [2752], "CA:1E59": [2680], "CA:21CB": [2679],
        "CA:2201": [2700], "CA:2237": [2702], "CA:3914": [1448],
        "CA:39B2": [1452], "CA:5CC6": [2216], "CA:6BB9": [1049],
        "CA:757E": [1012], "CA:889F": [1699], "CA:892F": [3133],
        "CA:986B": [3409],
    }
    for sid, android_ids in audited_android_replacements.items():
        expected = semantic_layout_normalized(" ".join(
            normalize_android_prose(android_fr[i]).replace("_", "").strip()
            for i in android_ids
        ))
        actual = semantic_layout_normalized(active.get(sid, ""))
        if actual != expected:
            die(f"dialogue-audit Android-FR dynamic payload drifted: {sid} <- {android_ids}")
    # $0295 is an explicitly user-validated local adaptation: Android FR 1518
    # carries a dynamic addressee absent from the desired localized rendering.
    if semantic_layout_normalized(active.get("C9:AF50", "")) != semantic_layout_normalized("Hé, salut ! J'suis au paradis, ici !"):
        die("$0295 validated local vocative removal drifted")

    for sid in ("C9:B1B0", "C9:9BCB"):
        if not active.get(sid, "").startswith(" : "):
            die(f"dialogue-audit stock PLAYER_NAME separator drifted: {sid}")
    for android_id in (1409, 1410):
        expected = semantic_layout_normalized(normalize_android_prose(android_fr[android_id]).replace("_", "").strip())
        if expected not in semantic_layout_normalized(active.get("C9:A4E9", "")):
            die(f"$026A Android-FR continuation missing: {android_id}")
    for android_id in (1021, 1022):
        expected = semantic_layout_normalized(normalize_android_prose(android_fr[android_id]).replace("_", "").strip())
        if expected not in semantic_layout_normalized(active.get("CA:747F", "")):
            die(f"$0592 Android-FR continuation missing: {android_id}")

    cov = mass["coverage"]
    if cov.get("user_validated_visually_complete_event_count", 0) < 5:
        die("validated visually-complete event count regressed")
    if cov.get("user_validated_structural_omission_event_count") != 6 or cov.get("user_validated_structural_omitted_command_count") != 7:
        die("validated structural omission coverage drifted")

    partial = {x["event_id"]: x for x in mass.get("partial_accepted_events", [])}
    if "04E1" in partial:
        if partial["04E1"] != {"event_id": "04E1", "partial_reason": "manual_resegmented_page_suppression", "manual_suppressed_semantic_ids": ["CA:2C84"]}:
            die("$04E1 suppression provenance drifted")
    else:
        complete = {x["event_id"]: x for x in mass.get("user_validated_visually_complete_events", [])}
        if complete.get("04E1") != {"event_id": "04E1", "manual_suppressed_semantic_ids": ["CA:2C84"], "reason": "user_validated_complete_with_manual_resegmentation"}:
            die("$04E1 completion provenance drifted/missing")

    deferred = ["CA:3335", "CA:3359", "CA:3362", "CA:33E4", "CA:3423"]
    p04e2 = partial.get("04E2")
    if p04e2 is not None and (p04e2.get("unresolved_semantic_ids") != deferred or p04e2.get("layout_deferred_semantic_ids") != deferred):
        die("$04E2 historical deferred set drifted")

    reports_04e1 = [x for x in mass.get("formatted_mappings", []) if x.get("event_id") == "04E1"]
    r04e1 = next((x for x in reports_04e1 if x.get("round67_user_reviewed_scene_redistribution")), None)
    if not r04e1 or r04e1.get("android_ids") != [3252, 3253, 3254, 3255, 3256, 3257]:
        die("$04E1 Android-FR redistribution report missing")

    reports_04e2 = [x for x in mass.get("formatted_mappings", []) if x.get("event_id") == "04E2"]
    r04e2 = next((x for x in reports_04e2 if x.get("snes_ids") == ["CA:32C5", "CA:32D7"]), None)
    r69 = next((x for x in reports_04e2 if x.get("round69_targeted_redistribution")), None)
    if r04e2 is not None and r04e2.get("android_fr_1280_intentionally_omitted"):
        die("$04E2 must no longer report Android-FR 1280 as omitted")
    if r69 is None:
        die("$04E2 reviewed redistribution report missing")


def check_scene_recipes(french: dict, mass: dict, auto: dict, recipes: dict) -> None:
    round68 = {eid: r for eid, r in recipes.items() if r.get("round") == 68}
    if set(round68) != {"0555", "0429", "05F8"}:
        die(f"Round-68 scene set drifted: {sorted(round68)}")
    for key, value in {"accepted_event_count": 697, "complete_accepted_event_count": 672, "accepted_semantic_source_id_count": 1780, "translation_entry_count": 1909}.items():
        if mass["coverage"].get(key, 0) < value:
            die(f"coverage {key} regressed below historical minimum")
    reports = mass.get("formatted_mappings", [])
    for eid in ("0555", "0429", "05F8"):
        if not any(r.get("event_id") == eid and r.get("round68_user_validated_android_fr_scene") for r in reports):
            die(f"{eid} validated scene report flag missing")

    round69 = {eid: r for eid, r in recipes.items() if r.get("round") == 69}
    if set(round69) != ROUND69_EVENTS:
        die(f"targeted redistribution set drifted: {sorted(round69)}")

    expected_cov = {
        "accepted_event_count": 701,
        "complete_accepted_event_count": 701,
        "partial_accepted_event_count": 0,
        "accepted_semantic_source_id_count": 1813,
        "translation_entry_count": 1959,
        "excluded_event_count": 3,
    }
    for key, value in expected_cov.items():
        if mass["coverage"].get(key) != value:
            die(f"coverage {key}: {mass['coverage'].get(key)!r} != {value!r}")
    if mass["coverage"].get("excluded_stage_counts") != {"alignment_incomplete": 3}:
        die("exclusion stages drifted")

    excluded = {x["event_id"]: x for x in mass.get("excluded_events", [])}
    if set(excluded) != set(ORPHANS):
        die(f"excluded events drifted: {sorted(excluded)}")
    for eid, sid in ORPHANS.items():
        x = excluded[eid]
        if x.get("missing_semantic_ids") != [sid]:
            die(f"{eid} orphan carrier drifted")
        if not any(d.get("snes_id") == sid and d.get("reason") == "validated_no_equivalent" for d in x.get("details", [])):
            die(f"{eid} lost validated_no_equivalent provenance")

    for eid in ROUND69_EVENTS:
        if not any(r.get("event_id") == eid and r.get("round69_targeted_redistribution") for r in reports):
            die(f"{eid} targeted redistribution report missing")

    if auto.get("coverage", {}).get("mapped_semantic_source_id_count") != 1798 or auto.get("coverage", {}).get("unmapped_semantic_source_id_count") != 40:
        die("Android semantic identity changed from 1798/1838")

    if french.get("partial_events"):
        die("PARTIEL should remain empty")
    complete_meta = {x["event_id"]: x for x in french.get("user_validated_visually_complete_events", [])}
    promoted = {"001E", "0042", "00EE", "00F1", "00F3", "0207", "0208", "024F", "0278", "02E1", "02FC", "035F", "04E1", "04E8", "0558"}
    if not promoted.issubset(complete_meta):
        die(f"completion provenance missing: {sorted(promoted - set(complete_meta))}")


def check_postaudit(french: dict, mass: dict, manual: dict) -> None:
    coverage_recipes = json.loads(FORMATTING_RECIPES.read_text(encoding="utf-8"))["sections"]["coverage_repair"]
    lot6 = [r for r in coverage_recipes.get("repairs", []) if r.get("event_id") == "0559" and r.get("carrier_id") == "CA:6787"]
    if len(lot6) != 1:
        die("expected exactly one $0559/CA:6787 coverage recipe")
    r = lot6[0]
    if r.get("android_ids") != [2151, 2152, 2153, 2154, 2155] or r.get("separator") != "\f" or r.get("android_separator") != "\f" or not r.get("wrap_android_units"):
        die("$0559/CA:6787 coverage recipe drifted")

    if any(e.get("event_id") == "0204" and e.get("id") == "C9:902F" for e in manual.get("entries", [])):
        die("$0204/C9:902F unexpectedly returned to manual supplements")

    lot6_reports = [x for x in mass.get("formatted_mappings", []) if x.get("event_id") == "0559" and x.get("coverage_repair") and x.get("android_ids") == [2151, 2152, 2153, 2154, 2155]]
    if len(lot6_reports) != 1:
        die("format report does not prove application of Android 2151..2155 to $0559")

    entry = next((item for group in french.get("groups", []) for item in group.get("entries", []) if item.get("id") == "CA:6787"), None)
    if not entry or entry.get("text", "").count("\f") < 5 or "%S(0,0)" not in entry.get("text", ""):
        die("generated CA:6787 lost the post-audit mini-transition")
    if not any(x.get("event_id") == "0204" and x.get("id") == "C9:902F" and not x.get("active_manual_supplement", True) for x in french.get("migrated_manual_dialogue_supplements", [])):
        die("generated metadata does not record $0204 manual->Android migration")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rom",
        type=Path,
        required=True,
        help="clean unheadered Secret of Mana (USA) ROM used by the mass formatter/simulator",
    )
    args = parser.parse_args()

    manual = json.loads(MANUAL.read_text(encoding="utf-8"))
    recipes = json.loads(RECIPES.read_text(encoding="utf-8"))["events"]
    english = read_scrtxt(DEFAULT_SCRTXT_EN)
    french_android = read_scrtxt(DEFAULT_SCRTXT_FR)
    base_rom = args.rom.resolve().read_bytes()
    source_document = load_or_extract_dialogues(base_rom)

    auto = make_dialogue_auto_alignment(
        english,
        french_android,
        english_path=DEFAULT_SCRTXT_EN,
        french_path=DEFAULT_SCRTXT_FR,
        source_document=source_document,
    )
    french, mass = make_dialogue_format_mass(
        english,
        french_android,
        english_path=DEFAULT_SCRTXT_EN,
        french_path=DEFAULT_SCRTXT_FR,
        base_rom=base_rom,
        alignment=auto,
        source_document=source_document,
    )

    check_targeted_reviews(manual, french, mass)
    check_scene_recipes(french, mass, auto, recipes)
    check_postaudit(french, mass, manual)
    print("Dialogue regressions verified from canonical inputs: targeted reviews, scene redistributions, 701/701 completion, 3 validated exclusions, Android identity 1798/1838, post-audit coverage repairs")


if __name__ == "__main__":
    main()
