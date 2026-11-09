"""Modèles immuables et traitements purs ; montants exprimés en centimes."""

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Literal


@dataclass(frozen=True)
class Transaction:
    datetime_transaction: datetime
    iban_origine: str
    pays_source: str
    banque_source: str
    iban_destinataire: str
    pays_destinataire: str
    montant: int
    flagged: bool = False


Group = Literal["iban_origine", "banque_source", "iban_destinataire"]
GROUPS: tuple[Group, ...] = ("iban_origine", "banque_source", "iban_destinataire")


def totals(transactions: tuple[Transaction, ...], group: Group) -> dict[str, int]:
    if group not in GROUPS:
        raise ValueError(f"Regroupement inconnu : {group}")
    result: dict[str, int] = {}
    for transaction in transactions:
        key = getattr(transaction, group)
        result[key] = result.get(key, 0) + transaction.montant
    return result


def flag_transactions(transactions: tuple[Transaction, ...]) -> tuple[Transaction, ...]:
    return tuple(replace(t, flagged=t.montant >= 500_000) for t in transactions)
