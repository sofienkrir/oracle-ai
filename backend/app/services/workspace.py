"""Copies de travail en mémoire.

Politique de conservation (documentée dans docs/architecture.md) :
- le DataFrame importé vit uniquement en mémoire du processus backend ;
- au plus `workspace_max_datasets` copies (éviction LRU) pendant `workspace_ttl_minutes` ;
- rien n'est écrit sur disque : après un redémarrage ou une expiration, seules les
  métadonnées restent dans SQLite et il faut réimporter le fichier.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from app.data.schemas import QualityReport


@dataclass
class WorkspaceEntry:
    df: pd.DataFrame
    report: QualityReport
    parse_info: dict[str, Any]
    transformations: list[dict[str, Any]]
    last_access: float = field(default_factory=time.monotonic)


class WorkspaceStore:
    def __init__(
        self,
        max_items: int,
        ttl_seconds: float,
        on_evict: Callable[[str], None] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._items: OrderedDict[str, WorkspaceEntry] = OrderedDict()
        self._max = max_items
        self._ttl = ttl_seconds
        self._on_evict = on_evict
        self._clock = clock
        self._lock = threading.Lock()

    def put(self, key: str, entry: WorkspaceEntry) -> None:
        with self._lock:
            entry.last_access = self._clock()
            self._items[key] = entry
            self._items.move_to_end(key)
            evicted = self._purge_locked()
        self._notify(evicted)

    def get(self, key: str) -> WorkspaceEntry | None:
        with self._lock:
            evicted = self._purge_locked()
            entry = self._items.get(key)
            if entry is not None:
                entry.last_access = self._clock()
                self._items.move_to_end(key)
        self._notify(evicted)
        return entry

    def remove(self, key: str) -> bool:
        with self._lock:
            found = self._items.pop(key, None) is not None
        if found:
            self._notify([key])
        return found

    def __contains__(self, key: str) -> bool:
        return key in self.keys()

    def keys(self) -> list[str]:
        with self._lock:
            evicted = self._purge_locked()
            keys = list(self._items)
        self._notify(evicted)
        return keys

    def _purge_locked(self) -> list[str]:
        now = self._clock()
        evicted = [k for k, e in self._items.items() if now - e.last_access > self._ttl]
        for k in evicted:
            del self._items[k]
        while len(self._items) > self._max:
            k, _ = self._items.popitem(last=False)
            evicted.append(k)
        return evicted

    def _notify(self, keys: list[str]) -> None:
        if self._on_evict:
            for k in keys:
                self._on_evict(k)
