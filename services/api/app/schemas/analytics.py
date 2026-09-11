from datetime import datetime

from pydantic import BaseModel


class EventTypeCount(BaseModel):
    event_type: str
    count: int


class QualityCount(BaseModel):
    quality_height: int
    count: int


class VideoAnalyticsSummary(BaseModel):
    views: int

    completed_sessions: int
    completion_rate: float

    active_sessions: int

    observed_watch_seconds: int

    buffer_events: int
    total_buffer_ms: int

    p50_buffer_ms: float | None
    p95_buffer_ms: float | None

    playback_errors: int

    events_by_type: list[EventTypeCount]
    quality_distribution: list[QualityCount]


class AnalyticsTimelinePoint(BaseModel):
    bucket: datetime
    events: int
    playback_starts: int
    buffering_events: int
    playback_errors: int

class RealtimeMetrics(BaseModel):
    scope: str

    active_viewers: int

    events_per_second_10s: float

    buffer_events_last_60s: int

    playback_errors_last_60s: int