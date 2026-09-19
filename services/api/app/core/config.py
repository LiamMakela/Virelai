from sqlalchemy.engine import URL
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    #
    # Local Docker Compose fallback.
    #
    database_url: str = (
        "postgresql+psycopg://virelai:virelai@postgres:5432/virelai"
    )

    #
    # AWS / component-based database configuration.
    #
    db_host: str | None = None
    db_port: int = 5432
    db_name: str = "virelai"
    db_user: str | None = None
    db_password: str | None = None

    #
    # Local MinIO defaults.
    #
    s3_endpoint_url: str = "http://minio:9000"
    s3_public_endpoint_url: str = "http://localhost:9000"

    s3_access_key: str = "virelai"
    s3_secret_key: str = "virelai-dev-password"

    #
    # AWS sets this to true so boto3 uses the
    # ECS task-role credential provider.
    #
    s3_use_default_credentials: bool = False

    s3_region: str = "us-east-1"

    s3_bucket_originals: str = "virelai-originals"
    s3_bucket_media: str = "virelai-media"

    kafka_bootstrap_servers: str = "kafka:19092"
    kafka_topic_video_uploaded: str = "video.uploaded.v1"

    redis_url: str = "redis://redis:6379/0"
    redis_host: str | None = None
    redis_port: int = 6379
    redis_password: str | None = None
    redis_tls: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    media_public_base_url: str = (
        "http://localhost:9000/virelai-media"
    )

    @property
    def effective_database_url(self) -> str:
        #
        # When DB_HOST is supplied, assume we're running
        # against component-based cloud configuration.
        #
        if self.db_host:
            if not self.db_user:
                raise ValueError(
                    "DB_USER must be set when DB_HOST is set"
                )

            if self.db_password is None:
                raise ValueError(
                    "DB_PASSWORD must be set when DB_HOST is set"
                )

            return URL.create(
                drivername="postgresql+psycopg",
                username=self.db_user,
                password=self.db_password,
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
            ).render_as_string(
                hide_password=False,
            )

        return self.database_url


settings = Settings()