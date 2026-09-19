# Prompt court de reprise

Je poursuis **Secret of Mana FR** depuis l’archive fournie, qui est prioritaire
sur GitHub. ROM de référence : **Secret of Mana (USA), non headerée** ; ne
jamais redistribuer les ROMs.

Commence par lire `README.md`, `docs/HANDOFF.md`,
`docs/WEAPON_MAGIC_SKILL_ROW_VWF_RESEARCH.md`,
`docs/WEAPON_MAGIC_DESCRIPTIONS_RESEARCH.md`, `docs/MEMORY_MAP.md`,
`components/vwf_ui/README.md`, `components/french_resources/README.md` et
`components/french_menus/README.md`. Ne modifie rien avant de m’avoir fait un
bref compte rendu.

Le menu **Niv. armes / Niv. magies** est désormais runtime-validé pour : titres
`Niv. armes` / `Niv. magies`, format `5:0 Nom` / `5:10 Nom`, VWF des noms,
72 descriptions d’armes françaises et panneau de magie 3×480 px avec les 42
phrases Android FR complètes. Les conditions stock de déblocage sont préservées.
Ne pas retoucher ces éléments sans régression prouvée.

**Priorité suivante : le texte d’aide/par défaut encore anglais de ce menu.**
Avant toute traduction ou insertion : retrouver le texte japonais original et
son chemin exact dans la ROM JPN, vérifier s’il existe un équivalent Android
EN/FR et établir l’identité, puis me proposer une adaptation française fidèle et
compatible avec la géométrie réelle du panneau. Ne pas insérer avant validation
linguistique avec moi.
