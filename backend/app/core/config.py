"""Configuration typée, chargée depuis l'environnement et le fichier .env.

Aucune valeur secrète n'est codée en dur : voir `.env.example` à la racine du dépôt.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_DIR.parent

ENGINE_VERSION = "0.2.0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ORACLE_",
        env_file=(REPO_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "ORACLE AI"
    environment: str = Field(default="dev", description="dev | test | prod")
    log_level: str = "INFO"

    # Stockage local : métadonnées SQLite uniquement (pas de copie du fichier source).
    data_dir: Path = REPO_DIR / "var"
    database_url: str | None = None

    # Limites d'import (fichiers traités comme non fiables).
    max_upload_mb: float = Field(default=50.0, gt=0)
    max_rows: int = Field(default=600_000, gt=0)
    max_columns: int = Field(default=200, gt=0)
    max_xlsx_uncompressed_mb: float = Field(default=300.0, gt=0)

    # Copies de travail en mémoire : nombre max de datasets et durée de vie.
    workspace_max_datasets: int = Field(default=5, gt=0)
    workspace_ttl_minutes: int = Field(default=120, gt=0)

    # Profilage.
    high_cardinality_ratio: float = Field(default=0.5, gt=0, le=1)
    high_cardinality_min_unique: int = Field(default=50, gt=0)
    mixed_type_min_share: float = Field(default=0.05, gt=0, lt=1)

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # LLM optionnel (étape ultérieure) — jamais requis pour le fonctionnement principal.
    llm_api_key: SecretStr | None = None

    samples_dir: Path = REPO_DIR / "datasets" / "samples"

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{(self.data_dir / 'oracle.db').as_posix()}"

    @property
    def max_upload_bytes(self) -> int:
        return int(self.max_upload_mb * 1024 * 1024)

    @property
    def llm_enabled(self) -> bool:
        return self.llm_api_key is not None and bool(self.llm_api_key.get_secret_value())


@lru_cache
def get_settings() -> Settings:
    return Settings()
