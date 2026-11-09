import hashlib
import logging
from typing import Protocol

from .csv_io import load_csv
from .database import Database
from .domain import flag_transactions
from .retry import FaultInjector, RetryPolicy

logger = logging.getLogger(__name__)


class Storage(Protocol):
    def keys(self) -> list[str]: ...
    def read(self, key: str) -> bytes: ...


def process(
    storage: Storage, database: Database, policy: RetryPolicy, faults: FaultInjector | None = None
) -> dict[str, int]:
    stats = {"inserted": 0, "skipped": 0}
    for key in storage.keys():
        content = storage.read(key)
        digest = hashlib.sha256(content).hexdigest()
        if database.processed(digest):
            logger.info("Déjà traité, ignoré : %s", key)
            stats["skipped"] += 1
            continue
        rows = flag_transactions(load_csv(content))
        inserted = database.insert(key, digest, rows, policy, faults)
        stats["inserted" if inserted else "skipped"] += 1
        logger.info("%s : %s (%s transactions)", key, "inséré" if inserted else "ignoré", len(rows))
    return stats
