"""S3 / MinIO pre-signed URL helper - spec Part 6.5.

Browsers upload/download directly to object storage; files never stream through
Flask. Works against MinIO locally (S3_ENDPOINT_URL set) and real S3 in prod.
"""
import uuid

import boto3
from botocore.config import Config as BotoConfig
from flask import current_app


def _client():
    cfg = current_app.config
    return boto3.client(
        "s3",
        endpoint_url=cfg.get("S3_ENDPOINT_URL"),
        region_name=cfg.get("S3_REGION"),
        aws_access_key_id=cfg.get("S3_ACCESS_KEY"),
        aws_secret_access_key=cfg.get("S3_SECRET_KEY"),
        config=BotoConfig(signature_version="s3v4"),
    )


def presign_upload(filename, content_type):
    cfg = current_app.config
    key = f"uploads/{uuid.uuid4().hex}/{filename}"
    url = _client().generate_presigned_url(
        "put_object",
        Params={"Bucket": cfg["S3_BUCKET"], "Key": key, "ContentType": content_type},
        ExpiresIn=cfg["S3_PRESIGN_EXPIRY"],
    )
    return {"upload_url": url, "key": key, "public_path": key}


def presign_download(key):
    cfg = current_app.config
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": cfg["S3_BUCKET"], "Key": key},
        ExpiresIn=cfg["S3_PRESIGN_EXPIRY"],
    )
