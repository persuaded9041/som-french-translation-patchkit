# HANDOFF — Secret of Mana FR — menus natifs et ressources françaises

Date : 2026-09-17

Cette archive est la **source de vérité** et prévaut sur GitHub. La ROM de référence est **Secret of Mana (USA), non headerée**, taille `0x200000`, SHA-256 `4c15013131351e694e05f22e38bb1b3e4031dedac77ec75abecebe8520d82d5f`. Elle ne doit jamais être redistribuée.

## État de reprise

Le backend battle/status `$AC` de `vwf_ui` reste **runtime-validé** et stable.
Depuis cette baseline, l'écran natif **Actions des personnages** a également été
traduit et runtime-validé avec son renderer fixe stock. Cette archive est le
nouveau point de départ.

**Priorité immédiate de la prochaine discussion : après lecture complète de
l'archive, NE RIEN MODIFIER et attendre explicitement le feu vert de l'utilisateur.
Une fois autorisé, reprendre la traduction des ressources et menus encore non
traduits par petits lots cohérents avec validation humaine entre les lots.**

Ne pas relancer un audit global des dialogues sans raison spécifique : leur
corpus reste gelé et validé.

Avant toute modification, lire intégralement :

- `README.md`
- `docs/HANDOFF.md`
- `docs/TEXT_RESOURCES.md`
- `docs/MENU_TEXT.md`
- `docs/INTERFACE_TEXT.md`
- `docs/TRANSLATIONS.md`
- `docs/COMPATIBILITY.md`
- `docs/MEMORY_MAP.md`
- `docs/UI_VWF.md`
- `components/french_resources/README.md`
- `components/french_menus/README.md`
- `components/vwf_ui/README.md`

Le corpus de dialogues est gelé : **701/701 événements jouables**, **1959 carriers traduits**, **0 erreur / 0 warning / 0 wrap implicite**, alignement Android **1798/1838**. Ne modifier aucun dialogue, mapping Android dialogue ou segmentation pendant le travail sur les ressources.


## Actions des personnages — runtime-validé

Les quatre axes de l'écran natif Action Settings sont désormais promus dans
`french_menus` :

- `ATTACK` -> `Attaquer` ;
- `GUARD` -> `Défendre` ;
- `APPROACH` -> `S'approcher` ;
- `KEEP AWAY` -> `S'éloigner`.

Décision d'architecture validée : **ne pas utiliser la VWF sur cette page**.
Un essai VWF a bien montré le rendu variable, mais a cassé les indices de tuiles
du texte d'aide et du panneau de droite ; il est rejeté et ne doit pas être
réintroduit. Le damier, les fenêtres et le renderer fixe restent stock.

Solution finale runtime-validée :

- largeur de la grande fenêtre : valeur stock `$18` ;
- checkerboard et fenêtre droite : stock ;
- `Défendre` est déplacé d'une cellule fixe (8 px) vers la gauche ;
- ressource texte relocalisée en `$C7:4DC0`, **34 cellules + `$00`** ;
- placement relocalisé en `$C7:4DE3`, six spans ;
- deux fragments de 2 cellules sont réutilisés via la table de placement pour
  rester dans l'enveloppe 34 cellules prouvée par la VF SNES Rev 1 ;
- `$C7:6C77 : $2180 -> $2184` pour la valeur dynamique du panneau droit ;
- `$C7:6D57 : $2090 -> $2094` et `$C7:6D5C : $2108 -> $210C` pour les deux
  redraws du texte d'aide supérieur.

Les trois compensations `+$04` existent également dans la VF SNES officielle.
Validation utilisateur effectuée sur toute la séquence : écran initial, choix
d'une position/gauge, puis annulation `Y` et retour au prompt initial.

Les deux phrases d'aide sont maintenant **runtime-validées** :

- `$C0:3620` -> `Choisissez le type d'action. Validez avec “Attaque”.` ;
- `$C0:3654` -> `Jusqu'où charger la jauge ? Validez avec “Attaque”.`.

Leur renderer fixe traite 29 colonnes / 58 caractères logiques de 4 px. Le bloc
est relocalisé en `$ED:8500+`. `$C0:368F` (`0 1 2 3 4 5 6 7 8`) reste structurel
et inchangé. Ne pas généraliser `vwf_ui` à cette page.

## Traductions natives déjà revues mais pas encore toutes promues

`translations/menu_text_french.json` contient désormais les traductions validées
des 16 états, des templates Statut, types d'armes et libellés associés.
`translations/interface_text_french.json` contient les dix caractéristiques
validées (`Force`, `Agilité`, `Endurance`, `Intelligence`, `% précision`, etc.).
Ces familles sont **translation-only** tant que leurs renderers natifs n'ont pas
été explicitement branchés et runtime-validés.

Le vocabulaire GAME FILE validé inclut désormais `COUNTER -> Sauvegardes` et
`MANA POWER -> Graines de Mana`. `Sauvegardes` tient dans les 15 cellules fixes
disponibles avant sa valeur. `Graines de Mana` remplit les 15 cellules source et
est rendu par un backend `vwf_ui` ultra-localisé, pair-aligné, sans déplacer la
valeur Mana dynamique. Les accents sur majuscules sont à conserver (`Étourdi` si
ce terme est utilisé ailleurs, `Épée`, etc.).

## Corrections menus/interface validées depuis la baseline précédente

- Aide sauvegarde GAME FILE :
  - `Sauvegarder sur un fichier utilisé efface ses données.`
  - `Pressez “Attaque” pour sauver, “Retour” pour annuler.`
  Les actions logiques sont utilisées ici plutôt que B/Y, car les contrôles peuvent déjà avoir été reconfigurés.
- Name Entry : `Choisissez un caractère avec la croix directionnelle.` ; les mentions physiques `B` et `Start` sont volontairement conservées car la création de partie précède le remapping des contrôles.
- GAME FILE : `Sauvegardes` est runtime-validé en renderer fixe stock.
- GAME FILE : `Graines de Mana` est runtime-validé via le backend VWF exact `$AD`; le texte reste dans `translations/menu_text_french.json` (`C7:73AA`) et la valeur à droite reste stock.
- GAME FILE argent : le bug `GO` est corrigé. Le renderer stock écrit le premier `G` séparément (`$C7:54A9`, opérande à `$C7:54AA`) et prend le second glyphe depuis le template `C7:7394`. Probes déterminants : `PO -> GO`, `XO -> GO`, `XX -> GX`. Le builder dérive le premier glyphe depuis le JSON `C7:7394`, donc aucune prose française n'est codée en dur.

### Espacement devant `PO` — **runtime-validé et promu**

Le rendu final validé est `1254536 PO`, avec `PO` conservé à son ancre droite stock. L'analyse ASM a établi le mécanisme exact :

- la ligne Argent du template GAME FILE fait 18 cellules ; `PO` occupe les colonnes 15-16 ;
- le moteur dynamique prépare `$7E:9C00`, puis le chemin `$C7:5D9A` envoie toujours `$0200` octets de graphismes, soit **16 caractères fixes** de 32 octets chacun ;
- les colonnes dynamiques `0..15` sont donc toujours réécrites, même si la chaîne temporaire se termine avant ; la colonne 16 reste statique et fournit le second glyphe de la monnaie ;
- le stock produit `8 espaces + 7 cellules montant + currency[0]` dans ces 16 colonnes ; simplement passer `8 -> 7` raccourcit la chaîne à 15 cellules et le moteur remplit la colonne 15 avec un espace, donnant `P O` ;
- la solution validée conserve **16 cellules dynamiques** : `7 espaces + 7 cellules montant + 1 espace + currency[0]`, puis la colonne 16 statique fournit `currency[1]`.

Implémentation promue dans `french_menus` :

- `$C7:549A : LDY #$0008 -> #$0007` ;
- `$C7:54A6 : JSR $54B0 -> JSR $4D32` ;
- helper 10 octets `$C7:4D32-$4D3B` : `JSR $54B0 / LDA #$80 / STA $9C00,X / INX / RTS` ;
- le code existant `$C7:54A9` écrit ensuite `currency[0]` en colonne 15, dérivé du premier caractère du JSON `C7:7394` ; `currency[1]` reste le caractère du template en colonne 16.

Les anciens probes écran noir / `PPO` / `P O` sont rejetés et absents du code final. Ils ne doivent pas être réintroduits. Le helper validé n'encode aucun texte français : il ajoute uniquement la cellule d'espacement `$80` et préserve l'architecture hybride stock.

### `Sauvegardes` + VWF ultra-localisée `Graines de Mana` — **runtime-validés et promus**

Deux autres champs GAME FILE sont maintenant validés :

- `COUNTER` (`C7:7398`) -> `Sauvegardes`. La ligne fixe offre 15 cellules entre la colonne 1 et la valeur dynamique en colonne 16 ; le libellé en utilise 11. Aucun renderer n'est modifié pour ce champ.
- `MANA POWER` (`C7:73AA`) -> `Graines de Mana`. Le payload remplit exactement les 15 cellules source, et seul ce champ passe par un backend `vwf_ui` dédié `$AD`.

Architecture du backend Mana :

- table générateur GAME FILE `$C7:5F95-$5F96` : pointeur `$5464 -> $4C88` ;
- trampoline libre `$C7:4C88-$4C8E` : `JSL $ED:7F40 / JMP $C7:5464` ;
- wrapper `$ED:7F40-$7FA4` : copie exactement les 15 cellules de `$C7:73AA` dans `$7E:9C00`, prépare la soumission menu stock, arme `$7E:93C1=$AD`, puis appelle `$C0:2ADB/$2AEA/$2ADF` ;
- le renderer `$AD` exige le caller exact `$235E`, la banque source `$7E`, utilise le vrai decoded count, et démarre à **9 px** ;
- le champ visible commence sur la cellule globale impaire 91. Le DMA validé est donc pair-aligné une cellule plus tôt, sur `$6820-$691F` : cellule 90 vide + libellé VWF à partir de la cellule 91 ;
- la valeur Mana dynamique commence à `$6920` et reste entièrement stock.

Le premier probe VWF, démarré directement sur la cellule 91 / `$6830`, est rejeté : il séparait les moitiés haut/bas des glyphes et laissait un demi-`G` résiduel. Le v2 a validé le renderer pair-aligné ; le v3 a ensuite corrigé uniquement le payload source complet `Graines de Mana`. Le `patches/all.ips` promu doit rester byte-identique à ce probe v3 runtime-validé. `vwf_ui` ne contient aucune prose française : il copie le champ source appartenant à `french_menus`.

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
- battle/status banner `$AC` **runtime-validé** ;
- GAME FILE Mana label `$AD` **runtime-validé**, pair-aligné, source `C7:73AA`, valeur dynamique stock.

Corrections promues :

- Ring/Forge/D9/merchandise commencent les lignes fraîches à **+1 px** pour préserver le contour noir gauche ; MONEY reste à x=0 ;
- merchandise `$AA` rend uniquement le vrai `SAVED_COUNT`, correction runtime-validée du `H` de `Haubert magique` ;
- prix merchandise : ancre **164 px** + séparateur monnaie **4 px** ;
- MONEY : séparateur monnaie **3 px**, largeur `$C7:714C` **9 -> 11 cellules** ;
- la fermeture MONEY utilise désormais le seed X indépendant `$C7:7140` **`$0A -> $09`**, runtime-validé, afin d'effacer la cellule supplémentaire ouverte à gauche ;
- le contenu monnaie reste source-owned, jamais codé dans `vwf_ui` : shop/MONEY `PO` vient de `french_resources`, GAME FILE `C7:7394` vient de `french_menus` ;
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
python3 build.py "Secret of Mana (USA).sfc" french-menus --combine
python3 build.py "Secret of Mana (USA).sfc" french-resources --combine
```

Pour une validation de versionnement, faire également un rebuild complet dans un dossier de patches neuf et comparer les hashes aux patches promus.

## Baseline propre actuelle — 2026-09-18

Rebuild complet depuis la ROM USA propre, après validation runtime de `Sauvegardes` et du backend VWF GAME FILE `Graines de Mana` :

- `patches/french_menus.ips` SHA-256 : `9234a73b7b4116e6eab0dcb9135aab3141fa9d44c255e4ffe62a1056ab8c264b`
- `patches/french_name_entry_extended.ips` SHA-256 : `6a488bc7cd6afe1ee98176c5bed3b4670bf12c789b5f58622d6aab23217ea6da`
- `patches/french_resources.ips` SHA-256 : `c9483c0a42ca85d2f9051f4d7f0355e09ce76279d3311f43bd574864fd492216`
- `patches/vwf_ui.ips` SHA-256 : `a031a40d9c3122a0b5b8bb02fdb4bcff92da3ddc5b924f71e30e1df42cceddcd`
- `patches/vwf_intro.ips` SHA-256 : `a5917976c7bf139e8f0ba69ee46f2ab0e23ab3db91453bf18bae6ba420d4110a`
- `patches/vwf_dialogues.ips` SHA-256 : `f9628f1c43ba2917a081fd2cf31b48ce90c9138980e720276602796f7b593dad`
- `patches/french_dialogues.ips` SHA-256 : `dfc94882e4162052ccd7195839ef7ef7f5a89f1bec51847d905ca6b05ad2de31`
- `patches/all.ips` SHA-256 : `c5ec6c1396a659740ae462f75c8ad08c2074a0276df0ada04e021a81b9530807`
- ROM finale reconstruite SHA-256 : `adbf1eba05ee6459ab63d0a4ecd2c1a5cc4e828f1de30429847e2acaf9b3180e`
- checksum SNES final : `$862D`.

Le rebuild complet dans un dossier de patches neuf est byte-identique aux patches promus. `patches/all.ips` est **byte-identique** au probe v3 GAME FILE Mana runtime-validé par l'utilisateur, qui inclut également `Sauvegardes`. La ROM de référence n'est pas incluse dans l'archive.
