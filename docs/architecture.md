# Architecture — ORACLE AI

> État : **v0.2.1 — étapes 1 et 2 livrées** (+ import multi-feuilles, constats selon le rôle) (squelette, import, qualité, historique).
> Les modules des étapes 3 à 8 sont listés mais **non implémentés**.

## 1. Vue d'ensemble

Monolithe modulaire, deux processus en local :

```
┌──────────────────────────┐   /api (proxy Vite)   ┌──────────────────────────────────────┐
│ frontend/ React + Vite   │ ────────────────────▶ │ backend/ FastAPI (app.main:create_app)│
│ TypeScript, sans état    │ ◀──────────────────── │                                      │
│ serveur (localStorage :  │        JSON           │  api/ ─▶ services/ ─▶ data/          │
│ seul le dataset actif)   │                       │              │          reporting/   │
└──────────────────────────┘                       │              ├─▶ WorkspaceStore (RAM)  │
                                                   │              └─▶ persistence/ SQLite  │
                                                   └──────────────────────────────────────┘
```

Écart assumé vis-à-vis du cahier des charges (§7) : l'interface est en **React/Vite** au lieu
de Streamlit (choix validé le 18/10/2026, pour coller à la maquette). Conséquence : l'API
FastAPI devient obligatoire (elle était optionnelle) et sert de contrat unique entre UI et
calculs. Le reste de l'arborescence §8 est conservé sous `backend/app/`.

## 2. Flux (étape 2)

`Import → Validation → Lecture → Profilage → Rôles → Rapport/Export → Historique`

1. **Validation** (`data/ingestion.py`) : extension (`.csv`, `.xlsx` ; `.xls`, `.xlsm`, `.xlsb`
   refusés), signature ZIP, taille, présence de macros (`vbaProject.bin`), nombre de lignes et
   de colonnes. Anti « zip bomb » : refus de toute grosse entrée compressée plus de 100×, et
   limite de taille décompressée appliquée à ce qui est réellement lu (1re feuille + parties
   communes ; en mode « toutes les feuilles », toutes comptent). Mémoire observée : ≈ 770 Mo pour
   525 k lignes, ≈ 1,3 Go pour 1,05 M lignes.
2. **Lecture** :
   - CSV : encodage (`utf-8-sig` → `cp1252` → `latin-1`), séparateur (`, ; tab |`), lecture
     **en texte brut** puis conversion numérique **seulement si sans perte** (pas de zéros de
     tête) ; chaque conversion est tracée dans `transformations`.
   - XLSX : moteur `calamine` (repli `openpyxl`), aucune formule évaluée. Deux modes :
     « première feuille » (défaut) ou « toutes les feuilles » (`sheets=all`) qui empile les
     feuilles non vides **à colonnes identiques** (sinon refus explicite), compte les lignes par
     feuille et signale les lignes dupliquées d'une feuille à l'autre (`cross_sheet_duplicates`)
     sans les supprimer.
   - Refus explicite des CSV dont les lignes ont plus de champs que l'en-tête (pandas
     décalerait silencieusement les colonnes).
3. **Profilage** (`data/profiling.py`, fonctions pures) : types sémantiques, manquants,
   doublons, colonnes vides/constantes, types incohérents, dates invalides ou ambiguës
   (jour/mois), forte cardinalité, valeurs infinies ; contrôles métier Retail / Maintenance
   (`data/domains.py`), dont la **fuite de cible** AI4I et le **déséquilibre de classes**.
4. **Rôles** (`data/roles.py`) : proposés, puis confirmés/corrigés par l'utilisateur ; un rôle
   incompatible avec le contenu est refusé avec une raison par colonne ; une seule cible. Chaque
   modification s'applique par-dessus les rôles déjà confirmés. Les constats qui dépendent du
   rôle (mélange chiffres/lettres : `mixed_types` si le rôle exige des nombres, `mixed_codes`
   sinon) et le score sont recalculés par `apply_roles()` sans relire les données.
5. **Export** (`reporting/quality_export.py`) : JSON complet ou CSV `;` (BOM UTF-8), cellules
   neutralisées contre l'injection de formules.
6. **Historique** (`persistence/`) : SQLite via SQLAlchemy 2 — tables `datasets` et
   `analyses` (type, paramètres, résumé, version du moteur, date).

## 3. Politique de conservation des données

- Le fichier téléversé est lu en mémoire ; FastAPI/Starlette peut le placer temporairement
  sur disque pendant la réception multipart (fichier temporaire supprimé en fin de requête).
- Le DataFrame de travail vit **uniquement en RAM** (`services/workspace.py`) : au plus
  `ORACLE_WORKSPACE_MAX_DATASETS` copies (éviction LRU), expirées après
  `ORACLE_WORKSPACE_TTL_MINUTES` d'inactivité, libérables via `DELETE /api/datasets/{id}`.
- SQLite ne stocke **que des métadonnées** : nom, empreinte SHA-256, taille, dimensions,
  domaine, rôles, résumés d'analyse. Jamais de valeurs de cellules.
- Les journaux ne contiennent que des métadonnées (identifiant, format, dimensions, durée).

## 4. API (v0.2.0)

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/api/health` | État, limites, **statut réel de chaque module** |
| GET | `/api/samples` | Catalogue des échantillons synthétiques |
| POST | `/api/datasets/upload` | Import multipart (CSV/XLSX, champ `sheets=first\|all`) → rapport qualité |
| POST | `/api/datasets/samples/{id}` | Charger un échantillon |
| GET | `/api/datasets` | Datasets connus (`loaded` = copie en mémoire) |
| GET | `/api/datasets/{id}` | Détail + rapport qualité (410 si copie expirée) |
| GET | `/api/datasets/{id}/preview` | Pagination des lignes brutes |
| PUT | `/api/datasets/{id}/roles` | Validation et enregistrement des rôles |
| GET | `/api/datasets/{id}/quality/export?format=json\|csv` | Rapport téléchargeable |
| DELETE | `/api/datasets/{id}` | Libère la copie de travail |
| GET | `/api/history` | Analyses journalisées |

Documentation interactive : http://127.0.0.1:8000/docs. Erreurs au format
`{code, message, details}` avec message lisible en français.

## 5. Indicateur de qualité

Moyenne de 4 composantes égales, **tronquée** au dixième (un fichier imparfait n'affiche jamais
100) : complétude (1 − part de cellules manquantes), unicité (1 − part de lignes dupliquées),
cohérence (part de colonnes sans types incohérents / dates invalides / infinis), utilité (part
de colonnes ni vides ni constantes). Heuristique interne, non normalisée.

## 6. Modules à venir

| Étape | Module | Dossier |
|---|---|---|
| 3 | KPI & exploration | `app/analytics/` |
| 4 | Anomalies (MAD, IQR, Isolation Forest) | `app/anomaly/` |
| 5 | Prévision | `app/forecasting/` |
| 6 | Hypothèses causales, Scenario Lab | `app/causal/`, `app/scenarios/` |
| 7 | Rapport de décision HTML, E2E | `app/reporting/` |
| 8 | Docker, captures, vidéo | racine |
