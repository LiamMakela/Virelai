import { useEffect, useRef } from "react";
import Hls from "hls.js";

import { TelemetryBatcher } from "../services/telemetry";

type VideoPlayerProps = {
  src: string;
  videoId: string;
  sessionId: string;
};

export function VideoPlayer({ src, videoId, sessionId }: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);

  useEffect(() => {
    const video = videoRef.current;

    if (!video) {
      return;
    }

    const telemetry = new TelemetryBatcher(sessionId, videoId);

    let hls: Hls | null = null;

    let started = false;

    let bufferingStartedAt: number | null = null;

    const position = () => Math.max(0, Math.round(video.currentTime * 1000));

    const handlePlaying = () => {
      if (!started) {
        started = true;

        telemetry.emit("playback_started", {
          playback_position_ms: position(),
        });
      } else {
        telemetry.emit("resume", {
          playback_position_ms: position(),
        });
      }

      if (bufferingStartedAt !== null) {
        telemetry.emit("buffer_ended", {
          playback_position_ms: position(),

          buffer_duration_ms: Math.round(
            performance.now() - bufferingStartedAt,
          ),
        });

        bufferingStartedAt = null;
      }
    };

    const handlePause = () => {
      // Browsers fire pause when playback
      // naturally reaches the end too.
      if (video.ended) {
        return;
      }

      // Don't report a pause before playback
      // has actually started.
      if (!started) {
        return;
      }

      telemetry.emit("pause", {
        playback_position_ms: position(),
      });
    };

    const handleWaiting = () => {
      if (!started) {
        return;
      }

      if (bufferingStartedAt !== null) {
        return;
      }

      bufferingStartedAt = performance.now();

      telemetry.emit("buffer_started", {
        playback_position_ms: position(),
      });
    };

    const handleEnded = () => {
      telemetry.emit("playback_ended", {
        playback_position_ms: position(),
      });

      void telemetry.flush();
    };

    video.addEventListener("playing", handlePlaying);

    video.addEventListener("pause", handlePause);

    video.addEventListener("waiting", handleWaiting);

    video.addEventListener("ended", handleEnded);

    const heartbeatTimer = window.setInterval(() => {
      if (started && !video.paused && !video.ended) {
        telemetry.emit("heartbeat", {
          playback_position_ms: position(),
        });
      }
    }, 10000);

    if (Hls.isSupported()) {
      hls = new Hls();

      hls.loadSource(src);
      hls.attachMedia(video);

      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        console.log(
          "HLS manifest loaded",
          hls?.levels.map((level) => ({
            width: level.width,
            height: level.height,
            bitrate: level.bitrate,
          })),
        );
      });

      hls.on(Hls.Events.LEVEL_SWITCHED, (_, data) => {
        const level = hls?.levels[data.level];

        if (!level) {
          return;
        }

        console.log(`Switched to ${level.height}p`);

        telemetry.emit("quality_changed", {
          playback_position_ms: position(),

          quality_height: level.height,

          bitrate_kbps: Math.round(level.bitrate / 1000),
        });
      });

      hls.on(Hls.Events.ERROR, (_, data) => {
        console.error("HLS error", data);

        telemetry.emit("playback_error", {
          playback_position_ms: position(),

          error_code: data.details,

          metadata: {
            type: data.type,
            fatal: data.fatal,
          },
        });
      });
    } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
      // Safari and some other browsers
      // support HLS natively.
      video.src = src;
    } else {
      console.error("This browser does not support HLS playback");

      telemetry.emit("playback_error", {
        error_code: "hls_not_supported",
      });
    }

    return () => {
      window.clearInterval(heartbeatTimer);

      video.removeEventListener("playing", handlePlaying);

      video.removeEventListener("pause", handlePause);

      video.removeEventListener("waiting", handleWaiting);

      video.removeEventListener("ended", handleEnded);

      telemetry.destroy();

      hls?.destroy();
    };
  }, [src, videoId, sessionId]);

  return (
    <video
      ref={videoRef}
      controls
      style={{
        width: "100%",
        maxWidth: "1000px",
        background: "#000",
      }}
    />
  );
}
