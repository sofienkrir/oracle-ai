# Spécification — Étape 3 : Explorer & KPI

> Statut : **v3 proposée, en attente de validation** (19/10/2026). Aucun code applicatif n'est
> écrit avant validation. Jeu de référence : UCI Online Retail II, deux feuilles empilées
> (≈ 1,07 M lignes).
>
> Historique : v1 règles R0–R8 · v2 signes, ajustements, unités gratuites, couverture, double
> réconciliation · **v3** corrections issues du recalcul indépendant (annexe D) : facturation
> client indicative, pont pour la configuration active, options réversibles et recalcul complet,
> valeurs manquantes, factures sans vente payante. L'annexe A est vérifiée par
> `docs/specs/verif_annexe_a.py` (oracle indépendant, `Decimal`, sans pandas).

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
| **R0** | Doublon exact | Identique sur **toutes les colonnes** à une ligne précédente (1re occurrence conservée) | Exclue des KPI | Oui (option O1) |
| **R1** | Valeur manquante | `Quantity`, `Price`, `Invoice` ou `InvoiceDate` manquant / invalide | Exclue de **tous** les KPI (§3.7) ; comptée et listée | Non |
| **R2** | Ajustement comptable | `préfixe = A` **ou** `Price < 0` | Exclue des KPI de vente ; visible en réconciliation financière (§3.2) | Oui (option O2) |
| **R3** | Ligne non-produit **validée** | Code atypique classé par l'utilisateur (Frais de port, Remise, Frais & commissions, Ajustement manuel, Échantillon, Test, Bon cadeau, Autre), **quel que soit le préfixe** | Exclue du CA produits ; montant signé conservé dans sa sous-catégorie | Oui (option O5) |
| **R4** | Annulation incohérente | `préfixe = C` **et** `Quantity > 0` | Exclue (§3.1) | Oui (option O3) |
| **R5** | Retour produit | `préfixe = C` **et** `Quantity < 0` | **Retours** (montant négatif) | Non (définition) |
| **R6** | Quantité nulle | `Quantity = 0` | Exclue (montant nul) | Non |
| **R7** | Unités gratuites | `Price = 0` **et** `Quantity > 0` | Hors CA ; unités comptées à part (§3.3) | Non (définition) |
| **R8** | Mouvement de stock sans valeur | `Price = 0` **et** `Quantity < 0` (hors C) | Exclue (montant nul) ; listée | Non |
| **R9** | Retour hors facture C | `Price > 0` **et** `Quantity < 0` (hors C) | Exclue ; listée « à examiner » (§3.8) | Oui (option O4) |
| **R10** | Vente valide | `Price > 0` **et** `Quantity > 0`, préfixe aucun ou inconnu | **Comptée** dans les ventes | — |

**Marqueurs** (n'affectent pas la catégorie, affichés et comptés) :
`F1` préfixe inconnu (ni A ni C) · `F2` code atypique **non validé** (dont `StockCode` vide) ·
`F3` sans `Customer ID`.

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
- *(v3 : l'indicateur « Total enregistré » de la v2 est supprimé ; il mélangeait des natures
  différentes. La réconciliation d'intégrité §6.1 donne déjà le montant de chaque catégorie.)*

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

### 3.4 Indicateurs de facturation (distincts des indicateurs de ventes de produits)

Deux familles d'indicateurs sont toujours affichées séparément :

- **Ventes de produits** (VB, R, CAN, TR, C, PM, UP, UG, PU, KPI clients) : lignes R10 et R5
  uniquement, donc **produits** au sens des règles validées.
- **Facturation** : lignes produits **plus** les lignes non-produit validées dont la
  sous-catégorie est marquée « facturée au client ».

```
Remises (signées)                    RM  = S_R3[Remise]            (≤ 0 en général)
Frais de port (signés)               FP  = S_R3[Frais de port]
CA net après remises                 = CAN + RM
Facturation client indicative        FCI = CAN + Σ S_R3[s] pour s « facturée au client »
```

Marquage par défaut (modifiable, validé avec les règles) : Frais de port, Remise, Bon cadeau,
Échantillon = facturés au client ; Frais & commissions, Ajustement manuel, Test, Autre = non.

**Pourquoi v3 change la formule.** La v2 définissait `Montant facturé = CAN + RM + FP`. Avec
cette formule, valider `GIFTX1` comme bon cadeau faisait passer le montant de 72 à 52 £ alors
qu'aucune facture n'a changé (annexe D). La FCI reste à 72 £ : la validation **reclasse** le
montant des ventes de produits vers la facturation non-produit, sans le faire disparaître.

**Limites de la FCI (affichées avec l'indicateur)** : ce n'est **ni un montant comptable, ni un
montant encaissé** ; aucune TVA, aucun avoir comptable, aucun paiement ne figure dans les données ;
les retours sont datés à l'annulation ; ajustements (R2), annulations incohérentes (R4) et retours
hors C (R9) en sont exclus par défaut ; sa valeur dépend du marquage des sous-catégories.

### 3.5 Options réversibles et recalcul complet

Tous les indicateurs sont une **fonction pure** `KPI = f(données, jeu de règles, filtres)`.
Changer une option relance **le calcul complet** (catégories, ventes, unités, commandes, panier,
clients, facturation, séries temporelles, produits, réconciliations) : aucun KPI n'est mis à jour
isolément. Le tableau avant/après (§6.3) affiche **tous** les KPI principaux.

| Option | Défaut | Alternative | Effet exact de l'alternative |
|---|---|---|---|
| **O1** Doublons | Exclus (R0) | Inclus | Les lignes R0 sont reclassées par R1…R10 comme des lignes ordinaires |
| **O2** Ajustements | Hors CA | Dans le CA net | `CAN += S_R2` ; VB, R, C, UP, clients inchangés |
| **O3** C incohérentes | Exclues | Retours à signe corrigé | `RS −= Σ |m|(R4)` ⇒ R, CAN, TR, FCI changent |
| **O4** Retours hors C | Exclus | Retours | `RS += S_R9` (≤ 0) ⇒ R, CAN, TR, FCI changent |
| **O5** Codes atypiques | Non validés (restent produits) | Catégorie validée | Lignes reclassées en R3 ⇒ tous les KPI produits et clients changent, FCI inchangée si la sous-catégorie est facturée |

### 3.6 Factures sans vente payante

`Factures sans vente payante = factures distinctes − factures ayant ≥ 1 ligne R10`. Elles
n'entrent **jamais** dans C ni dans le dénominateur de PM. Elles sont comptées et listées avec
leur **motif** = catégories de leurs lignes (ex. « uniquement gratuites », « annulation »,
« ajustement », « valeur manquante »).

### 3.7 Valeurs manquantes (R1)

Une ligne R1 est exclue de **tous** les KPI : montants, unités (même si `Quantity` est
renseignée), commandes, séries temporelles, clients, produits. Elle apparaît dans la
réconciliation d'intégrité (nombre de lignes, montant « non calculable ») et dans la liste des
lignes, et elle ne compte pas dans `M_brut`. Une facture ne contenant que des lignes R1 est une
facture sans vente payante (motif « valeur manquante »). `Customer ID` manquant n'est **pas** R1
(marqueur F3).

### 3.8 Retours hors facture C (R9)

`Quantity < 0`, `Price > 0`, facture sans préfixe C : retour non documenté par une facture
d'annulation, ou erreur de signe. Par défaut exclu (listé « à examiner », montant affiché) ; avec
l'option O4, il est ajouté aux retours. Il n'affecte jamais VB, C ni UP.

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

Cas limite : une période **complète sans aucune ligne** (ex. un mois entier vide à l'intérieur de
la fenêtre) affiche ses KPI à 0 avec l'avertissement « aucune donnée : fermeture ou données
manquantes ? » et apparaît dans la liste des trous ; elle n'est jamais qualifiée de partielle.

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

But : expliquer le passage du montant brut au CA **pour la configuration active**. Le pont
retire le montant signé de chaque catégorie hors CA, puis **réintègre** ce que les options
actives font entrer dans le CA net, avec le signe défini par l'option :

```
M_brut
 − S_R0  doublons exacts                    (0 si O1 = inclus : lignes déjà reclassées)
 − S_R2  ajustements comptables
 − S_R3  lignes non-produit validées (détail par sous-catégorie)
 − S_R4  annulations incohérentes (montant saisi)
 − S_R6 − S_R7 − S_R8                        (montants nuls, affichés pour mémoire)
 − S_R9  retours hors facture C (montant saisi)
 + S_R2          si O2 = ajustements dans le CA net
 − Σ |m|(R4)     si O3 = retours à signe corrigé
 + S_R9          si O4 = retours
 = CAN
```

Contrôle ✓/✗ : le résultat du pont égale le CAN calculé directement (`VB + RS`, plus `S_R2` si
O2). *(v3 : la v2 ne présentait que le pont des options par défaut ; il ne retombait pas sur le CAN
quand O2, O3 ou O4 étaient activées — annexe D.)*

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
- **Vérification** (tests détaillés en annexe B) :
  1. la fixture de l'annexe A est un test automatique (valeurs exactes, tous scénarios) ;
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

**Scénarios avant / après — tous les KPI** (recalculés par `verif_annexe_a.py`) :

| KPI | S0 défaut | S1 doublons inclus | S2 ajust. dans CA | S3 C incoh. = retours | S4 hors C = retours | S5 GIFTX1 = bon cadeau |
|---|---|---|---|---|---|---|
| Ventes brutes VB | 80 | 100 | 80 | 80 | 80 | 60 |
| Retours R | 10 | 10 | 10 | 30 | 30 | 10 |
| **CA produits net** | **70** | **90** | **20** | **50** | **50** | **50** |
| Taux de retour | 12,5 % | 10,0 % | 12,5 % | 37,5 % | 37,5 % | 16,7 % |
| Commandes C | 4 | 4 | 4 | 4 | 4 | 3 |
| Panier moyen | 20,00 | 25,00 | 20,00 | 20,00 | 20,00 | 20,00 |
| Unités payantes | 7 | 9 | 7 | 7 | 7 | 6 |
| Unités gratuites | 5 | 5 | 5 | 5 | 5 | 5 |
| Prix moyen unitaire | 11,43 | 11,11 | 11,43 | 11,43 | 11,43 | 10,00 |
| Factures sans vente payante | 9 | 9 | 9 | 9 | 9 | 10 |
| Clients actifs | 2 | 2 | 2 | 2 | 2 | 2 |
| VB clients identifiés | 50 | 70 | 50 | 50 | 50 | 30 |
| Part du CA sans client | 37,5 % | 30,0 % | 37,5 % | 37,5 % | 37,5 % | 50,0 % |
| CA net après remises | 67 | 87 | 67 | 47 | 47 | 47 |
| **Facturation client indicative** | **72** | **92** | **72** | **52** | **52** | **72** |
| Codes non validés (£ / lignes) | 20 / 1 | 20 / 1 | 20 / 1 | 20 / 1 | 20 / 1 | 0 / 0 |
| Pont actif = CAN | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

Note S2 : la FCI n'inclut pas les ajustements, même lorsque O2 les ajoute au CA net (limite
documentée §3.4). Inclure les C incohérentes telles quelles donnerait CAN = 90 : option refusée.

**Effet de la validation de `GIFTX1` comme « Bon cadeau » (S0 → S5)**

| Famille | Indicateur | Avant | Après | Explication |
|---|---|---|---|---|
| Ventes de produits | VB / CAN | 80 / 70 | 60 / 50 | La ligne 16 (20 £) quitte R10 pour R3 |
| | Unités payantes | 7 | 6 | Sa quantité (1) n'est plus une unité de produit |
| | Commandes | 4 | 3 | La facture 1013 n'a plus de ligne R10 |
| | Panier moyen | 20,00 | 20,00 | 80/4 → 60/3 (égalité fortuite) |
| | Prix moyen unitaire | 11,43 | 10,00 | 80/7 → 60/6 |
| | Taux de retour | 12,5 % | 16,7 % | Retours inchangés, VB plus faible |
| | Factures sans vente payante | 9 | 10 | 1013 rejoint la liste (motif « non-produit ») |
| Clients | Clients actifs | 2 | 2 | 17003 reste actif grâce à la ligne 14 |
| | VB identifié / part sans client | 50 / 37,5 % | 30 / 50,0 % | La part des ventes anonymes augmente mécaniquement |
| Facturation | Bons cadeaux BC | 0 | 20 | Montant reclassé, pas supprimé |
| | **FCI** | **72** | **72** | Inchangée : aucune facture n'a changé |
| | « Montant facturé » formule v2 | 72 | **52** | **Incohérence corrigée en v3** |
| Transparence | Bandeau codes non validés | 20 £ / 1 | aucun | Validation tracée (version vN) |

## Annexe B — Tests qui confirmeront l'exactitude

À écrire **avant** le code de calcul (ils doivent échouer, puis passer) :

| Test | Vérifie |
|---|---|
| `test_annexe_a_categories` | Catégorie attendue pour chacune des 16 lignes |
| `test_annexe_a_integrity` | Σ N_k = 16 ; Σ S_k = M_brut = 42 ; R1 non calculable |
| `test_annexe_a_scenarios[S0…S5]` | **Vecteur complet** des KPI de la table de l'annexe A pour chaque scénario |
| `test_bridge_equals_net_for_every_option` | Pont actif = CAN pour S0…S5 et pour toutes les combinaisons O1–O4 (16) |
| `test_validation_reclassifies_without_changing_billing` | S0 → S5 : FCI = 72 constante ; VB, C, UP, clients changent comme indiqué |
| `test_no_double_subtraction` | `CAN = VB + RS = VB − R = Σ m(R10 ∪ R5)` (fixture + 1 000 lignes aléatoires) |
| `test_partition_exhaustive_random` | Toute combinaison préfixe × signe Q × signe P × manquants tombe dans exactement une catégorie |
| `test_free_lines_do_not_block_orders` | 1001 est une commande malgré sa ligne gratuite ; 1003 n'en est pas une |
| `test_missing_values_excluded_everywhere` | Une ligne R1 n'apparaît dans aucun KPI ni série, mais dans l'intégrité |
| `test_invoices_without_paid_sale` | 9 factures en S0 avec leurs motifs ; 10 en S5 |
| `test_r9_option` | O4 change R, CAN, TR, FCI ; jamais VB, C, UP |
| `test_coverage_empty_days_not_incomplete` | Fixture annexe C : statuts, couvertures, jours vides, trous |
| `test_coverage_iso_weeks` | 2024-W01 complète, 2024-W06 complète malgré 2 jours vides, 2024-W11 partielle 5/7 |
| `test_empty_month_inside_window` | Mois sans ligne = complet, 29 jours vides, signalé comme trou |
| `test_oracle_agreement` | Sur l'échantillon synthétique retail (18 337 lignes) : l'application et `verif_annexe_a.py` (adapté) donnent les mêmes KPI |
| Non-régression | Les 56 tests backend et 8 tests frontend existants restent verts (CI Linux + Windows) |

## Annexe C — Fixture de couverture temporelle

Lignes chaque jour du 01/01/2024 au 15/03/2024, **sauf** : tous les samedis ; du 15 au 17/01
(3 jours) ; du 10 au 20/02 (11 jours). Fenêtre = 01/01/2024 → 15/03/2024. Résultats recalculés :

| Période | Statut | Couverture | Jours sans données | Trou ≥ 7 jours |
|---|---|---|---|---|
| Janvier 2024 | **Complète** | 31/31 | 7 (4 samedis + 15–17/01) | Non (3 jours < 7) |
| Février 2024 | **Complète** | 29/29 | 13 (2 samedis isolés + 10–20/02) | **Oui : 10/02 → 20/02, 11 jours** |
| Mars 2024 | **Partielle (bord)** | 15/31 | 2 (samedis 2 et 9) | Non |
| Semaine 2024-W01 | Complète | 7/7 | — | — |
| Semaine 2024-W11 | Partielle | 5/7 | — | — |

Jours vides par jour de semaine : samedi 10/10 (fermeture structurelle) ; lundi 3/11, mardi 3/11,
mercredi 2/11, jeudi 1/11, vendredi 1/11, dimanche 2/10.

Second cas : données du 02/01 au 30/01 puis du 01/03 au 19/03/2024, rien en février → février
**complète** avec 29 jours sans données, trou du 31/01 au 29/02 (30 jours).

## Annexe D — Résultat du recalcul indépendant de la v2

`verif_annexe_a.py` : **24/24 valeurs écrites dans la v2 concordent** avec le recalcul. Le
recalcul de **tous** les KPI de chaque scénario a révélé deux incohérences de la v2, corrigées en
v3 :

1. « Montant facturé = CAN + RM + FP » variait (72 → 52 £) lors de la validation d'un code
   atypique alors qu'aucune facture ne change → remplacé par la FCI (§3.4).
2. Le pont §6.2 ne retombait sur le CAN qu'avec les options par défaut (ex. S2 : pont 70, CAN 20)
   → pont calculé pour la configuration active.

Autres précisions v3 : R1 étendu à `Invoice` et `InvoiceDate` ; R7 non réversible (définition) ;
« Total enregistré » supprimé ; options O1–O5 formalisées ; factures sans vente payante, valeurs
manquantes et retours hors C détaillés (§3.6–3.8) ; mois vide à l'intérieur de la fenêtre.
