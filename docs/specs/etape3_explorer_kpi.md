# Spécification — Étape 3 : Explorer & KPI

> Statut : **proposée, en attente de validation** (19/10/2026). Aucun code n'est écrit avant
> validation. Jeu de référence : UCI Online Retail II, deux feuilles empilées (≈ 1,07 M lignes).

## 1. Objectif et périmètre

L'étape 3 transforme un dataset qualifié (étape 2) en **indicateurs descriptifs vérifiables**.
Tous les résultats sont des **faits observés** calculés de façon déterministe (pandas) :
aucune prédiction, aucune causalité, aucun LLM.

Principes non négociables :

1. **Aucune ligne n'est exclue sans règle explicite**, affichée avec son nombre de lignes et
   son montant.
2. **Toute exclusion est réversible** et son impact sur chaque KPI est visible (avant/après).
3. **Les règles métier sont validées par l'utilisateur** ; un code atypique non validé n'est
   jamais exclu automatiquement.
4. **Réconciliation exacte** : la somme des catégories redonne toujours le total du fichier
   (lignes et montants).
5. Chaque KPI affiche **formule, numérateur, dénominateur, période, filtres et jeu de règles**.

Hors périmètre (documenté à l'écran) : marge (pas de coût d'achat), ruptures et surstock (pas de
stock), péremption (pas de dates), détection statistique d'anomalies (étape 4), prévision
(étape 5), explication causale (étape 6).

## 2. Grandeurs de base

- `montant_ligne = Quantity × Price` (en £, devise du jeu UCI ; affichée telle quelle).
- `préfixe_facture` = première lettre de `Invoice` si c'est une lettre, sinon aucun.
- `code_standard` : `StockCode` conforme au motif produit `^\d{5}[A-Za-z]{0,2}$`
  (5 chiffres + 0 à 2 lettres, ex. `22423`, `85123A`, `15056BL`). Motif affiché et modifiable.
- `code_atypique` : tout autre `StockCode` (ex. `POST`, `C2`, `gift_0001_10`). La détection
  ne repose **pas** sur « code sans chiffre » (règle trop fragile : `C2` ou `gift_…` contiennent
  des chiffres).

## 3. Règles de classification des lignes

Chaque ligne reçoit **une seule catégorie**, en appliquant les règles **dans cet ordre** (la
première qui s'applique gagne). Les identifiants R0…R8 sont stables (cités dans l'interface,
l'historique et les tests).

| Règle | Catégorie | Condition exacte | Traitement par défaut | Réversible |
|---|---|---|---|---|
| **R0** | Doublon exact | Ligne identique sur **toutes les colonnes** à une ligne précédente (la 1re occurrence est conservée) | Exclue de tous les KPI | Oui (interrupteur) |
| **R1** | Ajustement comptable | `préfixe_facture = A` **ou** `Price < 0` | Exclue des KPI de vente ; montant affiché à part | Oui |
| **R2** | Annulation incohérente | `préfixe_facture = C` **et** `Quantity > 0` | Exclue ; listée comme anomalie de saisie | Oui |
| **R3** | Annulation / retour | `préfixe_facture = C` **et** `Quantity ≤ 0` | Comptée dans **Retours** (si code produit) ou dans la catégorie de son code (si code non-produit validé, ex. remboursement de port) | Non (définition) |
| **R4** | Préfixe de facture inconnu | `préfixe_facture` ∉ {aucun, A, C} | **Incluse** comme vente mais signalée « à valider » | Oui (validation) |
| **R5** | Code non-produit **validé** | `code_atypique` **et** catégorie validée par l'utilisateur ∈ {Frais de port, Remise, Frais & commissions, Ajustement manuel, Échantillon, Test, Bon cadeau, Autre non-produit} | Exclue du CA produits ; affichée dans sa catégorie ; Remises et Frais de port entrent dans le **Montant facturé** | Oui |
| **R6** | Ligne sans valeur | `Price = 0` | Exclue du CA (montant nul), des **unités** et du **comptage de commandes** | Oui |
| **R7** | Quantité négative hors annulation | `Quantity < 0` et `préfixe_facture` ≠ C et `Price > 0` | Exclue ; listée « à examiner » (retour sans facture C) | Oui |
| **R8** | Vente valide | Tout le reste (`Quantity > 0`, `Price > 0`, facture sans préfixe ou R4) | **Comptée** dans les KPI de vente | — |

Précisions :

- **Codes atypiques non validés** : classés R8 (vente valide), **jamais exclus automatiquement**.
  Les KPI affichent « dont X £ issus de N codes atypiques non validés ».
- **Lignes sans `Customer ID`** : classées normalement (R8 si vente valide → comptées dans le
  CA) ; **exclues des seuls KPI qui exigent un client identifié** (§5.4), avec dénominateur
  affiché.
- **Retours (R3)** : comptés **à la date de l'annulation**, sans rapprochement avec la vente
  d'origine (qui peut précéder la période du fichier). Limite affichée.
- **Prix négatifs** : toujours R1, quelle que soit la facture (un prix unitaire négatif n'est
  pas une vente).
- **Remises** (code validé « Remise ») : montant généralement négatif ; non incluses dans le
  CA produits, incluses dans le Montant facturé et dans le « CA net après remises ».

## 4. Validation des règles métier (codes atypiques)

1. L'outil liste **tous** les codes atypiques avec : nombre de lignes, montant total, nombre de
   factures, 3 descriptions les plus fréquentes, période d'apparition.
2. Il **propose** une catégorie à partir de la description (mots-clés documentés : `POSTAGE` →
   Frais de port, `DISCOUNT` → Remise, `MANUAL` → Ajustement manuel, `BANK CHARGES` /
   `FEE` / `COMMISSION` → Frais & commissions, `ADJUST` → Ajustement, `SAMPLE` → Échantillon,
   `TEST` → Test, `GIFT` / `VOUCHER` → Bon cadeau). La proposition est marquée **« proposée »**
   et **n'est pas appliquée**.
3. L'utilisateur confirme ou corrige chaque code (catégorie = « Produit » possible), puis
   **valide le jeu de règles**.
4. Chaque validation crée une **version** du jeu de règles (`v1`, `v2`…), enregistrée dans
   l'historique avec les modifications ; chaque résultat de KPI cite la version utilisée.

Le jeu de règles contient aussi : interrupteurs R0, R1, R2, R4, R6, R7 ; motif `code_standard` ;
seuils de rotation lente (§5.6).

## 5. Indicateurs

### 5.1 Ventes (lignes R8)

| KPI | Formule | Dénominateur / remarque |
|---|---|---|
| CA produits brut | Σ `montant_ligne` (R8) | — |
| Retours produits | Σ \|`montant_ligne`\| (R3 sur codes produits) | Date d'annulation |
| **CA produits net** | CA brut − Retours | KPI principal |
| CA net après remises | CA net + Σ remises (R5 « Remise », négatives) | — |
| Montant facturé | CA net + frais de port + remises (R5) | Rapprochable des factures |
| Taux de retour | Retours ÷ CA brut | Même période, limite affichée |
| Commandes | nb de `Invoice` distinctes ayant ≥ 1 ligne R8 | — |
| Panier moyen | CA brut ÷ Commandes | — |
| Unités vendues | Σ `Quantity` (R8) | — |
| Prix moyen unitaire | CA brut ÷ Unités | — |

### 5.2 Temps

- Agrégation **mensuelle** (par défaut) et **hebdomadaire** (semaine ISO).
- **Période incomplète** : un mois dont les données ne couvrent pas tous les jours calendaires
  entre son 1er et son dernier jour attendu (ex. décembre 2011 s'arrêtant le 9) est marqué et
  **exclu des comparaisons** (affiché grisé).
- Comparaisons : mois vs mois précédent ; mois vs même mois de l'année précédente (si les deux
  sont complets).

### 5.3 Décomposition d'une variation (descriptive)

Pour deux périodes P0 → P1 : `CA = Commandes × Panier`, donc
`ΔCA = ΔCommandes × Panier₀ + Commandes₀ × ΔPanier + ΔCommandes × ΔPanier` (somme exacte
affichée). Contributions à ΔCA par **pays** et par **produit** (top 10 hausses / baisses).
Étiquette obligatoire : « Association descriptive — n'établit pas de cause ».

### 5.4 Clients (lignes R8 avec `Customer ID`)

Clients actifs, nouveaux clients (1er achat dans la période, sur l'historique disponible),
clients récurrents, taux de réachat, CA moyen par client identifié, **part du CA sans client
identifié**. Chaque KPI affiche « calculé sur N lignes identifiées (x % des ventes valides) ».

### 5.5 Pays

CA net, commandes, panier moyen et part du CA par pays ; part du pays dominant.

### 5.6 Produits

- Top produits par CA net et par unités ; produits les plus retournés (montant, taux).
- **ABC** : tri par CA net décroissant ; A = cumul ≤ 80 %, B = 80–95 %, C = > 95 % (seuils
  affichés).
- **Rotation lente** (sens « fréquence de vente », pas rotation de stock comptable) : pour chaque
  produit, date de dernière vente, jours depuis (référence = dernière date du dataset filtré),
  part des semaines avec ≥ 1 vente depuis sa 1re vente, unités / semaine. « Lent » si
  `jours depuis dernière vente ≥ 90` **ou** `part des semaines < 25 %` — **seuils
  configurables** ; un produit vendu depuis moins de 8 semaines est « trop récent pour
  conclure ».

### 5.7 Autres domaines

- **Maintenance** : taux de panne global et par `Type`, statistiques des capteurs par classe
  (descriptif, pas de modèle).
- **Générique** : statistiques descriptives, distributions (histogrammes), corrélations
  descriptives entre colonnes numériques (Pearson et Spearman, avec mention « corrélation ≠
  causalité »).

## 6. Transparence : impact des règles

1. **Tableau de réconciliation** : pour chaque catégorie R0…R8 → lignes, montant, part. Total =
   total du fichier (contrôle affiché ✓/✗).
2. **Pont « somme naïve → CA produits net »** : Σ `montant_ligne` de toutes les lignes, puis
   chaque règle retire ou reclasse un montant, jusqu'au CA net.
3. **Avant / après par règle** : pour chaque règle réversible, valeur des KPI principaux (CA net,
   commandes, panier moyen, unités, clients actifs) avec la règle active et désactivée, et l'écart.
4. **Détail** : clic sur une règle → lignes concernées (paginées), exportables en CSV.

## 7. API (prévue)

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/api/datasets/{id}/rules` | Jeu de règles courant + codes atypiques et propositions |
| PUT | `/api/datasets/{id}/rules` | Valider une nouvelle version du jeu de règles |
| GET | `/api/datasets/{id}/kpi?from=&to=&country=&granularity=` | KPI, séries, réconciliation, pont, impact |
| GET | `/api/datasets/{id}/kpi/products?…` | Top, ABC, rotation lente |
| GET | `/api/datasets/{id}/kpi/lines?rule=R3&offset=&limit=` | Lignes d'une catégorie |
| GET | `/api/datasets/{id}/kpi/export?format=csv\|json` | Export des résultats |

Chaque calcul est journalisé (`kind = "kpi"`) avec filtres, version des règles et résumé.

## 8. Interface « Explorer »

Onglets : **Règles** (codes atypiques à valider, interrupteurs, seuils) · **Vue d'ensemble**
(cartes KPI avec formule, série mensuelle CA net / retours avec mois incomplets grisés,
réconciliation, pont) · **Évolution** (comparaisons, décomposition) · **Produits** (top, ABC,
rotation lente) · **Clients & pays**. Filtres : période, pays. Bandeau permanent si des codes
atypiques ne sont pas validés.

## 9. Vérification

1. **Fixture calculée à la main** (~20 lignes couvrant R0…R8, sans client, remise, port, mois
   incomplet) : valeurs exactes attendues pour chaque KPI.
2. **Invariant de réconciliation** testé sur fixtures, échantillons synthétiques et fichier
   réel : Σ catégories = total (lignes et montants, au centime).
3. **Recalcul indépendant** : script séparé (`scripts/verify_kpi.py`), écrit sans réutiliser
   le module, recalculant CA net mensuel, commandes et retours ; écart attendu = 0.
4. **Contrôle manuel Excel** : procédure documentée (tableau croisé sur un mois, filtres
   équivalents aux règles) pour retrouver le CA net affiché.
5. **Non-régression** : tous les tests existants (étapes 1–2) restent verts ; CI Linux + Windows.
6. **Performance** : KPI sur 1,07 M lignes en moins de 10 s (objectif, à mesurer et reporter).

## 10. Critères d'acceptation

- Les 9 catégories et leurs comptes s'affichent ; la réconciliation est exacte sur le fichier réel.
- Aucun code atypique n'est exclu sans validation ; la version des règles est tracée.
- Chaque règle réversible montre son impact avant/après sur les KPI principaux.
- Les KPI clients n'utilisent que des lignes identifiées et l'indiquent.
- Les mois incomplets sont signalés et exclus des comparaisons.
- Le recalcul indépendant concorde ; les résultats et limites sont consignés dans
  `docs/evaluation.md` avec la date d'exécution.
