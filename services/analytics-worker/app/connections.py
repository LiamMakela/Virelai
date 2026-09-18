import os

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