from __future__ import annotations

import io
import zipfile

import pandas as pd
import pytest

from app.core.config import Settings
from app.core.exceptions import FileTooLargeError, InvalidFileError, UnsupportedFileTypeError
from app.data.ingestion import detect_format, ingest_bytes
from tests.conftest import xlsx_bytes


def test_csv_comma_reads_all_rows_including_duplicates(settings: Settings, known_csv: bytes):
    res = ingest_bytes(known_csv, "known.csv", settings)
    assert res.file_format == "csv"
    assert res.df.shape == (20, 9)  # aucune ligne supprimée, doublon compris
    assert res.parse_info == {"encoding": "utf-8-sig", "delimiter": ","}
    assert len(res.sha256) == 64


def test_semicolon_and_cp1252_detected(settings: Settings):
    content = "ville;montant\nGabès;12\nSfax;7\n".encode("cp1252")
    res = ingest_bytes(content, "f.csv", settings)
    assert res.parse_info == {"encoding": "cp1252", "delimiter": ";"}
    assert res.df["ville"].tolist() == ["Gabès", "Sfax"]


def test_lossless_numeric_conversion_is_traced(settings: Settings):
    content = b"a,b,zip,mixed\n1,1.5,0123,1\n2,2.5,0456,x\n"
    res = ingest_bytes(content, "f.csv", settings)
    assert str(res.df["a"].dtype) == "Int64"
    assert res.df["b"].dtype == "float64"
    # zéros de tête : conservé en texte (conversion avec perte refusée)
    assert res.df["zip"].tolist() == ["0123", "0456"]
    assert not pd.api.types.is_numeric_dtype(res.df["mixed"])
    converted = {t["column"] for t in res.transformations if t["action"] == "text_to_numeric"}
    assert converted == {"a", "b"}


def test_duplicate_headers_reported(settings: Settings):
    res = ingest_bytes(b"x,x\n1,2\n", "f.csv", settings)
    assert any(t["action"] == "rename_duplicate_headers" for t in res.transformations)


@pytest.mark.parametrize(
    ("content", "exc"),
    [
        (b"", InvalidFileError),
        (b"a,b\n", InvalidFileError),
        (b"a,b\n1,2\n3,4,5\n", InvalidFileError),
        (b"a,b\n\x00\x01,2\n", InvalidFileError),
        (b"a,b\n1,2,3\n4,5,6\n", InvalidFileError),
    ],
    ids=["empty", "header-only", "ragged", "binary", "extra-field"],
)
def test_invalid_csv_rejected_with_message(settings: Settings, content: bytes, exc: type):
    with pytest.raises(exc) as info:
        ingest_bytes(content, "f.csv", settings)
    assert info.value.message


@pytest.mark.parametrize(
    "name", ["data.exe", "macro.xlsm", "old.xls", "noext", "report.xlsb", "x.json"]
)
def test_unsupported_extensions(name: str):
    with pytest.raises(UnsupportedFileTypeError):
        detect_format(name)


def test_size_limit(settings: Settings):
    small = settings.model_copy(update={"max_upload_mb": 0.0001})
    with pytest.raises(FileTooLargeError):
        ingest_bytes(b"a\n" + b"1\n" * 200, "f.csv", small)


def test_row_and_column_limits(settings: Settings):
    with pytest.raises(FileTooLargeError):
        ingest_bytes(b"a\n1\n2\n3\n", "f.csv", settings.model_copy(update={"max_rows": 2}))
    with pytest.raises(InvalidFileError):
        ingest_bytes(b"a,b,c\n1,2,3\n", "f.csv", settings.model_copy(update={"max_columns": 2}))


def test_valid_xlsx(settings: Settings):
    df = pd.DataFrame({"d": pd.to_datetime(["2024-01-01", "2024-01-02"]), "v": [1.5, 2.0]})
    res = ingest_bytes(xlsx_bytes(df), "f.xlsx", settings)
    assert res.file_format == "xlsx"
    assert res.df.shape == (2, 2)
    assert pd.api.types.is_datetime64_any_dtype(res.df["d"])


def test_fake_xlsx_rejected(settings: Settings, known_csv: bytes):
    with pytest.raises(InvalidFileError):
        ingest_bytes(known_csv, "renamed.xlsx", settings)


def test_xlsx_with_macro_rejected(settings: Settings):
    buf = io.BytesIO(xlsx_bytes(pd.DataFrame({"a": [1]})))
    with zipfile.ZipFile(buf, "a") as zf:
        zf.writestr("xl/vbaProject.bin", b"fake")
    with pytest.raises(UnsupportedFileTypeError):
        ingest_bytes(buf.getvalue(), "f.xlsx", settings)


def test_xlsx_decompression_bomb_guard(settings: Settings):
    content = xlsx_bytes(pd.DataFrame({"a": range(10)}))
    tiny = settings.model_copy(update={"max_xlsx_uncompressed_mb": 0.0001})
    with pytest.raises(FileTooLargeError):
        ingest_bytes(content, "f.xlsx", tiny)


def _two_sheet_xlsx(rows: int) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf) as w:
        pd.DataFrame({"a": range(rows), "b": ["x" * 20] * rows}).to_excel(
            w, sheet_name="s1", index=False
        )
        pd.DataFrame({"a": range(rows), "b": ["y" * 20] * rows}).to_excel(
            w, sheet_name="s2", index=False
        )
    return buf.getvalue()


def test_only_first_sheet_counts_toward_uncompressed_limit(settings: Settings):
    content = _two_sheet_xlsx(20_000)
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        sizes = {i.filename: i.file_size for i in zf.infolist()}
    sheet = sizes["xl/worksheets/sheet1.xml"]
    total = sum(sizes.values())
    # limite entre « ce qui est lu » et « tout le classeur »
    limit_mb = (total - sheet / 2) / 1_048_576
    res = ingest_bytes(
        content, "f.xlsx", settings.model_copy(update={"max_xlsx_uncompressed_mb": limit_mb})
    )
    assert res.df.shape == (20_000, 2)
    assert res.parse_info["sheets_available"] == ["s1", "s2"]


def test_high_compression_ratio_rejected(settings: Settings):
    buf = io.BytesIO(xlsx_bytes(pd.DataFrame({"a": [1]})))
    with zipfile.ZipFile(buf, "a", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("xl/worksheets/sheet9.xml", b"\0" * (30 * 1_048_576))
    with pytest.raises(InvalidFileError) as e:
        ingest_bytes(buf.getvalue(), "f.xlsx", settings)
    assert "compression" in e.value.message


def _workbook(sheets: dict[str, pd.DataFrame]) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf) as w:
        for name, frame in sheets.items():
            frame.to_excel(w, sheet_name=name, index=False)
    return buf.getvalue()


Y1 = pd.DataFrame({"Invoice": ["1", "2", "3"], "Quantity": [1, 2, 3]})
Y2 = pd.DataFrame({"Invoice": ["3", "4"], "Quantity": [3, 4]})  # « 3 » chevauche Y1


def test_first_sheet_mode_is_default_and_unchanged(settings: Settings):
    res = ingest_bytes(_workbook({"y1": Y1, "y2": Y2}), "f.xlsx", settings)
    assert len(res.df) == 3
    assert res.parse_info["sheet_mode"] == "first" and res.parse_info["sheet"] == "y1"
    assert res.findings == []


def test_all_sheets_stacked_in_order_without_loss(settings: Settings):
    res = ingest_bytes(_workbook({"y1": Y1, "y2": Y2}), "f.xlsx", settings, sheets="all")
    assert res.df["Invoice"].astype(str).tolist() == ["1", "2", "3", "3", "4"]
    assert res.parse_info["sheet_mode"] == "all"
    assert res.parse_info["sheets_imported"] == ["y1 : 3 lignes", "y2 : 2 lignes"]
    (dup,) = res.findings
    assert dup["code"] == "cross_sheet_duplicates" and dup["count"] == 1
    assert "« y2 » : 1" in dup["message"]


def test_all_sheets_requires_identical_columns(settings: Settings):
    other = Y2.rename(columns={"Quantity": "Qty"})
    with pytest.raises(InvalidFileError) as e:
        ingest_bytes(_workbook({"y1": Y1, "y2": other}), "f.xlsx", settings, sheets="all")
    assert "Qty" in e.value.message and "Quantity" in e.value.message


def test_all_sheets_skips_empty_sheet(settings: Settings):
    content = _workbook({"y1": Y1, "vide": pd.DataFrame(), "y2": Y2})
    res = ingest_bytes(content, "f.xlsx", settings, sheets="all")
    assert len(res.df) == 5 and res.parse_info["sheets_skipped"] == ["vide (vide)"]


def test_all_sheets_row_limit_is_global(settings: Settings):
    tiny = settings.model_copy(update={"max_rows": 4})
    with pytest.raises(FileTooLargeError):
        ingest_bytes(_workbook({"y1": Y1, "y2": Y2}), "f.xlsx", tiny, sheets="all")


def test_all_sheets_count_toward_uncompressed_limit(settings: Settings):
    content = _two_sheet_xlsx(20_000)
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        sizes = {i.filename: i.file_size for i in zf.infolist()}
    limit_mb = (sum(sizes.values()) - sizes["xl/worksheets/sheet1.xml"] / 2) / 1_048_576
    s = settings.model_copy(update={"max_xlsx_uncompressed_mb": limit_mb})
    assert len(ingest_bytes(content, "f.xlsx", s).df) == 20_000  # 1re feuille : passe
    with pytest.raises(FileTooLargeError):
        ingest_bytes(content, "f.xlsx", s, sheets="all")  # toutes : dépasse
