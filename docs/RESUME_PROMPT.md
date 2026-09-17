# Prompt de reprise

Je poursuis le projet **Secret of Mana FR** à partir de l'archive fournie. **L'archive est prioritaire sur GitHub.** La ROM de référence reste **Secret of Mana (USA), non headerée** et ne doit jamais être redistribuée.

## Première consigne impérative

Commence par **étudier l'archive seulement**. Lis intégralement :

- `README.md`
- `docs/HANDOFF.md`
- `docs/MENU_TEXT.md`
- `docs/INTERFACE_TEXT.md`
- `docs/TRANSLATIONS.md`
- `docs/MEMORY_MAP.md`
- `components/french_menus/README.md`
- `components/french_menus/docs/MEMORY_MAP.md`
- `components/french_resources/README.md`
- `components/vwf_ui/README.md`

Après cette étude, **ne lance aucune recherche supplémentaire, aucun patch, aucun build expérimental et aucune traduction**. Fais uniquement un bref compte rendu de ce que tu as compris et **attends mon feu vert explicite**.

## Priorité 1 après mon feu vert : espace devant `PO` dans GAME FILE

La baseline runtime-validée affiche correctement `PO`, mais collé au montant (`1254536PO`). Le bug précédent `GO` est résolu : le chemin GAME FILE est hybride, avec un premier `G` stock codé séparément à `$C7:54A9` (opérande `$C7:54AA`) et l'autre glyphe provenant du champ `C7:7394`. Les probes `PO -> GO`, `XO -> GO`, `XX -> GX` ont prouvé ce mécanisme ; le builder dérive maintenant le premier glyphe depuis le JSON et affiche bien `PO`.

Le but suivant est, si possible, d'obtenir `1254536 PO` **sans déplacer `PO` vers la droite**. Repartir uniquement de la baseline validée de l'archive. Ne réutiliser aucun ancien probe IPS. Les essais précédents de déplacement du formateur de chiffres ont produit :

- écran noir à cause d'un hook posé à `$C7:54A7` au lieu du début du `JSR` à `$C7:54A6` ;
- après correction du hook : `PPO` ;
- une variante de neutralisation : `P O` ;
- d'autres tentatives de neutralisation des cellules stock/relocalisées : toujours `PPO`.

Ces résultats montrent qu'il reste une superposition/copie runtime mal comprise. **Tracer d'abord précisément les écritures et le buffer autour de `$C7:54A6-$54B0`**, puis avancer par micro-probes démontrables. Ne promouvoir aucun changement avant validation runtime.

## Priorité 2

Une fois le sujet `PO` terminé ou explicitement abandonné, reprendre la traduction des **ressources et menus encore manquants**, par petits lots cohérents avec validation humaine entre les lots. Comparer US / Android FR / VF SNES officielle / japonais lorsque c'est utile. Tout texte français doit rester sous `translations/*.json`, jamais codé en dur dans Python ou ASM.

État à préserver :

- Actions des personnages : `Attaquer`, `Défendre`, `S'approcher`, `S'éloigner`, renderer fixe stock ; aides runtime-validées `Choisissez le type d'action. Validez avec “Attaque”.` et `Jusqu'où charger la jauge ? Validez avec “Attaque”.` ;
- aide sauvegarde : `Pressez “Attaque” pour sauver, “Retour” pour annuler.` ;
- GAME FILE : `Graines Mana` runtime-validé ;
- Name Entry : `Choisissez un caractère avec la croix directionnelle.` ; conserver `B` et `Start` physiques, intentionnels avant remapping ;
- écran Statut : traductions déjà revues dans les JSON mais encore largement **translation-only** tant que leur renderer n'est pas promu ;
- dialogues : corpus gelé et validé, ne pas relancer d'audit global et ne pas modifier mapping/segmentation.
