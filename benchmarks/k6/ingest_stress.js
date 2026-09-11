import http from "k6/http";
import { check } from "k6";

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
 * Module state is isolated per VU.
 *
 * Each virtual user therefore represents
 * an independent playback session.
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
    ingest_stress: {
      executor:
        "ramping-arrival-rate",

      /*
       * Rate means HTTP iterations/sec.
       *
       * Every iteration contains 10 events.
       */
      startRate: 100,

      timeUnit: "1s",

      preAllocatedVUs: 150,

      maxVUs: 500,

      stages: [
        /*
         * 200 requests/sec
         * = 2,000 events/sec
         */
        {
          target: 200,
          duration: "15s",
        },

        /*
         * 400 requests/sec
         * = 4,000 events/sec
         */
        {
          target: 400,
          duration: "15s",
        },

        /*
         * 600 requests/sec
         * = 6,000 events/sec
         */
        {
          target: 600,
          duration: "15s",
        },

        /*
         * 800 requests/sec
         * = 8,000 events/sec
         */
        {
          target: 800,
          duration: "15s",
        },
      ],
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

    /*
     * If this fails, k6 itself could not
     * generate the requested load.
     */
    dropped_iterations: [
      "count==0",
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


  sessionId =
    response.json().session_id;
}


export default function () {
  ensureSession();


  const events = [];


  for (
    let i = 0;
    i < BATCH_SIZE;
    i += 1
  ) {
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
}