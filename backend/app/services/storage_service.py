import boto3
from botocore.client import Config

from app.config import settings

_s3_client = None


def get_s3_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
            config=Config(signature_version="s3v4"),
        )
        try:
            _s3_client.head_bucket(Bucket=settings.S3_BUCKET)
        except Exception:
            _s3_client.create_bucket(Bucket=settings.S3_BUCKET)
    return _s3_client


def build_s3_key(tenant_id: str, doc_id: str, filename: str) -> str:
    return f"{tenant_id}/{doc_id}/{filename}"


def validate_s3_key(tenant_id: str, s3_key: str) -> None:
    if not s3_key.startswith(f"{tenant_id}/"):
        raise ValueError("Key does not belong to this tenant")


async def upload_to_s3(s3_key: str, content: bytes) -> None:
    client = get_s3_client()
    client.put_object(Bucket=settings.S3_BUCKET, Key=s3_key, Body=content)


def download_from_s3(s3_key: str) -> bytes:
    client = get_s3_client()
    response = client.get_object(Bucket=settings.S3_BUCKET, Key=s3_key)
    return response["Body"].read()


def delete_from_s3(s3_key: str) -> None:
    if not s3_key:
        return
    client = get_s3_client()
    client.delete_object(Bucket=settings.S3_BUCKET, Key=s3_key)


def generate_presigned_url(tenant_id: str, s3_key: str, expires_in: int = 3600) -> str:
    validate_s3_key(tenant_id, s3_key)
    client = get_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET, "Key": s3_key},
        ExpiresIn=expires_in,
    )
