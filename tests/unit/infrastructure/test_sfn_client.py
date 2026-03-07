from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

_JOB_ID = "550e8400-e29b-41d4-a716-446655440000"
_ARN = "arn:aws:states:us-east-1:123456789012:stateMachine:scrappy-ScrapingStateMachine"


def _make_client(arn: str = _ARN) -> object:
    """Import SfnStarterClient with STATE_MACHINE_ARN set in env."""
    import importlib
    import os

    os.environ["STATE_MACHINE_ARN"] = arn
    os.environ.setdefault("AWS_REGION", "us-east-1")

    import app.infrastructure.aws.sfn_client as mod

    importlib.reload(mod)
    return mod.SfnStarterClient


# ---------------------------------------------------------------------------
# start_execution — happy path
# ---------------------------------------------------------------------------


def test_start_execution_calls_boto3_with_correct_args() -> None:
    SfnStarterClient = _make_client()
    mock_boto_client = MagicMock()

    with patch("boto3.client", return_value=mock_boto_client):
        client = SfnStarterClient()
        client.start_execution(_JOB_ID)

    mock_boto_client.start_execution.assert_called_once_with(
        stateMachineArn=_ARN,
        name=f"scraping-{_JOB_ID}",
        input=json.dumps({"job_id": _JOB_ID}),
    )


def test_start_execution_name_is_prefixed_with_scraping() -> None:
    SfnStarterClient = _make_client()
    mock_boto_client = MagicMock()

    with patch("boto3.client", return_value=mock_boto_client):
        client = SfnStarterClient()
        client.start_execution(_JOB_ID)

    call_kwargs = mock_boto_client.start_execution.call_args.kwargs
    assert call_kwargs["name"] == f"scraping-{_JOB_ID}"


def test_start_execution_input_is_json_with_job_id() -> None:
    SfnStarterClient = _make_client()
    mock_boto_client = MagicMock()

    with patch("boto3.client", return_value=mock_boto_client):
        client = SfnStarterClient()
        client.start_execution(_JOB_ID)

    call_kwargs = mock_boto_client.start_execution.call_args.kwargs
    parsed = json.loads(call_kwargs["input"])
    assert parsed == {"job_id": _JOB_ID}


def test_boto3_client_created_with_stepfunctions_service() -> None:
    SfnStarterClient = _make_client()
    mock_boto_client = MagicMock()
    with patch("boto3.client", return_value=mock_boto_client) as mock_boto:
        client = SfnStarterClient()
        client.start_execution(_JOB_ID)  # trigger lazy init

    mock_boto.assert_called_once()
    assert mock_boto.call_args.args[0] == "stepfunctions"


# ---------------------------------------------------------------------------
# start_execution — error propagation
# ---------------------------------------------------------------------------


def test_start_execution_propagates_boto3_client_error() -> None:
    from botocore.exceptions import ClientError

    SfnStarterClient = _make_client()
    mock_boto_client = MagicMock()
    mock_boto_client.start_execution.side_effect = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "no perms"}},
        "StartExecution",
    )

    with patch("boto3.client", return_value=mock_boto_client):
        client = SfnStarterClient()
        with pytest.raises(ClientError):
            client.start_execution(_JOB_ID)
