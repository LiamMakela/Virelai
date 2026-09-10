import json
import logging
import mimetypes
import os
import subprocess
import tempfile
import uuid
from pathlib import Path

import boto3
import psycopg

from confluent_kafka import Consumer
from pydantic import BaseModel, ValidationError


logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s "
        "%(levelname)s "
        "%(name)s "
        "%(message)s"
    ),
)

logger = logging.getLogger("virelai.transcoder")


DATABASE_URL = os.environ["DATABASE_URL"]

KAFKA_BOOTSTRAP_SERVERS = os.environ[
    "KAFKA_BOOTSTRAP_SERVERS"
]

KAFKA_TOPIC_VIDEO_UPLOADED = os.environ.get(
    "KAFKA_TOPIC_VIDEO_UPLOADED",
    "video.uploaded.v1",
)

S3_ENDPOINT_URL = os.environ["S3_ENDPOINT_URL"]
S3_ACCESS_KEY = os.environ["S3_ACCESS_KEY"]
S3_SECRET_KEY = os.environ["S3_SECRET_KEY"]
S3_REGION = os.environ.get(
    "S3_REGION",
    "us-east-1",
)

S3_BUCKET_MEDIA = os.environ.get(
    "S3_BUCKET_MEDIA",
    "virelai-media",
)


s3 = boto3.client(
    "s3",
    endpoint_url=S3_ENDPOINT_URL,
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY,
    region_name=S3_REGION,
)


class SourceObject(BaseModel):
    bucket: str
    key: str


class VideoUploadedEvent(BaseModel):
    event_id: uuid.UUID
    event_version: int
    event_type: str

    video_id: uuid.UUID

    source: SourceObject


def inspect_video(
    input_path: Path,
) -> dict:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,codec_name,avg_frame_rate",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(input_path),
    ]

    result = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )

    data = json.loads(result.stdout)

    if not data.get("streams"):
        raise RuntimeError(
            "Uploaded file does not contain a video stream"
        )

    stream = data["streams"][0]

    return {
        "width": int(stream["width"]),
        "height": int(stream["height"]),
        "codec": stream.get("codec_name"),
        "frame_rate": stream.get(
            "avg_frame_rate",
            "30/1",
        ),
        "duration_seconds": float(
            data["format"]["duration"]
        ),
    }


def parse_frame_rate(value: str) -> float:
    try:
        numerator, denominator = value.split("/")

        denominator_float = float(denominator)

        if denominator_float == 0:
            return 30.0

        return (
            float(numerator)
            / denominator_float
        )

    except (ValueError, ZeroDivisionError):
        return 30.0


def create_thumbnail(
    input_path: Path,
    thumbnail_path: Path,
    duration_seconds: float,
) -> None:
    seek_time = min(
        1.0,
        max(
            0.0,
            duration_seconds / 2,
        ),
    )

    command = [
        "ffmpeg",
        "-y",
        "-ss",
        str(seek_time),
        "-i",
        str(input_path),
        "-frames:v",
        "1",
        "-vf",
        "scale=640:-2",
        str(thumbnail_path),
    ]

    subprocess.run(
        command,
        check=True,
    )


def create_hls(
    input_path: Path,
    output_directory: Path,
    metadata: dict,
) -> None:
    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    frame_rate = parse_frame_rate(
        metadata["frame_rate"]
    )

    # Target a keyframe about every 4 seconds,
    # matching our HLS segment duration.
    gop_size = max(
        1,
        round(frame_rate * 4),
    )

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),

        "-map",
        "0:v:0",

        # Audio is optional.
        "-map",
        "0:a:0?",

        "-c:v",
        "libx264",

        "-preset",
        "veryfast",

        "-crf",
        "23",

        "-pix_fmt",
        "yuv420p",

        "-flags",
        "+cgop",

        "-g",
        str(gop_size),

        "-sc_threshold",
        "0",
    ]

    # For this first version, cap output at 720p
    # but never upscale smaller videos.
    if metadata["height"] > 720:
        command.extend(
            [
                "-vf",
                "scale=-2:720",
            ]
        )

    command.extend(
        [
            "-c:a",
            "aac",

            "-b:a",
            "128k",

            "-f",
            "hls",

            "-hls_time",
            "4",

            "-hls_playlist_type",
            "vod",

            "-hls_segment_filename",
            str(
                output_directory
                / "segment_%03d.ts"
            ),

            str(
                output_directory
                / "playlist.m3u8"
            ),
        ]
    )

    subprocess.run(
        command,
        check=True,
    )


def content_type_for_file(
    path: Path,
) -> str:
    if path.suffix == ".m3u8":
        return "application/vnd.apple.mpegurl"

    if path.suffix == ".ts":
        return "video/mp2t"

    if path.suffix in {
        ".jpg",
        ".jpeg",
    }:
        return "image/jpeg"

    guessed, _ = mimetypes.guess_type(
        path.name
    )

    return (
        guessed
        or "application/octet-stream"
    )


def upload_generated_media(
    video_id: uuid.UUID,
    hls_directory: Path,
    thumbnail_path: Path,
) -> None:
    hls_prefix = (
        f"videos/{video_id}/hls"
    )

    for file_path in sorted(
        hls_directory.iterdir()
    ):
        if not file_path.is_file():
            continue

        object_key = (
            f"{hls_prefix}/{file_path.name}"
        )

        logger.info(
            "uploading media object %s",
            object_key,
        )

        s3.upload_file(
            str(file_path),
            S3_BUCKET_MEDIA,
            object_key,
            ExtraArgs={
                "ContentType": (
                    content_type_for_file(
                        file_path
                    )
                )
            },
        )

    thumbnail_key = (
        f"videos/{video_id}/"
        "thumbnail.jpg"
    )

    s3.upload_file(
        str(thumbnail_path),
        S3_BUCKET_MEDIA,
        thumbnail_key,
        ExtraArgs={
            "ContentType": "image/jpeg",
        },
    )


def get_video_status(
    video_id: uuid.UUID,
) -> str | None:
    with psycopg.connect(
        DATABASE_URL
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT status::text
                FROM videos
                WHERE id = %s
                """,
                (video_id,),
            )

            row = cursor.fetchone()

            if row is None:
                return None

            return row[0]


def mark_processing(
    video_id: uuid.UUID,
) -> None:
    with psycopg.connect(
        DATABASE_URL
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE videos
                SET
                    status = 'processing',
                    updated_at = NOW()
                WHERE id = %s
                """,
                (video_id,),
            )

        connection.commit()


def mark_ready(
    video_id: uuid.UUID,
) -> None:
    with psycopg.connect(
        DATABASE_URL
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE videos
                SET
                    status = 'ready',
                    updated_at = NOW()
                WHERE id = %s
                """,
                (video_id,),
            )

        connection.commit()


def mark_failed(
    video_id: uuid.UUID,
) -> None:
    with psycopg.connect(
        DATABASE_URL
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE videos
                SET
                    status = 'failed',
                    updated_at = NOW()
                WHERE id = %s
                """,
                (video_id,),
            )

        connection.commit()


def process_video(
    event: VideoUploadedEvent,
) -> None:
    video_id = event.video_id

    logger.info(
        "processing video=%s event=%s",
        video_id,
        event.event_id,
    )

    status = get_video_status(
        video_id
    )

    if status is None:
        raise RuntimeError(
            f"Video {video_id} does not exist"
        )

    # Basic idempotency.
    #
    # If Kafka redelivers an already-successful event,
    # do not transcode the video again.
    if status == "ready":
        logger.info(
            "video=%s already ready; skipping",
            video_id,
        )

        return

    mark_processing(
        video_id
    )

    try:
        with tempfile.TemporaryDirectory(
            prefix="virelai-"
        ) as temporary_directory:
            work_directory = Path(
                temporary_directory
            )

            source_path = (
                work_directory
                / "source"
            )

            hls_directory = (
                work_directory
                / "hls"
            )

            thumbnail_path = (
                work_directory
                / "thumbnail.jpg"
            )

            logger.info(
                "downloading "
                "s3://%s/%s",
                event.source.bucket,
                event.source.key,
            )

            s3.download_file(
                event.source.bucket,
                event.source.key,
                str(source_path),
            )

            metadata = inspect_video(
                source_path
            )

            logger.info(
                "video=%s "
                "resolution=%sx%s "
                "codec=%s "
                "duration=%.2fs",
                video_id,
                metadata["width"],
                metadata["height"],
                metadata["codec"],
                metadata[
                    "duration_seconds"
                ],
            )

            create_thumbnail(
                source_path,
                thumbnail_path,
                metadata[
                    "duration_seconds"
                ],
            )

            create_hls(
                source_path,
                hls_directory,
                metadata,
            )

            upload_generated_media(
                video_id,
                hls_directory,
                thumbnail_path,
            )

        mark_ready(
            video_id
        )

        logger.info(
            "video=%s transcode complete",
            video_id,
        )

    except Exception:
        mark_failed(
            video_id
        )

        raise


def main() -> None:
    consumer = Consumer(
        {
            "bootstrap.servers": (
                KAFKA_BOOTSTRAP_SERVERS
            ),

            "group.id": (
                "virelai-transcoders"
            ),

            "enable.auto.commit": False,

            "auto.offset.reset": (
                "earliest"
            ),
        }
    )

    consumer.subscribe(
        [
            KAFKA_TOPIC_VIDEO_UPLOADED
        ]
    )

    logger.info(
        "transcoder started topic=%s",
        KAFKA_TOPIC_VIDEO_UPLOADED,
    )

    try:
        while True:
            message = consumer.poll(
                timeout=1.0
            )

            if message is None:
                continue

            if message.error():
                logger.error(
                    "Kafka consumer error: %s",
                    message.error(),
                )

                continue

            try:
                event = (
                    VideoUploadedEvent
                    .model_validate_json(
                        message.value()
                    )
                )

                if (
                    event.event_version != 1
                    or event.event_type
                    != "video.uploaded"
                ):
                    raise ValueError(
                        "Unsupported event contract"
                    )

                process_video(
                    event
                )

                consumer.commit(
                    message=message,
                    asynchronous=False,
                )

            except ValidationError:
                logger.exception(
                    "invalid Kafka event"
                )

                # For now consume poison messages.
                # Later they go to a DLQ.
                consumer.commit(
                    message=message,
                    asynchronous=False,
                )

            except Exception:
                logger.exception(
                    "transcode failed"
                )

                # First iteration:
                # mark FAILED and consume the job.
                #
                # Later:
                # retries + backoff + DLQ.
                consumer.commit(
                    message=message,
                    asynchronous=False,
                )

    finally:
        consumer.close()


if __name__ == "__main__":
    main()