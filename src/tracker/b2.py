"""Sync the SQLite file with a private Backblaze B2 bucket (S3 API). Credentials from env."""
from __future__ import annotations
import os
import boto3
from botocore.exceptions import ClientError

OBJ = "price-tracker/tracker.db"


def _s3():
    ep = os.environ["B2_ENDPOINT"]
    if not ep.startswith("http"):
        ep = "https://" + ep
    return boto3.client("s3", endpoint_url=ep, aws_access_key_id=os.environ["B2_KEY_ID"],
                        aws_secret_access_key=os.environ["B2_APPLICATION_KEY"])


def pull(path: str) -> bool:
    try:
        _s3().download_file(os.environ["B2_BUCKET"], OBJ, path)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
            return False
        raise


def push(path: str):
    _s3().upload_file(path, os.environ["B2_BUCKET"], OBJ)
