# Datasets

## 1. Échantillons synthétiques (`samples/`) — commités

| Fichier | Lignes | Domaine | Nature |
|---|---|---|---|
| `synthetic_retail_2024.csv` | 18 337 | Retail | **100 % synthétique** |
| `synthetic_retail_2024_jan_feb.xlsx` | 2 990 | Retail | **100 % synthétique** (extrait du précédent) |
| `synthetic_maintenance.csv` | 5 000 | Maintenance | **100 % synthétique** |

- Générés par `scripts/generate_samples.py` (seed `20261018`) ; le mécanisme générateur et les
  événements injectés (journée promo ×3, quantités extrêmes, annulations, doublons, prix nuls,
  valeurs manquantes) sont décrits dans `samples/manifest.json`.
- Ils reprennent **uniquement les noms de colonnes** des jeux UCI pour tester les parcours ;
  ils ne proviennent pas de ces jeux et ne représentent aucune entreprise ni usine réelle.
- Les identifiants clients sont fictifs (`17000`–`17399`).
- Note : le nombre de lignes strictement identiques détectées (270 pour le CSV retail) dépasse
  les 91 doublons injectés, car une même facture peut contenir deux fois le même article avec
  la même quantité — ce qui arrive aussi dans les vraies données.

Régénération :

```powershell
uv run --project backend python scripts/generate_samples.py
```

## 2. Jeux publics officiels (`raw/`) — jamais commités

| Jeu | Page officielle | Usage prévu | Précautions |
|---|---|---|---|
| UCI Online Retail (id 352) | https://archive.ics.uci.edu/dataset/352/online+retail | KPI, agrégation temporelle, anomalies exploratoires | Retours/annulations (`C…`), doublons, prix nuls, `CustomerID` manquants ; identifiants clients pseudonymes → ne pas republier |
| UCI AI4I 2020 Predictive Maintenance (id 601) | https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset | Classification de panne, seuils | **Jeu synthétique** ; forte asymétrie des classes ; colonnes TWF/HDF/PWF/OSF/RNF dérivées du label (fuite de cible) |
| Numenta Anomaly Benchmark | https://github.com/numenta/NAB | Benchmark secondaire (étape 4) | Sous-partie à documenter ; suivre la convention d'évaluation NAB |

Licence : les pages UCI indiquent une licence Creative Commons — **à reconfirmer sur chaque page
avant toute redistribution** (cahier des charges §6). Ce dépôt ne redistribue pas ces fichiers.

Téléchargement : `uv run --project backend python scripts/download_datasets.py` (le script
affiche l'empreinte SHA-256 de chaque fichier extrait, à reporter dans `docs/evaluation.md`).
À défaut, téléchargez manuellement et placez les fichiers dans `datasets/raw/`.

Statut au 18/10/2026 : le script n'a **pas encore été exécuté avec succès** — l'environnement
de développement initial n'avait pas accès à archive.ics.uci.edu. Les empreintes seront
consignées lors de la première exécution.
