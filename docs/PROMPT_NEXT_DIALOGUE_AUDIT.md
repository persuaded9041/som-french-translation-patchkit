# Prompt de reprise — seconde passe exhaustive des dialogues

Je poursuis le projet **Secret of Mana FR** à partir du checkpoint final de la première passe exhaustive des dialogues.

Commence par lire :

1. `README.md`
2. `docs/HANDOFF.md`
3. uniquement ensuite la documentation pertinente pour l’audit des dialogues.

L’archive fournie est prioritaire sur GitHub. Le ROM de référence est **Secret of Mana (USA), non headeré** et ne doit jamais être redistribué.

## État de départ validé

La première passe exhaustive en 12 lots est terminée et a été suivie d’un audit de non-régression.

État final :

- **701/701 événements jouables simulator-clean**
- **1959 carriers traduits**
- Android **1798/1838**
- **0 erreur / 0 warning / 0 wrap implicite**
- **0 `Nom :` / `%S(...) :` avec retour forcé indésirable**
- **0 candidat restant au scroll contrôlé selon le garde-fou actuel**
- redistribution : **302 carriers actifs**
- round-trip : **713 événements / 87 487 octets**
- **2048 scripts stock parsables**
- double build reproductible

Hashes de référence :

- `translations/dialogues_french.json`
  `4c71ee39ef1c10acbff1934401afdb4ded788bb525b7282c5a8227606863be82`
- `patches/french_dialogues.ips`
  `006281fc3240ccef2ab10abe0d3a307ed274d13ab58d62a52503776c64b06c79`
- `patches/all.ips`
  `a4510f1675a9b0be80518961338d847b3218f296dfa74032954b6b79570dc2e4`

L’audit de non-régression a confirmé que les phrases non ciblées n’ont pas subi de changement collatéral : les carriers modifiés appartiennent tous aux événements explicitement corrigés/revus pendant la première passe.

## Nouvelle tâche

Refaire **une seconde passe exhaustive indépendante**, événement par événement, en **lots d’environ 60 événements**, dans le même esprit que la première passe.

Le but n’est pas de chercher des corrections à tout prix ni de rejouer mécaniquement les mêmes heuristiques. Il faut chercher **de nouvelles pistes de problèmes ou d’améliorations** qui auraient pu échapper à la première passe.

Préserver toutes les corrections déjà validées. Ne rouvrir un texte ou une structure validés que si une anomalie concrète est démontrée dans le flux sérialisé, le contexte de sous-événement, le rendu ou la structure événementielle.

### Axes obligatoires à revérifier

1. **Complétude Android FR**
   - IDs alignés ;
   - slots FR-only ;
   - extensions absentes d’Android EN ;
   - `%S(...)` ;
   - redistributions multi-carriers ;
   - sous-événements/callers ;
   - phrases absorbées dans un carrier voisin.

2. **Affichage sérialisé réel**
   - `WAIT != NEWLINE` ;
   - `WAIT + TEXT_CLEAR` ;
   - scrolling ;
   - lignes vivantes ;
   - max 3 lignes ;
   - max 216 px ;
   - max 38 caractères décodés ;
   - nom dynamique pire cas 9 caractères ;
   - texte présent dans le JSON mais mal ou partiellement visible.

3. **Structure événementielle USA → FR**
   - boîtes ;
   - sons/musiques ;
   - animations/mouvements ;
   - flags/états ;
   - sprites/actions ;
   - appels/sauts/branches ;
   - récompenses ;
   - WAIT ;
   - choix ;
   - map/position ;
   - toute commande non textuelle.

4. **Qualité visuelle humaine**
   - ponctuation/espaces ;
   - labels de locuteur ;
   - phrases concaténées ;
   - retours étranges ;
   - mots/lignes orphelins ;
   - pagination absurde ;
   - choix trop compacts ;
   - transition de locuteur confuse ;
   - ordre de phrases suspect.

### Angles supplémentaires à privilégier dans cette seconde passe

Chercher particulièrement :

- les problèmes de continuité **caller ↔ sous-événement** ;
- les queues ou débuts de phrases dupliqués/perdus entre événements ;
- les WAIT/animations/mouvements dont le timing pourrait rendre une ligne visible trop tôt ou trop tard ;
- les changements de locuteur où un nom dynamique appartient à la mauvaise réplique ;
- les labels stock conservés alors qu’Android FR les omet volontairement ;
- les petits carriers de ponctuation (`:`, `...`, `!`, etc.) dont la conservation/suppression change réellement le rendu ;
- les choix activés alors que la dernière ligne de dialogue est encore vivante ;
- les cas où le système de scroll contrôlé serait utile mais n’est pas détecté par l’heuristique actuelle ;
- les pages d’une seule ligne et les fragments de phrase qui sont techniquement valides mais visuellement mauvais ;
- les carriers réutilisés par plusieurs callers : vérifier qu’une correction locale pour une scène ne casse pas une autre scène ;
- les divergences entre **JSON final**, **flux sérialisé** et **snapshot HTML** ;
- les interactions inattendues entre les corrections de la première passe et du texte voisin pourtant non ciblé.

Les outils automatiques sont uniquement des aides à la découverte. Toute alerte doit être interprétée manuellement avant d’être remontée.

## Méthode par lot

Pour chaque lot d’environ 60 événements :

1. déterminer précisément la plage canonique ;
2. générer un HTML complet du lot ;
3. inspecter chaque événement ;
4. suivre les appels de sous-événements quand nécessaire ;
5. comparer Android EN/FR lorsque l’identité ou la redistribution est suspecte ;
6. comparer le script US original et le script FR final pour les commandes non textuelles ;
7. tester le pire nom de 9 caractères pour tout layout dynamique suspect ;
8. ne remonter au user que :
   - les **problèmes certains à corriger** ;
   - les **cas réellement ambigus à valider**.

Ne pas lister individuellement les événements propres.

Quand une correction est validée :

- privilégier une recette reproductible ;
- ne jamais mettre de français en dur si la source vient d’Android FR ;
- préserver les `%S(...)` comme vraies commandes dynamiques ;
- vérifier le JSON final régénéré **et** le flux sérialisé ;
- ajouter/mettre à jour les régressions ;
- faire une régénération froide avant de poursuivre trop loin.

## Invariants à préserver

- Android FR reste la source principale.
- `WAIT != NEWLINE`.
- `$0360` reste neutralisé.
- `$035F / C9:D1B8` reste `Dryade fera réagir l'orbe !`.
- Les `%S(...)` Android FR restent des `PLAYER_NAME` dynamiques.
- Le scroll contrôlé validé utilise le WAIT seul (`\r`) suivi d’un NEWLINE ; il reste un choix de layout revu manuellement, pas une règle automatique globale.
- Ne pas rouvrir les décisions déjà validées pour préférence stylistique.

## Fin de la seconde passe

Après le dernier lot :

1. refaire le scan global de complétude Android FR ;
2. refaire le scan global des vocatifs dynamiques ;
3. refaire la comparaison structurelle US → FR ;
4. régénérer `dialogues_french.json` à froid ;
5. lancer simulation complète, régressions, hygiène et round-trip ;
6. comparer carrier par carrier avec le checkpoint de départ de cette seconde passe pour détecter les effets collatéraux ;
7. reconstruire les IPS deux fois et vérifier leur reproductibilité ;
8. seulement ensuite promouvoir un nouveau checkpoint.

**Commence directement par le lot 1 de cette seconde passe.**
