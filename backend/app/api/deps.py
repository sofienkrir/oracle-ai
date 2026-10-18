"""Dépendances FastAPI : accès aux services stockés sur l'application."""

from __future__ import annotations

from fastapi import Request

from app.core.config import Settings
from app.persistence.db import Database
from app.persistence.repositories import HistoryRepository
from app.services.datasets import DatasetService


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request) -> Database:
    return request.app.state.db


def get_repo(request: Request) -> HistoryRepository:
    return request.app.state.repo


def get_dataset_service(request: Request) -> DatasetService:
    return request.app.state.datasets
