Je poursuis le projet Secret of Mana FR à partir du **Round 77 — intro VWF/French payload split**.

Commence par lire `README.md`, puis `docs/HANDOFF.md`, puis **`docs/UI_VWF.md`**. Consulte `docs/FORGE_VWF_RESEARCH.md` uniquement pour l'historique Forge et les mauvaises pistes déjà rejetées. L'archive fournie est prioritaire sur GitHub.

Les dialogues restent verrouillés au Round 72 : **701/701 événements complets, 0 PARTIEL, 0 erreur, 0 warning, 0 wrap implicite**. Ne les modifie pas.

Les composants utilisent désormais des IDs sémantiques non numérotés. Les familles principales sont `french_*` pour les contenus traduits et `vwf_*` pour les moteurs VWF. L'ordre d'assemblage est porté explicitement par `build_order` dans les manifests, et non par le nom des dossiers.

`french_intro` et `vwf_intro` sont désormais séparés. `french_intro` possède le payload FR de `$0400`, son layout, les glyphes et le DTE privé ; `vwf_intro` possède uniquement le runtime VWF/parser. Leur union reproduit exactement l'ancien composant hybride et `all.ips` reste byte-identique au Round 76. Ne les refusionne pas.

`vwf_ui` est autonome et runtime-validé. Son backend Forge est terminé : tag armé uniquement au submit exact `$00:19D0`, parser/buffer stock, marge logique +3, nom d'arme VWF et suffixe `→...` repositionné dynamiquement. GAME SELECT et le dialogue de Watts restent stock avec `vwf_ui` seul. **Ne rouvre pas la Forge sauf régression démontrée.**

`french_resources` est également autonome et `all.ips` inclut reproductiblement les noms de ressources FR validés. `vwf_ui` ne doit pas dépendre de `french_resources` et ne doit posséder aucune traduction.

Observation runtime importante : la VWF fonctionne déjà dans les Ring Menus, probablement via un chemin partagé exposé par le travail Forge. Avant toute modification Ring Menu, caractérise et prouve ce chemin exact au lieu de chercher à réactiver la VWF. Ensuite, poursuis sur les **messages/menus de ramassage d'objets** : retrouve et prouve d'abord le builder/submit exact avec une sonde locale inoffensive, puis ajoute seulement si nécessaire un gate one-shot étroit dans `vwf_ui`. Ne crée aucun gate VWF global. Teste toujours `vwf_ui` seul sur ROM USA propre, puis `all.ips`, avec régressions GAME SELECT / Forge / dialogue Watts.
