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

    let firstPlayRequestedAt: number | null = null;

    let pausedByUser = false;

    let bufferingStartedAt: number | null = null;

    let watchSegmentStartedAt: number | null = null;

    let seekFromMs: number | null = null;

    let lastKnownPositionMs = 0;

    const position = () => Math.max(0, Math.round(video.currentTime * 1000));

    /*
     * Close an interval during which
     * the video was genuinely playing.
     *
     * restart=true is used by heartbeat:
     * account for the interval but
     * immediately begin another one.
     */
    const closeWatchSegment = (restart = false) => {
      if (watchSegmentStartedAt === null) {
        return undefined;
      }

      const now = performance.now();

      const delta = Math.max(0, Math.round(now - watchSegmentStartedAt));

      watchSegmentStartedAt = restart ? now : null;

      return delta;
    };

    const startWatchSegment = () => {
      if (watchSegmentStartedAt === null) {
        watchSegmentStartedAt = performance.now();
      }
    };

    const handlePlay = () => {
      if (!started && firstPlayRequestedAt === null) {
        firstPlayRequestedAt = performance.now();

        telemetry.emit("play_requested", {
          playback_position_ms: position(),
        });
      }
    };

    const handlePlaying = () => {
      /*
       * First actual frame/playback
       * after the user requested play.
       */
      if (!started) {
        started = true;

        const startupTime =
          firstPlayRequestedAt !== null
            ? Math.max(0, Math.round(performance.now() - firstPlayRequestedAt))
            : undefined;

        telemetry.emit("playback_started", {
          playback_position_ms: position(),

          startup_time_ms: startupTime,
        });
      } else if (pausedByUser) {

      /*
       * Genuine user pause -> resume.
       *
       * Don't call every buffer recovery
       * a resume.
       */
        pausedByUser = false;

        telemetry.emit("resume", {
          playback_position_ms: position(),
        });
      }

      /*
       * Recovering from buffering.
       */
      if (bufferingStartedAt !== null) {
        telemetry.emit("buffer_ended", {
          playback_position_ms: position(),

          buffer_duration_ms: Math.max(
            0,
            Math.round(performance.now() - bufferingStartedAt),
          ),
        });

        bufferingStartedAt = null;
      }

      startWatchSegment();
    };

    const handlePause = () => {
      if (video.ended || !started) {
        return;
      }

      const watchDelta = closeWatchSegment();

      pausedByUser = true;

      telemetry.emit("pause", {
        playback_position_ms: position(),

        watch_delta_ms: watchDelta,
      });
    };

    const handleWaiting = () => {
      if (!started || bufferingStartedAt !== null) {
        return;
      }

      const watchDelta = closeWatchSegment();

      bufferingStartedAt = performance.now();

      telemetry.emit("buffer_started", {
        playback_position_ms: position(),

        watch_delta_ms: watchDelta,
      });
    };

    const handleSeeking = () => {
      if (!started) {
        return;
      }

      const watchDelta = closeWatchSegment();

      seekFromMs = lastKnownPositionMs;

      /*
       * Attach the accumulated watch
       * interval here so it isn't lost
       * when seeking interrupts playback.
       */
      if (watchDelta !== undefined) {
        telemetry.emit("heartbeat", {
          playback_position_ms: seekFromMs,

          watch_delta_ms: watchDelta,
        });
      }
    };

    const handleSeeked = () => {
      if (!started) {
        return;
      }

      const target = position();

      telemetry.emit("seek", {
        playback_position_ms: target,

        seek_from_ms: seekFromMs ?? lastKnownPositionMs,

        seek_to_ms: target,
      });

      lastKnownPositionMs = target;

      seekFromMs = null;

      if (!video.paused && bufferingStartedAt === null) {
        startWatchSegment();
      }
    };

    const handleTimeUpdate = () => {
      if (!video.seeking) {
        lastKnownPositionMs = position();
      }
    };

    const handleEnded = () => {
      const watchDelta = closeWatchSegment();

      telemetry.emit("playback_ended", {
        playback_position_ms: position(),

        watch_delta_ms: watchDelta,
      });

      void telemetry.flush();
    };

    video.addEventListener("play", handlePlay);

    video.addEventListener("playing", handlePlaying);

    video.addEventListener("pause", handlePause);

    video.addEventListener("waiting", handleWaiting);

    video.addEventListener("seeking", handleSeeking);

    video.addEventListener("seeked", handleSeeked);

    video.addEventListener("timeupdate", handleTimeUpdate);

    video.addEventListener("ended", handleEnded);

    /*
     * Heartbeats still exist, but they
     * no longer imply "exactly 10 seconds
     * watched".
     *
     * They carry the actual elapsed
     * monotonic watch interval.
     */
    const heartbeatTimer = window.setInterval(() => {
      if (
        !started ||
        video.paused ||
        video.ended ||
        video.seeking ||
        bufferingStartedAt !== null
      ) {
        return;
      }

      const watchDelta = closeWatchSegment(true);

      telemetry.emit("heartbeat", {
        playback_position_ms: position(),

        watch_delta_ms: watchDelta,
      });
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

        const watchDelta = data.fatal ? closeWatchSegment() : undefined;

        telemetry.emit("playback_error", {
          playback_position_ms: position(),

          watch_delta_ms: watchDelta,

          error_code: data.details,

          metadata: {
            type: data.type,

            fatal: data.fatal,
          },
        });
      });
    } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
      video.src = src;
    } else {
      console.error("This browser does not support HLS playback");

      telemetry.emit("playback_error", {
        error_code: "hls_not_supported",
      });
    }

    return () => {
      window.clearInterval(heartbeatTimer);

      /*
       * Account for whatever portion of
       * playback occurred since the last
       * heartbeat before unmounting.
       */
      const finalWatchDelta = closeWatchSegment();

      if (finalWatchDelta !== undefined && started && !video.ended) {
        telemetry.emit("heartbeat", {
          playback_position_ms: position(),

          watch_delta_ms: finalWatchDelta,
        });
      }

      video.removeEventListener("play", handlePlay);

      video.removeEventListener("playing", handlePlaying);

      video.removeEventListener("pause", handlePause);

      video.removeEventListener("waiting", handleWaiting);

      video.removeEventListener("seeking", handleSeeking);

      video.removeEventListener("seeked", handleSeeked);

      video.removeEventListener("timeupdate", handleTimeUpdate);

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
