Je poursuis le projet Secret of Mana FR à partir du **Round 67**.

Commence par lire `README.md`, puis `docs/HANDOFF.md`. L’archive fournie est prioritaire sur GitHub.

État : Android **1798/1838** ; corpus **695 événements = 669 complets + 26 PARTIEL** ; **1687 IDs sémantiques / 1783 entrées JSON** ; simulation **0 erreur / 0 warning / 0 wrap implicite**.

Priorité : poursuivre la réorganisation manuelle de **`$04E2`** à partir de `mappings/android/dialogue_04E2_android_fr_round67.html`. Il ne reste que `CA:3335`, `CA:3359`, `CA:3362`, `CA:33E4`, `CA:3423`. Préserver les décisions Round 67 autour de `CA:32C5/CA:32D7` et ne pas rouvrir `$04E1` ni `$013A/C9:40D7`.

Règles : ne pas forcer d’identité Android, `WAIT != NEWLINE`, utiliser le JP SNES comme source primaire lorsqu’il est disponible, conserver PARTIEL/TO REVIEW quand nécessaire, et après modification obtenir round-trip + simulation 0/0/0. Rebuild seulement les composants modifiés, puis recombiner `all.ips`; fournir un IPS autonome et les HTML de revue.
