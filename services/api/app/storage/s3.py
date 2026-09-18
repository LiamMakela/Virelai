import boto3

from botocore.config import Config

from app.core.config import settings


def _client(endpoint_url: str):
    kwargs = {
        "service_name": "s3",
        "endpoint_url": endpoint_url,
        "region_name": settings.s3_region,
        "config": Config(
            signature_version="s3v4",
            s3={
                "addressing_style": "path",
            },
        ),
    }

    #
    # Local development uses explicit MinIO credentials.
    #
    # AWS leaves credentials unspecified so boto3 obtains
    # temporary credentials from the ECS task role.
    #
    if not settings.s3_use_default_credentials:
        kwargs["aws_access_key_id"] = (
            settings.s3_access_key
        )

        kwargs["aws_secret_access_key"] = (
            settings.s3_secret_key
        )

    return boto3.client(**kwargs)


_internal_client = _client(
    settings.s3_endpoint_url
)


_public_signing_client = _client(
    settings.s3_public_endpoint_url
)


def create_multipart_upload(
    object_key: str,
    content_type: str,
) -> str:
    response = _internal_client.create_multipart_upload(
        Bucket=settings.s3_bucket_originals,
        Key=object_key,
        ContentType=content_type,
    )

    return response["UploadId"]


def generate_upload_part_url(
    object_key: str,
    multipart_upload_id: str,
    part_number: int,
    expires_in: int = 3600,
) -> str:
    return _public_signing_client.generate_presigned_url(
        ClientMethod="upload_part",
        Params={
            "Bucket": settings.s3_bucket_originals,
            "Key": object_key,
            "UploadId": multipart_upload_id,
            "PartNumber": part_number,
        },
        ExpiresIn=expires_in,
        HttpMethod="PUT",
    )


def complete_multipart_upload(
    object_key: str,
    multipart_upload_id: str,
    parts: list[dict],
) -> None:
    _internal_client.complete_multipart_upload(
        Bucket=settings.s3_bucket_originals,
        Key=object_key,
        UploadId=multipart_upload_id,
        MultipartUpload={
            "Parts": parts,
        },
    )


def abort_multipart_upload(
    object_key: str,
    multipart_upload_id: str,
) -> None:
    _internal_client.abort_multipart_upload(
        Bucket=settings.s3_bucket_originals,
        Key=object_key,
        UploadId=multipart_upload_id,
    )


def get_object_size(
    object_key: str,
) -> int:
    response = _internal_client.head_object(
        Bucket=settings.s3_bucket_originals,
        Key=object_key,
    )

    return response["ContentLength"]


def generate_media_download_url(
    object_key: str,
    expires_in: int = 3600,
) -> str:
    return _public_signing_client.generate_presigned_url(
        ClientMethod="get_object",
        Params={
            "Bucket": settings.s3_bucket_media,
            "Key": object_key,
        },
        ExpiresIn=expires_in,
        HttpMethod="GET",
    )


def media_public_url(
    object_key: str,
) -> str:
    return (
        f"{settings.s3_public_endpoint_url}/"
        f"{settings.s3_bucket_media}/"
        f"{object_key}"
    )