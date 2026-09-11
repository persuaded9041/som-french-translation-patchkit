Je poursuis le projet Secret of Mana FR à partir du **Round 72 — automatic 216 px completion**.

Commence par lire `README.md`, puis `docs/HANDOFF.md`. L’archive fournie est prioritaire sur GitHub.

État dialogues : **701/701 événements jouables complets, 0 PARTIEL, 0 erreur, 0 warning, 0 wrap implicite**. Contrat VWF runtime validé : **38 glyphes max et 216 px max** pour une ligne de dialogue ordinaire. Préserver toutes les décisions Round 67–72 et ne pas rouvrir les dialogues.

Prochaine étape : préparer la **traduction des objets**. **Ne lance aucune traduction ni insertion tout de suite.** Je veux d’abord discuter et valider la procédure.

Inspecte `docs/TEXT_RESOURCES.md`, `assets/text_resources.json`, les sources Android disponibles et les outils d’extraction/import pertinents. Le premier périmètre envisagé est `$0B9-$0C5` (13 `item/special names`). Propose une méthode entièrement reproductible : identification SNES ↔ Android, provenance EN/FR, contraintes de longueur/charset/UI, stratégie d’insertion ou de repacking si nécessaire, fichier de traduction sparse, checks déterministes et HTML de revue avant insertion.

Ne mets pas de texte français en dur dans le code : les traductions devront pouvoir être régénérées depuis les sources Android, sauf éventuels suppléments explicitement revus plus tard.
