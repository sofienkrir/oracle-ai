"""Validation des rôles de colonnes confirmés ou corrigés par l'utilisateur."""

from __future__ import annotations

from typing import get_args

from app.core.exceptions import InvalidRolesError
from app.data.schemas import ROLE_LABELS, ColumnRole, QualityReport

VALID_ROLES = set(get_args(ColumnRole))
_MIN_SHARE = 0.95


def default_roles(report: QualityReport) -> dict[str, ColumnRole]:
    return {c.name: c.suggested_role for c in report.columns}


def validate_roles(
    report: QualityReport,
    roles: dict[str, str],
    current: dict[str, ColumnRole] | None = None,
) -> dict[str, ColumnRole]:
    """Vérifie la compatibilité de chaque rôle avec le contenu de la colonne.

    Retourne le dictionnaire complet : les rôles fournis s'appliquent par-dessus les rôles
    déjà confirmés (`current`), à défaut par-dessus les suggestions.
    Lève `InvalidRolesError` avec le détail par colonne si un rôle est incompatible.
    """
    profiles = {c.name: c for c in report.columns}
    errors: dict[str, str] = {}

    for col, role in roles.items():
        if col not in profiles:
            errors[col] = "Colonne inconnue."
            continue
        if role not in VALID_ROLES:
            errors[col] = f"Rôle « {role} » inconnu."
            continue
        prof = profiles[col]
        if role in {"numeric", "measure"} and prof.semantic_type != "numeric":
            share = prof.numeric_parse_share or 0.0
            if share < _MIN_SHARE:
                errors[col] = (
                    f"Seulement {share:.0%} des valeurs sont numériques : rôle "
                    f"« {ROLE_LABELS[role]} » impossible sans nettoyage préalable."
                )
        if role == "datetime" and prof.semantic_type != "datetime":
            errors[col] = "Les valeurs ne sont pas interprétables comme des dates."
        if role == "target" and prof.n_unique < 2:
            errors[col] = "Une cible doit avoir au moins deux valeurs distinctes."

    merged: dict[str, ColumnRole] = {c.name: c.suggested_role for c in report.columns}
    if current:
        merged.update({k: v for k, v in current.items() if k in merged})
    merged.update({k: v for k, v in roles.items() if k not in errors})  # type: ignore[misc]

    n_targets = sum(1 for r in merged.values() if r == "target")
    if n_targets > 1:
        errors["__all__"] = f"{n_targets} colonnes ont le rôle « Cible » : une seule est permise."

    if errors:
        raise InvalidRolesError(
            "Certains rôles sont incompatibles avec les données.", details={"errors": errors}
        )
    return merged
