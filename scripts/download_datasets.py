"""Télécharge les jeux UCI officiels dans `datasets/raw/` (jamais commités).

Usage (depuis la racine du dépôt) :
    uv run --project backend python scripts/download_datasets.py

Les URL suivent le schéma de téléchargement des pages UCI listées dans datasets/README.md.
Elles n'ont pas pu être testées depuis l'environnement de développement initial (réseau
restreint) : en cas d'échec, téléchargez manuellement depuis les pages officielles et
placez les fichiers dans datasets/raw/.
"""

from __future__ import annotations

import hashlib
import sys
import urllib.request
import zipfile
from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "datasets" / "raw"

SOURCES = {
    "online_retail": "https://archive.ics.uci.edu/static/public/352/online+retail.zip",
    "ai4i_2020": (
        "https://archive.ics.uci.edu/static/public/601/"
        "ai4i+2020+predictive+maintenance+dataset.zip"
    ),
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    ok = True
    for name, url in SOURCES.items():
        archive = RAW / f"{name}.zip"
        try:
            print(f"→ {name} : {url}")
            urllib.request.urlretrieve(url, archive)  # noqa: S310 (URL fixe, HTTPS)
            with zipfile.ZipFile(archive) as zf:
                for member in zf.namelist():
                    target = (RAW / member).resolve()
                    if RAW.resolve() not in target.parents:
                        raise ValueError(f"chemin suspect dans l'archive : {member}")
                zf.extractall(RAW)
                for member in zf.namelist():
                    p = RAW / member
                    if p.is_file():
                        print(f"   {member}  sha256={sha256(p)}")
        except Exception as exc:  # message lisible, on continue avec l'autre jeu
            ok = False
            print(f"   ÉCHEC : {exc}. Téléchargez manuellement depuis la page UCI.", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
