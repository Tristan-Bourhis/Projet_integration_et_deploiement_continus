"""Chargement strict du CSV, indépendant des traitements."""

import csv
import io
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from .domain import Transaction

FIELDS = (
    "datetime_transaction",
    "iban_origine",
    "pays_source",
    "banque_source",
    "iban_destinataire",
    "pays_destinataire",
    "montant",
)
IBAN_LENGTHS = {"FR": 27, "DE": 22, "GB": 22, "ES": 24, "IT": 27, "BE": 16, "NL": 18}


def valid_iban(value: str, country: str) -> bool:
    if country not in IBAN_LENGTHS or len(value) != IBAN_LENGTHS[country]:
        return False
    if not value.startswith(country) or not re.fullmatch(r"[A-Z]{2}[0-9]{2}[A-Z0-9]+", value):
        return False
    rearranged = value[4:] + value[:4]
    digits = "".join(str(ord(c) - 55) if c.isalpha() else c for c in rearranged)
    return int(digits) % 97 == 1


def load_csv(content: bytes) -> tuple[Transaction, ...]:
    try:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")), strict=True)
        if reader.fieldnames != list(FIELDS):
            raise ValueError(f"Colonnes attendues : {', '.join(FIELDS)}")
        result = []
        for line, row in enumerate(reader, start=2):
            try:
                if None in row or any(v is None or not v.strip() for v in row.values()):
                    raise ValueError("champ vide ou nombre de colonnes incorrect")
                row = {k: v.strip() for k, v in row.items()}
                for iban, country in (
                    ("iban_origine", "pays_source"),
                    ("iban_destinataire", "pays_destinataire"),
                ):
                    if not valid_iban(row[iban], row[country]):
                        raise ValueError(f"{iban} invalide ou incohérent avec {country}")
                try:
                    amount = Decimal(row["montant"])
                except InvalidOperation as exc:
                    raise ValueError("montant non numérique") from exc
                if (
                    not amount.is_finite()
                    or amount <= 0
                    or amount > Decimal("999999999999")
                    or amount * 100 != (amount * 100).to_integral_value()
                ):
                    raise ValueError("montant positif, fini et à deux décimales maximum requis")
                date = datetime.fromisoformat(row["datetime_transaction"])
                if date.tzinfo is None:
                    raise ValueError("la date doit inclure un fuseau horaire")
                result.append(
                    Transaction(
                        date,
                        row["iban_origine"],
                        row["pays_source"],
                        row["banque_source"],
                        row["iban_destinataire"],
                        row["pays_destinataire"],
                        int(amount * 100),
                    )
                )
            except (ValueError, InvalidOperation) as exc:
                raise ValueError(f"CSV ligne {line} : {exc}") from exc
        if not result:
            raise ValueError("CSV vide : aucune transaction")
        return tuple(result)
    except (UnicodeError, csv.Error) as exc:
        raise ValueError(f"CSV illisible : {exc}") from exc
