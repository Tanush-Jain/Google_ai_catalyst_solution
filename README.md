# SentinelLLM 🛡️

**Production-Grade Observability for LLM Applications on Google Vertex AI**

SentinelLLM is a FastAPI gateway that instruments LLM requests to Google Gemini (Vertex AI) with comprehensive OpenTelemetry observability and Datadog integration.

---

## What SentinelLLM Does

LLM applications fail in non-obvious ways. SentinelLLM makes these failures visible:

- **Hallucinations** — Confident but incorrect responses
- **Prompt injection attacks** — Malicious users manipulating the AI
- **Silent latency regressions** — Performance degradation over time
- **Runaway token costs** — Unexpected budget overruns
- **Sensitive data leakage** — PII exposure in responses

---

## Architecture

```
┌─────────────┐     ┌─────────────────────┐     ┌──────────────────┐
│   Client    │────▶│   SentinelLLM       │────▶│  Vertex AI       │
│  (cURL/API) │     │   FastAPI Gateway   │     │  Gemini 2.0      │
└─────────────┘     └─────────────────────┘     └──────────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │OpenTelemetry │
                     └──────────────┘
                            │
                            ▼
                     ┌──────────────┐     ┌──────────────────┐
                     │   Datadog    │────▶│  APM Dashboards  │
                     │    Agent     │     │  & Alerts        │
                     └──────────────┘     └──────────────────┘
```

### Data Flow

1. **Request** — Client sends prompt to gateway
2. **Instrumentation** — OpenTelemetry span starts
3. **LLM Call** — Request to Vertex AI Gemini
4. **Response** — Response parsed with token counts
5. **Telemetry** — Metrics sent to Datadog Agent
6. **Monitoring** — Traces appear in Datadog APM

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Request Tracing** | Every LLM call creates a distributed trace |
| **Token Monitoring** | Input/output token counts per request |
| **Latency Tracking** | P50/P95 latency with percentiles |
| **Cost Estimation** | Per-request cost based on token usage |
| **Prompt Injection Detection** | Security monitoring for attacks |

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Language** | Python 3.11+ |
| **Framework** | FastAPI |
| **LLM Provider** | Google Vertex AI (Gemini 2.0) |
| **Observability** | OpenTelemetry |
| **Monitoring** | Datadog APM |
| **Containerization** | Docker |

---

## Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd sentinel-llm
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Google Cloud (required)
export GCP_PROJECT_ID=<your-project-id>
export VERTEX_LOCATION=us-central1
export GEMINI_MODEL=gemini-2.0-flash
export GOOGLE_APPLICATION_CREDENTIALS=<path-to-credentials>

# Datadog (optional for local dev)
export DD_SERVICE=sentinelllm
export DD_ENV=development
export DD_TRACE_ENABLED=true
```

### 3. Run the Gateway

```bash
# With Datadog tracing
ddtrace-run python -m uvicorn src.main:app --host 0.0.0.0 --port 8080

# Without Datadog (console output only)
python -m uvicorn src.main:app --host 0.0.0.0 --port 8080
```

### 4. Test the API

```bash
# Generate text
curl -X POST http://localhost:8080/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Explain zero trust security in 2 sentences"}'

# Health check
curl http://localhost:8080/health
```

---

## API Reference

### POST /generate

Generate text using Gemini with full observability.

**Request:**
```json
{
  "prompt": "Your prompt here",
  "max_tokens": 100,
  "temperature": 0.7
}
```

**Response:**
```json
{
  "text": "Generated response...",
  "input_tokens": 25,
  "output_tokens": 45,
  "latency_ms": 1234.5,
  "cost_estimate": 0.00125,
  "model": "gemini-2.0-flash"
}
```

### GET /health

Returns service health status.

---

## Observability in Datadog

### View Traces

1. Navigate to **APM → Traces**
2. Filter by service: `sentinel-llm`
3. Search: `env:development service:sentinel-llm`

### View Metrics

1. Navigate to **Metrics → Metrics Explorer**
2. Query: `sentinel_llm.request.count`
3. Filter: `service:sentinel-llm env:development`

### Key Metrics

| Metric | Description |
|--------|-------------|
| `sentinel_llm.request.latency` | Request duration (ms) |
| `sentinel_llm.tokens.input` | Input tokens per request |
| `sentinel_llm.tokens.output` | Output tokens per request |
| `sentinel_llm.cost.estimate` | Estimated cost (USD) |

---

## Project Structure

```
sentinel-llm/
├── src/
│   ├── main.py           # FastAPI application entry point
│   ├── api/
│   │   └── routes.py     # API endpoints
│   ├── gateway/
│   │   ├── llm_client.py # Vertex AI Gemini client
│   │   ├── config.py     # Settings management
│   │   └── telemetry.py  # OpenTelemetry instrumentation
│   └── utils/
│       └── token_counter.py  # Token estimation
├── requirements.txt
├── Dockerfile
└── README.md
```

---

## Why This Wins

1. **Real Production Problem** — LLM observability is critical for enterprise adoption
2. **Clean Architecture** — FastAPI gateway with clear separation of concerns
3. **Strong Observability Story** — OpenTelemetry → Datadog APM integration
4. **Working Demo** — End-to-end system that traces real Gemini requests
5. **Production-Ready** — Structured logging, metrics, and distributed tracing

---

## License

MIT License

