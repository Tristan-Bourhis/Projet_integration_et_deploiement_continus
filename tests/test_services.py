"""Tests isolés : bucket et schéma PostgreSQL uniques, nettoyés en sortie."""

import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, text

from transaction_pipeline.database import Database
from transaction_pipeline.generate import DE, FR, GB, generate_files
from transaction_pipeline.pipeline import process
from transaction_pipeline.retry import FaultInjector, RetryPolicy, TransientFailure
from transaction_pipeline.storage import S3Storage

pytestmark = [
    pytest.mark.services,
    pytest.mark.skipif(
        os.getenv("RUN_SERVICE_TESTS") != "1",
        reason="Activer via make integration",
    ),
]


@pytest.fixture
def services():
    identifier = "test_" + uuid.uuid4().hex
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{identifier}"'))
    db = Database(os.environ["DATABASE_URL"])
    db.engine.dispose()
    db.engine = create_engine(
        os.environ["DATABASE_URL"],
        connect_args={
            "options": f"-csearch_path={identifier}",
        },
    )
    db.initialize()
    storage = S3Storage(
        os.environ["S3_ENDPOINT_URL"],
        identifier.replace("_", "-"),
        os.environ["S3_ACCESS_KEY"],
        os.environ["S3_SECRET_KEY"],
        RetryPolicy(5, 0.1),
    )
    try:
        storage.ensure_bucket()
        yield storage, db
    finally:
        for key in storage.keys():
            storage.client.delete_object(Bucket=storage.bucket, Key=key)
        storage.client.delete_bucket(Bucket=storage.bucket)
        db.engine.dispose()
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{identifier}" CASCADE'))
        engine.dispose()


def test_s3_postgres_end_to_end_with_retries(services):
    storage, db = services
    storage.upload(generate_files())
    assert len(storage.keys()) == 2
    storage.faults = FaultInjector(2)
    assert process(storage, db, RetryPolicy(3, 0), FaultInjector(2))["inserted"] == 2
    storage.upload({"copy.csv": next(iter(generate_files().values()))})
    assert process(storage, db, RetryPolicy())["skipped"] == 3
    assert db.report() == {
        "files": 2,
        "transactions": 12,
        "flagged": 4,
        "iban_origine": {FR: 1060060, DE: 1000004, GB: 1240000},
        "banque_source": {"Banque Alpha": 1060060, "Banque Beta": 1000004, "Banque Gamma": 1240000},
        "iban_destinataire": {DE: 60060, GB: 1000002, FR: 2240002},
    }


def test_s3_exhaustion_does_not_insert(services):
    storage, db = services
    storage.upload(generate_files())
    storage.faults = FaultInjector(5)
    with pytest.raises(TransientFailure):
        process(storage, db, RetryPolicy(3, 0))
    assert db.report()["transactions"] == 0


def test_postgres_rollback_and_concurrent_deduplication(services):
    storage, db = services
    storage.upload(generate_files())
    with pytest.raises(TransientFailure):
        process(storage, db, RetryPolicy(2, 0), FaultInjector(2))
    assert db.report()["files"] == 0
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: process(storage, db, RetryPolicy()), range(2)))
    assert sum(result["inserted"] for result in results) == 2
    assert db.report()["transactions"] == 12
