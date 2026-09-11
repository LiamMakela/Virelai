import { useEffect, useState } from "react";

type RealtimeMetrics = {
  scope: string;

  active_viewers: number;

  events_per_second_10s: number;

  buffer_events_last_60s: number;

  playback_errors_last_60s: number;
};

type LivePlaybackEvent = {
  event_id: string;

  session_id: string;
  video_id: string;

  sequence_number: number;

  event_time: string;
  event_type: string;

  playback_position_ms?: number;

  buffer_duration_ms?: number;

  quality_height?: number;
  bitrate_kbps?: number;

  error_code?: string;

  metadata?: Record<string, unknown>;
};

type ConnectionState = "connecting" | "connected" | "reconnecting";

const MAX_EVENTS = 50;

function formatTime(timestamp: string) {
  return new Date(timestamp).toLocaleTimeString();
}

function formatPosition(milliseconds?: number) {
  if (milliseconds === undefined) {
    return "—";
  }

  const seconds = Math.floor(milliseconds / 1000);

  const minutes = Math.floor(seconds / 60);

  const remainingSeconds = seconds % 60;

  return `${minutes}:` + remainingSeconds.toString().padStart(2, "0");
}

export function OperationsDashboard() {
  const [metrics, setMetrics] = useState<RealtimeMetrics | null>(null);

  const [events, setEvents] = useState<LivePlaybackEvent[]>([]);

  const [connectionState, setConnectionState] =
    useState<ConnectionState>("connecting");

  useEffect(() => {
    const source = new EventSource(
      "http://localhost:8000/analytics/realtime/stream",
    );

    const handleOpen = () => {
      setConnectionState("connected");
    };

    const handleMetrics = (event: MessageEvent) => {
      const nextMetrics: RealtimeMetrics = JSON.parse(event.data);

      setMetrics(nextMetrics);
    };

    const handlePlaybackEvent = (event: MessageEvent) => {
      const playbackEvent: LivePlaybackEvent = JSON.parse(event.data);

      setEvents((current) => [playbackEvent, ...current].slice(0, MAX_EVENTS));
    };

    const handleError = () => {
      //
      // EventSource automatically attempts
      // to reconnect after a failure.
      //
      setConnectionState("reconnecting");
    };

    source.addEventListener("open", handleOpen);

    source.addEventListener("metrics", handleMetrics);

    source.addEventListener("playback_event", handlePlaybackEvent);

    source.addEventListener("error", handleError);

    return () => {
      source.close();
    };
  }, []);

  return (
    <section
      style={{
        marginTop: "48px",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div>
          <h2>Platform Operations</h2>

          <p>Live Virelai playback telemetry</p>
        </div>

        <strong>{connectionState}</strong>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: "16px",
          marginTop: "24px",
          marginBottom: "32px",
        }}
      >
        <MetricCard
          label="Active viewers"
          value={metrics ? metrics.active_viewers : "—"}
        />

        <MetricCard
          label="Events / sec"
          value={metrics ? metrics.events_per_second_10s.toFixed(2) : "—"}
        />

        <MetricCard
          label="Buffer events / 60s"
          value={metrics ? metrics.buffer_events_last_60s : "—"}
        />

        <MetricCard
          label="Errors / 60s"
          value={metrics ? metrics.playback_errors_last_60s : "—"}
        />
      </div>

      <div
        style={{
          border: "1px solid currentColor",
          borderRadius: "8px",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            padding: "16px 20px",
            borderBottom: "1px solid currentColor",
          }}
        >
          <strong>Live Events</strong>
        </div>

        <div
          style={{
            maxHeight: "500px",
            overflowY: "auto",
          }}
        >
          {events.length === 0 ? (
            <p
              style={{
                padding: "20px",
              }}
            >
              Waiting for playback activity...
            </p>
          ) : (
            <table
              style={{
                width: "100%",
                borderCollapse: "collapse",
              }}
            >
              <thead>
                <tr>
                  <th style={headerStyle}>Time</th>

                  <th style={headerStyle}>Event</th>

                  <th style={headerStyle}>Position</th>

                  <th style={headerStyle}>Quality</th>

                  <th style={headerStyle}>Session</th>
                </tr>
              </thead>

              <tbody>
                {events.map((event) => (
                  <tr key={event.event_id}>
                    <td style={cellStyle}>{formatTime(event.event_time)}</td>

                    <td style={cellStyle}>{event.event_type}</td>

                    <td style={cellStyle}>
                      {formatPosition(event.playback_position_ms)}
                    </td>

                    <td style={cellStyle}>
                      {event.quality_height ? `${event.quality_height}p` : "—"}
                    </td>

                    <td style={cellStyle}>
                      <code>{event.session_id.slice(0, 8)}</code>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </section>
  );
}

function MetricCard({
  label,
  value,
}: {
  label: string;
  value: string | number;
}) {
  return (
    <div
      style={{
        padding: "20px",
        border: "1px solid currentColor",
        borderRadius: "8px",
      }}
    >
      <div
        style={{
          fontSize: "14px",
          marginBottom: "8px",
        }}
      >
        {label}
      </div>

      <strong
        style={{
          fontSize: "28px",
        }}
      >
        {value}
      </strong>
    </div>
  );
}

const headerStyle = {
  textAlign: "left" as const,
  padding: "12px 16px",
  borderBottom: "1px solid currentColor",
};

const cellStyle = {
  padding: "10px 16px",
  borderBottom: "1px solid currentColor",
};
