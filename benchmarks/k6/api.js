import http from "k6/http";
import { check, sleep } from "k6";
import {
  Rate,
  Trend,
} from "k6/metrics";


const API_BASE_URL =
  __ENV.API_BASE_URL ||
  "http://api:8000";

const VIDEO_ID =
  __ENV.VIDEO_ID;


if (!VIDEO_ID) {
  throw new Error(
    "VIDEO_ID environment variable is required",
  );
}


const playbackLatency =
  new Trend(
    "playback_latency_ms",
    true,
  );

const analyticsLatency =
  new Trend(
    "analytics_latency_ms",
    true,
  );

const playbackFailures =
  new Rate(
    "playback_failures",
  );

const analyticsFailures =
  new Rate(
    "analytics_failures",
  );


export const options = {
  scenarios: {
    api_reads: {
      executor:
        "ramping-vus",

      stages: [
        {
          duration: "10s",
          target: 10,
        },
        {
          duration: "20s",
          target: 25,
        },
        {
          duration: "20s",
          target: 50,
        },
        {
          duration: "10s",
          target: 0,
        },
      ],
    },
  },

  thresholds: {
    playback_failures: [
      "rate<0.01",
    ],

    analytics_failures: [
      "rate<0.01",
    ],

    playback_latency_ms: [
      "p(95)<500",
    ],

    analytics_latency_ms: [
      "p(95)<1000",
    ],
  },

  summaryTrendStats: [
    "avg",
    "med",
    "p(90)",
    "p(95)",
    "p(99)",
    "max",
  ],
};


export default function () {
  const playback =
    http.get(
      `${API_BASE_URL}/videos/${VIDEO_ID}/playback`,
      {
        tags: {
          endpoint:
            "playback",
        },
      },
    );


  const playbackOk =
    check(
      playback,
      {
        "playback status 200":
          (r) =>
            r.status === 200,
      },
    );


  playbackFailures.add(
    !playbackOk,
  );

  playbackLatency.add(
    playback.timings.duration,
  );


  const analytics =
    http.get(
      `${API_BASE_URL}/analytics/videos/${VIDEO_ID}/summary`,
      {
        tags: {
          endpoint:
            "analytics",
        },
      },
    );


  const analyticsOk =
    check(
      analytics,
      {
        "analytics status 200":
          (r) =>
            r.status === 200,
      },
    );


  analyticsFailures.add(
    !analyticsOk,
  );

  analyticsLatency.add(
    analytics.timings.duration,
  );


  sleep(0.1);
}