# Prompt de reprise — Secret of Mana FR — bug `Haubert magique` en boutique

Je poursuis le projet **Secret of Mana FR** à partir de l'archive propre fournie.
L'archive est **prioritaire sur GitHub**. La ROM de référence reste **Secret of
Mana (USA), non headerée** et ne doit jamais être redistribuée.

Commence par lire intégralement :

- `README.md`
- `docs/HANDOFF.md`
- `docs/COMPATIBILITY.md`
- `docs/MEMORY_MAP.md`
- `docs/UI_VWF.md`
- `components/vwf_ui/README.md`
- `components/vwf_ui/docs/MEMORY_MAP.md`
- `components/french_resources/README.md`

Le corpus de dialogues est gelé : ne modifie aucun dialogue, mapping Android FR
ou segmentation.

## Baseline validée à préserver

La boutique est maintenant runtime-validée :

- VWF des noms d'objets achat/vente via le tag dédié `$AA` ;
- VWF des messages Shop D9 via `$A9` ;
- `PO` appartient à `french_resources`, jamais à `vwf_ui` :
  `$C7:7B6A` et `$D0:D894` sont traduits `GP -> PO` depuis
  `translations/french_resources_reviewed_literals.json` ;
- `vwf_ui` ne fait que le rendu/géométrie : prix à 164 px + séparateur 4 px,
  MONEY type 2 à 11 cellules + séparateur 3 px ;
- `vwf_ui` est standalone et ne dépend plus de `vwf_dialogues` ;
- GAME SELECT fonctionne ; Ring `$A8`, Forge `$A7`, Shop D9 `$A9`, merchandise
  `$AA` et MONEY `$AB` restent isolés.

Ne refactore pas cette architecture sans nécessité directe.

## Bug à corriger

Chez le vendeur, l'armure **`Haubert magique`** apparaît comme **`aubert magique`** :
le caractère le plus à gauche (`H`) n'est pas visible. Les autres objets testés
s'affichent correctement.

Ressource déjà identifiée :

- ROM/resource : **`CA:9F8E`**
- resource ID : **`$09C`**
- catégorie : **`armor_name`**
- USA : **`Magical Armor`**
- FR généré : **`Haubert magique`**
- renderer concerné : boutique merchandise VWF **tag `$AA`**.

Commence par reproduire et expliquer précisément pourquoi **cet item seulement**
perd son premier caractère. Compare-le à un item connu bon, par exemple
`Noix magique` : source `$CA`, flux de décodage, contenu/indices du buffer stock,
copie privée VWF, position de départ, éventuel shift/clipping et commit de cellules.

Procède par petites preuves. Ne change pas le texte `Haubert magique` pour
contourner le bug. N'implémente un correctif qu'une fois la cause attribuée, puis
fournis un **`all.ips` complet applicable à la ROM USA propre** et, si le
correctif touche `vwf_ui`, un test standalone `vwf_ui.ips` sur ROM propre.
