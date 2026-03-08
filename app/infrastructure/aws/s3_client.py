from __future__ import annotations

import os
from abc import ABC, abstractmethod

import boto3


class IS3Client(ABC):
    @abstractmethod
    def get_object_bytes(self, key: str) -> bytes: ...


class S3Client(IS3Client):
    def __init__(self) -> None:
        self._bucket = os.environ.get("RESULTS_BUCKET", "")

    def get_object_bytes(self, key: str) -> bytes:
        client = boto3.client("s3")
        response = client.get_object(Bucket=self._bucket, Key=key)
        return response["Body"].read()  # type: ignore[no-any-return]
