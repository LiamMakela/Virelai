import os

import boto3
import psycopg


def database_connection():
    database_url = os.environ.get(
        "DATABASE_URL"
    )

    if database_url:
        return psycopg.connect(
            database_url
        )

    return psycopg.connect(
        host=os.environ["DB_HOST"],
        port=int(
            os.environ.get(
                "DB_PORT",
                "5432",
            )
        ),
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
    )


def s3_client():
    endpoint_url = os.environ.get(
        "S3_ENDPOINT_URL"
    )

    region = os.environ.get(
        "S3_REGION",
        "us-east-1",
    )

    use_default_credentials = (
        os.environ.get(
            "S3_USE_DEFAULT_CREDENTIALS",
            "false",
        ).lower()
        in {
            "1",
            "true",
            "yes",
        }
    )

    kwargs = {
        "region_name": region,
    }

    if endpoint_url:
        kwargs["endpoint_url"] = (
            endpoint_url
        )

    if not use_default_credentials:
        kwargs["aws_access_key_id"] = (
            os.environ["S3_ACCESS_KEY"]
        )

        kwargs[
            "aws_secret_access_key"
        ] = os.environ[
            "S3_SECRET_KEY"
        ]

    return boto3.client(
        "s3",
        **kwargs,
    )