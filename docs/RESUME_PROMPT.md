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
- `components/french_menus/README.md`
- `components/french_menus/docs/MEMORY_MAP.md`
- `components/french_resources/README.md`
- `components/vwf_ui/README.md`

Après cette étude, **ne lance aucune recherche supplémentaire, aucun patch, aucun build expérimental et aucune traduction**. Fais uniquement un bref compte rendu de ce que tu as compris et **attends mon feu vert explicite**.

## Nouvelle priorité après discussion : futur composant `french_gfx`

La traduction des menus et ressources est **mise en pause**. Elle reste dans le backlog et sera reprise plus tard ; ne relance pas automatiquement les lots de traduction.

Je souhaite discuter d'un nouveau composant **`french_gfx`** destiné à remplacer certains éléments graphiques du jeu par des versions spécifiques à la traduction française. **Ne commence pas l'implémentation avant qu'on en ait discuté après l'étude de l'archive.** En particulier, avant mon accord explicite :

- ne crée pas `components/french_gfx/` ;
- ne réserve aucune zone ROM ;
- n'extrais, ne redessine et ne réinjecte aucun graphisme ;
- ne produis aucun IPS/probe ;
- n'invente pas encore le format des assets ni l'architecture du composant.

La première étape sera de discuter des éléments graphiques que je veux remplacer, puis d'étudier leur stockage/rendu stock et de choisir une architecture propre. Les assets français devront appartenir à `french_gfx`; éviter de mettre des données localisées dans un composant générique.

## État runtime à préserver

- **Choix de fenêtre** : renderer fixe stock, sans VWF ; titre `Choix de fenêtre`; `Fond` gauche/droite; `Bordure` haut/bas; aides `Choisissez le fond : gauche/droite, bordure : haut/bas.`, `Réglez la couleur : maintenez A, Y ou X et gauche/droite.`, `Appuyez sur B pour valider, Select pour annuler.`. Ressource `$C7:4700`, placement `$C7:4730`, frame `$C7:75CA=$09`. Ne réintroduire aucun des probes VWF/glitchés.
- aide sauvegarde : `Appuyez sur “Attaque” pour sauver, “Retour” pour annuler.`
- GAME FILE argent : `1254536 PO`, architecture hybride 16 cellules, helper `$C7:4D32-$4D3B`.
- GAME FILE : `Sauvegardes` fixe et `Graines de Mana` via la VWF ultra-localisée `$AD`, valeur dynamique stock.
- Actions des personnages : `Attaquer`, `Défendre`, `S'approcher`, `S'éloigner`, renderer fixe stock ; aides runtime-validées.
- Name Entry : `Choisissez un caractère avec la croix directionnelle.` ; conserver `B` et `Start` physiques.
- écran Statut : traductions déjà revues dans les JSON mais encore largement **translation-only**.
- dialogues : corpus gelé et validé ; ne pas relancer d'audit global, ne pas modifier mapping/segmentation.

## Backlog menus / ressources — à garder pour plus tard

Ne pas le supprimer du handoff, mais ne pas le reprendre pendant la phase `french_gfx`. Les familles importantes encore à traiter incluent les menus natifs restant à promouvoir, l'écran Statut, ainsi que les descriptions d'armes/magie `$CA` qui nécessitent revue de géométrie.
