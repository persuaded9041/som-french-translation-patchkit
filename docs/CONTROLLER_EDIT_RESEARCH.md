# Controller Edit / configuration de la manette — recherche 2026-09-26

## Statut

**Runtime-validé / promu le 2026-09-26.**

Baseline : aides Niv. armes / Niv. magies et `Épée` confirmées en jeu par
l'utilisateur le 2026-09-26. `dialogue_background` reste volontairement hors
scope.

## Comparaison JAP / USA / France

Les trois ROMs SNES ont été comparées avant insertion.

| Fonction | Japonais | USA | France officielle | Projet |
| --- | --- | --- | --- | --- |
| sélection | `セレクト` | `SELECT` | `Flèche` | `Choisir` |
| titre | `コントローラーエディット` | `CONTROLLER EDIT` | `Editer Commande` | `Réglage manette` |
| menu joueur | `じぶんのコマンド` | `YOUR ICONS` | `Vos icônes` | `Votre menu` |
| menus alliés | `なかまのコマンド` | `ALLY'S ICONS` | `Icônes Alliés` | `Menus alliés` |
| attaque | `アタック` | `ATTACK` | `Attaque` | `Attaque` |
| course | `ダッシュ` | `DASH` | `Foncer` | `Course` |

Le japonais emploie `コマンド` (commande/action) plutôt que l'équivalent
littéral de l'anglais `ICONS`. La formulation du projet décrit donc directement
le menu auquel les boutons donnent accès.

Le texte d'aide japonais indique explicitement que Start valide et Select
annule. L'USA conserve cette distinction (`START TO SET`, `SELECT TO EXIT`),
alors que la VF officielle supprime Select et traduit le changement de type de
contrôleur par « inverser la manette de jeu ». Le projet restaure l'information
de l'original :

1. `Pour changer un bouton, maintenez-le enfoncé puis`
2. `choisissez sa fonction avec gauche/droite. Relâchez.`
3. `L/R : change le type de manette.`
4. `Start : valider.  Select : annuler.`

## Structure USA et intégration

Ressource native : `C7:7400-C7:745A` (91 octets avec terminateur).

Les emplacements physiques disponibles sont suffisants sans modifier les
descripteurs, les cadres ou le renderer :

- `C7:7409` SELECT : 8 octets disponibles ;
- `C7:7411` titre : 18 ;
- `C7:7423` menu joueur : 14 ;
- `C7:7431` menus alliés : 14 ;
- `C7:743F` attaque : 14 ;
- `C7:744D` course : 13 octets stockés + le terminateur comme dernière cellule logique.

Le placement natif de `SELECT` reste inchangé (`C7:7522+`) et le layout/cadres
restent inchangés (`C7:75D1+`). Aucun nouveau hook n'est ajouté.

Aide : pointeur stock `C0:33CA -> C7:795F`. Le bloc USA occupe exactement
201 octets jusqu'à `C7:7A27`. Le texte projet occupe 172 octets, séparateurs
`$7F` et terminateur `$00` compris, et est donc écrit en place.

## Validation statique

- `french_menus` compile depuis une ROM USA propre ;
- build agrégé réussi, 15 composants, sans `dialogue_background` ;
- ROM agrégée : 3 MiB, checksum SNES recalculé `$15A3` ;
- par rapport au candidat skill-help validé, les changements hors checksum sont
  limités aux six champs `C7:7409-C7:7452` et au bloc d'aide `C7:795F+`.

## Test runtime demandé

1. ouvrir le menu de configuration de la manette ;
2. vérifier les six libellés et l'absence de texte résiduel / chevauchement ;
3. vérifier les quatre lignes d'aide ;
4. tester gauche/droite lors du remappage, puis relâcher un bouton ;
5. tester L/R pour le type de manette ;
6. vérifier Start (validation) et Select (annulation/sortie) ;
7. revenir dans les menus déjà validés pour un contrôle rapide de non-régression.


## Validation runtime

Validation utilisateur le **2026-09-26** :

- les six libellés du menu sont corrects ;
- les quatre lignes d'aide sont correctes ;
- le remappage et les commandes L/R, Start et Select fonctionnent ;
- aucun problème visuel ou régression signalé.

Le candidat `controller-edit-20260926` est donc **promu comme nouvelle baseline**.
