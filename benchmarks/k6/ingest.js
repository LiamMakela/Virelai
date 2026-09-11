import http from "k6/http";
import { check, sleep } from "k6";
import {
  Counter,
  Rate,
  Trend,
} from "k6/metrics";


const API_BASE_URL =
  __ENV.API_BASE_URL ||
  "http://api:8000";

const INGEST_BASE_URL =
  __ENV.INGEST_BASE_URL ||
  "http://ingest:8001";

const VIDEO_ID =
  __ENV.VIDEO_ID;

const BATCH_SIZE = 10;


/*
 * IMPORTANT:
 *
 * k6 gives each VU its own JavaScript runtime.
 *
 * Therefore each VU gets its own copy of:
 *
 *   sessionId
 *   sequenceNumber
 *
 * Each virtual viewer will create exactly one
 * playback session and reuse it throughout
 * that VU's iterations.
 */
let sessionId = null;

let sequenceNumber = 0;


if (!VIDEO_ID) {
  throw new Error(
    "VIDEO_ID environment variable is required",
  );
}


const ingestLatency =
  new Trend(
    "ingest_latency_ms",
    true,
  );


const ingestFailures =
  new Rate(
    "ingest_failures",
  );


const telemetryEvents =
  new Counter(
    "telemetry_events_sent",
  );


export const options = {
  scenarios: {
    ingest_load: {
      executor: "ramping-vus",

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

      gracefulRampDown: "30s",
    },
  },


  thresholds: {
    ingest_failures: [
      "rate<0.01",
    ],

    ingest_latency_ms: [
      "p(95)<500",
      "p(99)<1000",
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


function uuid() {
  return (
    "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx"
  ).replace(
    /[xy]/g,
    (character) => {
      const random =
        Math.random() * 16 | 0;

      const value =
        character === "x"
          ? random
          : (
              random & 0x3
            ) | 0x8;

      return value.toString(
        16,
      );
    },
  );
}


function ensureSession() {
  if (sessionId !== null) {
    return;
  }


  const response = http.post(
    `${API_BASE_URL}/videos/${VIDEO_ID}/sessions`,
    null,
    {
      tags: {
        endpoint:
          "create_session",
      },
    },
  );


  const ok = check(
    response,
    {
      "session created":
        (r) =>
          r.status === 201,
    },
  );


  if (!ok) {
    throw new Error(
      `Unable to create VU session: ${response.status} ${response.body}`,
    );
  }


  const body =
    response.json();


  sessionId =
    body.session_id;
}


export default function () {
  ensureSession();


  const events = [];


  for (
    let i = 0;
    i < BATCH_SIZE;
    i += 1
  ) {
    /*
     * Sequence numbers only need to be
     * unique within a session.
     *
     * Since each VU owns one session,
     * each VU can simply count upward
     * from 1.
     */
    sequenceNumber += 1;


    events.push({
      event_id:
        uuid(),

      session_id:
        sessionId,

      video_id:
        VIDEO_ID,

      sequence_number:
        sequenceNumber,

      event_time:
        new Date()
          .toISOString(),

      event_type:
        "heartbeat",

      /*
       * Synthetic playback position.
       *
       * Each generated heartbeat represents
       * approximately one second of simulated
       * playback progress.
       */
      playback_position_ms:
        sequenceNumber * 1000,

      watch_delta_ms:
        1000,
    });
  }


  const response = http.post(
    `${INGEST_BASE_URL}/events/batch`,

    JSON.stringify({
      events,
    }),

    {
      headers: {
        "Content-Type":
          "application/json",
      },

      tags: {
        endpoint:
          "ingest",
      },
    },
  );


  const ok = check(
    response,
    {
      "ingest returned 202":
        (r) =>
          r.status === 202,
    },
  );


  ingestFailures.add(
    !ok,
  );


  ingestLatency.add(
    response.timings.duration,
  );


  if (ok) {
    telemetryEvents.add(
      BATCH_SIZE,
    );
  }


  sleep(0.1);
}