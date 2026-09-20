# Virelai

Virelai is a distributed video streaming and analytics platform I built to learn more about backend systems, event-driven architectures, video processing, observability, and cloud infrastructure.

The project started as a basic video streaming application, but I gradually expanded it into a system with direct multipart uploads, asynchronous FFmpeg transcoding, adaptive HLS playback, Kafka-based event processing, realtime analytics, monitoring, load testing, and an AWS deployment managed with Terraform.

It is still an actively developed student project, but the core video and analytics pipelines are working end-to-end both locally and on AWS.

## What It Does

At a high level, Virelai supports:

- direct multipart video uploads to S3-compatible storage
- asynchronous video processing with Kafka
- FFmpeg/ffprobe transcoding
- adaptive 360p and 720p HLS playback
- video metadata and processing state in PostgreSQL
- playback session and QoE telemetry
- historical analytics backed by PostgreSQL
- realtime analytics backed by Redis/Valkey
- live metric updates using Server-Sent Events
- Prometheus/Grafana monitoring
- OpenTelemetry tracing
- load testing with k6
- AWS deployment using Terraform and ECS/Fargate
- private S3 media delivery through CloudFront

---

## Architecture

### Video pipeline

```text
                         ┌─────────────────┐
                         │  React Client   │
                         └────────┬────────┘
                                  │
                           create upload
                                  │
                                  ▼
                         ┌─────────────────┐
                         │     FastAPI     │
                         └────────┬────────┘
                                  │
                         presigned URLs
                                  │
                                  ▼
                        ┌──────────────────┐
                        │ Object Storage   │
                        │  MinIO / S3      │
                        └────────┬─────────┘
                                 │
                          upload complete
                                 │
                                 ▼
                           ┌───────────┐
                           │   Kafka   │
                           └─────┬─────┘
                                 │
                                 ▼
                      ┌────────────────────┐
                      │ Transcoder Worker  │
                      │ FFmpeg / ffprobe   │
                      └─────────┬──────────┘
                                │
                       HLS + thumbnail
                                │
                                ▼
                       ┌─────────────────┐
                       │  Media Storage  │
                       └────────┬────────┘
                                │
                         CloudFront / HLS
                                │
                                ▼
                         ┌──────────────┐
                         │ hls.js Player│
                         └──────────────┘
```

Large video files are never proxied through FastAPI. The API creates presigned upload URLs, and the browser uploads the file directly to object storage.

After the upload finishes, the API publishes a Kafka event. A separate worker consumes the event, inspects the file with `ffprobe`, transcodes it with FFmpeg, generates adaptive HLS output, uploads the result, and updates the video state in PostgreSQL.

---

## Analytics Pipeline

Playback telemetry is handled separately from the main video-processing path.

```text
Browser
   │
   │ playback events
   ▼
Telemetry Ingest Service
   │
   ▼
Kafka: playback.events.v1
   │
   ├───────────────┐
   │               │
   ▼               ▼
Historical       Realtime
Worker           Worker
   │               │
   ▼               ▼
PostgreSQL      Redis / Valkey
                   │
                   ▼
                  SSE
```

The Kafka topic currently uses six partitions.

Two different consumer groups process the same event stream:

- the historical worker stores playback events in PostgreSQL
- the realtime worker maintains short-lived metrics in Redis/Valkey

This lets the same telemetry stream support both durable analytics and realtime dashboards without coupling the two consumers together.

---

## Video Processing

The transcoding worker currently generates:

- 360p HLS
- 720p HLS
- a master HLS playlist
- MPEG-TS video segments
- a thumbnail
- source metadata from ffprobe

A successful upload moves through a simple video state machine and eventually reaches `READY`.

Example:

```text
CREATED
   ↓
UPLOADING
   ↓
UPLOADED
   ↓
PROCESSING
   ↓
READY
```

The playback endpoint then returns the URL for the video's HLS master playlist.

---

## Playback Telemetry

Virelai records playback sessions and QoE events such as:

```text
playback_started
startup latency
bitrate
quality / resolution
buffering
playback errors
session ID
sequence number
```

Historical analytics currently include things like:

```text
view count
events by type
startup latency p50
startup latency p95
startup latency p99
```

Realtime projections include:

```text
active viewers
events per second
buffer events
errors
```

PostgreSQL is treated as the durable system of record, while Redis/Valkey is used for temporary realtime state.

---

## Performance Testing

I load tested the telemetry ingestion path locally using k6.

| Metric | Result |
| --- | ---: |
| Total events | 300,010 |
| Throughput | **9,966.9 events/sec** |
| Request failures | **0** |
| Dropped events | **0** |
| Average latency | 74.38 ms |
| p95 latency | 197 ms |
| p99 latency | 269.7 ms |

The test demonstrated sustained ingestion of about **10,000 telemetry events per second** with zero request failures or dropped events.

This was one of the more useful parts of the project because it gave me an actual measurement of how the system behaved under load instead of only reasoning about the architecture.

---

## AWS Deployment

I also deployed the system on AWS using Terraform.

The AWS version uses:

- ECS/Fargate for application services and workers
- ECR for container images
- RDS PostgreSQL
- ElastiCache for Valkey
- S3 for originals and generated media
- CloudFront for media delivery
- Application Load Balancer for HTTP traffic
- Cloud Map for internal service discovery
- CloudWatch for logs
- Terraform remote state in S3

The AWS environment was used to validate the architecture end-to-end rather than as a permanently running production deployment.

### AWS video path

```text
Client
  │
  ▼
FastAPI
  │
  ├── presigned multipart upload
  ▼
Private S3 Originals
  │
  ▼
Kafka
  │
  ▼
ECS Transcoder Worker
  │
  ├── ffprobe
  └── FFmpeg
  │
  ▼
Private S3 Media
  │
  ▼
CloudFront
  │
  ▼
Adaptive HLS Playback
```

I tested this with an actual 1280x720 H.264 video.

The AWS pipeline successfully:

1. uploaded the original file directly to S3
2. published the upload event through Kafka
3. processed the video in the ECS transcoder worker
4. generated 360p and 720p HLS output
5. stored metadata and processing state in PostgreSQL
6. marked the video as `READY`
7. served the generated HLS stream through CloudFront

---

## Private Media Delivery

The generated media bucket is not public.

CloudFront accesses it through Origin Access Control:

```text
Browser
   │
   ▼
CloudFront
   │
   │ OAC / SigV4
   ▼
Private S3 Bucket
```

During testing:

```text
CloudFront master playlist    -> 200
CloudFront rendition playlist -> 200
CloudFront HLS segment        -> 200
Direct S3 media request       -> 403
```

This let me keep the S3 origin private while still serving the video through a CDN.

---

## AWS Analytics Test

I also tested the telemetry path separately in AWS:

```text
Client
  ↓
Application Load Balancer
  ↓
Telemetry Ingest Service
  ↓
Kafka
  ├───────────────┐
  ↓               ↓
Analytics       Realtime
Worker          Worker
  ↓               ↓
RDS             Valkey
```

A test playback event was accepted by the ingest service, consumed by both worker groups, persisted to PostgreSQL, and reflected in the realtime Valkey projection.

---

## Local Development

The local environment uses Docker Compose.

Main services:

| Service | Port |
| --- | ---: |
| API | 8000 |
| Telemetry Ingest | 8001 |
| PostgreSQL | 5432 |
| Redis | 6379 |
| Kafka | 9092 |
| MinIO | 9000 |
| MinIO Console | 9001 |
| Grafana | 3000 |
| Prometheus | 9090 |
| Tempo | 3200 |
| OTLP gRPC | 4317 |
| OTLP HTTP | 4318 |

Start the development stack with:

```bash
docker compose up -d
```

---

## Observability

The local stack includes:

- Prometheus
- Grafana
- OpenTelemetry
- Tempo

I added observability because debugging the project became much harder once requests started crossing several services.

Metrics and traces make it easier to follow work across the API, Kafka, workers, database, and analytics services.

---

## Infrastructure as Code

The AWS infrastructure is defined in Terraform.

The larger runtime components can be enabled or disabled individually:

```hcl
enable_managed_data_services = false
enable_public_alb             = false

enable_api_service = false

enable_kafka_service = false

enable_worker_services = false

enable_ingest_service = false
```

This was useful while developing the project because I could deploy the full AWS environment, test it, and then return it to a much cheaper inactive state.

After the AWS end-to-end test, I shut down:

```text
ECS/Fargate services
temporary Kafka broker
Application Load Balancer
RDS instance
Valkey cluster
```

while keeping things such as:

```text
S3 media
ECR images
CloudFront configuration
Terraform state
VPC configuration
manual RDS snapshot
```

---

## Tech Stack

| Area | Technologies |
| --- | --- |
| Backend | Python, FastAPI |
| Frontend | React, TypeScript, Vite |
| Video Playback | hls.js |
| Video Processing | FFmpeg, ffprobe |
| Database | PostgreSQL, SQLAlchemy, Alembic |
| Messaging | Apache Kafka |
| Realtime State | Redis / Valkey |
| Storage | MinIO, Amazon S3 |
| Cloud | AWS ECS/Fargate, ECR, RDS, ElastiCache, CloudFront, ALB |
| Infrastructure | Terraform, Docker, Docker Compose |
| Observability | Prometheus, Grafana, OpenTelemetry, Tempo, CloudWatch |
| Load Testing | k6 |

---

## Project Structure

The project is split into several independently running services rather than one large backend.

```text
services/
├── api/
├── ingest/
├── transcoder/
├── analytics-worker/
└── realtime-worker/

infra/
└── terraform/

frontend/
```

The exact structure may continue changing as I clean up the project.

---

## Current Status

Working:

- [x] video metadata and state management
- [x] presigned multipart uploads
- [x] direct object-storage uploads
- [x] Kafka upload events
- [x] asynchronous FFmpeg transcoding
- [x] 360p / 720p adaptive HLS
- [x] thumbnail generation
- [x] hls.js playback
- [x] playback sessions
- [x] QoE telemetry
- [x] six-partition telemetry Kafka topic
- [x] historical analytics consumer
- [x] realtime analytics consumer
- [x] PostgreSQL analytics
- [x] Redis / Valkey projections
- [x] Server-Sent Events
- [x] Prometheus / Grafana
- [x] OpenTelemetry / Tempo
- [x] k6 load testing
- [x] Docker Compose environment
- [x] Terraform AWS infrastructure
- [x] ECS/Fargate deployment
- [x] RDS PostgreSQL deployment
- [x] ElastiCache Valkey deployment
- [x] private S3 storage
- [x] CloudFront OAC media delivery
- [x] end-to-end AWS validation

Still working on:

- [ ] transactional outbox
- [ ] retries and dead-letter queues
- [ ] authentication and authorization
- [ ] automated failure/recovery tests
- [ ] CI/CD
- [ ] more analytics and caching work
- [ ] project documentation and diagrams

---

## Things I Learned

A big reason I built Virelai was to go beyond building another CRUD web application.

Some of the areas I wanted to understand better were:

- how large files should move through a backend system
- why background jobs should be separated from request handling
- how Kafka consumer groups can support different views of the same event stream
- when to use PostgreSQL versus Redis
- how adaptive video streaming works
- how to benchmark an event ingestion pipeline
- how distributed tracing helps debug multi-service applications
- how private S3 origins can be served through CloudFront
- how Terraform changes the way cloud infrastructure is developed and tested
- what actually breaks when a local distributed system is moved onto AWS

There are still several parts of the system I want to improve, especially around reliability, authentication, and deployment automation.