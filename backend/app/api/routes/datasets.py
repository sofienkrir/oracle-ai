from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response

from app.api.deps import get_dataset_service, get_repo, get_settings_dep
from app.api.schemas import (
    AnalysisOut,
    DatasetDetailOut,
    DatasetOut,
    PreviewOut,
    RolesIn,
    RolesOut,
)
from app.core.config import Settings
from app.core.exceptions import FileTooLargeError
from app.persistence.models import DatasetRecord
from app.persistence.repositories import HistoryRepository
from app.reporting.quality_export import report_to_csv, report_to_json
from app.services.datasets import DatasetService

router = APIRouter(tags=["datasets"])

_CHUNK = 1024 * 1024


def _out(rec: DatasetRecord, service: DatasetService) -> DatasetOut:
    return DatasetOut(
        id=rec.id,
        name=rec.name,
        source_kind=rec.source_kind,
        file_format=rec.file_format,
        sha256=rec.sha256,
        size_bytes=rec.size_bytes,
        n_rows=rec.n_rows,
        n_columns=rec.n_columns,
        domain=rec.domain,
        roles=rec.roles,
        created_at=rec.created_at,
        released_at=rec.released_at,
        loaded=service.is_loaded(rec.id),
    )


def _detail(dataset_id: str, service: DatasetService) -> DatasetDetailOut:
    entry = service.get_entry(dataset_id)
    rec = service.get_record(dataset_id)
    return DatasetDetailOut(
        **_out(rec, service).model_dump(),
        parse_info=entry.parse_info,
        transformations=entry.transformations,
        quality=entry.report,
    )


@router.post("/datasets/upload", response_model=DatasetDetailOut, status_code=201)
async def upload(
    file: UploadFile = File(...),
    service: DatasetService = Depends(get_dataset_service),
    settings: Settings = Depends(get_settings_dep),
) -> DatasetDetailOut:
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(_CHUNK):
        total += len(chunk)
        if total > settings.max_upload_bytes:
            raise FileTooLargeError(
                f"Le fichier dépasse la limite de {settings.max_upload_mb:g} Mo "
                "(paramètre ORACLE_MAX_UPLOAD_MB)."
            )
        chunks.append(chunk)
    content = b"".join(chunks)
    rec = await run_in_threadpool(service.import_upload, content, file.filename or "")
    return _detail(rec.id, service)


@router.post("/datasets/samples/{sample_id}", response_model=DatasetDetailOut, status_code=201)
async def load_sample(
    sample_id: str, service: DatasetService = Depends(get_dataset_service)
) -> DatasetDetailOut:
    rec = await run_in_threadpool(service.import_sample, sample_id)
    return _detail(rec.id, service)


@router.get("/datasets", response_model=list[DatasetOut])
def list_datasets(
    loaded_only: bool = False,
    service: DatasetService = Depends(get_dataset_service),
    repo: HistoryRepository = Depends(get_repo),
) -> list[DatasetOut]:
    items = [_out(r, service) for r in repo.list_datasets()]
    return [d for d in items if d.loaded] if loaded_only else items


@router.get("/datasets/{dataset_id}", response_model=DatasetDetailOut)
def get_dataset(
    dataset_id: str, service: DatasetService = Depends(get_dataset_service)
) -> DatasetDetailOut:
    return _detail(dataset_id, service)


@router.get("/datasets/{dataset_id}/preview", response_model=PreviewOut)
def preview(
    dataset_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    service: DatasetService = Depends(get_dataset_service),
) -> PreviewOut:
    return PreviewOut(**service.preview(dataset_id, offset, limit))


@router.put("/datasets/{dataset_id}/roles", response_model=RolesOut)
def update_roles(
    dataset_id: str, body: RolesIn, service: DatasetService = Depends(get_dataset_service)
) -> RolesOut:
    return RolesOut(roles=service.update_roles(dataset_id, dict(body.roles)))


@router.get("/datasets/{dataset_id}/quality/export")
def export_quality(
    dataset_id: str,
    format: Literal["json", "csv"] = "json",
    service: DatasetService = Depends(get_dataset_service),
) -> Response:
    entry = service.get_entry(dataset_id)
    rec = service.get_record(dataset_id)
    meta = {
        "id": rec.id,
        "name": rec.name,
        "sha256": rec.sha256,
        "source_kind": rec.source_kind,
        "roles": rec.roles,
        "parse_info": entry.parse_info,
        "transformations": entry.transformations,
    }
    stem = re.sub(r"[^A-Za-z0-9._-]", "_", rec.name.rsplit(".", 1)[0])[:80] or "dataset"
    if format == "csv":
        body = "﻿" + report_to_csv(entry.report, meta)  # BOM : accents corrects dans Excel
        media = "text/csv; charset=utf-8"
    else:
        body = report_to_json(entry.report, meta)
        media = "application/json"
    return Response(
        content=body.encode("utf-8"),
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="qualite_{stem}.{format}"'},
    )


@router.delete("/datasets/{dataset_id}", status_code=204)
def release_dataset(
    dataset_id: str, service: DatasetService = Depends(get_dataset_service)
) -> Response:
    service.release(dataset_id)
    return Response(status_code=204)


@router.get("/history", response_model=list[AnalysisOut])
def history(
    dataset_id: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    repo: HistoryRepository = Depends(get_repo),
) -> list[AnalysisOut]:
    return [
        AnalysisOut(
            id=a.id,
            dataset_id=a.dataset_id,
            dataset_name=name,
            kind=a.kind,
            params=a.params,
            summary=a.summary,
            engine_version=a.engine_version,
            created_at=a.created_at,
        )
        for a, name in repo.list_analyses(dataset_id, limit)
    ]
