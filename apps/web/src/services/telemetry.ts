export type PlaybackEventType =
  | "play_requested"
  | "playback_started"
  | "pause"
  | "resume"
  | "buffer_started"
  | "buffer_ended"
  | "quality_changed"
  | "heartbeat"
  | "seek"
  | "playback_ended"
  | "playback_error";

export type PlaybackEvent = {
  event_id: string;

  session_id: string;
  video_id: string;

  sequence_number: number;

  event_time: string;
  event_type: PlaybackEventType;

  playback_position_ms?: number;

  buffer_duration_ms?: number;

  bitrate_kbps?: number;
  quality_height?: number;

  error_code?: string;

  metadata?: Record<string, unknown>;

  startup_time_ms?: number;

  watch_delta_ms?: number;

  seek_from_ms?: number;
  seek_to_ms?: number;  
};

type PlaybackEventData = Partial<
  Pick<
    PlaybackEvent,
    | "playback_position_ms"
    | "buffer_duration_ms"
    | "bitrate_kbps"
    | "quality_height"
    | "error_code"
    | "metadata"
    | "startup_time_ms"
    | "watch_delta_ms"
    | "seek_from_ms"
    | "seek_to_ms"
  >
>;

export class TelemetryBatcher {
  private queue: PlaybackEvent[] = [];

  private sequenceNumber = 0;

  private flushTimer: number | null = null;

  private isFlushing = false;

  constructor(
    private readonly sessionId: string,
    private readonly videoId: string,
  ) {
    this.flushTimer = window.setInterval(() => {
      void this.flush();
    }, 5000);
  }

  emit(
    eventType: PlaybackEventType,
    data: PlaybackEventData = {},
  ) {
    this.sequenceNumber += 1;

    const event: PlaybackEvent = {
      event_id: crypto.randomUUID(),

      session_id: this.sessionId,
      video_id: this.videoId,

      sequence_number: this.sequenceNumber,

      event_time: new Date().toISOString(),

      event_type: eventType,

      ...data,
    };

    this.queue.push(event);

    if (this.queue.length >= 10) {
      void this.flush();
    }
  }

  async flush() {
    if (
      this.queue.length === 0 ||
      this.isFlushing
    ) {
      return;
    }

    this.isFlushing = true;

    const events = this.queue.splice(
      0,
      this.queue.length,
    );

    try {
      const response = await fetch(
        "http://localhost:8001/events/batch",
        {
          method: "POST",

          headers: {
            "Content-Type": "application/json",
          },

          body: JSON.stringify({
            events,
          }),

          keepalive: true,
        },
      );

      if (!response.ok) {
        throw new Error(
          `Telemetry ingestion returned ${response.status}`,
        );
      }
    } catch (error) {
      console.error(
        "Unable to send telemetry",
        error,
      );

      // Restore the events in their original order.
      this.queue.unshift(...events);
    } finally {
      this.isFlushing = false;
    }
  }

  destroy() {
    if (this.flushTimer !== null) {
      window.clearInterval(
        this.flushTimer,
      );

      this.flushTimer = null;
    }

    void this.flush();
  }
}