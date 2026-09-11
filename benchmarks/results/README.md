## Local Docker Baseline

### API benchmark
- Max virtual users: 50
- Duration: 60s
- Requests: 9,840
- Throughput: 163.82 req/s
- Error rate: 0%

#### Playback endpoint
- Median: 60.41 ms
- p95: 256.64 ms
- p99: 446.75 ms
- Max: 1.18 s

#### Analytics endpoint
- Median: 75.92 ms
- p95: 253.13 ms
- p99: 450.21 ms
- Max: 1.29 s

### Telemetry ingestion
- Max virtual users: 50
- Duration: 60s
- HTTP requests: 8,720
- Events accepted: 87,190
- Throughput: 1,451.07 events/s
- Error rate: 0%
- Median latency: 48.89 ms
- p95: 139.35 ms
- p99: 185.30 ms
- Max: 285.73 ms