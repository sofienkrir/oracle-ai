from __future__ import annotations

import pandas as pd
import pytest

from app.core.exceptions import InvalidRolesError
from app.data.domains import detect_domain
from app.data.profiling import profile_dataframe
from app.data.roles import validate_roles
from app.reporting.quality_export import report_to_csv, safe_cell
from app.services.workspace import WorkspaceEntry, WorkspaceStore

RETAIL = pd.DataFrame(
    {
        "InvoiceNo": ["1", "2", "C3"],
        "StockCode": ["A", "B", "A"],
        "Quantity": [2, 5, -2],
        "InvoiceDate": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
        "UnitPrice": [1.0, 0.0, 1.0],
        "CustomerID": [10.0, None, 10.0],
    }
)

MAINT = pd.DataFrame(
    {
        "UDI": [1, 2, 3, 4],
        "Type": ["L", "M", "L", "H"],
        "Torque [Nm]": [40.0, 41.0, 39.0, 60.0],
        "Tool wear [min]": [0, 10, 20, 230],
        "Machine failure": [0, 0, 0, 1],
        "TWF": [0, 0, 0, 1],
        "HDF": [0, 0, 0, 0],
    }
)


def test_domain_detection():
    assert detect_domain(list(RETAIL.columns))[0] == "retail"
    assert detect_domain(list(MAINT.columns))[0] == "maintenance"
    assert detect_domain(["a", "b"])[0] == "generic"


def test_retail_checks_counts():
    r = profile_dataframe(RETAIL)
    by_code = {i.code: i for i in r.issues}
    assert by_code["retail_negative_quantity"].count == 1
    assert by_code["retail_non_positive_price"].count == 1
    assert by_code["retail_cancellations"].count == 1
    assert by_code["retail_missing_customer"].count == 1


def test_maintenance_leakage_and_imbalance():
    r = profile_dataframe(MAINT)
    roles = {c.name: c.suggested_role for c in r.columns}
    assert roles["Machine failure"] == "target"
    assert roles["TWF"] == roles["HDF"] == "ignore"
    leak = next(i for i in r.issues if i.code == "target_leakage")
    assert "TWF" in leak.column and "HDF" in leak.column
    imb = next(i for i in r.issues if i.code == "class_imbalance")
    assert imb.count == 1 and "25.00%" in imb.message


def test_roles_validation():
    r = profile_dataframe(MAINT)
    merged = validate_roles(r, {"Type": "categorical", "Torque [Nm]": "numeric"})
    assert merged["Torque [Nm]"] == "numeric"
    assert merged["Machine failure"] == "target"  # rôle non fourni = suggestion

    with pytest.raises(InvalidRolesError) as e:
        validate_roles(r, {"Type": "measure", "nope": "numeric", "UDI": "datetime"})
    errors = e.value.details["errors"]
    assert set(errors) == {"Type", "nope", "UDI"}

    with pytest.raises(InvalidRolesError) as e:
        validate_roles(r, {"Tool wear [min]": "target"})
    assert "__all__" in e.value.details["errors"]


def _entry() -> WorkspaceEntry:
    df = pd.DataFrame({"a": [1]})
    return WorkspaceEntry(df=df, report=profile_dataframe(df), parse_info={}, transformations=[])


def test_workspace_lru_and_ttl():
    now = [0.0]
    evicted: list[str] = []
    store = WorkspaceStore(
        max_items=2, ttl_seconds=10, on_evict=evicted.append, clock=lambda: now[0]
    )
    store.put("a", _entry())
    store.put("b", _entry())
    store.get("a")  # a devient le plus récent
    store.put("c", _entry())
    assert evicted == ["b"] and store.keys() == ["a", "c"]

    now[0] = 11
    assert store.get("a") is None
    assert sorted(evicted) == ["a", "b", "c"]


def test_csv_export_neutralises_formulas():
    assert safe_cell("=HYPERLINK(1)") == "'=HYPERLINK(1)"
    assert safe_cell("normal") == "normal"
    df = pd.DataFrame({"=cmd()": ["x", "y"]})
    out = report_to_csv(profile_dataframe(df), {"name": "+evil.csv", "sha256": "0"})
    assert ";'=cmd();" in out and "'+evil.csv" in out
