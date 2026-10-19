"""Profilage sur une fixture dont toutes les valeurs attendues sont connues à la main."""

from __future__ import annotations

import pandas as pd
import pytest

from app.core.config import Settings
from app.data.ingestion import ingest_bytes
from app.data.profiling import apply_roles, infer_datetime, profile_dataframe


@pytest.fixture
def report(settings: Settings, known_csv: bytes):
    df = ingest_bytes(known_csv, "known.csv", settings).df
    return profile_dataframe(df)


def _col(report, name):
    return next(c for c in report.columns if c.name == name)


def _issue(report, code, column=None):
    return [i for i in report.issues if i.code == code and (column is None or i.column == column)]


def test_shape_missing_and_duplicates(report):
    assert (report.n_rows, report.n_columns) == (20, 9)
    # 20 (empty_col) + 1 (amount) + 1 (country)
    assert report.n_cells_missing == 22
    assert report.n_duplicate_rows == 1
    assert report.pct_duplicate_rows == pytest.approx(0.05)
    assert _col(report, "amount").n_missing == 1
    assert _col(report, "country").pct_missing == pytest.approx(0.05)


def test_numeric_stats_exact(report):
    stats = _col(report, "amount").numeric
    values = [10, 20, 40, 50, 50, *list(range(70, 210, 10))]
    assert stats.min == 10 and stats.max == 200
    assert stats.mean == pytest.approx(sum(values) / len(values))
    assert stats.median == pytest.approx(pd.Series(values).median())


def test_structural_issues(report):
    assert _issue(report, "constant_column", "constant_flag")
    assert _issue(report, "empty_column", "empty_col")
    assert _col(report, "empty_col").semantic_type == "empty"
    assert _col(report, "empty_col").suggested_role == "ignore"


def test_mixed_values_depend_on_role(report):
    # Rôle proposé « Catégorie » : mélange chiffres/lettres = code normal, info sans pénalité.
    assert _col(report, "mixed").suggested_role == "categorical"
    (info,) = _issue(report, "mixed_codes", "mixed")
    assert info.severity == "info" and info.count == 1 and "X9" in info.message
    assert not _issue(report, "mixed_types", "mixed")
    assert report.score_breakdown["consistency"] == pytest.approx(88.8)  # 8/9 (dates)

    # Même colonne en « Mesure métier » : valeur texte = anomalie, pénalise la cohérence.
    as_measure = apply_roles(report, {**report.roles_applied, "mixed": "measure"})
    (warn,) = _issue(as_measure, "mixed_types", "mixed")
    assert warn.severity == "warning" and warn.count == 1 and "ignorées" in warn.message
    assert not _issue(as_measure, "mixed_codes", "mixed")
    assert as_measure.score_breakdown["consistency"] == pytest.approx(77.7)  # 7/9
    assert as_measure.score < report.score
    assert as_measure.roles_applied["mixed"] == "measure"

    # Retour au rôle catégorie : idempotent, aucun constat dupliqué.
    back = apply_roles(as_measure, report.roles_applied)
    assert [i.code for i in back.issues] == [i.code for i in report.issues]
    assert back.score == report.score

    # colonne à zéros de tête : 100 % numérique en texte, aucun constat de mélange
    assert not _issue(report, "mixed_types", "zip_code")
    assert not _issue(report, "mixed_codes", "zip_code")


def test_stockcode_like_codes_not_penalised():
    codes = [str(20000 + i) for i in range(85)] + [f"{85000 + i}A" for i in range(15)]
    df = pd.DataFrame({"StockCode": codes, "Quantity": range(100)})
    report = profile_dataframe(df)
    assert not [i for i in report.issues if i.code == "mixed_types"]
    assert [i.count for i in report.issues if i.code == "mixed_codes"] == [15]
    assert report.score_breakdown["consistency"] == 100


def test_text_dates_detected_and_invalid_counted(report):
    col = _col(report, "order_date")
    assert col.semantic_type == "datetime"
    assert col.suggested_role == "datetime"
    assert col.datetime.format == "ISO8601"
    assert col.datetime.min.startswith("2024-01-01")
    (issue,) = _issue(report, "invalid_dates", "order_date")
    assert issue.count == 1


def test_identifier_suggested(report):
    assert _col(report, "order_id").suggested_role == "identifier"


def test_score_breakdown_is_documented_average(report):
    b = report.score_breakdown
    assert set(b) == {"completeness", "uniqueness", "consistency", "usefulness"}
    assert report.score <= sum(b.values()) / 4 < report.score + 0.1
    assert b["uniqueness"] == pytest.approx(95.0)


def test_imperfect_file_never_scores_100():
    df = pd.DataFrame({"x": [1.0] * 9999 + [None], "y": range(10000)})
    report = profile_dataframe(df)
    assert report.score < 100 and report.score_breakdown["completeness"] < 100


def test_profiling_does_not_mutate_input(settings: Settings, known_csv: bytes):
    df = ingest_bytes(known_csv, "known.csv", settings).df
    before = df.copy()
    profile_dataframe(df)
    pd.testing.assert_frame_equal(df, before)


def test_high_cardinality_flagged():
    df = pd.DataFrame({"label": [f"v{i}" for i in range(80)] + ["v0"] * 20})
    report = profile_dataframe(df)
    assert [i.count for i in report.issues if i.code == "high_cardinality"] == [80]


def test_ambiguous_day_month_flagged():
    s = pd.Series(["01/02/2024", "03/04/2024", "05/06/2024"])
    inferred = infer_datetime(s)
    assert inferred.share == 1.0
    assert inferred.ambiguous is True
    assert inferred.fmt == "%d/%m/%Y"


def test_unambiguous_month_day():
    s = pd.Series(["12/31/2023", "01/15/2024"])
    inferred = infer_datetime(s)
    assert inferred.fmt == "%m/%d/%Y" and inferred.ambiguous is False


def test_infinite_values_are_errors():
    report = profile_dataframe(pd.DataFrame({"x": [1.0, float("inf"), 2.0]}))
    assert any(i.code == "infinite_values" and i.severity == "error" for i in report.issues)
