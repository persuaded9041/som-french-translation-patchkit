Je poursuis le projet Secret of Mana FR à partir du **Round 84 — Name Entry prefill cleanup / fully runtime-validated checkpoint**.

Commence par lire `README.md`, puis `docs/HANDOFF.md`, puis `docs/UI_VWF.md`. Consulte `docs/FORGE_VWF_RESEARCH.md` uniquement pour l’historique Forge et les mauvaises pistes déjà rejetées. L’archive fournie est prioritaire sur GitHub.

Les dialogues restent verrouillés au Round 72 : **701/701 événements complets, 0 PARTIEL, 0 erreur, 0 warning, 0 wrap implicite**. Ne les modifie pas.

Le chantier Name Entry est terminé et runtime-validé : `name_entry_extended` = 3 rangées génériques ; `french_name_entry_extended` ajoute la 4e rangée FR ; `name_entry_prefill` propose les noms US éditables ; `french_name_entry_prefill` propose **Randy / Prim / Popoï**. Le `ï` réel de `Popoï` a aussi été validé dès le premier écran via un diagnostic temporaire. Ne rouvre pas ce chantier sans régression démontrée.

`vwf_ui` est autonome et son backend Forge est verrouillé. La VWF est déjà visible dans les Ring Menus, vraisemblablement par effet du chemin UI existant : **ne cherche pas à l’activer de nouveau**. Reprends l’étude UI VWF en caractérisant d’abord précisément pourquoi/par quel builder-submit le Ring Menu passe déjà en VWF, avec une sonde locale inoffensive si nécessaire. Ensuite, poursuis vers les **messages/menus de ramassage d’objets**. Pour chaque nouvelle famille, prouve le builder/submit exact puis ajoute seulement un gate one-shot étroit ; aucun gate VWF global.

Teste toujours `vwf_ui` seul sur ROM USA propre puis `all.ips`, avec régressions GAME SELECT, Forge, dialogue Watts et dialogues ordinaires.
