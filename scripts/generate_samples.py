"""Génère les datasets de démonstration SYNTHÉTIQUES de `datasets/samples/`.

Ces fichiers ne sont PAS les jeux UCI : ils en reprennent seulement les noms de colonnes
pour permettre des démonstrations et des tests reproductibles sans données réelles.
Leur mécanisme générateur est entièrement décrit ici et dans `manifest.json`.

Usage (depuis la racine du dépôt) :
    uv run --project backend python scripts/generate_samples.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 20261018
OUT = Path(__file__).resolve().parents[1] / "datasets" / "samples"


# --------------------------------------------------------------------------- Retail


def make_retail(rng: np.random.Generator) -> tuple[pd.DataFrame, dict]:
    days = pd.date_range("2024-01-01", "2024-12-31", freq="D")
    n_products = 60
    products = pd.DataFrame(
        {
            "StockCode": [f"SKU{1000 + i}" for i in range(n_products)],
            "Description": [f"ARTICLE SYNTHETIQUE {i + 1:02d}" for i in range(n_products)],
            "base_price": np.round(rng.lognormal(mean=1.2, sigma=0.6, size=n_products), 2),
            "popularity": rng.dirichlet(np.ones(n_products) * 0.8),
        }
    )
    customers = [f"{17000 + i}" for i in range(400)]
    countries = ["France", "Tunisia", "Germany", "Spain", "Belgium", "Italy"]
    country_w = np.array([0.45, 0.2, 0.12, 0.1, 0.08, 0.05])
    customer_country = dict(
        zip(customers, rng.choice(countries, len(customers), p=country_w), strict=True)
    )

    weekday_factor = np.array([1.0, 1.05, 1.1, 1.05, 1.2, 0.7, 0.5])
    promo_day = pd.Timestamp("2024-06-14")

    rows = []
    invoice_no = 500000
    for day in days:
        seasonal = 1.0 + 0.35 * max(0.0, (day.dayofyear - 270) / 95)  # hausse T4
        lam = 14 * weekday_factor[day.dayofweek] * seasonal
        if day == promo_day:
            lam *= 3.0  # événement injecté (documenté)
        for _ in range(rng.poisson(lam)):
            invoice_no += 1
            cust = rng.choice(customers) if rng.random() > 0.2 else None
            country = customer_country[cust] if cust else rng.choice(countries, p=country_w)
            ts = day + pd.Timedelta(minutes=int(rng.integers(8 * 60, 19 * 60)))
            for _ in range(int(rng.integers(1, 7))):
                p = products.iloc[rng.choice(n_products, p=products["popularity"])]
                qty = int(rng.geometric(0.25))
                price = p["base_price"]
                rows.append(
                    [
                        str(invoice_no),
                        p["StockCode"],
                        p["Description"],
                        qty,
                        ts,
                        price,
                        cust,
                        country,
                    ]
                )

    df = pd.DataFrame(
        rows,
        columns=[
            "InvoiceNo",
            "StockCode",
            "Description",
            "Quantity",
            "InvoiceDate",
            "UnitPrice",
            "CustomerID",
            "Country",
        ],
    )

    # Annulations : 2 % des factures dupliquées avec préfixe C et quantités négatives.
    inv_ids = df["InvoiceNo"].unique()
    cancelled = rng.choice(inv_ids, size=int(0.02 * len(inv_ids)), replace=False)
    canc = df[df["InvoiceNo"].isin(cancelled)].copy()
    canc["InvoiceNo"] = "C" + canc["InvoiceNo"]
    canc["Quantity"] = -canc["Quantity"]
    canc["InvoiceDate"] = canc["InvoiceDate"] + pd.Timedelta(hours=2)

    # Lignes à prix nul (ajustements) : 0,3 %.
    zero_idx = rng.choice(df.index, size=int(0.003 * len(df)), replace=False)
    df.loc[zero_idx, "UnitPrice"] = 0.0

    # Quantités extrêmes injectées : 6 lignes.
    extreme_idx = rng.choice(df.index, size=6, replace=False)
    df.loc[extreme_idx, "Quantity"] = rng.integers(2000, 6000, size=6)

    # Doublons exacts : 0,5 %.
    dup = df.sample(frac=0.005, random_state=SEED)

    out = pd.concat([df, canc, dup]).sort_values(["InvoiceDate", "InvoiceNo"], kind="stable")
    out = out.reset_index(drop=True)
    out["InvoiceDate"] = out["InvoiceDate"].dt.strftime("%Y-%m-%d %H:%M:%S")

    meta = {
        "injected_events": {
            "promo_spike_day": str(promo_day.date()),
            "promo_spike_factor": 3.0,
            "extreme_quantity_rows": len(extreme_idx),
            "cancelled_invoices": len(cancelled),
            "zero_price_rows": len(zero_idx),
            "exact_duplicate_rows": len(dup),
            "missing_customer_share": 0.2,
        },
        "mechanism": "Commandes/jour ~ Poisson(14 × facteur jour de semaine × hausse T4 "
        "linéaire jusqu'à +35 %) ; 1–6 lignes par facture ; quantité ~ géométrique(0,25) ; "
        "prix = prix de base log-normal par produit.",
    }
    return out, meta


# --------------------------------------------------------------------------- Maintenance


def make_maintenance(rng: np.random.Generator, n: int = 5000) -> tuple[pd.DataFrame, dict]:
    types = rng.choice(["L", "M", "H"], size=n, p=[0.5, 0.3, 0.2])
    air = 300 + np.cumsum(rng.normal(0, 0.05, n)) + rng.normal(0, 0.3, n)
    air = 300 + (air - air.mean()) * (2.0 / air.std())
    process = air + 10 + rng.normal(0, 1.0, n)
    speed = np.clip(rng.normal(1540, 180, n), 1160, 2880).round()
    torque = np.clip(40 - (speed - 1540) * 0.045 + rng.normal(0, 6, n), 3.5, 77).round(1)
    wear_inc = {"L": 2, "M": 3, "H": 5}
    wear = np.zeros(n)
    w = 0.0
    for i, t in enumerate(types):
        w = 0.0 if w > 240 or rng.random() < 0.004 else w + wear_inc[t]
        wear[i] = w

    power = torque * speed * 2 * np.pi / 60
    osf_limit = np.select([types == "L", types == "M"], [11000, 12000], 13000)
    twf = ((wear >= 200) & (wear <= 240) & (rng.random(n) < 0.05)).astype(int)
    hdf = (((process - air) < 8.6) & (speed < 1380)).astype(int)
    pwf = ((power < 3500) | (power > 9000)).astype(int)
    osf = ((wear * torque) > osf_limit).astype(int)
    rnf = (rng.random(n) < 0.001).astype(int)
    failure = ((twf + hdf + pwf + osf + rnf) > 0).astype(int)

    df = pd.DataFrame(
        {
            "UDI": np.arange(1, n + 1),
            "Product ID": [f"{t}{40000 + i}" for i, t in enumerate(types)],
            "Type": types,
            "Air temperature [K]": air.round(1),
            "Process temperature [K]": process.round(1),
            "Rotational speed [rpm]": speed.astype(int),
            "Torque [Nm]": torque,
            "Tool wear [min]": wear.astype(int),
            "Machine failure": failure,
            "TWF": twf,
            "HDF": hdf,
            "PWF": pwf,
            "OSF": osf,
            "RNF": rnf,
        }
    )
    # Valeurs manquantes injectées (0,5 %) pour exercer le contrôle qualité.
    miss = rng.choice(n, size=int(0.005 * n), replace=False)
    df["Air temperature [K]"] = df["Air temperature [K]"].astype(float)
    df.loc[miss, "Air temperature [K]"] = np.nan

    meta = {
        "injected_events": {"missing_air_temperature_rows": len(miss)},
        "failure_rate": float(failure.mean()),
        "mechanism": "Règles inspirées de la documentation publique AI4I 2020 : TWF (usure "
        "200–240 min, p=5 %), HDF (ΔT < 8,6 K et vitesse < 1380 tr/min), PWF (puissance hors "
        "[3500, 9000] W), OSF (usure × couple > 11000/12000/13000 selon L/M/H), RNF (0,1 %). "
        "Valeurs générées indépendamment : ce n'est pas le jeu AI4I.",
    }
    return df, meta


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)

    retail, retail_meta = make_retail(rng)
    retail.to_csv(OUT / "synthetic_retail_2024.csv", index=False)

    retail_q1 = retail[retail["InvoiceDate"] < "2024-03-01"].copy()
    retail_q1["InvoiceDate"] = pd.to_datetime(retail_q1["InvoiceDate"])
    retail_q1.to_excel(
        OUT / "synthetic_retail_2024_jan_feb.xlsx", index=False, sheet_name="transactions"
    )

    maint, maint_meta = make_maintenance(rng)
    maint.to_csv(OUT / "synthetic_maintenance.csv", index=False)

    manifest = {
        "generator": "scripts/generate_samples.py",
        "seed": SEED,
        "warning": "Données 100 % synthétiques générées par ORACLE AI. Elles ne proviennent "
        "pas des jeux UCI et ne représentent aucune entreprise ni usine réelle.",
        "samples": [
            {
                "id": "retail-synthetic",
                "file": "synthetic_retail_2024.csv",
                "title": "Retail — transactions synthétiques 2024",
                "domain": "retail",
                "description": "Transactions de vente simulées sur 12 mois (schéma de colonnes "
                "Online Retail), avec annulations, retours, doublons et une journée promo.",
                "synthetic": True,
                "provenance": "Synthétique — " + retail_meta["mechanism"],
                "rows": len(retail),
                "meta": retail_meta,
            },
            {
                "id": "retail-synthetic-xlsx",
                "file": "synthetic_retail_2024_jan_feb.xlsx",
                "title": "Retail — extrait Excel (janv.–févr.)",
                "domain": "retail",
                "description": "Sous-ensemble du jeu précédent au format .xlsx, pour tester "
                "l'import Excel.",
                "synthetic": True,
                "provenance": "Synthétique — extrait de synthetic_retail_2024.csv",
                "rows": len(retail_q1),
            },
            {
                "id": "maintenance-synthetic",
                "file": "synthetic_maintenance.csv",
                "title": "Maintenance — capteurs machine synthétiques",
                "domain": "maintenance",
                "description": "5 000 mesures simulées (schéma de colonnes AI4I 2020) avec label "
                "de panne et modes de panne.",
                "synthetic": True,
                "provenance": "Synthétique — " + maint_meta["mechanism"],
                "rows": len(maint),
                "meta": maint_meta,
            },
        ],
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"retail: {len(retail)} lignes ; xlsx: {len(retail_q1)} ; maintenance: {len(maint)}")
    print(f"taux de panne synthétique : {maint_meta['failure_rate']:.2%}")


if __name__ == "__main__":
    main()
