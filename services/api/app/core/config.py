from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = (
        "postgresql+psycopg://virelai:virelai@postgres:5432/virelai"
    )

    s3_endpoint_url: str = "http://minio:9000"
    s3_public_endpoint_url: str = "http://localhost:9000"

    s3_access_key: str = "virelai"
    s3_secret_key: str = "virelai-dev-password"
    s3_region: str = "us-east-1"

    s3_bucket_originals: str = "virelai-originals"
    
    s3_bucket_media: str = "virelai-media"

    kafka_bootstrap_servers: str = "kafka:19092"
    kafka_topic_video_uploaded: str = "video.uploaded.v1"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()