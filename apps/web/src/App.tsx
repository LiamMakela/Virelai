import { useState } from "react";

import { VideoPlayer } from "./components/VideoPlayer";

type PlaybackResponse = {
  video_id: string;
  playback_url: string;
};

type PlaybackSessionResponse = {
  session_id: string;
  video_id: string;
  started_at: string;
};

function App() {
  const [videoId, setVideoId] = useState("");

  const [playbackUrl, setPlaybackUrl] = useState<string | null>(null);

  const [sessionId, setSessionId] = useState<string | null>(null);

  const [error, setError] = useState<string | null>(null);

  const [loading, setLoading] = useState(false);

  async function loadVideo() {
    if (!videoId.trim()) {
      return;
    }

    setLoading(true);
    setError(null);

    setPlaybackUrl(null);
    setSessionId(null);

    try {
      const playbackResponse = await fetch(
        `http://localhost:8000/videos/${videoId}/playback`,
      );

      if (!playbackResponse.ok) {
        const body = await playbackResponse.json();

        throw new Error(body.detail ?? "Unable to load video");
      }

      const playback: PlaybackResponse = await playbackResponse.json();

      const sessionResponse = await fetch(
        `http://localhost:8000/videos/${videoId}/sessions`,
        {
          method: "POST",
        },
      );

      if (!sessionResponse.ok) {
        const body = await sessionResponse.json();

        throw new Error(body.detail ?? "Unable to create playback session");
      }

      const session: PlaybackSessionResponse = await sessionResponse.json();

      setSessionId(session.session_id);

      setPlaybackUrl(playback.playback_url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
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

      <p>Adaptive HLS playback</p>

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
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              void loadVideo();
            }
          }}
          placeholder="Video UUID"
          style={{
            flex: 1,
            padding: "10px",
          }}
        />

        <button
          onClick={() => void loadVideo()}
          disabled={!videoId.trim() || loading}
        >
          {loading ? "Loading..." : "Load video"}
        </button>
      </div>

      {error && <p style={{ color: "red" }}>{error}</p>}

      {playbackUrl && sessionId && (
        <>
          <VideoPlayer
            src={playbackUrl}
            videoId={videoId}
            sessionId={sessionId}
          />

          <p>
            Session: <code>{sessionId}</code>
          </p>
        </>
      )}
    </main>
  );
}

export default App;
