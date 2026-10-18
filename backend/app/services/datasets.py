"""Orchestration : import → validation → profilage → historique."""

from __future__ import annotations

import math
import secrets
import time
from dataclasses import asdict
from typing import Any

import pandas as pd

from app.core.config import Settings
from app.core.exceptions import DatasetExpiredError, DatasetNotFoundError
from app.core.logging import get_logger
from app.data.ingestion import ingest_bytes
from app.data.profiling import ProfileParams, profile_dataframe
from app.data.roles import default_roles, validate_roles
from app.persistence.models import DatasetRecord
from app.persistence.repositories import HistoryRepository
from app.services.samples import sample_path
from app.services.workspace import WorkspaceEntry, WorkspaceStore

log = get_logger("datasets")


class DatasetService:
    def __init__(self, settings: Settings, repo: HistoryRepository):
        self.settings = settings
        self.repo = repo
        self.store = WorkspaceStore(
            max_items=settings.workspace_max_datasets,
            ttl_seconds=settings.workspace_ttl_minutes * 60,
            on_evict=repo.mark_released,
        )

    # ------------------------------------------------------------------ import

    def import_upload(self, content: bytes, filename: str) -> DatasetRecord:
        return self._import(content, filename, source_kind="upload")

    def import_sample(self, sample_id: str) -> DatasetRecord:
        info, path = sample_path(self.settings.samples_dir, sample_id)
        return self._import(path.read_bytes(), info.file, source_kind="sample")

    def _import(self, content: bytes, filename: str, source_kind: str) -> DatasetRecord:
        t0 = time.perf_counter()
        ingested = ingest_bytes(content, filename, self.settings)
        params = self._profile_params()
        report = profile_dataframe(ingested.df, params)
        elapsed = time.perf_counter() - t0

        dataset_id = secrets.token_hex(8)
        record = DatasetRecord(
            id=dataset_id,
            name=_safe_name(filename),
            source_kind=source_kind,
            file_format=ingested.file_format,
            sha256=ingested.sha256,
            size_bytes=ingested.size_bytes,
            n_rows=report.n_rows,
            n_columns=report.n_columns,
            domain=report.domain,
            roles=default_roles(report),
        )
        self.repo.add_dataset(record)
        self.store.put(
            dataset_id,
            WorkspaceEntry(
                df=ingested.df,
                report=report,
                parse_info=ingested.parse_info,
                transformations=ingested.transformations,
            ),
        )
        self.repo.add_analysis(
            dataset_id,
            kind="quality_profile",
            params={"profile": asdict(params), "parse": ingested.parse_info},
            summary={
                "score": report.score,
                "n_rows": report.n_rows,
                "n_columns": report.n_columns,
                "n_issues": len(report.issues),
                "n_warnings": sum(i.severity == "warning" for i in report.issues),
                "n_duplicate_rows": report.n_duplicate_rows,
                "pct_cells_missing": report.pct_cells_missing,
                "domain": report.domain,
                "duration_s": round(elapsed, 3),
            },
        )
        log.info(
            "dataset importé id=%s format=%s lignes=%d colonnes=%d durée=%.2fs",
            dataset_id,
            ingested.file_format,
            report.n_rows,
            report.n_columns,
            elapsed,
        )
        return record

    # ------------------------------------------------------------------ lecture

    def get_record(self, dataset_id: str) -> DatasetRecord:
        rec = self.repo.get_dataset(dataset_id)
        if rec is None:
            raise DatasetNotFoundError(f"Dataset « {dataset_id} » introuvable.")
        return rec

    def get_entry(self, dataset_id: str) -> WorkspaceEntry:
        rec = self.get_record(dataset_id)
        entry = self.store.get(dataset_id)
        if entry is None:
            raise DatasetExpiredError(
                f"La copie de travail de « {rec.name} » n'est plus en mémoire (expiration ou "
                "redémarrage). Les métadonnées sont conservées ; réimportez le fichier pour "
                "poursuivre l'analyse."
            )
        return entry

    def is_loaded(self, dataset_id: str) -> bool:
        return dataset_id in self.store

    def preview(self, dataset_id: str, offset: int = 0, limit: int = 50) -> dict[str, Any]:
        entry = self.get_entry(dataset_id)
        df = entry.df
        page = df.iloc[offset : offset + limit]
        return {
            "columns": [str(c) for c in df.columns],
            "rows": _to_json_rows(page),
            "offset": offset,
            "limit": limit,
            "total": len(df),
        }

    def update_roles(self, dataset_id: str, roles: dict[str, str]) -> dict[str, str]:
        entry = self.get_entry(dataset_id)
        merged = validate_roles(entry.report, roles)
        rec = self.get_record(dataset_id)
        changed = {k: v for k, v in merged.items() if rec.roles.get(k) != v}
        self.repo.update_roles(dataset_id, dict(merged))
        if changed:
            self.repo.add_analysis(
                dataset_id,
                kind="roles_update",
                params={"changed": changed},
                summary={"n_changed": len(changed)},
            )
        return dict(merged)

    def release(self, dataset_id: str) -> None:
        self.get_record(dataset_id)
        if not self.store.remove(dataset_id):
            self.repo.mark_released(dataset_id)

    def _profile_params(self) -> ProfileParams:
        s = self.settings
        return ProfileParams(
            high_cardinality_ratio=s.high_cardinality_ratio,
            high_cardinality_min_unique=s.high_cardinality_min_unique,
            mixed_type_min_share=s.mixed_type_min_share,
        )


def _safe_name(filename: str) -> str:
    base = filename.replace("\\", "/").split("/")[-1]
    return base[:255] or "sans_nom"


def _to_json_rows(df: pd.DataFrame) -> list[list[Any]]:
    out: list[list[Any]] = []
    for row in df.itertuples(index=False, name=None):
        out.append([_json_value(v) for v in row])
    return out


def _json_value(v: Any) -> Any:
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return None
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    if hasattr(v, "item"):  # types numpy
        v = v.item()
    if isinstance(v, float) and not math.isfinite(v):
        return str(v)
    if isinstance(v, int | float | bool | str):
        return v
    return str(v)
