import io

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from botocore.response import StreamingBody
from botocore.stub import Stubber

from transaction_pipeline.retry import FaultInjector, RetryPolicy, TransientFailure
from transaction_pipeline.storage import S3Storage


@pytest.fixture
def storage():
    return S3Storage("http://localhost:8333", "transactions", "test", "test", RetryPolicy(3, 0))


def test_s3_recovers_from_http_503(storage):
    with Stubber(storage.client) as stub:
        stub.add_client_error(
            "get_object", service_error_code="ServiceUnavailable", http_status_code=503
        )
        stub.add_response("get_object", {"Body": StreamingBody(io.BytesIO(b"csv"), 3)})
        assert storage.read("test.csv") == b"csv"
        stub.assert_no_pending_responses()


def test_s3_access_denied_fails_immediately(storage):
    with Stubber(storage.client) as stub:
        stub.add_client_error("get_object", service_error_code="AccessDenied", http_status_code=403)
        with pytest.raises(ClientError):
            storage.read("test.csv")
        stub.assert_no_pending_responses()


def test_s3_network_exhaustion(storage, monkeypatch):
    calls = []

    def fail(**kwargs):
        calls.append(1)
        raise EndpointConnectionError(endpoint_url="http://localhost:8333")

    monkeypatch.setattr(storage.client, "get_object", fail)
    with pytest.raises(TransientFailure):
        storage.read("test.csv")
    assert len(calls) == 3


def test_s3_injected_faults(storage):
    storage.faults = FaultInjector(2)
    with Stubber(storage.client) as stub:
        stub.add_response("get_object", {"Body": StreamingBody(io.BytesIO(b"csv"), 3)})
        assert storage.read("test.csv") == b"csv"


def test_s3_pagination(storage):
    with Stubber(storage.client) as stub:
        stub.add_response(
            "list_objects_v2",
            {
                "IsTruncated": True,
                "NextContinuationToken": "next",
                "Contents": [{"Key": "a.csv"}, {"Key": "ignored.txt"}],
            },
            {"Bucket": "transactions"},
        )
        stub.add_response(
            "list_objects_v2",
            {
                "IsTruncated": False,
                "Contents": [{"Key": "b.csv"}],
            },
            {"Bucket": "transactions", "ContinuationToken": "next"},
        )
        assert storage.keys() == ["a.csv", "b.csv"]
