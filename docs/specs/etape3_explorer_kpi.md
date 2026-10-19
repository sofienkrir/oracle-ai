# Spécification — Étape 3 : Explorer & KPI

> Statut : **v2 proposée, en attente de validation** (19/10/2026). v2 intègre les 5
> clarifications demandées : convention de signe et retours, ajustements comptables, unités
> gratuites, couverture temporelle, double réconciliation. Aucun code applicatif n'est écrit avant
> validation. Jeu de référence : UCI Online Retail II, deux feuilles empilées (≈ 1,07 M lignes).
> L'exemple chiffré de l'annexe A a été recalculé par un script indépendant.

## 1. Objectif et principes

L'étape 3 transforme un dataset qualifié (étape 2) en **indicateurs descriptifs vérifiables**,
calculés de façon déterministe : aucune prédiction, aucune causalité, aucun LLM.

1. **Aucune ligne n'est exclue sans règle explicite**, affichée avec son nombre de lignes et
   son montant signé.
2. **Toute exclusion est réversible** et son impact sur chaque KPI est visible (avant/après).
3. **Les règles métier sont validées par l'utilisateur** ; un code atypique non validé n'est
   jamais exclu automatiquement. Chaque validation crée une version tracée du jeu de règles.
4. **Deux réconciliations distinctes** (§6) : intégrité des lignes et montants bruts, puis pont
   financier du montant brut au CA produits net.
5. Chaque KPI affiche **formule, numérateur, dénominateur, période, filtres et version des
   règles**.

Hors périmètre (affiché à l'écran) : marge (pas de coût d'achat), ruptures et surstock (pas de
stock), péremption, détection statistique d'anomalies (étape 4), prévision (étape 5), causalité
(étape 6).

## 2. Conventions de calcul

### 2.1 Montant signé

- `m = Quantity × Price`, **toujours signé, tel que saisi** (£, devise du jeu UCI).
  Une annulation (`Quantity < 0`, `Price > 0`) a donc un montant **négatif** ; un ajustement à
  prix négatif a un montant négatif.
- **Aucun montant n'est jamais « mis en valeur absolue » avant agrégation.** Les valeurs
  absolues n'apparaissent qu'à l'**affichage** (ex. « Retours : 10,00 £ »), jamais dans une
  formule de somme.
- Calcul exact : `m` est converti en entier de **dix-millièmes de £**
  (`round(Q × P × 10 000)`, prix jusqu'à 4 décimales exacts) ; toutes les sommes sont des sommes
  d'entiers, l'affichage est arrondi au centime. Les contrôles d'égalité sont donc exacts.

### 2.2 Grandeurs élémentaires

- `préfixe` = première lettre de `Invoice` si c'est une lettre (`C`, `A`, autre), sinon aucun.
- `code_standard` : `StockCode` conforme à `^\d{5}[A-Za-z]{0,2}$` (ex. `22423`, `85123A`,
  `15056BL`). Motif affiché et modifiable. Tout autre code est **atypique** (ex. `POST`, `C2`,
  `gift_0001_10`) ; la détection ne repose pas sur « code sans chiffre ».
- `S_k` = somme des montants signés de la catégorie `k` ; `N_k` = nombre de lignes.

## 3. Classification des lignes

Chaque ligne reçoit **une seule catégorie**, en appliquant les règles **dans l'ordre** (la
première qui s'applique gagne). La partition est exhaustive : toute combinaison de préfixe,
signe de quantité et signe de prix tombe dans exactement une catégorie.

| Règle | Catégorie | Condition exacte (après les règles précédentes) | Traitement par défaut | Réversible |
|---|---|---|---|---|
| **R0** | Doublon exact | Identique sur **toutes les colonnes** à une ligne précédente (1re occurrence conservée) | Exclue des KPI | Oui |
| **R1** | Valeur manquante | `Quantity` ou `Price` manquant / non numérique (`m` non calculable) | Exclue ; comptée en lignes, montant « non calculable » | Non |
| **R2** | Ajustement comptable | `préfixe = A` **ou** `Price < 0` | Exclue des KPI de vente ; visible en réconciliation financière (§3.2) | Oui |
| **R3** | Ligne non-produit **validée** | Code atypique classé par l'utilisateur (Frais de port, Remise, Frais & commissions, Ajustement manuel, Échantillon, Test, Bon cadeau, Autre), **quel que soit le préfixe** | Exclue du CA produits ; montant signé conservé dans sa sous-catégorie | Oui |
| **R4** | Annulation incohérente | `préfixe = C` **et** `Quantity > 0` | Exclue (§3.1) | Oui (2 options) |
| **R5** | Retour produit | `préfixe = C` **et** `Quantity < 0` | **Retours** (montant négatif) | Non (définition) |
| **R6** | Quantité nulle | `Quantity = 0` | Exclue (montant nul) | Non |
| **R7** | Unités gratuites | `Price = 0` **et** `Quantity > 0` | Hors CA ; unités comptées à part (§3.3) | Oui |
| **R8** | Mouvement de stock sans valeur | `Price = 0` **et** `Quantity < 0` (hors C) | Exclue (montant nul) ; listée | Non |
| **R9** | Retour hors facture C | `Price > 0` **et** `Quantity < 0` (hors C) | Exclue ; listée « à examiner » | Oui (option « traiter comme retour ») |
| **R10** | Vente valide | `Price > 0` **et** `Quantity > 0`, préfixe aucun ou inconnu | **Comptée** dans les ventes | — |

**Marqueurs** (n'affectent pas la catégorie, affichés et comptés) :
`F1` préfixe inconnu (ni A ni C) · `F2` code atypique **non validé** · `F3` sans `Customer ID`.

- Un code atypique non validé (`F2`) reste dans sa catégorie normale (souvent R10 ou R5) :
  **jamais exclu automatiquement**. Bandeau : « dont X £ issus de N codes non validés ».
- R3 passe **avant** les règles C : une remise ou un remboursement de port saisis sur une facture
  `C` sont classés dans leur sous-catégorie (Remise, Frais de port), pas dans les retours
  produits. Tant que le code n'est pas validé, ils restent en R5 (marqués `F2`).

### 3.1 Retours et annulations (point 1)

```
Ventes brutes          VB  = S_R10                     (≥ 0)
Retours signés         RS  = S_R5                      (≤ 0)
Retours (affichage)    R   = −RS                       (≥ 0, affichage uniquement)
CA produits net        CAN = Σ m sur R10 ∪ R5 = VB + RS
Taux de retour         TR  = R / VB
```

- **Une seule soustraction** : le CA net est la **somme signée** des lignes R10 et R5. Il n'existe
  aucune formule du type `VB − |RS|` appliquée à un total qui contiendrait déjà RS. Test
  automatique : `CAN = VB + RS = VB − R`, et `CAN = Σ m(R10 ∪ R5)` calculé indépendamment.
- Les retours sont comptés **à la date de l'annulation**, sans rapprochement avec la vente
  d'origine (qui peut précéder la période). Limite affichée.
- **Factures C incohérentes (R4, `Quantity > 0`)** : leur montant est **positif** ; les compter
  comme retours tels quels **augmenterait** le CA. Trois traitements, au choix de l'utilisateur :
  1. **Exclure** (défaut) : listées, montant affiché, aucun effet sur les KPI.
  2. **Traiter comme retour à signe corrigé** : contribution `−|m|` aux retours.
  3. (Non proposé) inclure tel quel : refusé car il ajouterait du CA à partir d'une annulation.

### 3.2 Ajustements comptables et prix négatifs (point 2)

- R2 regroupe `préfixe A` (ajustements de créances, etc.) **et** toute ligne à `Price < 0`.
- Exclues des KPI de vente, elles restent **visibles avec leur montant signé** dans une section
  dédiée de la réconciliation financière : nombre de lignes, `S_R2`, détail par facture/code,
  descriptions.
- Impact expliqué : « Inclure les ajustements ferait passer le CA net de CAN à CAN + S_R2. »
- Indicateur complémentaire : **Total enregistré** = `CAN + S_R3 + S_R2` (tout ce qui a un
  montant, hors doublons, anomalies et R9), pour rapprocher d'une vision comptable.

### 3.3 Unités gratuites et commandes (point 3)

```
Unités payantes      UP = Σ Quantity sur R10
Unités gratuites     UG = Σ Quantity sur R7
Commandes            C  = nb de factures distinctes ayant ≥ 1 ligne R10
Factures sans vente payante = factures sans ligne R10 (listées)
Panier moyen         PM = VB / C
Prix moyen unitaire  PU = VB / UP
```

- Une ligne gratuite **n'empêche jamais** de compter une facture : c'est la présence d'au moins
  une ligne R10 qui fait la commande ; les lignes R7 de la même facture sont simplement hors CA et
  hors `UP`.
- Une facture ne contenant **que** des lignes gratuites n'est pas une commande ; elle est comptée
  dans « factures sans vente payante ».

### 3.4 Autres indicateurs dérivés

```
Remises (signées)          RM = S_R3[Remise]            (≤ 0 en général)
Frais de port (signés)     FP = S_R3[Frais de port]
CA net après remises       = CAN + RM
Montant facturé            = CAN + RM + FP
```

## 4. Validation des règles métier

1. L'outil liste **tous** les codes atypiques : lignes, montant signé, factures, 3 descriptions
   les plus fréquentes, période, part sur factures `C`.
2. Il **propose** une catégorie d'après la description (mots-clés documentés : `POSTAGE`,
   `CARRIAGE` → Frais de port ; `DISCOUNT` → Remise ; `MANUAL` → Ajustement manuel ;
   `BANK CHARGES`, `FEE`, `COMMISSION` → Frais & commissions ; `ADJUST` → Ajustement ;
   `SAMPLE` → Échantillon ; `TEST` → Test ; `GIFT`, `VOUCHER` → Bon cadeau). Statut
   **« proposée »**, **non appliquée**.
3. L'utilisateur confirme ou corrige (« Produit » possible), choisit les options (R0, R2, R4,
   R7, R9, motif de code, seuils), puis **valide** : nouvelle version `vN` enregistrée avec le
   détail des changements. Tous les résultats citent `vN`.

## 5. Indicateurs

### 5.1 Ventes — voir §3.1, §3.3, §3.4.

### 5.2 Couverture temporelle et périodes (point 4)

**Fenêtre d'observation** `[J_min, J_max]` = premier et dernier **jour** (date sans heure) portant
au moins une ligne, toutes catégories confondues (hors R1). Elle ne dépend pas des filtres de
règles.

Pour chaque période calendaire `P = [début, fin]` (mois, ou semaine ISO), on distingue :

| Statut | Règle | Traitement |
|---|---|---|
| **Complète** | `début ≥ J_min` **et** `fin ≤ J_max` (entièrement dans la fenêtre) | Comparée normalement |
| **Partielle (bord)** | La période chevauche la fenêtre sans y être incluse | Affichée grisée avec sa **couverture** = jours de P dans la fenêtre ÷ jours de P ; **exclue des comparaisons** |
| Hors fenêtre | Aucune intersection | Non affichée |

**Données absentes ≠ période incomplète.** À l'intérieur de la fenêtre, un jour sans aucune
ligne est un **jour sans données** ; il ne rend pas la période incomplète. L'outil affiche :

- le nombre de jours sans données par période et **par jour de semaine** (ex. « 0 ligne sur
  104 samedis » : fermeture structurelle) ;
- les **trous** : suites d'au moins `G` jours consécutifs sans données (défaut `G = 7`,
  configurable), avec leurs dates ; la période qui les contient reste « complète » mais porte un
  avertissement « trou de X jours : fermeture ou données manquantes ? ».

Comparaisons : mois vs mois précédent et vs même mois N-1, **uniquement entre périodes
complètes** ; sinon « comparaison impossible (période partielle) ».

### 5.3 Décomposition d'une variation (descriptive)

`CA = C × PM` ⇒ `ΔCA = ΔC × PM₀ + C₀ × ΔPM + ΔC × ΔPM` (somme exacte affichée), puis
contributions par pays et par produit (top 10). Étiquette : « Association descriptive — n'établit
pas de cause ».

### 5.4 Clients (lignes R10 avec `Customer ID`)

Clients actifs, nouveaux (1er achat dans la période, sur l'historique disponible), récurrents,
taux de réachat, CA moyen par client identifié, **part du CA sans client** = `1 − VB_identifié /
VB`. Chaque KPI affiche « calculé sur N lignes identifiées (x % des ventes valides) ». Les lignes
sans client restent dans VB, CAN, C, UP.

### 5.5 Pays, 5.6 Produits, 5.7 Autres domaines

Inchangés par rapport à v1 : CA net et parts par pays ; top produits, retours par produit, ABC
(80 / 95 %), rotation lente (≥ 90 jours sans vente **ou** < 25 % des semaines vendues depuis la 1re
vente, seuils configurables, « trop récent » si < 8 semaines) ; KPI maintenance et statistiques
génériques.

## 6. Les deux réconciliations (point 5)

### 6.1 Réconciliation d'intégrité (lignes et montants bruts)

But : prouver qu'**aucune ligne ni aucun montant ne disparaît**. Une ligne par catégorie R0…R10 :
`N_k`, `S_k`, `Σ Quantity_k`, part des lignes. Contrôles affichés ✓/✗ :

```
Σ_k N_k = nombre de lignes du fichier
Σ_k S_k = M_brut = Σ m sur toutes les lignes où m est calculable (R1 exclu, compté à part)
```

Aucune notion de CA ici : c'est un contrôle de partition.

### 6.2 Réconciliation financière (pont M_brut → CA produits net)

But : expliquer le passage du montant brut au CA. Chaque étape retire le montant signé d'une
catégorie exclue, avec son explication :

```
M_brut
 − S_R0  doublons exacts
 − S_R2  ajustements comptables (A, prix < 0)
 − S_R3  lignes non-produit validées (dont remises RM, frais de port FP, …)
 − S_R4  annulations incohérentes (option 1)
 − S_R6 − S_R7 − S_R8   (montants nuls, affichés pour mémoire)
 − S_R9  retours hors facture C
 = CAN = S_R10 + S_R5
```

Contrôle ✓/✗ : le résultat du pont égale `S_R10 + S_R5` calculé directement.

### 6.3 Avant / après par règle

Pour chaque règle ou option réversible : KPI principaux (VB, R, CAN, C, PM, UP, clients actifs)
avec le réglage courant et avec ce seul réglage inversé, et l'écart. Clic → lignes concernées
(paginées, export CSV).

## 7. API, interface, vérification, acceptation

- **API** (prévue) : `GET/PUT /api/datasets/{id}/rules` · `GET /api/datasets/{id}/kpi` (KPI,
  séries, couverture, réconciliations, impacts ; filtres `from`, `to`, `country`,
  `granularity`) · `GET …/kpi/products` · `GET …/kpi/lines?category=R5` · `GET …/kpi/export`.
  Chaque calcul est journalisé (`kind = "kpi"`) avec filtres et version des règles.
- **Interface « Explorer »** : onglets Règles · Vue d'ensemble · Réconciliations · Évolution ·
  Produits · Clients & pays ; bandeau si des codes ne sont pas validés.
- **Vérification** :
  1. la fixture de l'annexe A est un test automatique (valeurs exactes) ;
  2. les invariants §6.1 et §6.2 sont testés sur fixtures, échantillons synthétiques et fichier
     réel ;
  3. le script indépendant `scripts/verify_kpi.py` recalcule CA net mensuel, commandes et retours
     sans réutiliser le module ;
  4. une procédure Excel permet de retrouver le CA net d'un mois ;
  5. tous les tests des étapes 1–2 restent verts, en CI Linux et Windows ;
  6. objectif de performance : KPI sur 1,07 M lignes en moins de 10 s (à mesurer et consigner).
- **Acceptation** : partition exhaustive et réconciliations exactes sur le fichier réel ; aucune
  exclusion de code sans validation ; impacts avant/après visibles ; KPI clients limités aux
  lignes identifiées ; périodes partielles et trous distingués ; résultats et limites consignés
  dans `docs/evaluation.md`.

## Annexe A — Exemple chiffré (fixture de test)

Codes validés : `POST` → Frais de port, `D` → Remise. `GIFTX1` est atypique **non validé**.

| # | Facture | Code | Q | Prix | Client | Catégorie | m (£) |
|---|---|---|---|---|---|---|---|
| 1 | 1001 | 22423 | 2 | 10,00 | 17001 | R10 vente | +20,00 |
| 2 | 1001 | 22423 | 2 | 10,00 | 17001 | R0 doublon de #1 | +20,00 |
| 3 | 1001 | 85123A | 1 | 0,00 | 17001 | R7 gratuit | 0,00 |
| 4 | 1001 | POST | 1 | 5,00 | 17001 | R3 frais de port | +5,00 |
| 5 | 1002 | 22423 | 3 | 10,00 | — | R10 vente (F3) | +30,00 |
| 6 | 1003 | 85123A | 4 | 0,00 | 17002 | R7 gratuit | 0,00 |
| 7 | C1004 | 22423 | −1 | 10,00 | 17001 | R5 retour | −10,00 |
| 8 | C1005 | D | −1 | 3,00 | 17001 | R3 remise | −3,00 |
| 9 | C1006 | 22423 | 2 | 10,00 | 17002 | R4 C incohérente | +20,00 |
| 10 | A1007 | B | 1 | −50,00 | — | R2 ajustement | −50,00 |
| 11 | 1008 | 22423 | −5 | 0,00 | — | R8 stock sans valeur | 0,00 |
| 12 | 1009 | 22423 | −2 | 10,00 | 17002 | R9 retour hors C | −20,00 |
| 13 | 1010 | 22423 | 0 | 10,00 | 17002 | R6 quantité nulle | 0,00 |
| 14 | 1011 | 22423 | 1 | 10,00 | 17003 | R10 vente | +10,00 |
| 15 | 1012 | 22423 | 1 | — | 17003 | R1 valeur manquante | n.c. |
| 16 | 1013 | GIFTX1 | 1 | 20,00 | 17003 | R10 vente (F2) | +20,00 |

**Intégrité (§6.1)** : 16 lignes = 1 (R0) + 1 (R1) + 1 (R2) + 2 (R3) + 1 (R4) + 1 (R5) + 1 (R6) + 2 (R7) + 1 (R8) + 1 (R9) + 4 (R10) ✓ ; `M_brut = 42,00 £` (15 montants
calculables) = Σ S_k ✓.

**Pont (§6.2)** : 42,00 − 20,00 (R0) − (−50,00) (R2) − 2,00 (R3 : +5 port −3 remise) −
20,00 (R4) − 0 (R6, R7, R8) − (−20,00) (R9) = **70,00 £** = S_R10 + S_R5 = 80,00 − 10,00 ✓.

**KPI** : VB = 80,00 · Retours R = 10,00 · **CAN = 70,00** · TR = 12,5 % · Commandes = 4
(1001, 1002, 1011, 1013 ; la facture 1003, 100 % gratuite, n'en est pas une ; la facture 1001
compte malgré sa ligne gratuite) · PM = 20,00 · UP = 7 · UG = 5 · CA net après remises = 67,00 ·
Montant facturé = 72,00 · Clients actifs = 2 · Part du CA sans client = 37,5 % · Bandeau
« dont 20,00 £ issus de 1 code non validé ».

**Avant / après** : C incohérente traitée comme retour → CAN 50,00 (inclure tel quel donnerait
90,00 : refusé) · doublons inclus → VB 100,00, CAN 90,00 · ajustements inclus → 20,00 ·
`GIFTX1` validé comme Bon cadeau → VB 60,00, CAN 50,00, commandes 3.
