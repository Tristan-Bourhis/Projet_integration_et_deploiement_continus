"""Retry borné des seules pannes transitoires."""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class TransientFailure(RuntimeError):
    pass


@dataclass(frozen=True)
class RetryPolicy:
    attempts: int = 4
    delay: float = 1.0

    def __post_init__(self):
        if self.attempts < 1 or self.delay < 0:
            raise ValueError("attempts >= 1 et delay >= 0 requis")


def retry[T](
    operation: Callable[[], T],
    policy: RetryPolicy,
    label: str,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    for attempt in range(1, policy.attempts + 1):
        try:
            return operation()
        except TransientFailure as exc:
            logger.warning("%s : échec tentative %s/%s : %s", label, attempt, policy.attempts, exc)
            if attempt == policy.attempts:
                raise
            sleep(policy.delay * 2 ** (attempt - 1))
    raise AssertionError("unreachable")


@dataclass
class FaultInjector:
    """Injection explicite de pannes, désactivée par défaut."""

    remaining: int = 0

    def trigger(self, label: str) -> None:
        if self.remaining > 0:
            self.remaining -= 1
            raise TransientFailure(f"panne temporaire simulée ({label})")
