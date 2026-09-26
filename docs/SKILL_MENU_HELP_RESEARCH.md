# Aides Niv. armes / Niv. magies — candidat du 2026-09-26

Formulations validées par l'utilisateur le 2026-09-26. Insertion construite et
vérifiée statiquement ; validation en jeu encore attendue.

## Identité et provenance

ROMs locales propres, non headerées, adressage HiROM : offset fichier = adresse
SNES moins $C00000. La ROM JPN a été vérifiée avec validate_japanese_rom ; la
ROM USA avec l'extracteur canonique. Aucun contenu ROM n'est distribué ici.

| Famille | Source JPN / offset | Source USA / offset | Pointeur USA | Android systxt |
|---|---|---|---|---|
| Armes | $C7:7A51 / 0x077A51 | $C7:784C / 0x07784C | $C0:33C4 | 101199 |
| Magies | $C7:7AA2 / 0x077AA2 | $C7:78D4 / 0x0778D4 | $C0:33C7 | 101200 |

L'identité SNES est établie par les mêmes sélecteurs d'aide 5/6 dans $A20F :
USA $C7:62FD/$6304, JPN $C7:63A6/$63AD. Le lecteur USA $C0:2293 utilise
la table 24 bits $C0:33B5 ; le lecteur JPN utilise la table 16 bits $C7:7808
(référence à l'offset 0x0025DB), dont les entrées 5/6 sont $7A51/$7AA2.
Le codec japonais existant décode les blocs, en consommant les paramètres de
shift avant de reconnaître les terminateurs.

Armes, japonais original :

> 武器のレベルかくにんができます。　
> 各武器を見るには、まず決定ボタンを押し、
> 十字ボタンで武器を選び、決定ボタンを押すと見れます。

Magies, japonais original :

> 魔法のレベルかくにんができます。　
> 各魔法を見るには、まず決定ボタンを押し、
> 十字ボタンで精れいを選び、決定ボタンを押すと見れます。

Sens : consulter les niveaux ; valider, sélectionner l'arme ou l'esprit à la
croix, puis valider pour voir les informations correspondantes.

Les unités Android EN/FR 101199/101200 sont les équivalents fonctionnels des
aides, identifiés par leur contenu explicite (niveaux d'armes/magies, choix
arme/esprit, affichage des détails). Elles ne sont pas des copies littérales :
Android ajoute « Niveau : Progression », remplace la croix par le tactile et
ajoute l'équipement par glisser-déposer pour les armes. La version française
Android précise « effets spéciaux » et « détail des sorts correspondants ».
L'adaptation SNES conserve la séquence japonaise, avec l'action logique
« Attaque » comme les autres aides USA/SNES déjà traduites.

## Texte approuvé et insertion

La source canonique est translations/interface_text_french.json :

- armes : C7:784C / C7:7874 / C7:78A8 ;
- magies : C7:78D4 / C7:78FB / C7:7933.

Armes :

    Niveaux des armes : appuyez sur “Attaque”, puis
    choisissez une arme avec la croix directionnelle.
    Validez avec “Attaque” pour voir les effets de l'arme.

Magies :

    Niveaux de magie : appuyez sur “Attaque”, puis
    choisissez un esprit avec la croix directionnelle.
    Validez avec “Attaque” pour voir le détail des sorts.

Les descripteurs stock $C7:761C/$764D sont 01 C0 04 06 1E : cadre inférieur
à six rangées de tuiles et 30 colonnes, soit trois lignes de 60 glyphes fixes.
Le chemin d'aide charge les pointeurs via $C0:2293, puis utilise $C0:2354 et
le convertisseur stock. Il est distinct du batch VWF des descriptions de magie.
Les blocs conservent deux séparateurs $7F et un terminateur $00 ; aucune
modification du renderer, des cadres, des placements ou des descriptions.
Le builder limite volontairement chaque ligne à 58 cellules (marge de deux).
Longueurs encodées : armes 47/49/54 ; magies 46/50/53.
La géométrie est établie statiquement ; l'aspect final reste à tester en jeu.

Les textes dépassent leurs anciens blocs de 136/139 octets :

- armes : 153 octets à $ED:A000-$A098, réserve $ED:A000-$A0FF ;
- magies : 152 octets à $ED:A100-$A197, réserve $ED:A100-$A1FF.

Les réserves ont été comparées aux allocations documentées et à tous les IPS
existants. Les deux pointeurs 24 bits sont redirigés ; les blocs USA restent
intacts. Aucun code 65816 ni état WRAM supplémentaire n'est introduit.

## Résultats statiques et fichiers

Les patches promus sous patches/ sont conservés. Les sources construisent le
candidat, disponible sous build/candidates/skill-help-20260926/patches/ :

- french_menus.ips : b2d2c9f4a7fb27b5b63a1b09568fe5c664f489aada5324b695e201310e919a51
- all.ips : e4b89be1aaf67c53bb815fae09ca030dc201b94a0185816e788399a9cff3ed99
- ROM combinée locale : 16e5db6c2687933aad400d7e73b492c613de0417ec6f3d6db6fdec7724edf2a8
- checksum SNES : $2608.

Le standalone et le combiné diffèrent chacun de leur baseline sur 313 octets :
6 octets de pointeurs à 0x0033C4-0x0033C9, 303 octets de texte dans les deux
réserves (les terminateurs étaient déjà nuls), 4 octets de checksum.
Tous les autres octets sont identiques ; les autres composants sont inchangés.

Contrôles passés : construction standalone + combinaison, audit des overlaps
(7272 octets identiques / 710 déclarés), source hygiene, round-trip des sources
avec parsing des 2048 scripts, liaison des 33 entrées interface françaises,
import Android resources --check, contrôle exact des pointeurs/payloads et des
plages de différences. Ces preuves ne constituent pas une validation runtime.

## Test en jeu attendu

1. Charger la ROM candidate puis ouvrir Niv. armes : trois lignes complètes,
   guillemets/accents corrects, aucune coupure ou corruption de cadre.
2. Appuyer sur Attaque, choisir une arme, afficher sa description, annuler et
   revenir à l'aide ; vérifier aussi les noms et valeurs de progression.
3. Même séquence dans Niv. magies avec un esprit débloqué ; vérifier les
   descriptions complètes et un esprit verrouillé si la sauvegarde le permet.
4. Fermer/réouvrir le menu ; vérifier rapidement Caractéristiques et Sauvegardes.
5. Faire également un contrôle des deux aides avec french_menus standalone.

Appliquer les IPS à une ROM USA propre, jamais à une ROM déjà patchée.
Après validation utilisateur seulement : promouvoir les deux IPS et actualiser
les empreintes de référence. Le candidat Épée préexistant n'est pas requalifié.
