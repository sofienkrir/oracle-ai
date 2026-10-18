from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_db, get_settings_dep
from app.api.schemas import HealthOut
from app.core.config import ENGINE_VERSION, Settings
from app.persistence.db import Database
from app.services.samples import SampleInfo, load_catalog

router = APIRouter(tags=["système"])

# État réel des modules : mis à jour à chaque étape livrée, jamais anticipé.
MODULE_STATUS: dict[str, str] = {
    "import_quality": "available",
    "history": "available",
    "explorer_kpi": "planned:3",
    "anomalies": "planned:4",
    "forecasting": "planned:5",
    "root_cause": "planned:6",
    "scenario_lab": "planned:6",
    "decision_report": "planned:7",
}


@router.get("/health", response_model=HealthOut)
def health(
    settings: Settings = Depends(get_settings_dep), db: Database = Depends(get_db)
) -> HealthOut:
    db_ok = db.ping()
    return HealthOut(
        status="ok" if db_ok else "degraded",
        app=settings.app_name,
        engine_version=ENGINE_VERSION,
        environment=settings.environment,
        database=db_ok,
        llm_enabled=settings.llm_enabled,
        limits={
            "max_upload_mb": settings.max_upload_mb,
            "max_rows": settings.max_rows,
            "max_columns": settings.max_columns,
            "workspace_max_datasets": settings.workspace_max_datasets,
            "workspace_ttl_minutes": settings.workspace_ttl_minutes,
        },
        modules=MODULE_STATUS,
    )


@router.get("/samples", response_model=list[SampleInfo])
def samples(settings: Settings = Depends(get_settings_dep)) -> list[SampleInfo]:
    return load_catalog(settings.samples_dir)
