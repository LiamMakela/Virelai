import time
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import redis_client
from app.models.video import Video
from app.schemas.analytics import (
    AnalyticsTimelinePoint,
    EventTypeCount,
    QualityCount,
    RealtimeMetrics,
    VideoAnalyticsSummary,
)


ACTIVE_SESSION_TTL_SECONDS = 30


class VideoNotFoundError(Exception):
    pass


# ---------------------------------------------------------
# Realtime analytics
# ---------------------------------------------------------


async def _get_realtime_metrics(
    *,
    scope: str,
    active_key: str,
    events_key: str,
    buffers_key: str,
    errors_key: str,
) -> RealtimeMetrics:
    now = time.time()

    active_cutoff = (
        now
        - ACTIVE_SESSION_TTL_SECONDS
    )

    async with redis_client.pipeline(
        transaction=False
    ) as pipe:

        #
        # Remove sessions that disappeared without
        # ever sending pause/end.
        #
        pipe.zremrangebyscore(
            active_key,
            "-inf",
            active_cutoff,
        )

        pipe.zcard(
            active_key
        )

        pipe.zcount(
            events_key,
            now - 10,
            "+inf",
        )

        pipe.zcount(
            buffers_key,
            now - 60,
            "+inf",
        )

        pipe.zcount(
            errors_key,
            now - 60,
            "+inf",
        )

        results = await pipe.execute()

    active_viewers = int(
        results[1]
    )

    events_last_10_seconds = int(
        results[2]
    )

    buffer_events = int(
        results[3]
    )

    playback_errors = int(
        results[4]
    )

    return RealtimeMetrics(
        scope=scope,

        active_viewers=active_viewers,

        events_per_second_10s=round(
            events_last_10_seconds / 10,
            2,
        ),

        buffer_events_last_60s=(
            buffer_events
        ),

        playback_errors_last_60s=(
            playback_errors
        ),
    )


async def get_platform_realtime_metrics(
) -> RealtimeMetrics:
    return await _get_realtime_metrics(
        scope="platform",

        active_key=(
            "realtime:active_sessions"
        ),

        events_key=(
            "realtime:events"
        ),

        buffers_key=(
            "realtime:buffers"
        ),

        errors_key=(
            "realtime:errors"
        ),
    )


async def get_video_realtime_metrics(
    db: AsyncSession,
    video_id: uuid.UUID,
) -> RealtimeMetrics:
    video = await db.get(
        Video,
        video_id,
    )

    if video is None:
        raise VideoNotFoundError(
            f"Video {video_id} does not exist"
        )

    prefix = (
        f"video:{video_id}"
    )

    return await _get_realtime_metrics(
        scope=f"video:{video_id}",

        active_key=(
            f"{prefix}:active_sessions"
        ),

        events_key=(
            f"{prefix}:realtime:events"
        ),

        buffers_key=(
            f"{prefix}:realtime:buffers"
        ),

        errors_key=(
            f"{prefix}:realtime:errors"
        ),
    )


# ---------------------------------------------------------
# Historical video analytics
# ---------------------------------------------------------


async def get_video_analytics(
    db: AsyncSession,
    video_id: uuid.UUID,
) -> VideoAnalyticsSummary:
    video = await db.get(
        Video,
        video_id,
    )

    if video is None:
        raise VideoNotFoundError(
            f"Video {video_id} does not exist"
        )

    summary_result = await db.execute(
        text(
            """
            WITH started AS (
                SELECT DISTINCT session_id
                FROM playback_events
                WHERE
                    video_id = :video_id
                    AND event_type = 'playback_started'
            ),

            completed AS (
                SELECT DISTINCT session_id
                FROM playback_events
                WHERE
                    video_id = :video_id
                    AND event_type = 'playback_ended'
            ),

            latest_events AS (
                SELECT DISTINCT ON (session_id)
                    session_id,
                    event_time,
                    event_type
                FROM playback_events
                WHERE video_id = :video_id
                ORDER BY
                    session_id,
                    event_time DESC
            )

            SELECT
                (
                    SELECT COUNT(*)
                    FROM started
                ) AS views,

                (
                    SELECT COUNT(*)
                    FROM completed
                ) AS completed_sessions,

                (
                    SELECT COUNT(*)
                    FROM latest_events
                    WHERE
                        event_time
                            >= NOW() - INTERVAL '30 seconds'
                        AND event_type
                            <> 'playback_ended'
                ) AS active_sessions,

                (
                    SELECT COALESCE(
                        SUM(watch_delta_ms),
                        0
                    )
                    FROM playback_events
                    WHERE
                        video_id = :video_id
                        AND watch_delta_ms IS NOT NULL
                ) AS total_watch_ms,

                (
                    SELECT COUNT(*)
                    FROM playback_events
                    WHERE
                        video_id = :video_id
                        AND event_type = 'buffer_ended'
                ) AS buffer_events,

                (
                    SELECT COALESCE(
                        SUM(buffer_duration_ms),
                        0
                    )
                    FROM playback_events
                    WHERE
                        video_id = :video_id
                        AND event_type = 'buffer_ended'
                        AND buffer_duration_ms IS NOT NULL
                ) AS total_buffer_ms,

                (
                    SELECT percentile_cont(0.50)
                        WITHIN GROUP (
                            ORDER BY buffer_duration_ms
                        )
                    FROM playback_events
                    WHERE
                        video_id = :video_id
                        AND event_type = 'buffer_ended'
                        AND buffer_duration_ms IS NOT NULL
                ) AS p50_buffer_ms,

                (
                    SELECT percentile_cont(0.95)
                        WITHIN GROUP (
                            ORDER BY buffer_duration_ms
                        )
                    FROM playback_events
                    WHERE
                        video_id = :video_id
                        AND event_type = 'buffer_ended'
                        AND buffer_duration_ms IS NOT NULL
                ) AS p95_buffer_ms,

                (
                    SELECT percentile_cont(0.50)
                        WITHIN GROUP (
                            ORDER BY startup_time_ms
                        )
                    FROM playback_events
                    WHERE
                        video_id = :video_id
                        AND event_type = 'playback_started'
                        AND startup_time_ms IS NOT NULL
                ) AS p50_startup_ms,

                (
                    SELECT percentile_cont(0.95)
                        WITHIN GROUP (
                            ORDER BY startup_time_ms
                        )
                    FROM playback_events
                    WHERE
                        video_id = :video_id
                        AND event_type = 'playback_started'
                        AND startup_time_ms IS NOT NULL
                ) AS p95_startup_ms,

                (
                    SELECT percentile_cont(0.99)
                        WITHIN GROUP (
                            ORDER BY startup_time_ms
                        )
                    FROM playback_events
                    WHERE
                        video_id = :video_id
                        AND event_type = 'playback_started'
                        AND startup_time_ms IS NOT NULL
                ) AS p99_startup_ms,

                (
                    SELECT COUNT(*)
                    FROM playback_events
                    WHERE
                        video_id = :video_id
                        AND event_type = 'seek'
                ) AS seek_events,

                (
                    SELECT COUNT(*)
                    FROM playback_events
                    WHERE
                        video_id = :video_id
                        AND event_type = 'playback_error'
                ) AS playback_errors
            """
        ),
        {
            "video_id": video_id,
        },
    )

    row = summary_result.mappings().one()

    views = int(
        row["views"]
    )

    completed_sessions = int(
        row["completed_sessions"]
    )

    completion_rate = (
        completed_sessions / views
        if views > 0
        else 0.0
    )

    total_watch_ms = int(
        row["total_watch_ms"]
    )

    total_buffer_ms = int(
        row["total_buffer_ms"]
    )

    #
    # Rebuffer ratio:
    #
    # time spent buffering /
    # (time spent playing + buffering)
    #
    experience_ms = (
        total_watch_ms
        + total_buffer_ms
    )

    rebuffer_ratio = (
        total_buffer_ms
        / experience_ms
        if experience_ms > 0
        else 0.0
    )

    #
    # Count events grouped by type.
    #
    event_result = await db.execute(
        text(
            """
            SELECT
                event_type,
                COUNT(*) AS count
            FROM playback_events
            WHERE video_id = :video_id
            GROUP BY event_type
            ORDER BY count DESC, event_type
            """
        ),
        {
            "video_id": video_id,
        },
    )

    events_by_type = [
        EventTypeCount(
            event_type=item[
                "event_type"
            ],
            count=int(
                item["count"]
            ),
        )
        for item
        in event_result.mappings()
    ]

    #
    # Count observed HLS quality switches.
    #
    quality_result = await db.execute(
        text(
            """
            SELECT
                quality_height,
                COUNT(*) AS count
            FROM playback_events
            WHERE
                video_id = :video_id
                AND event_type = 'quality_changed'
                AND quality_height IS NOT NULL
            GROUP BY quality_height
            ORDER BY quality_height
            """
        ),
        {
            "video_id": video_id,
        },
    )

    quality_distribution = [
        QualityCount(
            quality_height=int(
                item[
                    "quality_height"
                ]
            ),
            count=int(
                item["count"]
            ),
        )
        for item
        in quality_result.mappings()
    ]

    return VideoAnalyticsSummary(
        views=views,

        completed_sessions=(
            completed_sessions
        ),

        completion_rate=round(
            completion_rate,
            4,
        ),

        active_sessions=int(
            row["active_sessions"]
        ),

        watch_time_seconds=round(
            total_watch_ms / 1000,
            2,
        ),

        buffer_events=int(
            row["buffer_events"]
        ),

        total_buffer_ms=(
            total_buffer_ms
        ),

        rebuffer_ratio=round(
            rebuffer_ratio,
            4,
        ),

        p50_buffer_ms=(
            float(
                row[
                    "p50_buffer_ms"
                ]
            )
            if row[
                "p50_buffer_ms"
            ]
            is not None
            else None
        ),

        p95_buffer_ms=(
            float(
                row[
                    "p95_buffer_ms"
                ]
            )
            if row[
                "p95_buffer_ms"
            ]
            is not None
            else None
        ),

        p50_startup_ms=(
            float(
                row[
                    "p50_startup_ms"
                ]
            )
            if row[
                "p50_startup_ms"
            ]
            is not None
            else None
        ),

        p95_startup_ms=(
            float(
                row[
                    "p95_startup_ms"
                ]
            )
            if row[
                "p95_startup_ms"
            ]
            is not None
            else None
        ),

        p99_startup_ms=(
            float(
                row[
                    "p99_startup_ms"
                ]
            )
            if row[
                "p99_startup_ms"
            ]
            is not None
            else None
        ),

        seek_events=int(
            row["seek_events"]
        ),

        playback_errors=int(
            row["playback_errors"]
        ),

        events_by_type=(
            events_by_type
        ),

        quality_distribution=(
            quality_distribution
        ),
    )


# ---------------------------------------------------------
# Timeline analytics
# ---------------------------------------------------------


async def get_video_timeline(
    db: AsyncSession,
    video_id: uuid.UUID,
    bucket: str,
) -> list[AnalyticsTimelinePoint]:
    video = await db.get(
        Video,
        video_id,
    )

    if video is None:
        raise VideoNotFoundError(
            f"Video {video_id} does not exist"
        )

    allowed_buckets = {
        "minute": "minute",
        "hour": "hour",
        "day": "day",
    }

    bucket_sql = (
        allowed_buckets.get(
            bucket
        )
    )

    if bucket_sql is None:
        raise ValueError(
            "bucket must be minute, hour, or day"
        )

    #
    # bucket_sql comes strictly from the
    # whitelist above, not directly from
    # arbitrary user input.
    #
    query = text(
        f"""
        SELECT
            date_trunc(
                '{bucket_sql}',
                event_time
            ) AS bucket,

            COUNT(*) AS events,

            COUNT(*) FILTER (
                WHERE event_type
                    = 'playback_started'
            ) AS playback_starts,

            COUNT(*) FILTER (
                WHERE event_type
                    = 'buffer_ended'
            ) AS buffering_events,

            COUNT(*) FILTER (
                WHERE event_type
                    = 'playback_error'
            ) AS playback_errors

        FROM playback_events

        WHERE video_id = :video_id

        GROUP BY 1
        ORDER BY 1
        """
    )

    result = await db.execute(
        query,
        {
            "video_id": video_id,
        },
    )

    return [
        AnalyticsTimelinePoint(
            bucket=row[
                "bucket"
            ],

            events=int(
                row["events"]
            ),

            playback_starts=int(
                row[
                    "playback_starts"
                ]
            ),

            buffering_events=int(
                row[
                    "buffering_events"
                ]
            ),

            playback_errors=int(
                row[
                    "playback_errors"
                ]
            ),
        )
        for row
        in result.mappings()
    ]