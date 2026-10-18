# Dictionnaire de données

## Schéma Retail (colonnes reconnues, insensible à la casse et aux espaces)

| Colonne | Rôle proposé | Description | Contrôles appliqués |
|---|---|---|---|
| `InvoiceNo` / `Invoice` | Identifiant | Numéro de facture ; préfixe `C` = annulation | Comptage des annulations ; types incohérents signalés |
| `StockCode` | Catégorie | Code produit | — |
| `Description` | Texte libre | Libellé produit | — |
| `Quantity` | Mesure métier | Quantité (négative = retour/annulation probable) | Comptage des quantités négatives (conservées) |
| `InvoiceDate` | Date / temps | Horodatage de facture | Format détecté, dates invalides, ambiguïté jour/mois |
| `UnitPrice` / `Price` | Mesure métier | Prix unitaire | Comptage des prix ≤ 0 |
| `CustomerID` | Identifiant | Client pseudonyme — **ne pas exporter** | Comptage des manquants |
| `Country` | Catégorie | Pays | — |

Reconnu si au moins 4 de ces noms sont présents.

## Schéma Maintenance (AI4I 2020)

| Colonne | Rôle proposé | Unité | Remarque |
|---|---|---|---|
| `UDI` | Identifiant | — | |
| `Product ID` | Identifiant | — | Encode aussi la qualité L/M/H |
| `Type` | Catégorie | — | L / M / H |
| `Air temperature [K]` | Mesure métier | K | |
| `Process temperature [K]` | Mesure métier | K | |
| `Rotational speed [rpm]` | Mesure métier | tr/min | |
| `Torque [Nm]` | Mesure métier | N·m | |
| `Tool wear [min]` | Mesure métier | min | |
| `Machine failure` | Cible / label | 0/1 | Taux de panne et déséquilibre signalés |
| `TWF`, `HDF`, `PWF`, `OSF`, `RNF` | **Ignorer** | 0/1 | Modes de panne dérivés du label → **fuite de cible** |

Reconnu si au moins 5 de ces noms sont présents.

## Rôles de colonnes

| Rôle | Contrainte de validation |
|---|---|
| Identifiant | — |
| Date / temps | La colonne doit être interprétable comme date |
| Numérique, Mesure métier | ≥ 95 % des valeurs numériques |
| Catégorie, Texte libre, Ignorer | — |
| Cible / label | ≥ 2 valeurs distinctes ; une seule cible par dataset |

## Codes de constats qualité

| Code | Gravité | Signification |
|---|---|---|
| `duplicate_rows` | Attention | Lignes strictement identiques à une précédente |
| `empty_column` | Attention | Colonne entièrement vide |
| `high_missing` | Attention | ≥ 30 % de manquants |
| `missing_values` | Info | Quelques manquants |
| `constant_column` | Attention | Une seule valeur distincte |
| `mixed_types` | Attention | Mélange de valeurs numériques et textuelles (≥ 5 % numériques) |
| `invalid_dates` | Attention | Valeurs non conformes au format de date détecté |
| `ambiguous_dates` | Attention | Jour/mois et mois/jour tous deux plausibles |
| `high_cardinality` | Info | ≥ 50 modalités et ≥ 50 % de valeurs distinctes |
| `infinite_values` | Erreur | Valeurs ±∞ |
| `unnamed_column` | Info | Colonne sans en-tête |
| `multiple_targets` | Info | Plusieurs cibles proposées |
| `retail_negative_quantity` | Attention | Quantités négatives |
| `retail_non_positive_price` | Attention | Prix ≤ 0 |
| `retail_cancellations` | Info | Factures d'annulation |
| `retail_missing_customer` | Info | Lignes sans client |
| `target_leakage` | Attention | Colonnes dérivées du label |
| `class_imbalance` | Attention / Info | Part de la classe positive (attention si < 10 %) |
