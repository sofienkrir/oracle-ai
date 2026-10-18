"""Catalogue des datasets de démonstration (fichiers synthétiques du dépôt)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.core.exceptions import DatasetNotFoundError


class SampleInfo(BaseModel):
    id: str
    file: str
    title: str
    domain: str
    description: str
    synthetic: bool
    provenance: str
    rows: int | None = None
    meta: dict[str, Any] | None = None


def load_catalog(samples_dir: Path) -> list[SampleInfo]:
    manifest = samples_dir / "manifest.json"
    if not manifest.exists():
        return []
    data = json.loads(manifest.read_text(encoding="utf-8"))
    return [SampleInfo(**item) for item in data.get("samples", [])]


def sample_path(samples_dir: Path, sample_id: str) -> tuple[SampleInfo, Path]:
    for info in load_catalog(samples_dir):
        if info.id == sample_id:
            path = (samples_dir / info.file).resolve()
            if samples_dir.resolve() not in path.parents or not path.exists():
                break
            return info, path
    raise DatasetNotFoundError(f"Dataset de démonstration « {sample_id} » introuvable.")
