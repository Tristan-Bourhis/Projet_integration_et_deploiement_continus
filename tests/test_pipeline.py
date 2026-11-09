import hashlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError

import pytest
from sqlalchemy import func, select

from transaction_pipeline.csv_io import load_csv
from transaction_pipeline.database import Database, aggregates, processed_files, transactions
from transaction_pipeline.domain import flag_transactions, totals
from transaction_pipeline.generate import DE, FR, GB, generate_files
from transaction_pipeline.pipeline import process
from transaction_pipeline.retry import FaultInjector, RetryPolicy, TransientFailure, retry

POLICY = RetryPolicy(3, 0)


class MemoryStorage:
    def __init__(self, files=None):
        self.files = generate_files() if files is None else files

    def keys(self):
        return sorted(self.files)

    def read(self, key):
        return self.files[key]


@pytest.fixture
def database(tmp_path):
    db = Database(f"sqlite:///{tmp_path / 'test.db'}")
    db.initialize()
    yield db
    db.engine.dispose()


def test_deterministic_generation_and_exact_totals():
    assert generate_files() == generate_files()
    batches = [load_csv(content) for content in generate_files().values()]
    assert [len(batch) for batch in batches] == [6, 6]
    rows = sum(batches, ())
    assert totals(rows, "iban_origine") == {FR: 1060060, DE: 1000004, GB: 1240000}
    assert totals(rows, "banque_source") == {
        "Banque Alpha": 1060060,
        "Banque Beta": 1000004,
        "Banque Gamma": 1240000,
    }
    assert totals(rows, "iban_destinataire") == {DE: 60060, GB: 1000002, FR: 2240002}


def test_flags_boundary_and_purity():
    rows = load_csv(next(iter(generate_files().values())))
    before = rows[:]
    flagged = flag_transactions(rows)
    assert rows == before
    assert all(not row.flagged for row in rows)
    assert [row.flagged for row in flagged] == [False, False, True, True, False, False]
    assert flag_transactions(rows) == flagged
    totals(rows, "iban_origine")
    assert rows == before
    with pytest.raises(FrozenInstanceError):
        rows[0].montant = 0


@pytest.mark.parametrize("value", ["-1", "0", "NaN", "Infinity", "1.001", "bonjour", "1e99999"])
def test_invalid_amounts(value):
    content = next(iter(generate_files().values())).replace(b"100.10", value.encode())
    with pytest.raises(ValueError, match="ligne 2"):
        load_csv(content)


@pytest.mark.parametrize(
    "old,new",
    [
        (b"iban_origine", b"iban_inconnu"),
        (FR.encode(), b"FR0000000000000000000000000"),
        (b"2026-09-01T10:00:00+00:00", b"2026-09-01T10:00:00"),
        (b"2026-09-01T10:00:00+00:00", b"2026-02-30T10:00:00+00:00"),
        (b"Banque Alpha", b""),
        (b",FR,", b",DE,"),
    ],
)
def test_invalid_csv(old, new):
    content = next(iter(generate_files().values())).replace(old, new)
    with pytest.raises(ValueError):
        load_csv(content)


def test_empty_csv():
    with pytest.raises(ValueError, match="vide"):
        load_csv(next(iter(generate_files().values())).splitlines()[0])


def test_full_pipeline_and_renamed_file(database):
    storage = MemoryStorage()
    assert process(storage, database, POLICY) == {"inserted": 2, "skipped": 0}
    assert process(storage, database, POLICY) == {"inserted": 0, "skipped": 2}
    storage.files["renamed.csv"] = next(iter(storage.files.values()))
    assert process(storage, database, POLICY) == {"inserted": 0, "skipped": 3}
    report = database.report()
    assert (report["files"], report["transactions"], report["flagged"]) == (2, 12, 4)
    assert report["iban_origine"] == {FR: 1060060, DE: 1000004, GB: 1240000}
    assert report["iban_destinataire"] == {DE: 60060, GB: 1000002, FR: 2240002}
    assert report["banque_source"] == {
        "Banque Alpha": 1060060,
        "Banque Beta": 1000004,
        "Banque Gamma": 1240000,
    }
    with database.engine.connect() as connection:
        rows = connection.execute(select(transactions)).mappings().all()
    assert sum(row["montant"] for row in rows) == 3300064
    assert all(row["flagged"] == (row["montant"] > 500000) for row in rows)


def test_sql_retry_rolls_back_and_never_duplicates(database):
    assert process(MemoryStorage(), database, POLICY, FaultInjector(2))["inserted"] == 2
    assert database.report()["transactions"] == 12
    assert database.report()["files"] == 2


def test_exhaustion_rolls_back_all_tables(database):
    with pytest.raises(TransientFailure):
        process(MemoryStorage(), database, POLICY, FaultInjector(3))
    with database.engine.connect() as connection:
        for table in (processed_files, transactions, aggregates):
            assert connection.scalar(select(func.count()).select_from(table)) == 0
    assert process(MemoryStorage(), database, POLICY)["inserted"] == 2


def test_invalid_file_is_not_marked_processed(database):
    with pytest.raises(ValueError):
        process(MemoryStorage({"bad.csv": b"bad\n"}), database, POLICY)
    assert database.report()["files"] == 0


def test_concurrent_claim_is_atomic(database):
    content = next(iter(generate_files().values()))
    digest = hashlib.sha256(content).hexdigest()
    rows = flag_transactions(load_csv(content))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda _: database.insert("same.csv", digest, rows, POLICY), range(2))
        )
    assert sorted(results) == [False, True]
    assert database.report()["transactions"] == 6


def test_retry_waits_with_bounded_exponential_delays():
    waits = []
    faults = FaultInjector(3)
    with pytest.raises(TransientFailure):
        retry(lambda: faults.trigger("test"), RetryPolicy(3, 0.5), "test", waits.append)
    assert waits == [0.5, 1.0]
    with pytest.raises(ValueError):
        RetryPolicy(0)


def test_permanent_error_is_not_retried():
    calls = []

    def fail():
        calls.append(1)
        raise ValueError("permanent")

    with pytest.raises(ValueError):
        retry(fail, POLICY, "test")
    assert calls == [1]
