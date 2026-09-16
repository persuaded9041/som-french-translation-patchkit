# Prompt de reprise — Secret of Mana FR — nouvelles traductions de ressources

Je poursuis le projet **Secret of Mana FR** à partir de l'archive propre fournie. L'archive est **prioritaire sur GitHub**. La ROM de référence reste **Secret of Mana (USA), non headerée** et ne doit jamais être redistribuée.

Commence par lire intégralement :

- `README.md`
- `docs/HANDOFF.md`
- `docs/TEXT_RESOURCES.md`
- `docs/TRANSLATIONS.md`
- `docs/COMPATIBILITY.md`
- `docs/MEMORY_MAP.md`
- `components/french_resources/README.md`

La prochaine tâche est d'**ajouter progressivement de nouvelles traductions de ressources non-dialogue**.

Le corpus de dialogues est gelé : ne modifie aucun dialogue, mapping Android dialogue ou segmentation.

Préserve l'architecture actuelle :

- `french_resources` possède les ressources `$CA`, les 9 réponses shop/forge D9 et les deux littéraux `GP -> PO` ;
- aucun `french_shop_text.ips` ne doit réapparaître ;
- `vwf_ui` ne possède aucun texte français et ne doit être modifié que si une nouvelle ressource révèle un problème de rendu concret ;
- aucune prose française ne doit être codée en dur dans Python/ASM : traductions et adaptations validées restent dans les JSON de `translations/` ;
- les correctifs runtime validés (`Haubert magique`, +1 px gauche, MONEY 11 cellules + close seed `$09`) sont à préserver.

Pour chaque nouveau lot, identifie d'abord les IDs/catégories et leur provenance Android EN/FR, propose les traductions à valider, puis seulement après validation insère-les via le pipeline `french_resources`. Les familles `weapon_description` (72) et `magic_description` (42) sont déjà mappées mais non promues et peuvent servir de point de départ si elles correspondent aux ressources que je veux traiter. N'active pas une catégorie entière sans vérifier son encodage, sa taille et son contexte d'affichage.

Procède par petits lots et fournis à chaque checkpoint un `all.ips` complet applicable à la ROM USA propre, ainsi qu'un `french_resources.ips` standalone si le lot touche ce composant.
