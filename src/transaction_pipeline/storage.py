"""Adaptateurs local et S3 ; les traitements ne connaissent pas le stockage."""

from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

import boto3
from botocore.config import Config
from botocore.exceptions import (
    ClientError,
    ConnectionClosedError,
    EndpointConnectionError,
    ReadTimeoutError,
)

from .retry import FaultInjector, RetryPolicy, TransientFailure, retry

T = TypeVar("T")


class LocalStorage:
    def __init__(self, directory: Path):
        self.directory = directory

    def keys(self) -> list[str]:
        return sorted(path.name for path in self.directory.glob("*.csv"))

    def read(self, key: str) -> bytes:
        return (self.directory / key).read_bytes()


class S3Storage:
    def __init__(
        self,
        endpoint: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        policy: RetryPolicy,
        faults: FaultInjector | None = None,
    ):
        self.bucket = bucket
        self.policy = policy
        self.faults = faults
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="us-east-1",
            config=Config(
                signature_version="s3v4",
                connect_timeout=5,
                read_timeout=10,
                retries={"total_max_attempts": 1},
                s3={"addressing_style": "path"},
            ),
        )

    def _call(self, operation: Callable[[], T], label: str) -> T:
        def attempt():
            try:
                return operation()
            except (EndpointConnectionError, ConnectionClosedError, ReadTimeoutError) as exc:
                raise TransientFailure(type(exc).__name__) from exc
            except ClientError as exc:
                status = exc.response["ResponseMetadata"]["HTTPStatusCode"]
                code = exc.response["Error"]["Code"]
                if status >= 500 or status in (408, 429) or code in {"SlowDown", "RequestTimeout"}:
                    raise TransientFailure(f"S3 HTTP {status} ({code})") from exc
                raise

        return retry(attempt, self.policy, label)

    def ensure_bucket(self) -> None:
        def operation():
            try:
                self.client.head_bucket(Bucket=self.bucket)
            except ClientError as exc:
                if exc.response["ResponseMetadata"]["HTTPStatusCode"] != 404:
                    raise
                try:
                    self.client.create_bucket(Bucket=self.bucket)
                except ClientError as creation:
                    if creation.response["Error"]["Code"] != "BucketAlreadyOwnedByYou":
                        raise

        self._call(operation, "création du bucket")

    def upload(self, files: dict[str, bytes]) -> None:
        for key, content in files.items():
            self._call(
                lambda k=key, c=content: self.client.put_object(
                    Bucket=self.bucket, Key=k, Body=c, ContentType="text/csv"
                ),
                "upload S3",
            )
            uploaded = self.read(key)
            if uploaded != content:
                raise ValueError(f"Vérification de l'upload échouée : {key}")

    def keys(self) -> list[str]:
        def operation():
            paginator = self.client.get_paginator("list_objects_v2")
            return sorted(
                obj["Key"]
                for page in paginator.paginate(Bucket=self.bucket)
                for obj in page.get("Contents", [])
                if obj["Key"].endswith(".csv")
            )

        return self._call(operation, "liste S3")

    def read(self, key: str) -> bytes:
        def operation():
            if self.faults:
                self.faults.trigger("lecture S3")
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            with response["Body"] as stream:
                return stream.read()

        return self._call(operation, f"lecture S3 {key}")
