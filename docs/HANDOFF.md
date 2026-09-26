# HANDOFF — Secret of Mana FR

Dernière mise à jour : **2026-09-26**

Ce document contient uniquement l’état nécessaire pour reprendre le projet.
Les preuves, essais rejetés et détails de reverse engineering sont conservés
dans les documents de recherche dédiés.

## Source de vérité

- Travailler depuis cette archive / ce dépôt, pas depuis un ancien état GitHub.
- ROM de référence : **Secret of Mana (USA), non headerée**.
- Ne jamais redistribuer de ROM.
- Les patchs promus sont dans `patches/`.
- `dialogue_background` est volontairement **hors de `all.ips`**.
- Ne pas retoucher un comportement runtime-validé sans régression démontrée
  ou demande explicite.

Baseline agrégée actuelle :

- `patches/all.ips`
- SHA-256 : `7fe9ee9e9d96e6beb272cc492e9bfb510392b39957f27eb3b0e5492669facf34`

## État global

La traduction principale est considérée comme **complète pour les familles de
texte actuellement cartographiées**.

Restent volontairement non traduits dans `assets/menu_text.json` :

- `C7:74B2` : alphabet du Name Entry ;
- `C7:7BB5` : `/`.

`C7:7B6A` est désormais explicitement traduit `GP -> PO` par `french_menus`
via `translations/menu_text_french.json`. Le littéral boutique `D0:D894`
reste la propriété de `french_resources`.

## Éléments runtime-validés à préserver

### Dialogues

- corpus français : **701/701 événements jouables** ;
- segmentation et contenu gelés ;
- VWF dialogues validée ;
- DTE/charset français validés ;
- ne pas rouvrir le corpus sauf régression ou demande explicite.

### Intro / ouverture / nom

- intro française + VWF : validées ;
- skip intro : validé ;
- ouverture / crédits français : validés ;
- Name Entry étendu : validé ;
- noms français préremplis : validés ;
- graphismes de boutons de manette : validés.

### Ressources / boutique / battle

- ressources `$CA` françaises : promues ;
- noms, équipements, objets, ennemis, lieux et labels : intégrés ;
- réponses boutique/forge `$D9` : intégrées ;
- `GP -> PO` boutique : intégré ;
- battle/status : 109 entrées auditées ;
- 103 entrées textuelles traduites, 6 entrées structurelles conservées ;
- backend battle/status `$AC` : runtime-validé.

### Menus

- GAME SELECT / GAME FILE : validés ;
- `Sauvegardes`, `Graines de Mana`, monnaie `PO` : validés ;
- Choix de fenêtre : validé ;
- Actions des personnages : validé ;
- Caractéristiques : validé, y compris **`Épée`** ;
- Niv. armes / Niv. magies :
  - titres et noms VWF validés ;
  - 72 descriptions d’armes validées ;
  - 42 descriptions de magie sur panneau 3×480 px validées ;
  - aides par défaut armes/magies validées ;
- Réglage manette / Controller Edit :
  - `Choisir`
  - `Réglage manette`
  - `Votre menu`
  - `Menus alliés`
  - `Attaque`
  - `Course`
  - quatre lignes d’aide validées ;
  - remappage, L/R, Start et Select validés.

### VWF / performances

Les optimisations VWF promues sont runtime-validées. Ne pas revenir aux anciens
probes ou implémentations rejetées.

Pour les détails de performance :
- `docs/VWF_PERFORMANCE_RESEARCH.md`
- `docs/MAGIC_PANEL_PERFORMANCE_RESEARCH.md`

## Architecture à préserver

### `french_menus`

Propriétaire des textes natifs de menus/statut et de leurs adaptations de
géométrie déjà validées.

Points importants :

- Window Settings reste en renderer fixe ;
- Action Settings reste en renderer fixe ;
- Controller Edit reste en renderer fixe, sans hook ni relocalisation ;
- `C7:7B6A` (`PO`) appartient désormais à `french_menus`.

### `french_resources`

Propriétaire :

- de la table/blob `$CA` traduite ;
- des réponses boutique/forge `$D9` ;
- du littéral boutique `D0:D894` (`GP -> PO`) ;
- du corpus battle/status relocalisé ;
- des données françaises du panneau de magie.

`vwf_ui` doit rester un composant de **présentation**, pas devenir propriétaire
du contenu français.

### `vwf_ui`

Conserver les chemins exacts déjà validés pour :

- Caractéristiques ;
- GAME FILE ;
- battle/status `$AC` ;
- niveaux armes/magies ;
- descriptions d’armes ;
- panneau de magie.

## Hors scope actuel

### `dialogue_background`

Le composant existe mais reste volontairement hors agrégat.

Le fond semi-transparent fonctionne déjà sur plusieurs cas, mais la validation
complète des interactions avec choix, boutiques, effets graphiques, eau/brouillard,
boss et menus n’est pas terminée.

Ne pas le réintroduire dans `all.ips` sans reprendre cette campagne de validation.

## Prochaine étape recommandée

Il n’y a plus de grande famille de textes connue à traduire.

La suite recommandée est une **revue visuelle du jeu** pour identifier d’éventuels
textes anglais encore visibles qui auraient échappé à l’inventaire statique.

Si aucun texte restant n’est trouvé, passer aux finitions techniques optionnelles
plutôt qu’à une nouvelle recherche exhaustive dans les tables déjà auditées.

## Build

Le dépôt de reprise ne contient pas de ROM.

Avec une ROM USA propre non headerée :

```bash
python3 build.py "Secret of Mana (USA).sfc" all
python3 build.py "Secret of Mana (USA).sfc" --combine
```

Ou :

```bash
./buildall.sh "Secret of Mana (USA).sfc"
```

Le build propre doit reproduire le `all.ips` promu indiqué en haut de ce document.

## Documentation utile

À lire seulement selon le chantier :

- `docs/MEMORY_MAP.md` — allocations et hooks ;
- `docs/COMPATIBILITY.md` — ownership et compatibilités ;
- `docs/TRANSLATIONS.md` — sources de traduction ;
- `docs/TEXT_INVENTORY.md` — familles de texte connues ;
- `docs/TEXT_RESEARCH_NOTES.md` — recherche de textes non évidents ;
- `docs/UI_VWF.md` — architecture UI VWF ;
- `docs/VWF_PERFORMANCE_RESEARCH.md` — optimisations VWF ;
- `docs/WEAPON_MAGIC_DESCRIPTIONS_RESEARCH.md` — descriptions armes/magies ;
- `docs/WEAPON_MAGIC_SKILL_ROW_VWF_RESEARCH.md` — lignes de niveaux ;
- `docs/SKILL_MENU_HELP_RESEARCH.md` — aides armes/magies ;
- `docs/CONTROLLER_EDIT_RESEARCH.md` — comparaison JAP/US/FR et menu manette ;
- `docs/DIALOGUE_TRANSPARENCY_RESEARCH.md` — chantier `dialogue_background`.

Les README des composants concernés restent la référence locale pour leur
architecture et leurs contraintes.
