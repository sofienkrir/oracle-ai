"""Contrats de données du module `data` (réutilisés par l'API)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

SemanticType = Literal["numeric", "boolean", "datetime", "categorical", "text", "empty"]
ColumnRole = Literal[
    "identifier", "datetime", "numeric", "categorical", "target", "measure", "text", "ignore"
]
Severity = Literal["info", "warning", "error"]
Domain = Literal["retail", "maintenance", "generic"]

ROLE_LABELS: dict[str, str] = {
    "identifier": "Identifiant",
    "datetime": "Date / temps",
    "numeric": "Numérique",
    "categorical": "Catégorie",
    "target": "Cible / label",
    "measure": "Mesure métier",
    "text": "Texte libre",
    "ignore": "Ignorer",
}


class NumericStats(BaseModel):
    min: float | None
    max: float | None
    mean: float | None
    std: float | None
    median: float | None
    q1: float | None
    q3: float | None
    n_zero: int
    n_negative: int


class DatetimeStats(BaseModel):
    min: str | None
    max: str | None
    parse_share: float = Field(description="Part des valeurs non vides interprétables en date")
    native: bool = Field(description="True si la colonne est déjà typée date dans le fichier")
    format: str | None = Field(default=None, description="Format retenu pour le texte")
    ambiguous: bool = Field(
        default=False, description="True si jour/mois et mois/jour donnent tous deux un résultat"
    )


class TopValue(BaseModel):
    value: str
    count: int


class ColumnProfile(BaseModel):
    name: str
    dtype: str
    semantic_type: SemanticType
    n_missing: int
    pct_missing: float
    n_unique: int
    unique_ratio: float
    numeric_parse_share: float | None = None
    numeric: NumericStats | None = None
    datetime: DatetimeStats | None = None
    top_values: list[TopValue] = []
    suggested_role: ColumnRole
    role_reason: str
    issues: list[str] = []


class QualityIssue(BaseModel):
    code: str
    severity: Severity
    column: str | None = None
    count: int | None = None
    message: str


class QualityReport(BaseModel):
    n_rows: int
    n_columns: int
    n_cells_missing: int
    pct_cells_missing: float
    n_duplicate_rows: int
    pct_duplicate_rows: float
    domain: Domain
    domain_reason: str
    columns: list[ColumnProfile]
    issues: list[QualityIssue]
    score: float = Field(description="Indicateur heuristique 0–100, documenté dans docs/")
    score_breakdown: dict[str, float]
    parameters: dict[str, Any]
