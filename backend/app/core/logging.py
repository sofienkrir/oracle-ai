"""Logging applicatif minimal.

Règle : ne jamais journaliser le contenu des données importées (valeurs de cellules),
uniquement des métadonnées (taille, nombre de lignes, identifiants internes).
"""

from __future__ import annotations

import logging

_FORMAT = "%(asctime)s %(levelname)s %(name)s — %(message)s"


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(level=level.upper(), format=_FORMAT, force=True)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"oracle.{name}")
