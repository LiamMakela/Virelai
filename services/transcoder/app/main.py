import json
import logging
import mimetypes
import os
import subprocess
import tempfile
import uuid
from pathlib import Path
import time

from prometheus_client import (
    Counter,
    Histogram,
    start_http_server,
)

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

RENDITION_LADDER = [
    {
        "name": "360p",
        "height": 360,
        "video_bitrate_kbps": 800,
        "audio_bitrate_kbps": 96,
    },
    {
        "name": "720p",
        "height": 720,
        "video_bitrate_kbps": 2800,
        "audio_bitrate_kbps": 128,
    },
    {
        "name": "1080p",
        "height": 1080,
        "video_bitrate_kbps": 5000,
        "audio_bitrate_kbps": 128,
    },
]

TRANSCODE_JOBS = Counter(
    "virelai_transcode_jobs_total",
    "Video transcoding jobs",
    [
        "result",
    ],
)


TRANSCODE_DURATION = Histogram(
    "virelai_transcode_duration_seconds",
    "Total video transcode job duration",
    buckets=(
        1,
        5,
        10,
        30,
        60,
        120,
        300,
        600,
        1200,
    ),
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
        "-show_entries",
        (
            "stream=index,codec_type,width,height,"
            "codec_name,avg_frame_rate"
        ),
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

    video_stream = next(
        (
            stream
            for stream in data.get("streams", [])
            if stream.get("codec_type") == "video"
        ),
        None,
    )

    if video_stream is None:
        raise RuntimeError(
            "Uploaded file does not contain a video stream"
        )

    audio_stream = next(
        (
            stream
            for stream in data.get("streams", [])
            if stream.get("codec_type") == "audio"
        ),
        None,
    )

    return {
        "width": int(video_stream["width"]),
        "height": int(video_stream["height"]),
        "codec": video_stream.get("codec_name"),
        "frame_rate": video_stream.get(
            "avg_frame_rate",
            "30/1",
        ),
        "duration_seconds": float(
            data["format"]["duration"]
        ),
        "has_audio": audio_stream is not None,
        "audio_codec": (
            audio_stream.get("codec_name")
            if audio_stream
            else None
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
    renditions: list[dict],
) -> None:
    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
    ]

    #
    # Map the source once for every output rendition.
    #
    # Output stream numbering becomes:
    #
    # v:0, a:0
    # v:1, a:1
    # v:2, a:2
    #
    for _ in renditions:
        command.extend(
            [
                "-map",
                "0:v:0",
            ]
        )

        if metadata["has_audio"]:
            command.extend(
                [
                    "-map",
                    "0:a:0",
                ]
            )

    command.extend(
        [
            "-c:v",
            "libx264",

            "-preset",
            "veryfast",

            "-pix_fmt",
            "yuv420p",

            "-flags",
            "+cgop",

            "-sc_threshold",
            "0",

            # Force aligned keyframes every ~4 seconds.
            "-force_key_frames",
            "expr:gte(t,n_forced*4)",
        ]
    )

    if metadata["has_audio"]:
        command.extend(
            [
                "-c:a",
                "aac",
            ]
        )

    #
    # Configure each video output separately.
    #
    for index, rendition in enumerate(
        renditions
    ):
        bitrate = rendition[
            "video_bitrate_kbps"
        ]

        maxrate = int(
            bitrate * 1.07
        )

        bufsize = int(
            bitrate * 1.5
        )

        command.extend(
            [
                f"-filter:v:{index}",
                (
                    f"scale=-2:"
                    f"{rendition['height']}"
                ),

                f"-b:v:{index}",
                f"{bitrate}k",

                f"-maxrate:v:{index}",
                f"{maxrate}k",

                f"-bufsize:v:{index}",
                f"{bufsize}k",
            ]
        )

        if metadata["has_audio"]:
            command.extend(
                [
                    f"-b:a:{index}",
                    (
                        f"{rendition['audio_bitrate_kbps']}k"
                    ),
                ]
            )

    #
    # Tell FFmpeg which output streams belong to
    # each HLS variant.
    #
    variant_entries = []

    for index, rendition in enumerate(
        renditions
    ):
        if metadata["has_audio"]:
            entry = (
                f"v:{index},"
                f"a:{index},"
                f"name:{rendition['name']}"
            )
        else:
            entry = (
                f"v:{index},"
                f"name:{rendition['name']}"
            )

        variant_entries.append(
            entry
        )

    variant_map = " ".join(
        variant_entries
    )

    command.extend(
        [
            "-f",
            "hls",

            "-hls_time",
            "4",

            "-hls_playlist_type",
            "vod",

            "-hls_flags",
            "independent_segments",

            "-var_stream_map",
            variant_map,

            "-master_pl_name",
            "master.m3u8",

            "-hls_segment_filename",
            str(
                output_directory
                / "%v"
                / "segment_%05d.ts"
            ),

            str(
                output_directory
                / "%v"
                / "playlist.m3u8"
            ),
        ]
    )

    logger.info(
        "running adaptive HLS transcode "
        "renditions=%s",
        [
            rendition["name"]
            for rendition in renditions
        ],
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
        hls_directory.rglob("*")
    ):
        if not file_path.is_file():
            continue

        relative_path = (
            file_path
            .relative_to(hls_directory)
            .as_posix()
        )

        object_key = (
            f"{hls_prefix}/{relative_path}"
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

def calculate_width(
    source_width: int,
    source_height: int,
    target_height: int,
) -> int:
    width = round(
        source_width
        * target_height
        / source_height
    )

    # H.264/YUV420 generally wants even dimensions.
    if width % 2 != 0:
        width += 1

    return width

def save_media_metadata(
    video_id: uuid.UUID,
    metadata: dict,
    renditions: list[dict],
) -> None:
    thumbnail_key = (
        f"videos/{video_id}/thumbnail.jpg"
    )

    master_playlist_key = (
        f"videos/{video_id}/hls/master.m3u8"
    )

    with psycopg.connect(
        DATABASE_URL
    ) as connection:
        with connection.cursor() as cursor:

            cursor.execute(
                """
                UPDATE videos
                SET
                    duration_ms = %s,
                    source_width = %s,
                    source_height = %s,
                    source_codec = %s,
                    thumbnail_key = %s,
                    master_playlist_key = %s,
                    status = 'ready',
                    updated_at = NOW()
                WHERE id = %s
                """,
                (
                    round(
                        metadata[
                            "duration_seconds"
                        ]
                        * 1000
                    ),
                    metadata["width"],
                    metadata["height"],
                    metadata["codec"],
                    thumbnail_key,
                    master_playlist_key,
                    video_id,
                ),
            )

            #
            # Makes processing idempotent if the same
            # video must be safely regenerated.
            #
            cursor.execute(
                """
                DELETE FROM renditions
                WHERE video_id = %s
                """,
                (video_id,),
            )

            for rendition in renditions:
                width = calculate_width(
                    source_width=metadata[
                        "width"
                    ],
                    source_height=metadata[
                        "height"
                    ],
                    target_height=rendition[
                        "height"
                    ],
                )

                cursor.execute(
                    """
                    INSERT INTO renditions (
                        id,
                        video_id,
                        name,
                        width,
                        height,
                        video_bitrate_kbps,
                        audio_bitrate_kbps,
                        video_codec,
                        audio_codec,
                        playlist_key
                    )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    )
                    """,
                    (
                        uuid.uuid4(),
                        video_id,
                        rendition["name"],
                        width,
                        rendition["height"],
                        rendition[
                            "video_bitrate_kbps"
                        ],
                        (
                            rendition[
                                "audio_bitrate_kbps"
                            ]
                            if metadata[
                                "has_audio"
                            ]
                            else None
                        ),
                        "h264",
                        (
                            "aac"
                            if metadata[
                                "has_audio"
                            ]
                            else None
                        ),
                        (
                            f"videos/{video_id}/"
                            f"hls/"
                            f"{rendition['name']}/"
                            "playlist.m3u8"
                        ),
                    ),
                )

        connection.commit()

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
    started = time.perf_counter()

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

            renditions = select_renditions(
                metadata["height"]
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
                renditions,
            )

            upload_generated_media(
                video_id,
                hls_directory,
                thumbnail_path,
            )


        save_media_metadata(
            video_id,
            metadata,
            renditions,
        )

        logger.info(
            "video=%s transcode complete",
            video_id,
        )

        TRANSCODE_JOBS.labels(
            result="success"
        ).inc()

    except Exception:
        mark_failed(
            video_id
        )

        TRANSCODE_JOBS.labels(
            result="failure"
        ).inc()


        raise

    finally:
        TRANSCODE_DURATION.observe(
            time.perf_counter()
            - started
        )

def select_renditions(
    source_height: int,
) -> list[dict]:
    selected = [
        rendition
        for rendition in RENDITION_LADDER
        if rendition["height"] <= source_height
    ]

    if selected:
        return selected

    # Handle unusually small source videos without
    # upscaling them to 360p.
    return [
        {
            "name": f"{source_height}p",
            "height": source_height,
            "video_bitrate_kbps": 500,
            "audio_bitrate_kbps": 96,
        }
    ]


def main() -> None:

    start_http_server(
        9102
    )

    logger.info(
        "Prometheus metrics listening on :9102"
    )
    
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