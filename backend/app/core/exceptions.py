"""Exceptions métier avec messages lisibles par un utilisateur non technique."""

from __future__ import annotations


class OracleError(Exception):
    """Erreur métier : `code` stable pour le frontend, `message` affichable tel quel."""

    status_code: int = 400
    code: str = "oracle_error"

    def __init__(self, message: str, *, code: str | None = None, details: dict | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        self.details = details or {}


class InvalidFileError(OracleError):
    status_code = 422
    code = "invalid_file"


class FileTooLargeError(OracleError):
    status_code = 413
    code = "file_too_large"


class UnsupportedFileTypeError(OracleError):
    status_code = 415
    code = "unsupported_file_type"


class DatasetNotFoundError(OracleError):
    status_code = 404
    code = "dataset_not_found"


class DatasetExpiredError(OracleError):
    """Les métadonnées existent mais la copie de travail en mémoire a été libérée."""

    status_code = 410
    code = "dataset_expired"


class InvalidRolesError(OracleError):
    status_code = 422
    code = "invalid_roles"
