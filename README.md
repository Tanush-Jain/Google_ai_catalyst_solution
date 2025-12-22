# SentinelLLM 🛡️

**Production-Grade Observability & Incident Response for LLM Applications**

SentinelLLM is an end-to-end observability and security platform for Large Language Model (LLM) applications running on Google Cloud. It transforms LLM behavior into measurable telemetry and actionable incidents using Datadog.

Built for the **AI Partner Catalyst Challenge (Datadog Track)**.

---

## 🚀 What SentinelLLM Does

Large Language Models fail in non-obvious ways:

* Hallucinations
* Prompt injection attacks
* Silent latency regressions
* Runaway token costs
* Sensitive data leakage

SentinelLLM makes these failures **visible, measurable, and actionable**.

---

## 🧠 Architecture Overview

```
Client → SentinelLLM Gateway → Vertex AI / Gemini
                      ↓
               OpenTelemetry
                      ↓
                  Datadog
```

The SentinelLLM Gateway instruments every LLM interaction and streams telemetry to Datadog for real-time monitoring, detection, and incident response.

---

## 🔧 Tech Stack

### Google Cloud

* Vertex AI (Gemini)
* Cloud Run / GKE
* OpenTelemetry

### Observability

* Datadog APM
* Datadog Logs
* Datadog Metrics
* Datadog Incident Management

### Backend

* Python (FastAPI)
* Docker

---

## 📊 Key Observability Signals

### Performance

* LLM latency (p50 / p95)
* Error rate
* Retry count

### Cost

* Input / output token count
* Estimated cost per request
* Cost per minute

### Quality

* Response confidence score
* Hallucination risk score

### Security

* Prompt injection detection
* PII exposure detection
* Jailbreak attempts

---

## 🚨 Automated Incident Detection

SentinelLLM defines detection rules in Datadog for:

* Prompt Injection Attempts
* Cost Explosions
* Latency Regressions
* Hallucination Risk Spikes
* Sensitive Data Leakage

When triggered, Datadog automatically creates an incident with full context:

* Prompt and response
* Model version
* Token usage and cost
* Trace ID and logs

---

## 🛠️ Setup Instructions

### 1️⃣ Prerequisites

* Google Cloud project
* Vertex AI enabled
* Datadog account
* Python 3.10+
* Docker

---

### 2️⃣ Clone Repository

```bash
git clone https://github.com/your-username/sentinel-llm.git
cd sentinel-llm
```

---

### 3️⃣ Configure Environment Variables

Create a `.env` file using `.env.example`:

```env
GCP_PROJECT_ID=your_project_id
VERTEX_LOCATION=us-central1
DATADOG_API_KEY=your_datadog_api_key
DATADOG_SITE=datadoghq.com
GEMINI_MODEL=gemini-1.5-pro
```

---

### 4️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

---

### 5️⃣ Run Locally

```bash
python src/gateway/app.py
```

The API will start at:

```
http://localhost:8080
```

---

### 6️⃣ Deploy to Google Cloud Run

```bash
gcloud builds submit --tag gcr.io/$GCP_PROJECT_ID/sentinel-llm
gcloud run deploy sentinel-llm \
  --image gcr.io/$GCP_PROJECT_ID/sentinel-llm \
  --platform managed \
  --region us-central1
```

---

## 🧪 Demo & Simulation

Use the provided scripts to simulate failures:

```bash
python scripts/simulate_attack.py
python scripts/simulate_cost_spike.py
```

These will trigger Datadog detection rules and generate incidents.

---

## 🎥 Demo Video

📺 Demo video (3 minutes):
**[YouTube / Vimeo link here]**

---

## 📂 Datadog Assets

* Dashboards: `infra/datadog/dashboards/`
* Monitors: `infra/datadog/monitors/`

---

## 📜 License

This project is open-source under the **MIT License**.

---

## 🙌 Built For

**AI Partner Catalyst – Datadog Challenge**
Accelerating innovation through the Google Cloud partner ecosystem.
