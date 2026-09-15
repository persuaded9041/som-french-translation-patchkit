# Prompt de reprise — étude approfondie des crédits de l'opening / `É` de `CHAUVIRÉ`

Je poursuis le projet **Secret of Mana FR** à partir de l'archive propre fournie.
L'archive fournie est **prioritaire sur GitHub**. Le ROM de référence reste
**Secret of Mana (USA), non headeré** et ne doit jamais être redistribué.

Commence par lire intégralement :

- `README.md`
- `docs/HANDOFF.md`
- `docs/OPENING_CREDIT_ACCENT_RESEARCH.md`
- `docs/OPENING_LITERAL_STREAM_ROUND85_13.md`
- `docs/OPENING_TEXT.md`
- `docs/MEMORY_MAP.md`
- `docs/COMPATIBILITY.md`
- `components/french_opening/README.md`
- `components/french_opening/docs/MEMORY_MAP.md`
- `components/french_opening/build_patch.py`
- `components/french_opening/src/opening_hook.asm`

Le corpus de dialogues est gelé et ne doit pas être rouvert. `intro_skip` est
également promu/validé ; ne le modifie pas dans ce chantier.

## But de cette reprise

Revenir sur le `É` final du crédit :

`Traduction : E.CHAUVIRÉ`

Aujourd'hui, les crédits utilisent un `É` monobloc dans le tile d'ouverture
`$7A`, qui remplace le `Z`. Je veux supprimer ce compromis :

- restaurer le `Z` normal dans la police de l'opening ;
- afficher le caractère de base `E` sur la ligne normale du crédit ;
- afficher l'accent aigu sur **la ligne de tiles juste au-dessus** ;
- faire en sorte que cette ligne d'accent suive **exactement le fade-in et le
  fade-out** de la ligne de crédit.

Important : nous avions déjà réussi historiquement à afficher l'accent sur la
ligne supérieure. Le problème restant était que **la ligne de l'accent ne
suivait pas le fade-in/fade-out du crédit**. Ne repars donc pas simplement de la
même idée sans expliquer ce comportement.

## Méthode obligatoire

Ne commence **pas** par implémenter une correction.

Commence par une étude très poussée et factuelle du renderer des crédits :

1. cartographie la boucle des cinq crédits dans le title-code décompressé, avec
   les adresses CPU/offsets utiles et le rôle des registres/variables ;
2. retrouve exactement comment une ligne de crédit est décodée et écrite vers
   le tilemap/buffer/VRAM ;
3. identifie la ligne de tiles immédiatement supérieure et les contraintes pour
   y écrire un accent sans endommager le reste de l'écran ;
4. reverse-engineer le fade-in/fade-out : détermine s'il dépend d'une palette,
   des attributs de tile, d'un buffer spécifique, de la luminosité globale ou
   d'un autre mécanisme ;
5. explique pourquoi un accent écrit séparément pouvait rester désynchronisé du
   fade de la ligne principale ;
6. compare ce chemin avec le système d'accents du prologue (`$7D-$7F`) sans
   supposer qu'il est directement réutilisable ;
7. propose ensuite seulement une ou plusieurs architectures minimales, classées
   par risque, pour obtenir un accent qui fade **frame-for-frame** avec le crédit.

Je veux d'abord voir cette étude et tes conclusions. **N'applique aucun patch et
ne modifie aucun code avant que l'architecture soit suffisamment prouvée.**

Préserve l'architecture d'opening validée : arrangement littéral à `$EE:A000`,
loader stock `$C1:0014`, helper `$EE:9000`, et aucune allocation `$EF` sans
nouvelle justification/runtime validation.
