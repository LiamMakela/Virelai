import { useEffect, useRef } from "react";
import Hls from "hls.js";

type VideoPlayerProps = {
  src: string;
};

export function VideoPlayer({ src }: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);

  useEffect(() => {
    const video = videoRef.current;

    if (!video) {
      return;
    }

    let hls: Hls | null = null;

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

        if (level) {
          console.log(`Switched to ${level.height}p`);
        }
      });

      hls.on(Hls.Events.ERROR, (_, data) => {
        console.error("HLS error", data);
      });
    } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
      video.src = src;
    } else {
      console.error("This browser does not support HLS playback");
    }

    return () => {
      hls?.destroy();
    };
  }, [src]);

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
