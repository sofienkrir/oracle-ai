"""Export du rapport de qualité en JSON ou CSV."""

from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime
from typing import Any

from app.core.config import ENGINE_VERSION
from app.data.schemas import QualityReport

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value: Any) -> Any:
    """Neutralise l'injection de formules quand le CSV est ouvert dans un tableur."""
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


def report_to_json(report: QualityReport, meta: dict[str, Any]) -> str:
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "engine_version": ENGINE_VERSION,
        "dataset": meta,
        "report": report.model_dump(mode="json"),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def report_to_csv(report: QualityReport, meta: dict[str, Any]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["# Rapport de qualité ORACLE AI", f"moteur {ENGINE_VERSION}"])
    w.writerow(["# Dataset", safe_cell(meta.get("name", "")), meta.get("sha256", "")])
    w.writerow(["# Généré le", datetime.now(UTC).isoformat()])
    w.writerow(["# Lignes", report.n_rows, "Colonnes", report.n_columns, "Score", report.score])
    w.writerow([])
    w.writerow(["section", "colonne", "gravité", "code", "nombre", "message"])
    for i in report.issues:
        w.writerow(
            [
                "probleme",
                safe_cell(i.column or ""),
                i.severity,
                i.code,
                "" if i.count is None else i.count,
                safe_cell(i.message),
            ]
        )
    w.writerow([])
    w.writerow(
        [
            "section",
            "colonne",
            "dtype",
            "type_semantique",
            "manquants",
            "pct_manquants",
            "valeurs_distinctes",
            "role_suggere",
            "justification",
        ]
    )
    for c in report.columns:
        w.writerow(
            [
                "colonne",
                safe_cell(c.name),
                c.dtype,
                c.semantic_type,
                c.n_missing,
                f"{c.pct_missing:.6f}",
                c.n_unique,
                c.suggested_role,
                safe_cell(c.role_reason),
            ]
        )
    return buf.getvalue()
