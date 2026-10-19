"""Parcours principal de bout en bout via l'API HTTP."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_health(client: TestClient):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["database"] is True
    assert body["llm_enabled"] is False
    assert body["modules"]["import_quality"] == "available"
    assert body["modules"]["anomalies"].startswith("planned")


def test_samples_catalog_is_labelled_synthetic(client: TestClient):
    samples = client.get("/api/samples").json()
    assert {s["id"] for s in samples} == {
        "retail-synthetic",
        "retail-synthetic-xlsx",
        "maintenance-synthetic",
    }
    assert all(s["synthetic"] for s in samples)


def test_load_each_sample(client: TestClient):
    expected = {
        "retail-synthetic": "retail",
        "retail-synthetic-xlsx": "retail",
        "maintenance-synthetic": "maintenance",
    }
    for sid, domain in expected.items():
        r = client.post(f"/api/datasets/samples/{sid}")
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["domain"] == domain
        assert body["quality"]["n_rows"] == body["n_rows"] > 0
    assert client.post("/api/datasets/samples/unknown").status_code == 404


def test_full_upload_flow_and_persistence(settings: Settings, known_csv: bytes):
    client = TestClient(create_app(settings))
    r = client.post("/api/datasets/upload", files={"file": ("ventes été.csv", known_csv)})
    assert r.status_code == 201, r.text
    ds = r.json()
    ds_id = ds["id"]
    assert ds["loaded"] is True
    assert ds["quality"]["n_duplicate_rows"] == 1
    assert ds["roles"]["order_date"] == "datetime"

    prev = client.get(f"/api/datasets/{ds_id}/preview", params={"limit": 3}).json()
    assert prev["total"] == 20 and len(prev["rows"]) == 3
    assert prev["rows"][2][2] is None  # montant manquant -> null JSON

    ok = client.put(f"/api/datasets/{ds_id}/roles", json={"roles": {"country": "target"}})
    assert ok.status_code == 200 and ok.json()["roles"]["country"] == "target"
    bad = client.put(f"/api/datasets/{ds_id}/roles", json={"roles": {"notes": "measure"}})
    assert bad.status_code == 422 and "notes" in bad.json()["details"]["errors"]

    # Le rôle change les constats : « mixed » (95 % numérique) passe de code à mesure.
    before = client.get(f"/api/datasets/{ds_id}").json()["quality"]
    assert {"mixed_codes"} <= {i["code"] for i in before["issues"] if i["column"] == "mixed"}
    ok2 = client.put(f"/api/datasets/{ds_id}/roles", json={"roles": {"mixed": "measure"}})
    assert ok2.status_code == 200
    after = client.get(f"/api/datasets/{ds_id}").json()["quality"]
    codes = {i["code"] for i in after["issues"] if i["column"] == "mixed"}
    assert "mixed_types" in codes and "mixed_codes" not in codes
    assert after["score"] < before["score"]
    assert after["roles_applied"]["mixed"] == "measure"
    client.put(f"/api/datasets/{ds_id}/roles", json={"roles": {"mixed": "categorical"}})

    j = client.get(f"/api/datasets/{ds_id}/quality/export", params={"format": "json"})
    assert j.status_code == 200
    payload = json.loads(j.content)
    assert payload["report"]["n_rows"] == 20 and payload["dataset"]["roles"]["country"] == "target"
    c = client.get(f"/api/datasets/{ds_id}/quality/export", params={"format": "csv"})
    assert c.status_code == 200 and "attachment" in c.headers["content-disposition"]
    assert "duplicate_rows" in c.content.decode("utf-8-sig")

    kinds = [a["kind"] for a in client.get("/api/history").json()]
    assert kinds == ["roles_update", "roles_update", "roles_update", "quality_profile"]
    last = client.get("/api/history").json()[1]
    assert last["summary"]["score_after"] < last["summary"]["score_before"]

    assert client.delete(f"/api/datasets/{ds_id}").status_code == 204
    gone = client.get(f"/api/datasets/{ds_id}")
    assert gone.status_code == 410 and gone.json()["code"] == "dataset_expired"

    # « Redémarrage » : nouvelle application sur la même base SQLite.
    restarted = TestClient(create_app(settings))
    history = restarted.get("/api/history").json()
    assert [a["kind"] for a in history][-1] == "quality_profile" and len(history) == 4
    listed = restarted.get("/api/datasets").json()
    assert listed[0]["id"] == ds_id and listed[0]["loaded"] is False
    assert listed[0]["released_at"] is not None
    assert listed[0]["roles"]["country"] == "target"


def test_upload_errors_are_readable(client: TestClient, settings: Settings):
    r = client.post("/api/datasets/upload", files={"file": ("x.xlsm", b"PK\x03\x04")})
    assert r.status_code == 415 and "macros" in r.json()["message"]
    r = client.post("/api/datasets/upload", files={"file": ("x.csv", b"")})
    assert r.status_code == 422 and r.json()["code"] == "invalid_file"
    r = client.post("/api/datasets/upload", files={"file": ("x.csv", b"a,b\n1,2,3\n")})
    assert r.status_code == 422

    small = TestClient(create_app(settings.model_copy(update={"max_upload_mb": 0.001})))
    r = small.post("/api/datasets/upload", files={"file": ("x.csv", b"a\n" + b"1\n" * 2000)})
    assert r.status_code == 413 and r.json()["code"] == "file_too_large"
    assert client.get("/api/datasets/doesnotexist").status_code == 404


def test_upload_all_sheets_reports_overlap(client: TestClient):
    import io

    import pandas as pd

    buf = io.BytesIO()
    with pd.ExcelWriter(buf) as w:
        pd.DataFrame({"Invoice": ["1", "2"], "Qty": [1, 2]}).to_excel(
            w, sheet_name="a", index=False
        )
        pd.DataFrame({"Invoice": ["2", "3"], "Qty": [2, 3]}).to_excel(
            w, sheet_name="b", index=False
        )
    files = {"file": ("multi.xlsx", buf.getvalue())}

    first = client.post("/api/datasets/upload", files=files)
    assert first.status_code == 201 and first.json()["n_rows"] == 2

    both = client.post("/api/datasets/upload", files=files, data={"sheets": "all"})
    assert both.status_code == 201, both.text
    body = both.json()
    assert body["n_rows"] == 4 and body["parse_info"]["sheet_mode"] == "all"
    codes = {i["code"]: i for i in body["quality"]["issues"]}
    assert codes["cross_sheet_duplicates"]["count"] == 1
    assert codes["duplicate_rows"]["count"] == 1

    bad = client.post("/api/datasets/upload", files=files, data={"sheets": "every"})
    assert bad.status_code == 422
