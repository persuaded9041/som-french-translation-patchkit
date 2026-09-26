# HANDOFF — Secret of Mana FR — VWF performances + descriptions armes/magies validées

Date : 2026-09-20

Cette archive est la **source de vérité** et prévaut sur GitHub. La ROM de référence est **Secret of Mana (USA), non headerée**, taille `0x200000`, SHA-256 `4c15013131351e694e05f22e38bb1b3e4031dedac77ec75abecebe8520d82d5f`. Elle ne doit jamais être redistribuée.

## Candidat actif — 2026-09-26 : aides armes/magies

L'étude JP/Android est terminée et l'utilisateur a validé les deux formulations.
Les sources `french_menus` insèrent désormais ces aides, **en attente de validation
en jeu**. Les IPS promus sous `patches/` restent ceux du 20 septembre ; les nouveaux
IPS et la ROM locale sont sous `build/candidates/skill-help-20260926/`.
Voir `docs/SKILL_MENU_HELP_RESEARCH.md` pour provenance, allocations, empreintes,
comparaison binaire et protocole de test. Prochaine étape : tester ce candidat,
puis le promouvoir uniquement après confirmation. Les sections suivantes décrivent
la baseline antérieure ; leur demande d'étude préalable est désormais satisfaite.

## État de reprise

Le backend battle/status `$AC` de `vwf_ui` reste **runtime-validé** et stable.
Depuis cette baseline, l'écran natif **Actions des personnages** a également été
traduit et runtime-validé avec son renderer fixe stock. Cette archive est le
nouveau point de départ.

**État immédiat : le menu `Niv. armes` / `Niv. magies` possède désormais les
noms VWF runtime-validés, les 72 descriptions d'armes françaises runtime-validées
et les 42 descriptions de magie Android FR complètes dans un panneau VWF 3×480 px
runtime-validé. Les conditions stock de déblocage restent autoritaires ; les
esprits non débloqués n'affichent aucune description et une ligne de magie non
émise par stock reste vide. Prochaine priorité demandée : traduire le texte
d'aide/par défaut encore anglais de ce même menu, en repartant du japonais
d'origine, puis vérifier l'existence d'un équivalent Android FR avant adaptation
SNES. Ne rien modifier avant cette étude.**

### Performance VWF — état promu

Les optimisations générales VWF sont runtime-validées jusqu'au **Stage 3A** :
Ring rendu au vrai nombre de caractères, scope de ligne inline, phase de glyphe
cachée, compositor compact sûr Stage 2C-R1, puis réparation de contour bornée.
Le premier Stage 2C utilisant `JMP (addr,X)` est **rejeté** (écran noir / lecture
du pointeur en bank 0) et ne doit jamais être restauré. Le travail général Ring
s'arrête volontairement à Stage 3A. Voir `docs/VWF_PERFORMANCE_RESEARCH.md`.

Le panneau inférieur `Niv. magies` est runtime-validé jusqu'au **Magic Stage 2** :
chaque ligne logique 480 px n'est plus rasterisée/convertie qu'une fois sur la
passe gauche ; la passe droite réutilise les 960 octets packed conservés dans
`$7E:97C0-$9B7F`. Les **6 DMA stock**, les IDs capturés, les conditions de
déblocage et les 42 textes restent inchangés. Magic Stage 1 est supersédé. Voir
`docs/MAGIC_PANEL_PERFORMANCE_RESEARCH.md`.

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
- `docs/WEAPON_MAGIC_SKILL_ROW_VWF_RESEARCH.md`
- `docs/WEAPON_MAGIC_DESCRIPTIONS_RESEARCH.md`
- `docs/VWF_PERFORMANCE_RESEARCH.md`
- `docs/MAGIC_PANEL_PERFORMANCE_RESEARCH.md`
- `docs/UI_VWF.md`
- `components/french_gfx/README.md`
- `components/french_gfx/docs/MEMORY_MAP.md`
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

## Écran Statut / Caractéristiques — promotion validée, `Épée` candidate

Le chemin fixe est compris et runtime-validé : les dix caractéristiques restent
structurées en slots source de 10 cellules à `$C7:7A28`, et les suffixes USA
`ON` / `CE` sont neutralisés comme dans la ROM France Rev 1. La VWF est
ultra-localisée aux **dix libellés de caractéristiques uniquement** ; valeurs
numériques, barres, états et tous les autres textes de l’écran restent stock.

Les formes longues `Intelligence`, `% précision` et `Déf. magique` sont
runtime-validées via la table localisée `$ED:8B00-$8B9F`. Les templates fixes
`Expérience`, `Niveau suivant`, `Graines de Mana` et l’espace avant `PO` sont
aussi runtime-validés sans nouvelle VWF. `french_resources` reste propriétaire
du littéral `GP -> PO` à `$C7:7B6A`.

Le candidat courant traite uniquement `Epée -> Épée`. `french_menus` passe au
profil partagé `full_french` (`$D4-$E5`, seuil DTE `$E6`) et encode `É`
directement en `$E2`; aucun nouveau hook, aucune VWF et aucune allocation ROM
ne sont ajoutés pour ce mot. Cette dernière étape reste à valider runtime.

## Corrections menus/interface validées depuis la baseline précédente

- Aide sauvegarde GAME FILE :
  - `Sauvegarder sur un fichier utilisé efface ses données.`
  - `Appuyez sur “Attaque” pour sauver, “Retour” pour annuler.`
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

Le premier probe VWF, démarré directement sur la cellule 91 / `$6830`, est rejeté : il séparait les moitiés haut/bas des glyphes et laissait un demi-`G` résiduel. Le v2 a validé le renderer pair-aligné ; le v3 a ensuite corrigé uniquement le payload source complet `Graines de Mana`. Le comportement de ce backend reste inchangé par les optimisations VWF ultérieures ; l'agrégat n'est naturellement plus byte-identique à l'ancien probe puisque `vwf_ui`/`vwf_dialogues` ont été optimisés depuis. `vwf_ui` ne contient aucune prose française : il copie le champ source appartenant à `french_menus`.

## Choix de fenêtre — runtime-validé et promu

L'écran natif Window Settings est maintenant entièrement traduit **sans VWF**.
Le probe VWF a cassé l'écran et est rejeté. La solution finale conserve le
renderer fixe stock et synchronise largeur de cadre, ressource et placement :

- titre : `Choix de fenêtre` ;
- croix directionnelle : `Fond` à gauche/droite, `Bordure` en haut/bas ;
- aide :
  - `Choisissez le fond : gauche/droite, bordure : haut/bas.`
  - `Réglez la couleur : maintenez A, Y ou X et gauche/droite.`
  - `Appuyez sur B pour valider, Select pour annuler.`
- ressource fixe relocalisée : `$C7:4700-$472E` ;
- placement dix spans : `$C7:4730-$4759` ;
- frame titre `$C7:75CA : $07 -> $09` (18 cellules) ;
- pointeur texte `$C7:7828 : $73BC -> $4700` ;
- pointeur placement `$C7:782C : $7506 -> $4730` ;
- aide relocalisée en `$ED:8600+`.

Points de recherche importants : le parseur de placement laisse un curseur de
tuiles source utilisé ensuite par le frame script. Élargir seulement le cadre
produit un `Ch` parasite et décale l'aide de deux caractères. Ajouter `Fond` /
`Bordure` après le titre fait consommer ces nouveaux spans comme début du titre
et corrompt le cadre du bas. L'ordre final des données est donc structurel :
contrôles -> span `Fond` -> span `Bordure` -> `Choix de fenêtre`; le placement
termine sur `Bordure`, ce qui laisse le curseur exactement au début du titre.

Le fallback compact `$C7:73D1` reste `Réglage` et `C7:73C9` contient `Choisir`;
ces textes sont eux aussi dans `translations/menu_text_french.json`, jamais en
dur dans Python/ASM.

### `french_gfx` — boutons de manette — **runtime-validé / promu**

Le premier périmètre a été choisi avec l'utilisateur : remplacer globalement les
icônes graphiques A/B/X/Y de la version USA par la forme et les couleurs de la
VF SNES Rev 1, en utilisant un PNG éditable comme source.

Architecture implémentée :

- `components/french_gfx/assets/controller_button.png` : PNG indexé 16×16,
  indices 0..3 directement convertis en quatre tiles SNES 2bpp ;
- `$D2:D8F0-$D2:D92F` : ressource graphique commune remplacée par la forme VF ;
- `controller_button_palettes.json` : quatre rampes BGR15 exactes VF, ordre
  runtime `X/A/Y/B`, écrites à `$D2:DBCC-$D2:DBE3` ;
- `$C0:2116-$2118` : l'appel USA `JSR $212F` est remplacé par `NOP NOP NOP`,
  ce qui laisse le moteur employer les quatre palettes distinctes au lieu de les
  rabattre sur violet/lavande ;
- aucune allocation ROM libre, aucune WRAM et aucun hook par écran ;
- le PNG fourni se réencode bit-exactement aux 64 octets de la VF officielle,
  et le JSON reproduit bit-exactement les 24 octets de palettes VF.

Le builder protège les trois régions USA attendues avant écriture. Le standalone
`patches/french_gfx.ips` et `patches/all.ips` ont été reconstruits sans collision.
La validation binaire et la validation visuelle runtime sont terminées.
L'utilisateur a validé le résultat en jeu ; cette première fonctionnalité est
promue. Toute utilisation du graphisme UI commun profite automatiquement du
changement ; les lettres A/B/X/Y rendues comme du texte ne sont évidemment pas
concernées.

Le principe de séparation reste : `french_gfx` possède les **assets français
graphiques** ; aucun graphisme localisé ne doit être déplacé dans `vwf_ui` ou un
autre composant générique.

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

Le build promu traduit **420 ressources `$CA`** : les familles précédentes plus 60 descriptions d'armes non vides. Les 12 descriptions d'armes vides conservent leur payload stock. Le blob fait **7171 / 7315 octets** et reste intégralement dans l'allocation stock `$CA:98E1-$B573`. Trois ressources mappées restent volontairement non insérées avec le profil actuel car `°` entre en conflit avec la frontière DTE des ressources non-event. Les 42 descriptions de magie complètes vivent séparément à `$ED:9200+`.

Les catégories actuellement activées dans `components/french_resources/build_patch.py` sont :

`magic_name`, `mana_spirit_name`, `weapon_name`, `weapon_description`, `helmet_name`, `armor_name`, `accessory_name`, `item_name`, `menu_label`, `enemy_name`, `location_name`, `system_message`.

Les deux `system_message` restent exclus du mapping Android positionnel automatique : leur liaison placeholder est explicitement revue dans `translations/text_resources_reviewed_overrides.json`.

Les familles `weapon_description` (**72**) et `magic_description` (**42**) sont désormais **promues et runtime-validées**, mais avec deux architectures différentes : les armes restent dans le blob `$CA` avec la géométrie stock en segments fixes de 30 caractères ; les descriptions de magie complètes ne sont pas injectées dans l'étroit format stock et vivent dans une table VWF dédiée à `$ED:9200+`. Les 4 `location_name` non résolus restent non forcés.

L'ancien audit `inside / geometry_review` reste utile comme historique, mais ne doit plus servir à décider du rendu de ces deux familles : la géométrie cible a maintenant été prouvée en runtime. Voir `docs/WEAPON_MAGIC_DESCRIPTIONS_RESEARCH.md`.

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

## Baseline propre actuelle — 2026-09-20

Rebuild complet depuis la ROM USA propre après promotion des descriptions
d'armes, du panneau complet de descriptions de magie, des optimisations VWF
générales jusqu'au Stage 3A et du panneau magie jusqu'au Magic Stage 2 :

- `patches/french_menus.ips` SHA-256 : `8148c43b42ed8d0cf88edf367d48b27f7407e161b9246d0f32bd4c7aff353c36`
- `patches/french_name_entry_extended.ips` SHA-256 : `6a488bc7cd6afe1ee98176c5bed3b4670bf12c789b5f58622d6aab23217ea6da`
- `patches/french_resources.ips` SHA-256 : `692f42a3508b9bf9091b3600193f6051cc272f2eac8963e708554e639fa056ff`
- `patches/vwf_ui.ips` SHA-256 : `f8152b53963d1c29c45c28533c8475cb348fb560228de896dd4659667b9a6c3f`
- `patches/vwf_intro.ips` SHA-256 : `a5917976c7bf139e8f0ba69ee46f2ab0e23ab3db91453bf18bae6ba420d4110a`
- `patches/vwf_dialogues.ips` SHA-256 : `a78baba621265992d737bcf049b85effc34a01955a22e896b2120debef183ce4`
- `patches/french_dialogues.ips` SHA-256 : `dfc94882e4162052ccd7195839ef7ef7f5a89f1bec51847d905ca6b05ad2de31`
- `patches/french_gfx.ips` SHA-256 : `5753358d9603e6422a8ce03223e362900671e403fe83b9f57988400e3f1ffdd2`
- `patches/all.ips` SHA-256 : `8153dc0fb1f5c06f74b3daaae2fbf0e1c39fd0f48b271dd04097c6b975684e86`
- ROM reconstruite SHA-256 : `87e278de2112c2c12265f16f790c3a4f0ea14fe61651b6b2e5d8b4f3d926fbb4`
- checksum SNES : `$7E11`.

Rebuild complet et audit d'overlaps : **7272 octets identiques partagés**, **710
octets d'overlaps déclarés**. `check_source_hygiene.py`,
`check_roundtrip.py --scan-all-events` et `import_android_resources.py --check`
passent ; les **2048 scripts** sont correctement parsés. Un rebuild complet dans
un dossier de patches neuf est byte-identique aux patches promus. Par rapport à la baseline descriptions précédente, les changements de performance
touchent `vwf_ui.ips`, `vwf_dialogues.ips` et `all.ips`; les composants de contenu
comme `french_resources.ips` et `french_menus.ips` restent byte-identiques. La ROM de référence n'est pas incluse dans l'archive.

## Niveaux armes / magies — VWF des noms runtime-validée

Les titres fixes `Niv. armes` / `Niv. magies` et les placements
`$C7:754A/$7558` restent inchangés. Le helper de progression
`$C7:4F00-$4F22` reste runtime-validé et produit les formes `5:0 Nom` /
`5:10 Nom` avec un seul espace fixe avant le nom.

La VWF des noms est maintenant runtime-validée sur les listes armes **et**
magies. Architecture promue :

- les deux submits 8-lignes `$C7:65B0/$6615` passent par `$C7:4F30`;
- ce wrapper maintient `$7E:93CD=$5A` pendant l'appel synchrone stock
  `$C7:5D9A`, puis remet le scope à zéro ;
- `$C0:2366` route d'abord vers `$ED:8C00` ;
- `$ED:8C00` recherche dynamiquement dans `$7E:A1A4` le motif compact
  `d:d ` / `d:dd ` au lieu de supposer qu'il commence à la cellule 0 ;
- la cellule trouvée est la frontière réelle : le niveau fixe est préservé,
  l'ancien bitmap du nom est seul effacé, puis le nom déjà décodé est rendu
  avec les métriques VWF UI validées ;
- tout non-match retombe directement sur le backend Statut `$ED:8700` inchangé.

La cause de l'échec du candidat précédent est donc établie : il testait le
préfixe à `$A1A4+0`, alors que le préfixe est décalé dans le buffer décodé. Le
gate menu 5/6 n'est plus utilisé ni nécessaire. `french_resources` conserve
l'entière propriété des noms d'armes et d'esprits de magie.

La séquence de preuve est conservée dans
`docs/WEAPON_MAGIC_SKILL_ROW_VWF_RESEARCH.md` : probe 01 (batch prouvé), probe
02 (hypothèse cellule 0 réfutée), probe 03 (frontière dynamique prouvée), probe
04 (VWF dynamique runtime-validée). Les fichiers de probes eux-mêmes ont été
retirés de l'archive propre après promotion.


## Descriptions d’armes — runtime-validées

Les **72** ressources `weapon_description` sont désormais promues dans
`french_resources`. Le mapping Android a été corrigé : Android ajoute un
séparateur après chaque famille de 9 armes, donc il faut parcourir 8 blocs de 9
et sauter les 8 séparateurs. Après correction, le motif vide/non-vide correspond
72/72 au SNES.

Le renderer SNES a été prouvé en runtime : il consomme des segments fixes de
**30 caractères** séparés par `$7F`. Les grands espaces du premier probe venaient
d'un reflow aux mots; supprimer les séparateurs faisait au contraire déborder et
perdre des glyphes. La solution validée conserve donc le wording Android FR,
aplatit uniquement les blancs de mise en page, ajoute l'inset stock, puis coupe
à 30 caractères exacts. Les **12** descriptions Android vides préservent leur
payload stock vide byte-identique.

## Descriptions de magie — panneau VWF 3×480 px runtime-validé

Le format stock `13 + 24` par sort est trop étroit pour conserver les phrases
Android FR complètes. La solution finale ne raccourcit **aucune** des 42
descriptions.

Architecture validée :

- le panneau stock est six demi-slots de **30 cellules / 240 px**, disposés en
  trois lignes : `0+1`, `2+3`, `4+5` ;
- `$A191=$03C0` confirme qu'un passage vaut 30 tuiles SNES 4bpp ; une paire vaut
  donc **60 cellules / 480 px** ;
- `$C7:649E`, `$6501`, `$650E` sont enveloppés mais rejouent le comportement
  stock. `$A1D0` est capturé à `$6501` : aucune reconnaissance du texte affiché
  n'est utilisée ;
- Lumina brut `42..47` est remappé comme stock en `36..41` ;
- les IDs sont invalidés à `$FF` avant chaque rebuild. La condition stock de
  déblocage reste donc autoritaire : un esprit verrouillé n'émet aucun ID et
  n'affiche aucune description ;
- une ligne non émise (cas Dryade/Mana dans l'état testé) est explicitement
  vide, ce qui évite la duplication d'un ancien bitmap ;
- `$C7:4F40-$4FB4` clone le six-pass stock. Aucun DMA maison n'est conservé ;
- `$C0:2366 -> $ED:8E00` exige l'exact stacked return du clone. Ce filtrage a
  restauré GAME SELECT après le probe qui le faisait glitcher;
- une ligne complète est rasterisée en VWF dans `$7E:9000-$92FF`, puis coupée
  **après rasterisation** en cellules 0..29 et 30..59 pour les deux passages
  stock. Le milieu est donc parfaitement continu ;
- `french_resources` possède les 42 records de 80 octets à `$ED:9200-$9F1F` et
  le marker `MFV1` à `$ED:9F20-$9F23`; `vwf_ui` reste présentation uniquement.
  Sans marker, il retombe sur le renderer stock ;
- largeur maximale actuelle : **445 px**, plafond de build **472 px**, largeur
  logique disponible **480 px**.

Aucun diagnostic spécial Ombre n'est conservé dans la version propre. Le slot
Ombre vide observé sur une sauvegarde était simplement non débloqué. Le détail
de toute la séquence de probes et des pistes rejetées est dans
`docs/WEAPON_MAGIC_DESCRIPTIONS_RESEARCH.md`.

## Prochaine reprise demandée — texte d’aide par défaut du menu

**Ne pas commencer automatiquement avant lecture de l'archive et compte rendu.**
La prochaine tâche est la traduction du texte par défaut encore anglais dans le
panneau inférieur de `Niv. armes / Niv. magies` (le texte d'instructions affiché
avant de demander les données d'un esprit/arme).

Méthode demandée :

1. identifier le **texte japonais original** et son chemin/source exact dans la
   ROM JPN ;
2. vérifier s'il existe une entrée correspondante dans les ressources **Android
   EN/FR** et établir l'identité, sans supposer un mapping à partir de l'anglais
   SNES seul ;
3. proposer une adaptation française fidèle au japonais/Android FR et compatible
   avec la géométrie réelle de ce panneau ;
4. discuter la formulation avec l'utilisateur **avant insertion** ;
5. seulement après validation linguistique, implémenter et tester sans toucher
   aux descriptions armes/magies désormais gelées.

Les ROMs JPN/FRA/USA utilisées pendant la session ne doivent évidemment jamais
être redistribuées.


## VWF performance — état au 2026-09-20

- Stage 1 runtime-validé : Ring limité au nombre réel de caractères.
- Stage 2A runtime-validé : test de scope de ligne inliné.
- Stage 2B runtime-validé : phase/Y calculés une fois par caractère et fast path privé.
- Premier Stage 2C **rejeté** : écran noir à l'ouverture du Ring. Cause prouvée :
  `JMP (addr,X)` lit son pointeur en bank 0 alors que la table avait été placée
  en `$ED:7Axx`. Ne jamais restaurer cette variante.
- Stage 2C-R1 runtime-validé : il repart de Stage 2B et remplace ce dispatch par
  une lecture longue explicite de table `$ED` + cible synthétique `PHA/RTS`.
  Helper `$ED:7AB0-$7AF2`, 67/80 octets.
- Stage 3A runtime-validé : conserver le contour stock `$C0:162C`, mais borner le
  second passage de réparation VWF à `min(32, $938F + 1)` cellules. Le snapshot
  `$938F` est désormais garanti avant le contour même sur les renderers
  true-count (dont Ring), sans changer les décisions de progression `$A1CE`.
  Le `+1` est une marge conservatrice : l'audit exhaustif du jeu de glyphes
  réellement installé ne trouve même aucun pixel d'encre au-delà de l'avance.
- `$C7:44C0/$4560/$4C90` sont inchangés ; intro, Caractéristiques, noms
  armes/magies et panneau magie restent sur leurs chemins validés.

Le builder `vwf_dialogues` installe aussi les helpers `$ED:7A80+` afin que son
IPS standalone reste autonome, comme `vwf_ui`.


## Performance panneau de magie — état au 2026-09-20

- La base générale VWF inclut désormais Stage 3A runtime-validé.
- Magic Stage 1 runtime-validé : sur la passe droite, les glyphes avant 224 px
  n'étaient plus rerasterisés; cette étape a confirmé que le double rendu était
  une cause majeure du délai.
- Magic Stage 2 **candidat** : la passe gauche conserve le bitmap logique 60
  cellules et laisse le convertisseur stock `$C0:2366` produire aussi la moitié
  droite dans sa zone de sortie non-DMA `$7E:97C0-$9B7F`. La passe droite copie
  ces 960 octets déjà convertis vers `$9400-$97BF` et saute le second raster +
  le second convertisseur, tout en gardant les six DMA stock.
- Aucun texte, ID, condition de déblocage, destination VRAM ou ordre des six
  passes n'est modifié. Les lignes non émises restent sur le chemin blanc
  conservateur.
