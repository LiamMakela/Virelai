### Ingest horizontal scaling

#### Single Uvicorn worker

Stress ramp target: up to 8,000 telemetry events/s

- Accepted average: 3,222 events/s
- HTTP error rate: 0%
- Median latency: 233.50 ms
- p95 latency: 553.39 ms
- p99 latency: 18.26 s
- Dropped iterations: 5,100
- Maximum active VUs: 500
- Result: saturated before reaching requested load

#### Four Uvicorn workers

Same stress workload:

- Scheduled iterations completed: 24,748
- Average accepted rate: 4,121 events/s
- Peak requested rate: 8,000 events/s
- HTTP error rate: 0%
- Median latency: 4.62 ms
- p95 latency: 165.50 ms
- p99 latency: 226.09 ms
- Maximum latency: 294.37 ms
- Dropped iterations: 0
- Maximum active VUs: 85
- Result: completed full requested load without saturation

### Sustained telemetry capacity

#### 10,000 events/sec
- Duration: 30 seconds
- Events accepted: 300,010
- Dropped iterations: 0
- HTTP error rate: 0%
- Median ingest latency: 57.55 ms
- p95 ingest latency: 197.02 ms
- p99 ingest latency: 269.70 ms
- Maximum ingest latency: 397.29 ms
- Result: PASS