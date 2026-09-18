# Prompt de reprise

Je poursuis le projet **Secret of Mana FR** à partir de l'archive fournie. **L'archive est prioritaire sur GitHub.** La ROM de référence reste **Secret of Mana (USA), non headerée** et ne doit jamais être redistribuée.

## Première consigne impérative

Commence par **étudier l'archive seulement**. Lis intégralement :

- `README.md`
- `docs/HANDOFF.md`
- `docs/MEMORY_MAP.md`
- `docs/COMPATIBILITY.md`
- `docs/MENU_TEXT.md`
- `docs/INTERFACE_TEXT.md`
- `docs/TRANSLATIONS.md`
- `components/french_gfx/README.md`
- `components/french_gfx/docs/MEMORY_MAP.md`
- `components/french_menus/README.md`
- `components/french_resources/README.md`
- `components/vwf_ui/README.md`

Après cette étude, fais uniquement un bref compte rendu et attends mon feu vert explicite avant toute nouvelle modification.

## Priorité actuelle : `french_gfx`

La traduction des menus et ressources est **mise en pause** et reste dans le backlog. Ne relance pas automatiquement les lots de traduction.

Le composant `french_gfx` existe maintenant. Sa première fonctionnalité est **runtime-validée et promue** : elle remplace globalement les icônes graphiques de boutons A/B/X/Y USA par la forme et les couleurs de la VF SNES Rev 1 :

- PNG source indexé 16×16 : `components/french_gfx/assets/controller_button.png` ;
- conversion au build vers les quatre tiles 2bpp `$D2:D8F0-$D2:D92F` ;
- palettes françaises exactes X/A/Y/B à `$D2:DBCC-$D2:DBE3` ;
- neutralisation de l'override USA à `$C0:2116` (`JSR $212F` -> `NOP NOP NOP`) ;
- aucune allocation ROM libre / WRAM ;
- `patches/french_gfx.ips` et `patches/all.ips` sont reconstruits ; validation binaire et validation visuelle runtime OK.

La prochaine étape est de **demander à l'utilisateur quel nouvel élément graphique il souhaite traiter**. Ne commence pas d'implémentation avant cette discussion : étudier ensuite le stockage et le rendu stock de la cible, puis proposer une architecture propre. Les lettres A/B/X/Y rendues comme texte ne sont pas concernées par la fonctionnalité déjà validée.

## État runtime à préserver

- **Choix de fenêtre** : renderer fixe stock, sans VWF ; titre `Choix de fenêtre`; `Fond` gauche/droite; `Bordure` haut/bas; aides `Choisissez le fond : gauche/droite, bordure : haut/bas.`, `Réglez la couleur : maintenez A, Y ou X et gauche/droite.`, `Appuyez sur B pour valider, Select pour annuler.`. Ressource `$C7:4700`, placement `$C7:4730`, frame `$C7:75CA=$09`.
- aide sauvegarde : `Appuyez sur “Attaque” pour sauver, “Retour” pour annuler.`
- GAME FILE argent : `1254536 PO`, architecture hybride 16 cellules, helper `$C7:4D32-$4D3B`.
- GAME FILE : `Sauvegardes` fixe et `Graines de Mana` via la VWF ultra-localisée `$AD`, valeur dynamique stock.
- Actions des personnages : `Attaquer`, `Défendre`, `S'approcher`, `S'éloigner`, renderer fixe stock ; aides runtime-validées.
- Name Entry : `Choisissez un caractère avec la croix directionnelle.` ; conserver `B` et `Start` physiques.
- écran Statut : traductions déjà revues dans les JSON mais encore largement **translation-only**.
- dialogues : corpus gelé et validé ; ne pas relancer d'audit global, ne pas modifier mapping/segmentation.

## Backlog menus / ressources — à garder pour plus tard

Ne pas le supprimer du handoff, mais ne pas le reprendre pendant la phase `french_gfx`. Les familles importantes encore à traiter incluent les menus natifs restant à promouvoir, l'écran Statut, ainsi que les descriptions d'armes/magie `$CA` qui nécessitent revue de géométrie.
