"""Import sécurisé de fichiers CSV / XLSX.

Principes (cf. cahier des charges §4.1 et §9) :
- le fichier est traité comme non fiable : extension, signature, taille, nombre de
  lignes/colonnes et taille décompressée (XLSX) sont vérifiés avant analyse ;
- aucune macro n'est acceptée (.xlsm / vbaProject.bin refusés), aucune formule n'est évaluée ;
- aucune ligne n'est supprimée ni modifiée ; les seules conversions effectuées
  (texte → numérique sans perte) sont listées dans `transformations`.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import PurePath
from typing import Any, Literal

import pandas as pd

from app.core.config import Settings
from app.core.exceptions import FileTooLargeError, InvalidFileError, UnsupportedFileTypeError

FileFormat = Literal["csv", "xlsx"]
SheetMode = Literal["first", "all"]

_CSV_DELIMITERS = [",", ";", "\t", "|"]
_ENCODINGS = ["utf-8-sig", "cp1252", "latin-1"]
_ZIP_MAGIC = b"PK\x03\x04"
_LEADING_ZERO = re.compile(r"^[+-]?0\d")


@dataclass
class IngestedFile:
    df: pd.DataFrame
    file_format: FileFormat
    sha256: str
    size_bytes: int
    parse_info: dict[str, Any] = field(default_factory=dict)
    transformations: list[dict[str, Any]] = field(default_factory=list)
    # Constats propres à la lecture (ex. doublons entre feuilles), ajoutés au rapport qualité.
    findings: list[dict[str, Any]] = field(default_factory=list)


def ingest_bytes(
    content: bytes, filename: str, settings: Settings, sheets: SheetMode = "first"
) -> IngestedFile:
    """Valide puis lit un fichier téléversé. Lève une `OracleError` explicite en cas d'échec.

    `sheets` (XLSX uniquement) : « first » lit la 1re feuille ; « all » empile toutes les
    feuilles non vides, qui doivent avoir exactement les mêmes colonnes."""
    size = len(content)
    if size == 0:
        raise InvalidFileError("Le fichier est vide.")
    if size > settings.max_upload_bytes:
        raise FileTooLargeError(
            f"Le fichier fait {size / 1_048_576:.1f} Mo ; la limite est "
            f"{settings.max_upload_mb:g} Mo (paramètre ORACLE_MAX_UPLOAD_MB).",
            details={"size_bytes": size, "limit_bytes": settings.max_upload_bytes},
        )

    fmt = detect_format(filename)
    sha = hashlib.sha256(content).hexdigest()

    findings: list[dict[str, Any]] = []
    if fmt == "xlsx":
        df, info, findings = _read_xlsx(content, settings, sheets)
        transformations: list[dict[str, Any]] = []
    else:
        df, info, transformations = _read_csv(content, settings)

    _check_shape(df, settings)
    return IngestedFile(
        df=df,
        file_format=fmt,
        sha256=sha,
        size_bytes=size,
        parse_info=info,
        transformations=transformations,
        findings=findings,
    )


def detect_format(filename: str) -> FileFormat:
    suffix = PurePath(filename or "").suffix.lower()
    if suffix == ".csv":
        return "csv"
    if suffix == ".xlsx":
        return "xlsx"
    if suffix in {".xlsm", ".xlsb"}:
        raise UnsupportedFileTypeError(
            "Les classeurs avec macros (.xlsm/.xlsb) sont refusés par sécurité. "
            "Enregistrez le fichier au format .xlsx ou .csv."
        )
    if suffix == ".xls":
        raise UnsupportedFileTypeError(
            "L'ancien format Excel .xls n'est pas pris en charge. Enregistrez-le en .xlsx ou .csv."
        )
    raise UnsupportedFileTypeError(
        f"Type de fichier « {suffix or 'sans extension'} » non pris en charge. "
        "Formats acceptés : .csv, .xlsx."
    )


# --------------------------------------------------------------------------- XLSX


def _read_xlsx(
    content: bytes, settings: Settings, sheets: SheetMode = "first"
) -> tuple[pd.DataFrame, dict[str, Any], list[dict[str, Any]]]:
    if not content.startswith(_ZIP_MAGIC):
        raise InvalidFileError(
            "Le fichier porte l'extension .xlsx mais n'est pas un classeur Excel valide."
        )
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            infos = zf.infolist()
            names = [i.filename for i in infos]
            if "xl/workbook.xml" not in names:
                raise InvalidFileError(
                    "Le fichier ne contient pas de classeur Excel (xl/workbook.xml)."
                )
            if any(n.lower().endswith("vbaproject.bin") for n in names):
                raise UnsupportedFileTypeError("Le classeur contient des macros : import refusé.")
            first_sheet = _first_sheet_part(zf)
    except zipfile.BadZipFile as exc:
        raise InvalidFileError("Classeur Excel corrompu ou illisible.") from exc

    # En mode « all », toutes les feuilles sont lues : elles comptent toutes dans la limite.
    _check_zip_entries(infos, first_sheet if sheets == "first" else None, settings)

    engine = _excel_engine()
    try:
        sheet_names = pd.ExcelFile(io.BytesIO(content), engine=engine).sheet_names
        raw = pd.read_excel(
            io.BytesIO(content),
            sheet_name=0 if sheets == "first" else None,
            engine=engine,
            nrows=settings.max_rows + 1,
        )
    except Exception as exc:  # erreurs de parsing variées selon le moteur
        raise InvalidFileError(f"Impossible de lire le classeur : {exc}") from exc

    note = "Les formules ne sont pas évaluées (valeurs mises en cache par Excel)."
    if sheets == "first":
        info = {
            "engine": engine,
            "sheet_mode": "first",
            "sheet": sheet_names[0] if sheet_names else None,
            "sheets_available": sheet_names,
            "note": "Seule la première feuille est importée. " + note,
        }
        return raw, info, []

    df, info, findings = _stack_sheets(raw, settings)
    info.update({"engine": engine, "sheets_available": sheet_names, "note": note})
    return df, info, findings


def _stack_sheets(
    frames: dict[str, pd.DataFrame], settings: Settings
) -> tuple[pd.DataFrame, dict[str, Any], list[dict[str, Any]]]:
    """Empile les feuilles non vides (mêmes colonnes, même ordre) sans modifier les lignes."""
    kept = {name: f for name, f in frames.items() if f.shape[1] > 0 and len(f) > 0}
    skipped = [name for name in frames if name not in kept]
    if not kept:
        raise InvalidFileError("Toutes les feuilles du classeur sont vides.")

    ref_name, ref = next(iter(kept.items()))
    ref_cols = [str(c) for c in ref.columns]
    for name, f in kept.items():
        cols = [str(c) for c in f.columns]
        if cols != ref_cols:
            missing = [c for c in ref_cols if c not in cols]
            extra = [c for c in cols if c not in ref_cols]
            detail = []
            if missing:
                detail.append(f"absentes : {missing}")
            if extra:
                detail.append(f"en plus : {extra}")
            if not detail:
                detail.append("ordre différent")
            raise InvalidFileError(
                f"Les feuilles « {ref_name} » et « {name} » n'ont pas les mêmes colonnes "
                f"({'; '.join(detail)}). Importez-les séparément (mode « première feuille »)."
            )

    total = sum(len(f) for f in kept.values())
    if total > settings.max_rows:
        raise FileTooLargeError(
            f"Les feuilles totalisent {total:,} lignes ; la limite est {settings.max_rows:,} "
            "(paramètre ORACLE_MAX_ROWS).".replace(",", " ")
        )

    findings = _cross_sheet_duplicates(kept)
    df = pd.concat(list(kept.values()), ignore_index=True)
    info: dict[str, Any] = {
        "sheet_mode": "all",
        "sheet": ", ".join(kept),
        "sheets_imported": [
            f"{name} : {len(f):,} lignes".replace(",", " ") for name, f in kept.items()
        ],
    }
    if skipped:
        info["sheets_skipped"] = [f"{name} (vide)" for name in skipped]
    return df, info, findings


def _cross_sheet_duplicates(frames: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    """Compte, pour chaque feuille après la première, les lignes strictement identiques à une
    ligne d'une feuille précédente (typiquement un chevauchement de période)."""
    seen: set[int] = set()
    per_sheet: dict[str, int] = {}
    for i, (name, f) in enumerate(frames.items()):
        hashes = pd.util.hash_pandas_object(f.astype(str), index=False)
        if i > 0:
            n = int(hashes.isin(seen).sum())
            if n:
                per_sheet[name] = n
        seen.update(hashes.tolist())
    if not per_sheet:
        return []
    total = sum(per_sheet.values())
    detail = ", ".join(f"« {k} » : {v}" for k, v in per_sheet.items())
    return [
        {
            "code": "cross_sheet_duplicates",
            "severity": "warning",
            "count": total,
            "message": f"{total} lignes d'une feuille sont strictement identiques à des lignes "
            f"d'une feuille précédente ({detail}) : chevauchement probable entre feuilles. "
            "Elles sont conservées et comptées dans les doublons ; à exclure avant tout total.",
        }
    ]


_SMALL_XML_LIMIT = 2 * 1_048_576
_SHEET_TAG = re.compile(rb"<(?:\w+:)?sheet\b[^>]*?\br:id=\"([^\"]+)\"")
_REL_TAG = re.compile(rb"<(?:\w+:)?Relationship\b[^>]*>")
_ATTR = re.compile(rb'\b(Id|Target)="([^"]+)"')
# Au-delà de ce taux de compression, une entrée est traitée comme une archive piégée.
_MAX_COMPRESSION_RATIO = 100
_RATIO_MIN_BYTES = 10 * 1_048_576


def _read_small(zf: zipfile.ZipFile, name: str) -> bytes:
    info = zf.getinfo(name)
    if info.file_size > _SMALL_XML_LIMIT:
        raise InvalidFileError(f"Partie « {name} » anormalement volumineuse.")
    return zf.read(name)


def _first_sheet_part(zf: zipfile.ZipFile) -> str | None:
    """Chemin de la 1re feuille (seule lue), d'après workbook.xml et ses relations."""
    try:
        sheet = _SHEET_TAG.search(_read_small(zf, "xl/workbook.xml"))
        rels = _read_small(zf, "xl/_rels/workbook.xml.rels")
    except KeyError:
        return None
    if not sheet:
        return None
    for tag in _REL_TAG.findall(rels):
        attrs = dict(_ATTR.findall(tag))
        if attrs.get(b"Id") == sheet.group(1) and b"Target" in attrs:
            target = attrs[b"Target"].decode("utf-8", "replace").lstrip("/")
            return target if target.startswith("xl/") else f"xl/{target}"
    return None


def _check_zip_entries(
    infos: list[zipfile.ZipInfo], first_sheet: str | None, settings: Settings
) -> None:
    """Protection anti « zip bomb » :
    1. taux de compression anormal sur une grosse entrée → refus ;
    2. la taille décompressée de ce qui est réellement lu (1re feuille + parties communes,
       hors autres feuilles) ne doit pas dépasser ORACLE_MAX_XLSX_UNCOMPRESSED_MB."""
    for i in infos:
        if i.file_size > _RATIO_MIN_BYTES and i.file_size > _MAX_COMPRESSION_RATIO * max(
            i.compress_size, 1
        ):
            raise InvalidFileError(
                "Taux de compression anormal dans le classeur (archive potentiellement "
                "malveillante) : import refusé."
            )
    read_size = sum(
        i.file_size
        for i in infos
        if not i.filename.startswith("xl/worksheets/sheet") or i.filename == first_sheet
    )
    if first_sheet is None:  # structure inhabituelle : on reste prudent et on compte tout
        read_size = sum(i.file_size for i in infos)
    if read_size > settings.max_xlsx_uncompressed_mb * 1_048_576:
        raise FileTooLargeError(
            f"Les feuilles à lire font {read_size / 1_048_576:.0f} Mo une fois décompressées ; "
            f"la limite est {settings.max_xlsx_uncompressed_mb:g} Mo "
            "(paramètre ORACLE_MAX_XLSX_UNCOMPRESSED_MB)."
        )


def _excel_engine() -> str:
    try:
        import python_calamine  # noqa: F401

        return "calamine"
    except ImportError:  # pragma: no cover - dépend de l'environnement
        return "openpyxl"


# --------------------------------------------------------------------------- CSV


def _read_csv(
    content: bytes, settings: Settings
) -> tuple[pd.DataFrame, dict[str, Any], list[dict[str, Any]]]:
    if b"\x00" in content[:65536]:
        raise InvalidFileError("Le fichier .csv semble binaire (octets nuls détectés).")

    text, encoding = _decode(content)
    sample = text[:65536]
    delimiter = _sniff_delimiter(sample)

    header = next(csv.reader(io.StringIO(sample), delimiter=delimiter), [])
    if not header or all(not h.strip() for h in header):
        raise InvalidFileError("Aucune ligne d'en-tête détectée dans le fichier CSV.")

    try:
        df = pd.read_csv(
            io.StringIO(text),
            sep=delimiter,
            dtype=str,  # lecture brute : aucune conversion implicite
            keep_default_na=False,
            na_values=["", "NA", "N/A", "NaN", "nan", "NULL", "null", "None"],
            nrows=settings.max_rows + 1,
            on_bad_lines="error",
            engine="c",
        )
    except pd.errors.ParserError as exc:
        raise InvalidFileError(f"Structure CSV incohérente : {exc}") from exc
    except pd.errors.EmptyDataError as exc:
        raise InvalidFileError("Le fichier CSV ne contient aucune donnée.") from exc

    if not isinstance(df.index, pd.RangeIndex):
        # pandas utilise silencieusement la 1re colonne comme index quand chaque ligne a un
        # champ de plus que l'en-tête : on refuse plutôt que de décaler les colonnes.
        raise InvalidFileError(
            "Les lignes de données comportent plus de champs que l'en-tête "
            "(séparateur ou en-tête incorrect)."
        )

    transformations: list[dict[str, Any]] = []
    dup_headers = sorted({h for h in header if header.count(h) > 1})
    if dup_headers:
        transformations.append(
            {
                "column": None,
                "action": "rename_duplicate_headers",
                "detail": f"En-têtes dupliqués renommés automatiquement : {dup_headers}",
            }
        )

    df, conversions = _convert_lossless_numeric(df)
    transformations.extend(conversions)

    info = {"encoding": encoding, "delimiter": delimiter}
    return df, info, transformations


def _decode(content: bytes) -> tuple[str, str]:
    for enc in _ENCODINGS:
        try:
            return content.decode(enc), enc
        except UnicodeDecodeError:
            continue
    raise InvalidFileError("Encodage du fichier non reconnu.")  # pragma: no cover


def _sniff_delimiter(sample: str) -> str:
    try:
        return csv.Sniffer().sniff(sample, delimiters="".join(_CSV_DELIMITERS)).delimiter
    except csv.Error:
        first = sample.splitlines()[0] if sample else ""
        counts = {d: first.count(d) for d in _CSV_DELIMITERS}
        best = max(counts, key=counts.get)
        return best if counts[best] > 0 else ","


def _convert_lossless_numeric(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Convertit en numérique les colonnes texte dont TOUTES les valeurs non vides sont des
    nombres et où la conversion est sans perte (pas de zéros de tête comme « 007 »).
    Chaque conversion est tracée ; les autres colonnes restent du texte brut."""
    conversions: list[dict[str, Any]] = []
    out = df.copy()
    for col in df.columns:
        s = df[col]
        non_null = s.dropna()
        if non_null.empty:
            continue
        stripped = non_null.str.strip()
        if stripped.str.match(_LEADING_ZERO).any():
            continue
        parsed = pd.to_numeric(stripped, errors="coerce")
        if parsed.notna().all():
            converted = pd.to_numeric(s.str.strip(), errors="coerce")
            if (converted.dropna() % 1 == 0).all():
                converted = converted.astype("Int64")
            out[col] = converted
            conversions.append(
                {
                    "column": str(col),
                    "action": "text_to_numeric",
                    "detail": f"{len(non_null)} valeurs texte converties en nombres "
                    f"(type {converted.dtype}).",
                }
            )
    return out, conversions


def _check_shape(df: pd.DataFrame, settings: Settings) -> None:
    if df.shape[1] == 0:
        raise InvalidFileError("Aucune colonne détectée.")
    if df.shape[1] > settings.max_columns:
        raise InvalidFileError(
            f"{df.shape[1]} colonnes détectées ; la limite est {settings.max_columns} "
            "(paramètre ORACLE_MAX_COLUMNS)."
        )
    if len(df) == 0:
        raise InvalidFileError("Le fichier contient un en-tête mais aucune ligne de données.")
    if len(df) > settings.max_rows:
        raise FileTooLargeError(
            f"Le fichier dépasse {settings.max_rows:,} lignes (paramètre ORACLE_MAX_ROWS).".replace(
                ",", " "
            )
        )
