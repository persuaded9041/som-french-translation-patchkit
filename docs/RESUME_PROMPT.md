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

## État GAME FILE `PO` à préserver

Le sujet de l'espace devant la monnaie est **terminé et runtime-validé**. Le rendu final est `1254536 PO`, sans déplacement de l'ancre droite de `PO`.

Le chemin stock est hybride et doit rester ainsi : les 16 premières cellules de la ligne Argent sont toujours réécrites dynamiquement, tandis que la colonne 16 du template conserve le second glyphe de l'unité. La solution promue utilise `7 espaces + 7 cellules montant + 1 espace + currency[0]` dans la fenêtre dynamique ; `currency[0]` reste dérivé du JSON `C7:7394`, et `currency[1]` reste dans le template. Le helper runtime-validé est à `$C7:4D32-$4D3B`. Ne pas réintroduire les anciens probes `PPO` / `P O`.

## Priorité après mon feu vert

Reprendre la traduction des **ressources et menus encore manquants**, par petits lots cohérents avec validation humaine entre les lots. Comparer US / Android FR / VF SNES officielle / japonais lorsque c'est utile. Tout texte français doit rester sous `translations/*.json`, jamais codé en dur dans Python ou ASM.

État à préserver :

- Actions des personnages : `Attaquer`, `Défendre`, `S'approcher`, `S'éloigner`, renderer fixe stock ; aides runtime-validées `Choisissez le type d'action. Validez avec “Attaque”.` et `Jusqu'où charger la jauge ? Validez avec “Attaque”.` ;
- aide sauvegarde : `Pressez “Attaque” pour sauver, “Retour” pour annuler.` ;
- GAME FILE : `Graines Mana` runtime-validé ;
- Name Entry : `Choisissez un caractère avec la croix directionnelle.` ; conserver `B` et `Start` physiques, intentionnels avant remapping ;
- écran Statut : traductions déjà revues dans les JSON mais encore largement **translation-only** tant que leur renderer n'est pas promu ;
- dialogues : corpus gelé et validé, ne pas relancer d'audit global et ne pas modifier mapping/segmentation.
