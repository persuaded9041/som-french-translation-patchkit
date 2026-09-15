# Prompt de reprise — Secret of Mana FR — baseline validée

Je poursuis le projet **Secret of Mana FR** à partir de l'archive propre fournie.
L'archive fournie est **prioritaire sur GitHub**. Le ROM de référence reste
**Secret of Mana (USA), non headeré** et ne doit jamais être redistribué.

Commence par lire intégralement :

- `README.md`
- `docs/HANDOFF.md`
- `docs/COMPATIBILITY.md`
- `docs/MEMORY_MAP.md`
- les README / memory maps du ou des composants concernés par ma prochaine demande.

Baselines à ne pas rouvrir sans défaut concret :

- corpus de dialogues jouables validé ;
- `intro_skip` hold-R 120 validé ;
- `french_opening` avec le `Z` stock restauré et `CHAUVIRÉ` rendu par `E` +
  accent `$7D` sur la ligne supérieure ;
- fade de cet accent synchronisé avec la ligne de crédit par la bande CGRAM
  HDMA validée `7/16` scanlines ;
- arrangement opening à `$EE:A000`, loader stock `$C1:0014`, helper `$EE:9000`,
  aucune allocation `$EF` pour `french_opening`.

Lis d'abord le dépôt et **n'engage aucun nouveau chantier de ta propre initiative**.
Attends ensuite ma prochaine demande et limite les modifications à son périmètre.
