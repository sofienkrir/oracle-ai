"""Accès aux données d'historique (couche fine au-dessus de SQLAlchemy)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.core.config import ENGINE_VERSION
from app.persistence.db import Database
from app.persistence.models import AnalysisRecord, DatasetRecord


class HistoryRepository:
    def __init__(self, db: Database):
        self.db = db

    def add_dataset(self, record: DatasetRecord) -> DatasetRecord:
        with self.db.session() as s:
            s.add(record)
        return record

    def get_dataset(self, dataset_id: str) -> DatasetRecord | None:
        with self.db.session() as s:
            return s.get(DatasetRecord, dataset_id)

    def list_datasets(self, limit: int = 50) -> list[DatasetRecord]:
        with self.db.session() as s:
            stmt = select(DatasetRecord).order_by(DatasetRecord.created_at.desc()).limit(limit)
            return list(s.scalars(stmt))

    def update_roles(self, dataset_id: str, roles: dict[str, Any]) -> None:
        with self.db.session() as s:
            rec = s.get(DatasetRecord, dataset_id)
            if rec is not None:
                rec.roles = roles

    def mark_released(self, dataset_id: str) -> None:
        with self.db.session() as s:
            rec = s.get(DatasetRecord, dataset_id)
            if rec is not None and rec.released_at is None:
                rec.released_at = datetime.now(UTC)

    def add_analysis(
        self,
        dataset_id: str,
        kind: str,
        params: dict[str, Any],
        summary: dict[str, Any],
    ) -> AnalysisRecord:
        rec = AnalysisRecord(
            dataset_id=dataset_id,
            kind=kind,
            params=params,
            summary=summary,
            engine_version=ENGINE_VERSION,
        )
        with self.db.session() as s:
            s.add(rec)
            s.flush()
        return rec

    def list_analyses(
        self, dataset_id: str | None = None, limit: int = 100
    ) -> list[tuple[AnalysisRecord, str]]:
        with self.db.session() as s:
            stmt = (
                select(AnalysisRecord, DatasetRecord.name)
                .join(DatasetRecord, AnalysisRecord.dataset_id == DatasetRecord.id)
                .order_by(AnalysisRecord.created_at.desc(), AnalysisRecord.id.desc())
                .limit(limit)
            )
            if dataset_id:
                stmt = stmt.where(AnalysisRecord.dataset_id == dataset_id)
            return [(a, name) for a, name in s.execute(stmt).all()]
