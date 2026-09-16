# HANDOFF — Secret of Mana FR — extension des ressources françaises

Date : 2026-09-16

Cette archive est la **source de vérité** et prévaut sur GitHub. La ROM de référence est **Secret of Mana (USA), non headerée**, taille `0x200000`, SHA-256 `4c15013131351e694e05f22e38bb1b3e4031dedac77ec75abecebe8520d82d5f`. Elle ne doit jamais être redistribuée.

## Prochaine tâche

La prochaine discussion doit travailler sur **l'ajout de traductions de ressources non-dialogue supplémentaires**. Elle ne doit pas relancer un audit des dialogues ni refactorer les backends VWF validés sans nécessité directe.

Avant toute modification, lire intégralement :

- `README.md`
- `docs/HANDOFF.md`
- `docs/TEXT_RESOURCES.md`
- `docs/TRANSLATIONS.md`
- `docs/COMPATIBILITY.md`
- `docs/MEMORY_MAP.md`
- `docs/UI_VWF.md`
- `components/french_resources/README.md`
- `components/vwf_ui/README.md`

Le corpus de dialogues est gelé : **701/701 événements jouables**, **1959 carriers traduits**, **0 erreur / 0 warning / 0 wrap implicite**, alignement Android **1798/1838**. Ne modifier aucun dialogue, mapping Android dialogue ou segmentation pendant le travail sur les ressources.

## Architecture `french_resources` à préserver

`french_resources` est l'unique composant de contenu pour les ressources françaises concernées. Il possède actuellement :

- la table de 513 pointeurs `$CA` et son blob de ressources ;
- les 9 mini-events shop/forge `$D9:FE20-$FEF3` et leurs 9 opérandes `LDX` en banque C0 ;
- les deux littéraux monnaie `$C7:7B6A` et `$D0:D894`, traduits `GP -> PO` depuis `translations/french_resources_reviewed_literals.json`.

Il n'existe plus de composant `french_shop_text` et aucun `french_shop_text.ips` ne doit être généré.

Les textes doivent rester **data-driven** :

- source USA : extraction propre dans `assets/*.json` (cache reproductible, non canonique) ;
- Android EN/FR : `sources/android/*` ;
- identité/layout : `recipes/android/*` ;
- adaptations SNES explicitement validées : JSON sous `translations/` ;
- aucun texte français de gameplay ne doit être codé en dur dans Python ou ASM.

`tools/text/check_source_hygiene.py` vérifie désormais explicitement l'absence de prose localisée copiée dans les sources Python/ASM des composants.

### État actuel des ressources

Le build promu traduit **358 ressources `$CA`**. Le blob fait **7103 / 7315 octets** et reste intégralement dans l'allocation stock `$CA:98E1-$B573`. Trois ressources mappées restent volontairement non insérées avec le profil actuel car `°` entre en conflit avec la frontière DTE des ressources non-event.

Les catégories actuellement activées dans `components/french_resources/build_patch.py` sont :

`magic_name`, `mana_spirit_name`, `weapon_name`, `helmet_name`, `armor_name`, `accessory_name`, `item_name`, `menu_label`, `enemy_name`, `location_name`.

Les deux grandes familles déjà mappées mais **non promues** sont `weapon_description` (**72**) et `magic_description` (**42**). Elles sont des candidates naturelles pour la prochaine passe, mais ne doivent pas être activées en bloc sans revue préalable de leur provenance, encodage, taille et géométrie d'affichage. Les 4 `location_name` non résolus restent non forcés.

Le dernier audit global des 475 ressources Android mappées classe **302** entrées dans l'enveloppe stock, **170** en `geometry_review` et **3** en `encoding_blocked` (le caractère `°`). Pour les candidates suivantes : `weapon_description` = **38 inside / 34 review** ; `magic_description` = **2 inside / 40 review**. Le dry-run des 472 entrées encodables fait 7304 octets, mais ce résultat de taille ne vaut pas validation de rendu : la géométrie reste le critère bloquant principal.

## Baseline UI/boutique runtime-validée à préserver

`vwf_ui` est **présentation uniquement** et reste standalone, sans dépendance à `vwf_dialogues` :

- Forge `$A7` ;
- Ring title `$A8` ;
- réponses D9 shop/forge `$A9` ;
- lignes merchandise achat/vente `$AA` ;
- total MONEY type 2 `$AB`.

Corrections promues :

- Ring/Forge/D9/merchandise commencent les lignes fraîches à **+1 px** pour préserver le contour noir gauche ; MONEY reste à x=0 ;
- merchandise `$AA` rend uniquement le vrai `SAVED_COUNT`, correction runtime-validée du `H` de `Haubert magique` ;
- prix merchandise : ancre **164 px** + séparateur monnaie **4 px** ;
- MONEY : séparateur monnaie **3 px**, largeur `$C7:714C` **9 -> 11 cellules** ;
- la fermeture MONEY utilise désormais le seed X indépendant `$C7:7140` **`$0A -> $09`**, runtime-validé, afin d'effacer la cellule supplémentaire ouverte à gauche ;
- `PO` reste la responsabilité exclusive de `french_resources`, jamais de `vwf_ui` ;
- GAME SELECT et les fallbacks stock restent validés.

Ne généraliser aucun de ces backends à une nouvelle famille de ressources sans tracer son chemin exact.

## Procédure recommandée pour les nouvelles ressources

Pour chaque lot :

1. identifier les IDs `$CA`, catégories et texte USA dans `assets/text_resources.json` ;
2. vérifier l'identité Android EN et le texte Android FR via le pipeline existant ;
3. conserver Android FR lorsque l'identité est solide ; utiliser `translations/text_resources_reviewed_overrides.json` uniquement pour une adaptation SNES explicitement revue ;
4. ne jamais mettre la traduction dans `build_patch.py` ou un ASM ;
5. auditer encodage, taille et contexte d'affichage avec `tools/text/audit_resource_layout.py` et/ou une inspection ciblée du renderer ;
6. promouvoir seulement les IDs/familles prouvés sûrs ; éviter d'ajouter aveuglément une catégorie entière à `DEFAULT_CATEGORIES` ;
7. reconstruire `french_resources.ips`, puis `all.ips`, et vérifier que les patches non ciblés restent byte-identiques ;
8. faire valider visuellement les textes concernés en jeu avant de poursuivre le lot suivant.

## Commandes de validation

```bash
python3 tools/text/check_source_hygiene.py
python3 tools/text/check_roundtrip.py "Secret of Mana (USA).sfc" --scan-all-events
python3 tools/text/import_android_resources.py "Secret of Mana (USA).sfc"
python3 tools/text/import_android_resources.py "Secret of Mana (USA).sfc" --check
python3 tools/text/audit_resource_layout.py "Secret of Mana (USA).sfc" --json /tmp/resource_layout.json --html /tmp/resource_layout.html
python3 tools/text/audit_resource_layout.py "Secret of Mana (USA).sfc" --json /tmp/resource_layout.json --html /tmp/resource_layout.html --check
python3 build.py "Secret of Mana (USA).sfc" french-resources --combine
```

Pour une validation de versionnement, faire également un rebuild complet dans un dossier de patches neuf et comparer les hashes aux patches promus.

## Baseline promue après cleanup

- `patches/french_resources.ips` SHA-256 : `82908a8e0fd594d50fd9bdb5acc43965baf6b2dadc2079f349ba4f3ab3659d2d`
- `patches/vwf_ui.ips` SHA-256 : `b32ae20b1b3836facafae5f3a32a6a799c12bbcfc7814e5a0b404c491ac0c834`
- `patches/french_dialogues.ips` SHA-256 : `dfc94882e4162052ccd7195839ef7ef7f5a89f1bec51847d905ca6b05ad2de31`
- `patches/all.ips` SHA-256 : `47744d9f094882e8b2a8c3916b9a675ecdd122330839ebbaa90e0279843c3bb4`
- ROM finale reconstruite SHA-256 : `a9e22f7dedffceb23ebc8d8093f14b57520cd35e3110904169a86a7eca76f9ff`
- checksum SNES final : `$C107`.

Le prochain travail doit modifier ces hashes uniquement si de nouvelles ressources sont effectivement promues.
