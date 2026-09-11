Je poursuis le projet Secret of Mana FR à partir du **Round 75 — UI VWF foundation / resource-names checkpoint**.

Commence par lire `README.md`, puis `docs/HANDOFF.md`, puis **`docs/UI_VWF.md`**. Consulte `docs/FORGE_VWF_RESEARCH.md` uniquement pour l'historique Forge et les mauvaises pistes déjà rejetées. L'archive fournie est prioritaire sur GitHub.

Les dialogues restent verrouillés au Round 72 : **701/701 événements complets, 0 PARTIEL, 0 erreur, 0 warning, 0 wrap implicite**. Ne les modifie pas.

`09_ui_vwf` est maintenant un composant autonome runtime-validé. Son backend Forge est terminé : tag armé uniquement au submit exact `$00:19D0`, parser/buffer stock, marge logique +3, nom d'arme VWF et suffixe `→...` repositionné dynamiquement. GAME SELECT et le dialogue de Watts restent stock avec 09 seul. **Ne rouvre pas la Forge sauf régression démontrée.**

`10_resource_names_fr` est également autonome et `all.ips` inclut désormais reproductiblement les noms de ressources FR validés. 09 ne doit pas dépendre de 10 et ne doit pas posséder de traduction.

Prochaine étape : poursuivre la **VWF d'interface**, d'abord sur les **Ring Menus**, puis sur les **messages/menus de ramassage d'objets**. Pour chaque famille, retrouve et prouve d'abord le builder/submit exact avec une sonde locale inoffensive ; ajoute ensuite un gate one-shot étroit dans 09. Ne crée aucun gate VWF global. Teste toujours 09 seul sur ROM USA propre, puis `all.ips`, avec régressions GAME SELECT / Forge / dialogue Watts.
