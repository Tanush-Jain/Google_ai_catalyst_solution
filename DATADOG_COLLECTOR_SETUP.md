# SentinelLLM → OpenTelemetry Collector → Datadog Integration

## 🎯 ARCHITECTURE

```
FastAPI (OpenTelemetry SDK)
        ↓
OpenTelemetry Collector (Docker)
        ↓
Datadog Exporter
        ↓
Datadog APM / Metrics / Traces
```

## 📁 1️⃣ OTEL COLLECTOR CONFIG

**File:** `otel-collector-config.yaml`

```yaml
# OpenTelemetry Collector Configuration for Datadog
# Receives OTLP data from FastAPI and exports to Datadog

receivers:
  # OTLP HTTP receiver for traces and metrics (port 4318)
  otlp:
    protocols:
      http:
        endpoint: 0.0.0.0:4318

processors:
  # Batch processor to optimize telemetry data
  batch:
    timeout: 1s
    send_batch_size: 1024
    send_batch_max_size: 2048

  # Resource processor to add service identity
  resource:
    attributes:
      - key: service.name
        value: sentinel-llm
        action: upsert
      - key: env
        value: development
        action: upsert
      - key: service.version
        value: "1.0.0"
        action: upsert

exporters:
  # Datadog exporter for traces and metrics
  datadog:
    api:
      key: 153529a0ed4bc293118aa4f21207fd43
      site: datadoghq.com
    # Enable traces pipeline
    traces:
      span_name_remapping:
        vertexai.generate_content: "llm.vertexai.request"
    # Enable metrics pipeline  
    metrics:
      resource_attributes_as_tags: true
      instrument_scope_as_name: true

  # Debug/logging exporter for troubleshooting
  debug:
    verbosity: basic
    sampling_initial: 2
    sampling_thereafter: 500

service:
  telemetry:
    logs:
      level: info
  
  # Define pipelines for traces and metrics
  pipelines:
    traces:
      receivers: [otlp]
      processors: [resource, batch]
      exporters: [debug, datadog]
    
    metrics:
      receivers: [otlp]
      processors: [resource, batch]
      exporters: [debug, datadog]

extensions: []
```

## 🐳 2️⃣ DOCKER SETUP

### Run OpenTelemetry Collector Container

```bash
# Navigate to project directory
cd /Users/wopseeion/Programming/Hackathons/Googe_catalyst/Google_ai_catalyst_solution

# Run OpenTelemetry Collector with Docker
docker run \
  --name otel-collector \
  --rm \
  -p 4318:4318 \
  -v $(pwd)/otel-collector-config.yaml:/etc/otelcol-contrib/config.yaml \
  otel/opentelemetry-collector-contrib:latest \
  --config=/etc/otelcol-contrib/config.yaml
```

### Background Collector (Optional)

```bash
# Run in background
docker run \
  --name otel-collector \
  --rm \
  -d \
  -p 4318:4318 \
  -v $(pwd)/otel-collector-config.yaml:/etc/otelcol-contrib/config.yaml \
  otel/opentelemetry-collector-contrib:latest \
  --config=/etc/otelcol-contrib/config.yaml

# Check collector logs
docker logs -f otel-collector

# Stop collector
docker stop otel-collector
```

## ⚙️ 3️⃣ FASTAPI CONFIG CHANGES

### Set Environment Variables

```bash
# Remove direct Datadog configuration
unset DATADOG_API_KEY
unset DATADOG_SITE
unset DATADOG_SERVICE
unset DATADOG_ENV

# Set OpenTelemetry Collector configuration
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
export OTEL_TRACES_EXPORTER=otlp
export OTEL_METRICS_EXPORTER=otlp
export OTEL_SERVICE_NAME=sentinel-llm
export OTEL_RESOURCE_ATTRIBUTES=service.name=sentinel-llm,env=development

# Keep application settings
export DATADOG_ENV=development
export GCP_PROJECT_ID=your_gcp_project
export GEMINI_MODEL=gemini-1.5-flash-002
export VERTEX_LOCATION=us-central1
```

### Update FastAPI Configuration

**Modify `src/gateway/telemetry.py`** to remove direct Datadog configuration:

```python
def initialize(self) -> None:
    """Initialize OpenTelemetry providers and exporters."""
    if self._initialized:
        return

    try:
        # Configure OTLP endpoint
        otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
        
        # Create OTLP exporters pointing to Collector
        span_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        metric_exporter = OTLPMetricExporter(endpoint=otlp_endpoint)

        # Get service configuration from environment
        service_name = os.getenv("OTEL_SERVICE_NAME", "sentinel-llm")
        service_env = os.getenv("OTEL_RESOURCE_ATTRIBUTES", "env=development")
        
        # Parse resource attributes
        resource_attrs = {}
        for attr in service_env.split(","):
            if "=" in attr:
                key, value = attr.split("=", 1)
                resource_attrs[key] = value

        logger.info(f"Telemetry: OTLP mode (Collector endpoint: {otlp_endpoint})")
        logger.info(f"Service: {service_name}")

        # Resource attributes
        resource = Resource.create({
            ResourceAttributes.SERVICE_NAME: service_name,
            ResourceAttributes.SERVICE_VERSION: "1.0.0",
            ResourceAttributes.DEPLOYMENT_ENVIRONMENT: resource_attrs.get("env", "development"),
            ResourceAttributes.TELEMETRY_SDK_NAME: "opentelemetry-python",
            ResourceAttributes.TELEMETRY_SDK_VERSION: "1.21.0",
        })

        # Tracing provider
        tracer_provider = TracerProvider(resource=resource)
        tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
        trace.set_tracer_provider(tracer_provider)
        self.tracer = trace.get_tracer(service_name)

        # Metrics provider
        metric_reader = PeriodicExportingMetricReader(
            metric_exporter,
            export_interval_millis=5000,
        )
        metrics.set_meter_provider(MeterProvider(
            resource=resource,
            metric_readers=[metric_reader]
        ))
        self.meter = metrics.get_meter(service_name)

        # Custom metrics
        self._initialize_metrics()

        self._initialized = True
        logger.info("Telemetry initialized successfully")

    except Exception as e:
        # Degraded mode (still lets app run)
        logger.exception(f"Telemetry init failed, degraded mode: {e}")
        self.tracer = trace.get_tracer(__name__)
        self.meter = metrics.get_meter(__name__)
        self._initialize_metrics()
```

## 🏷️ 4️⃣ SERVICE IDENTITY

**✅ Automatically handled by Collector configuration:**

- `service.name = sentinel-llm`
- `env = development`
- `service.version = 1.0.0`

**Verification in Collector logs:**
```
2024-01-01T00:00:00.000Z	info	ResourceProcessor	{"kind": "processor", "name": "resource", "pipeline": "traces", "resource": {"service.name":"sentinel-llm","env":"development","service.version":"1.0.0"}}
```

## 📊 5️⃣ EXPECTED DATADOG RESULTS

After setup, Datadog will automatically show:

### APM → Services
- **Service Name:** `sentinel-llm`
- **Environment:** `development`
- **Language:** `python`

### APM → Traces
- **Endpoint:** `/generate` (FastAPI route)
- **Span:** `vertexai.generate_content` (renamed to `llm.vertexai.request`)
- **Attributes:** model_name, region, latency_ms, error_type

### Metrics Explorer
- **Custom Metrics:**
  - `sentinel_llm.request.count`
  - `sentinel_llm.request.latency_ms`
  - `sentinel_llm.request.errors`
  - `sentinel_llm.llm.failures`
  - `sentinel_llm.security.prompt_injection`

### Service Page
- Request latency graphs
- Error rate graphs
- Throughput metrics
- Custom LLM metrics (tokens, latency, cost)

## 🔍 6️⃣ VERIFICATION STEPS

### Step 1: Start Collector
```bash
docker run --name otel-collector --rm -p 4318:4318 -v $(pwd)/otel-collector-config.yaml:/etc/otelcol-contrib/config.yaml otel/opentelemetry-collector-contrib:latest --config=/etc/otelcol-contrib/config.yaml
```

**Expected Collector Logs:**
```
2024-01-01T00:00:00.000Z	info	otlpreceiver	{"kind": "receiver", "name": "otlp", "pipeline": "traces", "protocol": "http", "endpoint": "0.0.0.0:4318"}
2024-01-01T00:00:00.000Z	info	datadogexporter	{"kind": "exporter", "name": "datadog", "pipeline": "traces"}
2024-01-01T00:00:00.000Z	info	service	{"kind": "service", "pipeline": "traces", "components": ["otlp", "resource", "batch", "datadog"]}
```

### Step 2: Start FastAPI Application
```bash
# Set environment variables
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
export OTEL_TRACES_EXPORTER=otlp
export OTEL_METRICS_EXPORTER=otlp
export OTEL_SERVICE_NAME=sentinel-llm
export OTEL_RESOURCE_ATTRIBUTES=service.name=sentinel-llm,env=development
export DATADOG_ENV=development
export GCP_PROJECT_ID=your_project

# Start application
python -m uvicorn src.main:app --host 0.0.0.0 --port 8080 --reload
```

**Expected Application Logs:**
```
INFO:Telemetry initialized successfully
INFO:SentinelLLM Gateway started successfully
```

### Step 3: Trigger Traces
```bash
# Health check
curl -X GET http://localhost:8080/health

# Generate request (this creates traces)
curl -X POST http://localhost:8080/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Explain quantum computing","max_tokens":100}'
```

### Step 4: Verify Collector Debug Output
**Collector should show debug traces like:**
```
2024-01-01T00:00:00.123Z	info	debugexporter	{"kind": "exporter", "name": "debug", "pipeline": "traces", "spans": 2}
	Trace ID: abc123...
	Span ID: def456...
	Name: /generate
	Status: OK
	
	Attributes:
	- http.method: POST
	- http.route: /generate
	- service.name: sentinel-llm
	- env: development
```

### Step 5: Verify Datadog UI
1. **APM → Services:** Look for `sentinel-llm` service
2. **APM → Traces:** Click on recent traces
3. **Metrics → Metrics Explorer:** Search for `sentinel_llm.*` metrics
4. **Service Map:** Verify service dependencies

## ⚠️ 7️⃣ COMMON MISTAKES CHECKLIST

### ❌ Collector Issues
- [ ] Collector container not running
- [ ] Port 4318 not exposed
- [ ] Configuration file path incorrect
- [ ] Datadog API key invalid
- [ ] Collector logs show errors

### ❌ FastAPI Issues
- [ ] OTEL_EXPORTER_OTLP_ENDPOINT not set
- [ ] Still using direct Datadog configuration
- [ ] Service name mismatch
- [ ] Environment variables not loaded

### ❌ Datadog Issues
- [ ] No traces in APM after 2-3 minutes
- [ ] Service not appearing in Service list
- [ ] Metrics not showing in Metrics Explorer
- [ ] Wrong environment tag

### ❌ Network Issues
- [ ] localhost not accessible from container
- [ ] Firewall blocking port 4318
- [ ] Docker network issues
- [ ] Host resolution problems

## 🚀 QUICK START COMMANDS

```bash
# 1. Start Collector
docker run --name otel-collector --rm -p 4318:4318 -v $(pwd)/otel-collector-config.yaml:/etc/otelcol-contrib/config.yaml otel/opentelemetry-collector-contrib:latest --config=/etc/otelcol-contrib/config.yaml

# 2. Set environment variables
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
export OTEL_TRACES_EXPORTER=otlp
export OTEL_METRICS_EXPORTER=otlp
export OTEL_SERVICE_NAME=sentinel-llm
export OTEL_RESOURCE_ATTRIBUTES=service.name=sentinel-llm,env=development

# 3. Start FastAPI
python -m uvicorn src.main:app --host 0.0.0.0 --port 8080 --reload

# 4. Test
curl -X POST http://localhost:8080/generate -H "Content-Type: application/json" -d '{"prompt":"hello"}'

# 5. Check Datadog APM for sentinel-llm service
```

## 🎯 SUCCESS CRITERIA

✅ **Collector running** on port 4318
✅ **FastAPI sending** OTLP data to localhost:4318
✅ **Debug exporter** showing traces in Collector logs
✅ **Datadog APM** showing sentinel-llm service
✅ **Datadog Metrics** showing custom LLM metrics
✅ **No errors** in Collector or FastAPI logs

**The OpenTelemetry Collector architecture is now production-ready!**
