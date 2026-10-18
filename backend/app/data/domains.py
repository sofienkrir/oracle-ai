"""Reconnaissance des deux démonstrateurs (Retail, Maintenance) par les noms de colonnes,
suggestions de rôles et contrôles métier associés.

La reconnaissance est purement déclarative (noms de colonnes) : l'utilisateur peut
toujours corriger les rôles proposés.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd

from app.data.schemas import ColumnRole, Domain, QualityIssue


def norm(name: str) -> str:
    return re.sub(r"[^a-z0-9\[\]]", "", str(name).lower())


@dataclass(frozen=True)
class RoleHint:
    role: ColumnRole
    reason: str


RETAIL_HINTS: dict[str, RoleHint] = {
    "invoiceno": RoleHint("identifier", "Numéro de facture (préfixe « C » = annulation)."),
    "invoice": RoleHint("identifier", "Numéro de facture (préfixe « C » = annulation)."),
    "stockcode": RoleHint("categorical", "Code produit."),
    "description": RoleHint("text", "Libellé produit en texte libre."),
    "quantity": RoleHint("measure", "Quantité vendue (négative = retour/annulation probable)."),
    "invoicedate": RoleHint("datetime", "Date et heure de la facture."),
    "unitprice": RoleHint("measure", "Prix unitaire."),
    "price": RoleHint("measure", "Prix unitaire."),
    "customerid": RoleHint(
        "identifier", "Identifiant client (donnée pseudonyme : ne pas exporter)."
    ),
    "country": RoleHint("categorical", "Pays du client."),
}

LEAKAGE_COLUMNS = {"twf", "hdf", "pwf", "osf", "rnf"}

MAINTENANCE_HINTS: dict[str, RoleHint] = {
    "udi": RoleHint("identifier", "Identifiant unique de la mesure."),
    "productid": RoleHint("identifier", "Identifiant produit (encode aussi le type)."),
    "type": RoleHint("categorical", "Qualité produit L / M / H."),
    "airtemperature[k]": RoleHint("measure", "Température de l'air (K)."),
    "processtemperature[k]": RoleHint("measure", "Température du process (K)."),
    "rotationalspeed[rpm]": RoleHint("measure", "Vitesse de rotation (tr/min)."),
    "torque[nm]": RoleHint("measure", "Couple (N·m)."),
    "toolwear[min]": RoleHint("measure", "Usure outil (min)."),
    "machinefailure": RoleHint("target", "Label de panne (0/1)."),
    **{
        c: RoleHint(
            "ignore",
            "Mode de panne dérivé du label « Machine failure » : risque de fuite de cible, "
            "à exclure des variables explicatives.",
        )
        for c in LEAKAGE_COLUMNS
    },
}

_RETAIL_MIN_MATCH = 4
_MAINT_MIN_MATCH = 5


def detect_domain(columns: list[str]) -> tuple[Domain, str]:
    normed = {norm(c) for c in columns}
    retail = sorted(normed & set(RETAIL_HINTS))
    maint = sorted(normed & set(MAINTENANCE_HINTS))
    if len(maint) >= _MAINT_MIN_MATCH and len(maint) >= len(retail):
        return "maintenance", f"{len(maint)} colonnes reconnues du schéma maintenance (AI4I)."
    if len(retail) >= _RETAIL_MIN_MATCH:
        return "retail", f"{len(retail)} colonnes reconnues du schéma transactions retail."
    return "generic", "Schéma non reconnu : profilage générique."


def domain_role_hint(domain: Domain, column: str) -> RoleHint | None:
    table = {"retail": RETAIL_HINTS, "maintenance": MAINTENANCE_HINTS}.get(domain, {})
    return table.get(norm(column))


def find_column(df: pd.DataFrame, *candidates: str) -> str | None:
    lookup = {norm(c): c for c in df.columns}
    for cand in candidates:
        if cand in lookup:
            return lookup[cand]
    return None


def domain_checks(domain: Domain, df: pd.DataFrame) -> list[QualityIssue]:
    if domain == "retail":
        return _retail_checks(df)
    if domain == "maintenance":
        return _maintenance_checks(df)
    return []


def _retail_checks(df: pd.DataFrame) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    qty = find_column(df, "quantity")
    price = find_column(df, "unitprice", "price")
    inv = find_column(df, "invoiceno", "invoice")
    cust = find_column(df, "customerid")

    if qty is not None:
        q = pd.to_numeric(df[qty], errors="coerce")
        n_neg = int((q < 0).sum())
        if n_neg:
            issues.append(
                QualityIssue(
                    code="retail_negative_quantity",
                    severity="warning",
                    column=qty,
                    count=n_neg,
                    message=f"{n_neg} lignes avec quantité négative (retours ou annulations "
                    "probables). Elles sont conservées ; leur traitement sera explicite dans "
                    "les KPI.",
                )
            )
    if price is not None:
        p = pd.to_numeric(df[price], errors="coerce")
        n_bad = int((p <= 0).sum())
        if n_bad:
            issues.append(
                QualityIssue(
                    code="retail_non_positive_price",
                    severity="warning",
                    column=price,
                    count=n_bad,
                    message=f"{n_bad} lignes avec prix unitaire nul ou négatif "
                    "(ajustements, échantillons gratuits ou erreurs de saisie).",
                )
            )
    if inv is not None:
        n_cancel = int(df[inv].astype("string").str.upper().str.startswith("C").fillna(False).sum())
        if n_cancel:
            issues.append(
                QualityIssue(
                    code="retail_cancellations",
                    severity="info",
                    column=inv,
                    count=n_cancel,
                    message=f"{n_cancel} lignes appartiennent à des factures d'annulation "
                    "(préfixe « C »).",
                )
            )
    if cust is not None:
        n_missing = int(df[cust].isna().sum())
        if n_missing:
            issues.append(
                QualityIssue(
                    code="retail_missing_customer",
                    severity="info",
                    column=cust,
                    count=n_missing,
                    message=f"{n_missing} lignes sans identifiant client : les KPI par client "
                    "les excluront, les KPI de chiffre d'affaires les incluront.",
                )
            )
    return issues


def _maintenance_checks(df: pd.DataFrame) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    target = find_column(df, "machinefailure")
    leaks = [c for c in df.columns if norm(c) in LEAKAGE_COLUMNS]
    if leaks:
        issues.append(
            QualityIssue(
                code="target_leakage",
                severity="warning",
                column=", ".join(leaks),
                count=len(leaks),
                message="Colonnes de mode de panne dérivées du label (fuite de cible) : "
                f"{', '.join(leaks)}. Rôle « Ignorer » proposé pour toute modélisation.",
            )
        )
    if target is not None:
        y = pd.to_numeric(df[target], errors="coerce")
        n_pos = int((y == 1).sum())
        n_valid = int(y.notna().sum())
        if n_valid:
            rate = n_pos / n_valid
            issues.append(
                QualityIssue(
                    code="class_imbalance",
                    severity="warning" if rate < 0.1 else "info",
                    column=target,
                    count=n_pos,
                    message=f"Classe « panne » : {n_pos} / {n_valid} lignes ({rate:.2%}). "
                    "Déséquilibre fort : utiliser Precision, Recall, F1 et PR-AUC, pas "
                    "l'accuracy seule.",
                )
            )
    return issues
