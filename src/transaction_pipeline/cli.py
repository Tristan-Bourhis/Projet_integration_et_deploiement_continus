import argparse
import json
import logging
import os
from pathlib import Path

from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy.exc import SQLAlchemyError

from .database import Database
from .generate import generate_files, write_files
from .pipeline import process
from .retry import FaultInjector, RetryPolicy, TransientFailure
from .storage import LocalStorage, S3Storage


def main() -> int:
    parser = argparse.ArgumentParser(description="Pipeline CSV → S3/local → SQL")
    parser.add_argument("command", choices=["generate", "init", "run", "process", "report"])
    parser.add_argument("--source", choices=["local", "s3"], default="local")
    parser.add_argument("--directory", type=Path, default=Path("data/input"))
    parser.add_argument(
        "--database-url", default=os.getenv("DATABASE_URL", "sqlite:///data/pipeline.db")
    )
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--retry-delay", type=float, default=1)
    parser.add_argument("--fail-db", type=int, default=0)
    parser.add_argument("--fail-s3", type=int, default=0)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    database = None
    try:
        policy = RetryPolicy(args.attempts, args.retry_delay)
        if args.fail_db < 0 or args.fail_s3 < 0:
            raise ValueError("Les nombres de pannes doivent être positifs")
        if args.command == "generate":
            write_files(args.directory)
            return 0
        if args.database_url == "sqlite:///data/pipeline.db":
            Path("data").mkdir(exist_ok=True)
        database = Database(args.database_url)
        database.initialize()
        if args.command == "report":
            print(json.dumps(database.report(), indent=2, ensure_ascii=False))
            return 0
        if args.source == "s3":
            storage = S3Storage(
                os.environ["S3_ENDPOINT_URL"],
                os.environ["S3_BUCKET"],
                os.environ["S3_ACCESS_KEY"],
                os.environ["S3_SECRET_KEY"],
                policy,
            )
            if args.command in {"run", "init"}:
                storage.ensure_bucket()
            if args.command == "init":
                return 0
            if args.command == "run":
                storage.upload(generate_files())
            # La simulation cible la récupération pour traitement, après l'upload.
            storage.faults = FaultInjector(args.fail_s3)
        else:
            if args.command == "run":
                write_files(args.directory)
            if not args.directory.is_dir():
                raise ValueError(f"Répertoire introuvable : {args.directory}")
            storage = LocalStorage(args.directory)
        stats = process(storage, database, policy, FaultInjector(args.fail_db))
        print(json.dumps({**stats, **database.report()}, indent=2, ensure_ascii=False))
        return 0
    except (
        ValueError,
        KeyError,
        OSError,
        TransientFailure,
        SQLAlchemyError,
        BotoCoreError,
        ClientError,
    ) as exc:
        # Ne pas imprimer les URLs, paramètres SQL ou identifiants issus des pilotes.
        message = (
            str(exc) if isinstance(exc, (ValueError, TransientFailure)) else type(exc).__name__
        )
        logging.error("Pipeline arrêtée : %s", message)
        return 1
    finally:
        if database:
            database.engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
