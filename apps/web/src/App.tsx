import { useEffect, useState } from "react";

import { VideoPlayer } from "./components/VideoPlayer";

type PlaybackResponse = {
  video_id: string;
  playback_url: string;
};

function App() {
  const [videoId, setVideoId] = useState("");
  const [playbackUrl, setPlaybackUrl] = useState<string | null>(null);

  const [error, setError] = useState<string | null>(null);

  async function loadVideo() {
    setError(null);
    setPlaybackUrl(null);

    try {
      const response = await fetch(
        `http://localhost:8000/videos/${videoId}/playback`,
      );

      if (!response.ok) {
        const body = await response.json();

        throw new Error(body.detail ?? "Unable to load video");
      }

      const data: PlaybackResponse = await response.json();

      setPlaybackUrl(data.playback_url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    }
  }

  return (
    <main
      style={{
        maxWidth: "1100px",
        margin: "0 auto",
        padding: "40px",
        fontFamily: "system-ui",
      }}
    >
      <h1>Virelai</h1>

      <p>Adaptive HLS playback test</p>

      <div
        style={{
          display: "flex",
          gap: "8px",
          marginBottom: "24px",
        }}
      >
        <input
          value={videoId}
          onChange={(event) => setVideoId(event.target.value)}
          placeholder="Video UUID"
          style={{
            flex: 1,
            padding: "10px",
          }}
        />

        <button onClick={loadVideo} disabled={!videoId}>
          Load video
        </button>
      </div>

      {error && <p style={{ color: "red" }}>{error}</p>}

      {playbackUrl && (
        <>
          <VideoPlayer src={playbackUrl} />

          <p>
            Manifest: <code>{playbackUrl}</code>
          </p>
        </>
      )}
    </main>
  );
}

export default App;
