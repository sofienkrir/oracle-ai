"""Schémas HTTP (Pydantic) exposés par l'API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.data.schemas import ColumnRole, QualityReport


class HealthOut(BaseModel):
    status: str
    app: str
    engine_version: str
    environment: str
    database: bool
    llm_enabled: bool
    limits: dict[str, float | int]
    modules: dict[str, str]


class DatasetOut(BaseModel):
    id: str
    name: str
    source_kind: str
    file_format: str
    sha256: str
    size_bytes: int
    n_rows: int
    n_columns: int
    domain: str
    roles: dict[str, str]
    created_at: datetime
    released_at: datetime | None
    loaded: bool


class DatasetDetailOut(DatasetOut):
    parse_info: dict[str, Any]
    transformations: list[dict[str, Any]]
    quality: QualityReport


class PreviewOut(BaseModel):
    columns: list[str]
    rows: list[list[Any]]
    offset: int
    limit: int
    total: int


class RolesIn(BaseModel):
    roles: dict[str, ColumnRole]


class RolesOut(BaseModel):
    roles: dict[str, str]


class AnalysisOut(BaseModel):
    id: int
    dataset_id: str
    dataset_name: str
    kind: str
    params: dict[str, Any]
    summary: dict[str, Any]
    engine_version: str
    created_at: datetime


class ErrorOut(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = {}
