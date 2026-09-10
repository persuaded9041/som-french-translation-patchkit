Je poursuis le projet Secret of Mana FR à partir du **Round 69 — zéro PARTIEL**.

Lire `README.md`, puis `docs/HANDOFF.md`. L’archive fournie est prioritaire sur GitHub.

État : Android **1798/1838** ; corpus **701 événements = 701 complets + 0 PARTIEL** ; **1810 IDs sémantiques / 1946 entrées JSON** ; 3 exclusions orphelines/inaccessibles ; simulation **0 erreur / 0 warning / 0 wrap implicite**.

Round 69 clôt les dialogues jouables à 100 %. Les 15 anciens PARTIEL ont été promus complets après revue sémantique de scène ; conserver leur provenance dans `user_validated_visually_complete_events`. Préserver les décisions Round 67/68 et ne pas rouvrir `$04E1`, `$013A/C9:40D7`, `$035F/C9:D1B8 = Dryade`, ni les scènes `$0555/$0429/$05F8`.

Après modification : round-trip + simulation clean ; ne reconstruire que les composants modifiés, puis recombiner `all.ips`.
