from __future__ import annotations

import json
import os
from typing import Any

import boto3


class SfnStarterClient:
    def __init__(self) -> None:
        self._state_machine_arn = os.environ.get("STATE_MACHINE_ARN", "")
        self._region = os.environ.get("AWS_REGION", "us-east-1")
        self._boto_client: Any = None

    def _client(self) -> Any:
        if self._boto_client is None:
            self._boto_client = boto3.client("stepfunctions", region_name=self._region)
        return self._boto_client

    def start_execution(self, job_id: str) -> None:
        self._client().start_execution(
            stateMachineArn=self._state_machine_arn,
            name=f"scraping-{job_id}",
            input=json.dumps({"job_id": job_id}),
        )
