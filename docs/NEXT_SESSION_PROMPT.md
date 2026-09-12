Je poursuis le projet Secret of Mana FR à partir du **Round 85 — post-audit dialogue coverage/layout cleanup**.

Commence par lire `README.md`, puis `docs/HANDOFF.md`. L’archive fournie est prioritaire sur GitHub. Ne redistribue jamais les ROMs de référence.

État dialogues : **701/701 complets, 0 PARTIEL, 0 erreur, 0 warning, 0 wrap implicite** au simulateur ; **1815 IDs sémantiques acceptés / 1947 entrées JSON** ; **17 surcharges manuelles = 15 traduites + 2 suppressions**. Le nouvel audit de couverture/layout est accepté pour poursuivre le développement, mais sa validation runtime détaillée est volontairement différée au prochain playthrough complet. Ne rouvre pas les textes sans régression concrète.

Priorité de cette session : **maintenance du pipeline**, pas nouvelle traduction.

1. Profiler `python3 tools/import_android_text.py --only dialogue-format-mass --rom "Secret of Mana (USA).sfc"` et identifier les vrais hotspots. Le PC cible est un **i5-10600K, 6 cœurs / 12 threads**. Chercher d’abord cache/mémoïsation, puis parallélisation event-local via multiprocessing si sûre. Prévoir un `--jobs N` déterministe (commencer par 4–6 workers) et prouver que `--jobs 1` et `--jobs N` génèrent des fichiers byte-identical / mêmes compteurs.
2. Réduire le bruit historique du dépôt. Faire d’abord un audit de dépendances puis nettoyer par petits lots : vieux `dialogues_review_round*`, worklists/reports HTML/CSV, anciens omission reviews, et checkers round-specific potentiellement consolidables. Mesurer le nombre de fichiers avant/après et ne supprimer aucun fichier encore consommé par build/check/génération.
3. Mettre README/HANDOFF au propre pour que l’état courant soit compréhensible sans connaître tous les anciens rounds.

Ne commence pas encore la traduction des objets/items. Préserver toutes les décisions fonctionnelles/runtime validées et le caractère reproductible depuis Android FR.