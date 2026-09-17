# HANDOFF — Secret of Mana FR — extension des ressources françaises

Date : 2026-09-17

Cette archive est la **source de vérité** et prévaut sur GitHub. La ROM de référence est **Secret of Mana (USA), non headerée**, taille `0x200000`, SHA-256 `4c15013131351e694e05f22e38bb1b3e4031dedac77ec75abecebe8520d82d5f`. Elle ne doit jamais être redistribuée.

## État de reprise

Le backend battle/status `$AC` de `vwf_ui` est désormais **runtime-validé**. Le
bug de suffixe après nom dynamique est corrigé dans la baseline propre ; il ne
reste aucune correction battle bloquante à reprendre avant la suite. Cette
archive est le nouveau point de départ pour les prochains travaux de ressources
ou d'UI, selon la priorité choisie dans la discussion suivante.

Ne pas relancer un audit global des dialogues sans raison spécifique : leur
corpus reste gelé et validé.

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
- les deux littéraux monnaie `$C7:7B6A` et `$D0:D894`, traduits `GP -> PO` depuis `translations/french_resources_reviewed_literals.json`;
- le contenu battle/status `$C0`, relocalisé en `$EE:6000+`, avec mapping Android dans `recipes/android/battle_text_mapping.json` et surcharges revues dans `translations/battle_text_reviewed_overrides.json`.

Il n'existe plus de composant `french_shop_text` et aucun `french_shop_text.ips` ne doit être généré.

Les textes doivent rester **data-driven** :

- source USA : extraction propre dans `assets/*.json` (cache reproductible, non canonique) ;
- Android EN/FR : `sources/android/*` ;
- identité/layout : `recipes/android/*` ;
- adaptations SNES explicitement validées : JSON sous `translations/` ;
- aucun texte français de gameplay ne doit être codé en dur dans Python ou ASM.

`tools/text/check_source_hygiene.py` vérifie désormais explicitement l'absence de prose localisée copiée dans les sources Python/ASM des composants.

### État actuel des ressources

Le build promu traduit **360 ressources `$CA`** (358 précédentes + les deux system messages `$1FF-$200`). Le blob fait **7103 / 7315 octets** et reste intégralement dans l'allocation stock `$CA:98E1-$B573`. Trois ressources mappées restent volontairement non insérées avec le profil actuel car `°` entre en conflit avec la frontière DTE des ressources non-event.

Les catégories actuellement activées dans `components/french_resources/build_patch.py` sont :

`magic_name`, `mana_spirit_name`, `weapon_name`, `helmet_name`, `armor_name`, `accessory_name`, `item_name`, `menu_label`, `enemy_name`, `location_name`, `system_message`.

Les deux `system_message` restent exclus du mapping Android positionnel automatique : leur liaison placeholder est explicitement revue dans `translations/text_resources_reviewed_overrides.json`.

Les deux grandes familles déjà mappées mais **non promues** sont `weapon_description` (**72**) et `magic_description` (**42**). Elles sont des candidates naturelles pour la prochaine passe, mais ne doivent pas être activées en bloc sans revue préalable de leur provenance, encodage, taille et géométrie d'affichage. Les 4 `location_name` non résolus restent non forcés.

Le dernier audit global des 475 ressources Android mappées classe **302** entrées dans l'enveloppe stock, **170** en `geometry_review` et **3** en `encoding_blocked` (le caractère `°`). Pour les candidates suivantes : `weapon_description` = **38 inside / 34 review** ; `magic_description` = **2 inside / 40 review**. Le dry-run des 472 entrées encodables fait 7304 octets, mais ce résultat de taille ne vaut pas validation de rendu : la géométrie reste le critère bloquant principal.

## Nouveau corpus battle/status — état à préserver

`french_resources` possède désormais le contenu du pool `assets/battle_text.json` :

- 109 records physiques source ; 107 records texte relocalisés en `$EE:6000+` ;
- 92 payloads Android-FR directs/templatisés + 11 adaptations SNES/JP validées ;
- les 8 anciennes entrées `needs_manual_translation` sont désormais traduites et validées depuis le japonais original ;
- `$C0:62F3` est maintenant validé en surcharge compacte : le sujet dynamique stock est conservé et le suffixe devient ` s'est rétabli !` ;
- 6 records vides/contrôle ;
- pool relocalisé actuel : 1573 octets, réserve `$EE:6000-$6FFF`.

Les huit anciennes traductions manquantes sont désormais validées dans `translations/battle_text_reviewed_overrides.json`, avec leur provenance JP conservée en note.

`vwf_ui` ajoute le backend `$AC` uniquement sur les submits exacts `$C0:5BEA/$5BF8 -> $C0:637D/$637F`. Il utilise le parser privé mode 3 (`$9390-$93C0`, 49 octets), conserve le vrai decoded count et est maintenant runtime-validé.

## Correction battle/status `$AC` — runtime-validée

Le défaut reproduit auparavant sur `IDGET se change en mog !` et `LINA rétrécit !`
était entièrement dans `vwf_ui`; `french_resources` seul affichait déjà les
phrases complètes. La comparaison stock/VWF a établi que le suffixe survivait
bien au `PLAYER_NAME` et atteignait le buffer privé.

Le point exact de divergence était le contrôle de continuité du renderer :

- `$C0:637D/$637F` ne sont que les mini-scripts `{50}/{51}` d'ouverture/fermeture ;
- le moteur battle copie ensuite le message réel vers `$7E:FF69` et pose `$1D03=$7E` ;
- parser mode 3 décode correctement le message complet dans `$7E:9390-$93C0` ;
- le selector battle 5 exigeait à tort `$1D03=$C0`, rejetait ce parse privé et
  retombait sur le renderer stock `$A1A4`, d'où les sorties résiduelles `IDGET` / `LINA`.

Correctif promu : **`$ED:7B83 : C0 -> 7E`** dans le contrôle de banque du
selector battle `$AC`. Aucun contenu, pointeur ou code de composition dynamique
de `french_resources` n'est modifié.

Validation runtime utilisateur :

- patch `vwf_ui` standalone validé ;
- patch combiné `french_resources + vwf_ui` validé.

Deux probes antérieurs restent explicitement rejetés et ne font pas partie de la
baseline : conserver `$AC` pendant `$1D00 & $08`, ou le conserver sur plusieurs
renders successifs.

## Baseline UI/boutique runtime-validée à préserver

`vwf_ui` est **présentation uniquement** et reste standalone, sans dépendance à `vwf_dialogues` :

- Forge `$A7` ;
- Ring title `$A8` ;
- réponses D9 shop/forge `$A9` ;
- lignes merchandise achat/vente `$AA` ;
- total MONEY type 2 `$AB`;
- battle/status banner `$AC` **runtime-validé**.

Corrections promues :

- Ring/Forge/D9/merchandise commencent les lignes fraîches à **+1 px** pour préserver le contour noir gauche ; MONEY reste à x=0 ;
- merchandise `$AA` rend uniquement le vrai `SAVED_COUNT`, correction runtime-validée du `H` de `Haubert magique` ;
- prix merchandise : ancre **164 px** + séparateur monnaie **4 px** ;
- MONEY : séparateur monnaie **3 px**, largeur `$C7:714C` **9 -> 11 cellules** ;
- la fermeture MONEY utilise désormais le seed X indépendant `$C7:7140` **`$0A -> $09`**, runtime-validé, afin d'effacer la cellule supplémentaire ouverte à gauche ;
- `PO` reste la responsabilité exclusive de `french_resources`, jamais de `vwf_ui` ;
- battle `$AC` : source réelle `$7E:FF69`, continuity gate `$ED:7B83=$7E`, runtime-validé ;
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

## Baseline propre après correction battle/status `$AC`

Rebuild propre complet reproductible :

- `patches/french_resources.ips` SHA-256 : `c9483c0a42ca85d2f9051f4d7f0355e09ce76279d3311f43bd574864fd492216`
- `patches/vwf_ui.ips` SHA-256 : `69bfbc246fffddd6a05e6421c51cf824b64269bb159de0acaa5fd297834a7ba9`
- `patches/vwf_intro.ips` SHA-256 : `a5917976c7bf139e8f0ba69ee46f2ab0e23ab3db91453bf18bae6ba420d4110a`
- `patches/vwf_dialogues.ips` SHA-256 : `1bff8d5f21ad9f372e2bedc8f1bf0515df51cfa825fc09c5a4ee680693b9258e`
- `patches/french_dialogues.ips` SHA-256 : `dfc94882e4162052ccd7195839ef7ef7f5a89f1bec51847d905ca6b05ad2de31` (inchangé)
- `patches/all.ips` SHA-256 : `1961a7b4a1ad18c787f8bb6f2e06db339508c2f7c57591269955b286614433ef`
- ROM finale reconstruite SHA-256 : `06cabc356ae82946cf6f01cf7fe43fb5ca61d92893231841c4e0a590b3b39f3e`
- checksum SNES final : `$22AD`.

Cette correction `$AC` ne modifie ni `vwf_intro.ips` ni `vwf_dialogues.ips`. Leur infrastructure partagée inclut déjà le classifier/parser battle mode 3 byte-identique requis par `vwf_ui`; leurs comportements intro/dialogue restent inchangés.
