"""Profilage et rapport de qualité des données.

Fonctions pures : elles ne modifient jamais le DataFrame reçu. Tous les seuils utilisés
sont renvoyés dans `QualityReport.parameters` pour la traçabilité.
"""

from __future__ import annotations

import math
import re
import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.data.domains import detect_domain, domain_checks, domain_role_hint
from app.data.schemas import (
    ColumnProfile,
    ColumnRole,
    DatetimeStats,
    NumericStats,
    QualityIssue,
    QualityReport,
    SemanticType,
    TopValue,
)

_ID_NAME = re.compile(r"(^id$|_id$|^id_|\bid\b|uuid|identifiant|^code$|number$|^no$|num(ero)?$)")
_DATE_NAME = re.compile(r"(date|time|timestamp|jour|mois|period|datetime)", re.I)
_MAX_TOP = 5
_DATETIME_MIN_SHARE = 0.95
_HIGH_MISSING = 0.30


@dataclass(frozen=True)
class ProfileParams:
    high_cardinality_ratio: float = 0.5
    high_cardinality_min_unique: int = 50
    mixed_type_min_share: float = 0.05
    high_missing_share: float = _HIGH_MISSING
    datetime_min_share: float = _DATETIME_MIN_SHARE


def profile_dataframe(df: pd.DataFrame, params: ProfileParams | None = None) -> QualityReport:
    p = params or ProfileParams()
    n_rows, n_cols = df.shape
    domain, domain_reason = detect_domain([str(c) for c in df.columns])

    columns: list[ColumnProfile] = []
    issues: list[QualityIssue] = []
    for col in df.columns:
        prof, col_issues = _profile_column(df[col], str(col), n_rows, p, domain)
        columns.append(prof)
        issues.extend(col_issues)

    n_dup = int(df.duplicated().sum()) if n_rows else 0
    if n_dup:
        issues.append(
            QualityIssue(
                code="duplicate_rows",
                severity="warning",
                count=n_dup,
                message=f"{n_dup} lignes strictement identiques à une ligne précédente "
                f"({n_dup / n_rows:.2%}). Elles ne sont pas supprimées.",
            )
        )

    issues.extend(domain_checks(domain, df))
    _check_single_target(columns, issues)

    n_missing = int(df.isna().sum().sum())
    total_cells = max(n_rows * n_cols, 1)
    score, breakdown = _quality_score(columns, n_missing / total_cells, n_dup / max(n_rows, 1))

    order = {"error": 0, "warning": 1, "info": 2}
    issues.sort(key=lambda i: (order[i.severity], i.column or ""))

    return QualityReport(
        n_rows=n_rows,
        n_columns=n_cols,
        n_cells_missing=n_missing,
        pct_cells_missing=round(n_missing / total_cells, 6),
        n_duplicate_rows=n_dup,
        pct_duplicate_rows=round(n_dup / max(n_rows, 1), 6),
        domain=domain,
        domain_reason=domain_reason,
        columns=columns,
        issues=issues,
        score=score,
        score_breakdown=breakdown,
        parameters={
            "high_cardinality_ratio": p.high_cardinality_ratio,
            "high_cardinality_min_unique": p.high_cardinality_min_unique,
            "mixed_type_min_share": p.mixed_type_min_share,
            "high_missing_share": p.high_missing_share,
            "datetime_min_share": p.datetime_min_share,
        },
    )


# --------------------------------------------------------------------------- colonnes


def _profile_column(
    s: pd.Series, name: str, n_rows: int, p: ProfileParams, domain: str
) -> tuple[ColumnProfile, list[QualityIssue]]:
    issues: list[QualityIssue] = []
    codes: list[str] = []
    non_null = s.dropna()
    n_missing = int(s.isna().sum())
    pct_missing = n_missing / n_rows if n_rows else 0.0
    n_unique = int(non_null.nunique())
    unique_ratio = n_unique / len(non_null) if len(non_null) else 0.0

    numeric_stats = None
    dt_stats = None
    numeric_share: float | None = None
    top: list[TopValue] = []

    sem = _semantic_type(s, non_null, n_unique)

    if sem == "numeric":
        numeric_stats = _numeric_stats(pd.to_numeric(non_null, errors="coerce"))
        if np.isinf(pd.to_numeric(non_null, errors="coerce").astype(float)).any():
            codes.append("infinite_values")
            issues.append(
                QualityIssue(
                    code="infinite_values",
                    severity="error",
                    column=name,
                    message=f"La colonne « {name} » contient des valeurs infinies.",
                )
            )
    elif sem == "datetime":
        dt_stats = _datetime_stats_native(non_null)
    elif sem in {"categorical", "text", "boolean"}:
        top = _top_values(non_null)
        as_str = non_null.astype("string").str.strip()
        num_parsed = pd.to_numeric(as_str, errors="coerce")
        numeric_share = float(num_parsed.notna().mean())
        if sem != "boolean" and _looks_like_date(name, as_str):
            inferred = infer_datetime(as_str)
            if inferred.share >= p.datetime_min_share:
                sem = "datetime"
                dt_stats = inferred.stats()
            if 0 < inferred.share < 1:
                n_bad = int(inferred.parsed.isna().sum()) if inferred.parsed is not None else 0
                codes.append("invalid_dates")
                issues.append(
                    QualityIssue(
                        code="invalid_dates",
                        severity="warning",
                        column=name,
                        count=n_bad,
                        message=f"{n_bad} valeurs de « {name} » ne sont pas des dates valides "
                        f"au format détecté ({inferred.fmt}).",
                    )
                )
            if inferred.ambiguous and sem == "datetime":
                codes.append("ambiguous_dates")
                issues.append(
                    QualityIssue(
                        code="ambiguous_dates",
                        severity="warning",
                        column=name,
                        message=f"Dates de « {name} » ambiguës : jour/mois et mois/jour sont "
                        f"tous deux possibles. Format retenu : {inferred.fmt} — à confirmer.",
                    )
                )
        if p.mixed_type_min_share <= numeric_share < 1.0 and sem != "datetime":
            n_text = int(num_parsed.isna().sum())
            example = _first_non_numeric(as_str)
            codes.append("mixed_types")
            issues.append(
                QualityIssue(
                    code="mixed_types",
                    severity="warning",
                    column=name,
                    count=n_text,
                    message=f"Types incohérents dans « {name} » : {numeric_share:.1%} des "
                    f"valeurs sont numériques et {n_text} ne le sont pas"
                    + (f" (ex. « {example} »)." if example else "."),
                )
            )

    # Manquants
    if n_missing == n_rows and n_rows:
        codes.append("empty_column")
        issues.append(
            QualityIssue(
                code="empty_column",
                severity="warning",
                column=name,
                count=n_missing,
                message=f"La colonne « {name} » est entièrement vide.",
            )
        )
    elif pct_missing >= p.high_missing_share:
        codes.append("high_missing")
        issues.append(
            QualityIssue(
                code="high_missing",
                severity="warning",
                column=name,
                count=n_missing,
                message=f"{pct_missing:.1%} de valeurs manquantes dans « {name} ».",
            )
        )
    elif n_missing:
        codes.append("missing_values")
        issues.append(
            QualityIssue(
                code="missing_values",
                severity="info",
                column=name,
                count=n_missing,
                message=f"{n_missing} valeurs manquantes dans « {name} » ({pct_missing:.2%}).",
            )
        )

    # Constante
    if n_unique == 1 and n_rows > 1:
        codes.append("constant_column")
        issues.append(
            QualityIssue(
                code="constant_column",
                severity="warning",
                column=name,
                message=f"« {name} » ne contient qu'une seule valeur distincte : "
                "aucune information exploitable.",
            )
        )

    role, reason = _suggest_role(name, sem, unique_ratio, n_unique, numeric_share, domain)

    # Cardinalité élevée (hors identifiants et texte libre)
    if (
        sem == "categorical"
        and role not in {"identifier", "text"}
        and n_unique >= p.high_cardinality_min_unique
        and unique_ratio >= p.high_cardinality_ratio
    ):
        codes.append("high_cardinality")
        issues.append(
            QualityIssue(
                code="high_cardinality",
                severity="info",
                column=name,
                count=n_unique,
                message=f"« {name} » a {n_unique} modalités distinctes ({unique_ratio:.0%} des "
                "lignes) : peu adaptée comme catégorie, vérifier s'il s'agit d'un identifiant.",
            )
        )

    if name.startswith("Unnamed:"):
        codes.append("unnamed_column")
        issues.append(
            QualityIssue(
                code="unnamed_column",
                severity="info",
                column=name,
                message=f"Colonne sans en-tête (« {name} »), souvent un index exporté.",
            )
        )

    profile = ColumnProfile(
        name=name,
        dtype=str(s.dtype),
        semantic_type=sem,
        n_missing=n_missing,
        pct_missing=round(pct_missing, 6),
        n_unique=n_unique,
        unique_ratio=round(unique_ratio, 6),
        numeric_parse_share=None if numeric_share is None else round(numeric_share, 6),
        numeric=numeric_stats,
        datetime=dt_stats,
        top_values=top,
        suggested_role=role,
        role_reason=reason,
        issues=codes,
    )
    return profile, issues


def _semantic_type(s: pd.Series, non_null: pd.Series, n_unique: int) -> SemanticType:
    if non_null.empty:
        return "empty"
    if pd.api.types.is_bool_dtype(s):
        return "boolean"
    if pd.api.types.is_datetime64_any_dtype(s):
        return "datetime"
    if pd.api.types.is_numeric_dtype(s):
        return "numeric"
    if n_unique <= 2 and set(non_null.astype("string").str.lower().unique()) <= {
        "true",
        "false",
        "yes",
        "no",
        "oui",
        "non",
    }:
        return "boolean"
    # objet Excel pouvant contenir des datetime Python
    if s.dtype == object and non_null.map(lambda v: isinstance(v, pd.Timestamp)).all():
        return "datetime"
    avg_len = non_null.astype("string").str.len().mean()
    if n_unique > 0 and avg_len and avg_len > 40:
        return "text"
    return "categorical"


def _numeric_stats(x: pd.Series) -> NumericStats:
    x = x.dropna().astype(float)
    x = x[np.isfinite(x)]
    if x.empty:
        return NumericStats(
            min=None,
            max=None,
            mean=None,
            std=None,
            median=None,
            q1=None,
            q3=None,
            n_zero=0,
            n_negative=0,
        )
    q1, med, q3 = np.percentile(x, [25, 50, 75])
    return NumericStats(
        min=float(x.min()),
        max=float(x.max()),
        mean=float(x.mean()),
        std=float(x.std(ddof=1)) if len(x) > 1 else None,
        median=float(med),
        q1=float(q1),
        q3=float(q3),
        n_zero=int((x == 0).sum()),
        n_negative=int((x < 0).sum()),
    )


_DATE_FORMATS = [
    "ISO8601",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M",
    "%m/%d/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%Y/%m/%d",
]
_SWAPPED = {
    f: f.replace("%d/%m", "%m/%d") if "%d/%m" in f else f.replace("%m/%d", "%d/%m")
    for f in _DATE_FORMATS
    if "%d/%m" in f or "%m/%d" in f
}
_ISO_START = re.compile(r"^\d{4}-\d{2}-\d{2}")


@dataclass(frozen=True)
class InferredDatetime:
    share: float
    fmt: str | None
    ambiguous: bool
    parsed: pd.Series | None

    def stats(self) -> DatetimeStats:
        values = self.parsed.dropna() if self.parsed is not None else pd.Series(dtype="object")
        return DatetimeStats(
            min=None if values.empty else values.min().isoformat(),
            max=None if values.empty else values.max().isoformat(),
            parse_share=round(self.share, 6),
            native=False,
            format=self.fmt,
            ambiguous=self.ambiguous,
        )


def _looks_like_date(name: str, as_str: pd.Series) -> bool:
    if _DATE_NAME.search(name):
        return True
    head = as_str.head(20)
    return bool(len(head)) and bool(head.str.match(_ISO_START).mean() > 0.8)


def _parse(values: pd.Series, fmt: str) -> pd.Series:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return pd.to_datetime(values, format=fmt, errors="coerce")


def infer_datetime(as_str: pd.Series) -> InferredDatetime:
    """Choisit le format de date le plus couvrant sur un échantillon, puis l'applique à
    toute la colonne (vectorisé). Signale l'ambiguïté jour/mois."""
    if as_str.empty:
        return InferredDatetime(0.0, None, False, None)
    sample = as_str.head(2000)
    shares = {f: float(_parse(sample, f).notna().mean()) for f in _DATE_FORMATS}
    best = max(shares, key=lambda f: shares[f])  # ordre de la liste = préférence en cas d'égalité
    if shares[best] == 0:
        return InferredDatetime(0.0, None, False, None)
    parsed = _parse(as_str, best)
    ambiguous = False
    swapped = _SWAPPED.get(best)
    if swapped and shares.get(swapped, 0) == shares[best]:
        alt = _parse(sample, swapped)
        ambiguous = bool((alt != _parse(sample, best)).fillna(False).any())
    return InferredDatetime(float(parsed.notna().mean()), best, ambiguous, parsed)


def _datetime_stats_native(non_null: pd.Series) -> DatetimeStats:
    values = pd.to_datetime(non_null, errors="coerce").dropna()
    return DatetimeStats(
        min=None if values.empty else values.min().isoformat(),
        max=None if values.empty else values.max().isoformat(),
        parse_share=1.0,
        native=True,
    )


def _top_values(non_null: pd.Series) -> list[TopValue]:
    vc = non_null.astype("string").value_counts().head(_MAX_TOP)
    return [TopValue(value=str(k)[:80], count=int(v)) for k, v in vc.items()]


def _first_non_numeric(as_str: pd.Series) -> str | None:
    mask = pd.to_numeric(as_str, errors="coerce").isna()
    hit = as_str[mask]
    return None if hit.empty else str(hit.iloc[0])[:40]


def _suggest_role(
    name: str,
    sem: SemanticType,
    unique_ratio: float,
    n_unique: int,
    numeric_share: float | None,
    domain: str,
) -> tuple[ColumnRole, str]:
    hint = domain_role_hint(domain, name)  # type: ignore[arg-type]
    if hint is not None:
        return hint.role, hint.reason
    lname = name.lower()
    if sem == "empty":
        return "ignore", "Colonne vide."
    if sem == "datetime":
        return "datetime", "Valeurs interprétables comme dates."
    if _ID_NAME.search(lname) and unique_ratio >= 0.5:
        return "identifier", "Nom évocateur d'un identifiant et valeurs majoritairement uniques."
    if sem == "numeric":
        if unique_ratio > 0.98 and n_unique > 50 and "id" in lname:
            return "identifier", "Entier unique par ligne."
        return "numeric", "Valeurs numériques."
    if sem == "boolean":
        return "categorical", "Variable binaire."
    if sem == "text":
        return "text", "Texte long (moyenne > 40 caractères)."
    if unique_ratio > 0.95 and n_unique > 50:
        return "identifier", "Presque toutes les valeurs sont distinctes."
    if numeric_share is not None and numeric_share >= 0.95:
        return "categorical", "Majoritairement numérique mais stocké en texte : à vérifier."
    return "categorical", "Texte court avec modalités répétées."


def _check_single_target(columns: list[ColumnProfile], issues: list[QualityIssue]) -> None:
    targets = [c.name for c in columns if c.suggested_role == "target"]
    if len(targets) > 1:
        issues.append(
            QualityIssue(
                code="multiple_targets",
                severity="info",
                message=f"Plusieurs cibles proposées ({', '.join(targets)}) : en choisir une.",
            )
        )


def _quality_score(
    columns: list[ColumnProfile], missing_share: float, dup_share: float
) -> tuple[float, dict[str, float]]:
    """Indicateur heuristique (0–100), moyenne de 4 composantes égales :
    complétude (1 - part de cellules manquantes), unicité (1 - part de doublons),
    cohérence (part de colonnes sans types incohérents / dates invalides / infinis),
    utilité (part de colonnes ni vides ni constantes).
    Ce n'est pas une mesure normalisée : il sert à comparer des versions d'un même fichier."""
    n = max(len(columns), 1)
    incoherent = {"mixed_types", "invalid_dates", "infinite_values"}
    useless = {"empty_column", "constant_column"}
    breakdown = {
        "completeness": 1 - missing_share,
        "uniqueness": 1 - dup_share,
        "consistency": sum(not (set(c.issues) & incoherent) for c in columns) / n,
        "usefulness": sum(not (set(c.issues) & useless) for c in columns) / n,
    }
    # Troncature (et non arrondi) : un fichier imparfait n'affiche jamais 100.
    breakdown = {k: math.floor(1000 * v + 1e-9) / 10 for k, v in breakdown.items()}
    score = math.floor(10 * sum(breakdown.values()) / len(breakdown) + 1e-9) / 10
    return score, breakdown
