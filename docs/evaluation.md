# Protocole et rapport d'évaluation

> **Aucun modèle n'est encore évalué** (v0.2.0). Ce document consignera, à partir de
> l'étape 4, uniquement des métriques réellement mesurées, avec date, versions, paramètres
> et seeds. Aucun chiffre ne sera ajouté par anticipation.

## Protocole retenu (cahier des charges §10)

- Baseline simple obligatoire pour chaque tâche.
- Séries temporelles : split chronologique train / validation / test, sans mélange.
- Sélection de modèle sur la validation ; le test sert une seule fois, à la fin.
- AI4I : exclusion de `TWF`, `HDF`, `PWF`, `OSF`, `RNF` (fuite de cible) ; métriques
  Precision, Recall, F1, PR-AUC et matrice de confusion — jamais l'accuracy seule.
- Expériences importantes répétées sur plusieurs seeds.
- Decision Engine : benchmark synthétique à mécanisme connu, stratégies (A) impact seul,
  (B) impact − coût, (C) impact, coût, incertitude et robustesse — présenté comme tel.

## Vérifications effectuées à ce jour (étapes 1–2)

| Date | Vérification | Résultat |
|---|---|---|
| 2026-10-18 | `pytest` backend (Python 3.11, Linux) | 45 tests réussis |
| 2026-10-18 | `vitest` frontend | 7 tests réussis |
| 2026-10-18 | Parcours navigateur réel (Chromium/Playwright) : accueil → échantillon → rôles → upload → refus `.xlsm` → historique | Réussi, captures dans `docs/screenshots/` |

Non vérifié : installation sous Windows (couverte par la CI `windows-latest`, à confirmer au
premier push), exécution sur les jeux UCI réels.

## Empreintes des jeux officiels

À compléter lors du premier téléchargement (`scripts/download_datasets.py`).
