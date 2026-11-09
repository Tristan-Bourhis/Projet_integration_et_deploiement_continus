"""Insertion atomique : empreinte, transactions, agrégats dans le même commit."""

from dataclasses import asdict

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import OperationalError

from .domain import GROUPS, Transaction, totals
from .retry import FaultInjector, RetryPolicy, TransientFailure, retry

metadata = MetaData()
processed_files = Table(
    "processed_files",
    metadata,
    Column("sha256", String(64), primary_key=True),
    Column("source", String, nullable=False),
    Column("row_count", Integer, nullable=False),
    Column("processed_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)
transactions = Table(
    "transactions",
    metadata,
    Column("file_sha256", ForeignKey("processed_files.sha256"), primary_key=True),
    Column("row_number", Integer, primary_key=True),
    Column("datetime_transaction", DateTime(timezone=True), nullable=False),
    Column("iban_origine", String(34), nullable=False),
    Column("pays_source", String(2), nullable=False),
    Column("banque_source", String, nullable=False),
    Column("iban_destinataire", String(34), nullable=False),
    Column("pays_destinataire", String(2), nullable=False),
    Column("montant", BigInteger, nullable=False),
    Column("flagged", Boolean, nullable=False),
    CheckConstraint("montant > 0"),
)
aggregates = Table(
    "aggregates",
    metadata,
    Column("file_sha256", ForeignKey("processed_files.sha256"), primary_key=True),
    Column("group_name", String(32), primary_key=True),
    Column("group_key", String, primary_key=True),
    Column("total_cents", BigInteger, nullable=False),
)


class Database:
    def __init__(self, url: str):
        self.engine = create_engine(url, pool_pre_ping=True)
        if self.engine.dialect.name not in {"sqlite", "postgresql"}:
            raise ValueError("Seuls SQLite et PostgreSQL sont supportés")

    def initialize(self) -> None:
        metadata.create_all(self.engine)

    def processed(self, digest: str) -> bool:
        with self.engine.connect() as connection:
            return (
                connection.execute(
                    select(processed_files.c.sha256).where(processed_files.c.sha256 == digest)
                ).first()
                is not None
            )

    def insert(
        self,
        source: str,
        digest: str,
        rows: tuple[Transaction, ...],
        policy: RetryPolicy,
        faults: FaultInjector | None = None,
    ) -> bool:
        grouped = {group: totals(rows, group) for group in GROUPS}

        def operation():
            try:
                with self.engine.begin() as connection:
                    insert = (
                        pg_insert if self.engine.dialect.name == "postgresql" else sqlite_insert
                    )
                    claim = connection.execute(
                        insert(processed_files)
                        .values(
                            sha256=digest,
                            source=source,
                            row_count=len(rows),
                        )
                        .on_conflict_do_nothing(index_elements=["sha256"])
                        .returning(processed_files.c.sha256)
                    )
                    if claim.first() is None:
                        return False
                    connection.execute(
                        transactions.insert(),
                        [
                            {"file_sha256": digest, "row_number": number, **asdict(row)}
                            for number, row in enumerate(rows, start=1)
                        ],
                    )
                    if faults:
                        faults.trigger("insertion après écriture, avant commit")
                    connection.execute(
                        aggregates.insert(),
                        [
                            {
                                "file_sha256": digest,
                                "group_name": group,
                                "group_key": key,
                                "total_cents": value,
                            }
                            for group, values in grouped.items()
                            for key, value in values.items()
                        ],
                    )
                return True
            except OperationalError as exc:
                code = getattr(exc.orig, "sqlstate", None)
                transient = (
                    exc.connection_invalidated
                    or (
                        code
                        and (
                            code.startswith("08")
                            or code in {"40001", "40P01", "55P03", "57P01", "57P03"}
                        )
                    )
                    or "database is locked" in str(exc.orig).lower()
                )
                if transient:
                    raise TransientFailure(
                        f"base indisponible ({code or 'verrou/connexion'})"
                    ) from exc
                raise

        return retry(operation, policy, "insertion SQL")

    def report(self) -> dict:
        with self.engine.connect() as connection:
            result = {
                "files": connection.scalar(select(func.count()).select_from(processed_files)),
                "transactions": connection.scalar(select(func.count()).select_from(transactions)),
                "flagged": connection.scalar(
                    select(func.count())
                    .select_from(transactions)
                    .where(transactions.c.flagged.is_(True))
                ),
            }
            for group in GROUPS:
                query = (
                    select(aggregates.c.group_key, func.sum(aggregates.c.total_cents))
                    .where(aggregates.c.group_name == group)
                    .group_by(aggregates.c.group_key)
                )
                result[group] = {key: int(value) for key, value in connection.execute(query)}
            return result
