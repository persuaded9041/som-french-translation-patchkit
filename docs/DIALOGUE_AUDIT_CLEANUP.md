# Cleanup — fin de la première passe exhaustive des dialogues

Date : 2026-09-14

Ce checkpoint clôt la première passe exhaustive en 12 lots et son audit de non-régression.

## État promu

- 701/701 événements jouables simulator-clean
- 1959 carriers traduits
- Android 1798/1838
- 0 erreur / 0 warning / 0 wrap implicite
- 0 label dynamique `Nom :` mal coupé
- 0 candidat restant au rolling-scroll selon le garde-fou actuel
- redistribution : 302 carriers actifs
- round-trip : 713 événements / 87 487 octets
- 2048 scripts stock parsables
- double build reproductible

## Non-régression

Comparaison carrier par carrier avec le checkpoint d'avant audit :

- 1807 carriers préexistants strictement inchangés ;
- 150 carriers préexistants modifiés, tous dans des événements explicitement audités/corrigés ;
- 2 micro-carriers de ponctuation ajoutés intentionnellement à `$042D` ;
- 148/150 modifications préexistantes = layout/espaces/contrôles seulement ;
- 2 modifications sémantiques validées : `$01DA` et `$0295` ;
- aucune modification collatérale identifiée sur un événement non ciblé.

## Références

- `dialogues_french.json`: `4c71ee39ef1c10acbff1934401afdb4ded788bb525b7282c5a8227606863be82`
- `french_dialogues.ips`: `006281fc3240ccef2ab10abe0d3a307ed274d13ab58d62a52503776c64b06c79`
- `all.ips`: `a4510f1675a9b0be80518961338d847b3218f296dfa74032954b6b79570dc2e4`

La prochaine étape recommandée est une **seconde passe exhaustive indépendante** des dialogues, toujours par lots d'environ 60, mais en cherchant de nouveaux angles morts plutôt qu'en rejouant mécaniquement les heuristiques de la première passe. Voir `docs/PROMPT_NEXT_DIALOGUE_AUDIT.md` et la fin de `docs/HANDOFF.md`.
