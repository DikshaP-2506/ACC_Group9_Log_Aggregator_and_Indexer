# Group9-Log-Aggregator | Distributed Log Aggregator & Indexer

**Advanced Cloud Computing & Kubernetes — Group 9 Project**

A modular, scalable, distributed log aggregation and indexing platform featuring deterministic consistent-hash partitioning, full-text inverted-index search via Elasticsearch, resilient microservice shippers with offset persistence, and a modern React + Vite monitoring dashboard.

---

## Architecture Overview

```
                                      +-----------------------------------------+
                                      |       Microservice Agents (Python)      |
                                      |  server-1   |   server-2   |  server-3  |
                                      +--------------------+--------------------+
                                                           |
                                      HTTP POST /logs      |  (Retries with Backoff,
                                                           |   Offset Persistence)
                                                           v
                                      +-----------------------------------------+
                                      |          FastAPI Aggregator Core        |
                                      |  * Pydantic Schema Validation           |
                                      |  * Deterministic Content Hashing        |
                                      |  * Duplicate Rejection (HTTP 409)       |
                                      +--------------------+--------------------+
                                                           |
                                                           v
                                      +-----------------------------------------+
                                      |       Distribution Routing Engine       |
                                      |  * Consistent Hashing Ring (SHA-256)    |
                                      |  * Virtual Replicas (100 per node)      |
                                      |  * Dynamic Clockwise Failover           |
                                      |  * Partitions: partition-0, 1, 2        |
                                      +--------------------+--------------------+
                                                           |
                                                           v
                                      +-----------------------------------------+
                                      |          Elasticsearch Engine           |
                                      |  * Single-Node Container (Docker)       |
                                      |  * Inverted Index (Full-Text Search)    |
                                      |  * Named Volume Persistence (es_data)   |
                                      +--------------------+--------------------+
                                                           ^
                                     REST Query DSL API    |  (/logs/search)
                                                           |
                                      +--------------------+--------------------+
                                      |        React + Vite Web Dashboard       |
                                      |  * Real-Time Stream & Search Filters    |
                                      |  * KPI Cards & Cluster Health Pill      |
                                      |  * Document Inspector & Ingest Dialog   |
                                      +-----------------------------------------+
```

> **Architecture Note (Simulation vs. Production):**  
> In local development, `partition-0`, `partition-1`, and `partition-2` are logical partitions tagged within the local Elasticsearch index. In an AWS EC2 or Kubernetes production deployment, these logical partitions map directly to physical Elasticsearch shard routing (`_routing=<partition>`) or separate cluster data nodes.

---

## Technology Stack

- **Indexer Engine**: Elasticsearch 8.11.3 (Official Docker image with single-node discovery and persistent volume).
- **Aggregator Backend**: Python 3.13, FastAPI, Pydantic v2, Elasticsearch-Py 8.x, Uvicorn.
- **Log Shippers**: Python log generator and file-tailing agent with byte-offset tracking and exponential backoff.
- **Frontend Dashboard**: React 19 + Vite with Vanilla CSS (Dark mode, Glassmorphism).
- **Environment**: Windows 11, PowerShell, Docker Desktop.

---

## Prerequisites

Before starting, ensure the following are installed:
1. **Docker Desktop** (Running with Linux container engine).
2. **Python 3.10+** (Available on PATH as `python`).
3. **Node.js v18+ & npm** (Available on PATH as `node` and `npm`).

---

## Clean Local Setup & Startup Guide (PowerShell)

### Step 1: Start Elasticsearch via Docker Compose

In your primary PowerShell terminal at the project root:

```powershell
# Navigate to project directory
cd D:\Projects\ACC_Group9_Log_Aggregator_and_Indexer

# Start Elasticsearch in background
docker compose up -d

# Verify container is running and healthy
docker ps --filter "name=group9-elasticsearch"

# Test Elasticsearch HTTP endpoint (Expects HTTP 200)
Invoke-RestMethod -Uri "http://localhost:9200" -Method Get
```

Indexed data is stored in the named Docker volume `es_data` and persists across container restarts.

---

### Step 2: Setup & Start the FastAPI Backend

In a **second PowerShell window**:

```powershell
cd D:\Projects\ACC_Group9_Log_Aggregator_and_Indexer\backend

# 1. Create Python virtual environment (if not already created)
python -m venv .venv

# 2. Activate virtual environment
.\.venv\Scripts\Activate.ps1

# 3. Install backend dependencies
pip install -r requirements.txt

# 4. Copy environment configuration (if needed)
if (-not (Test-Path .env)) { Copy-Item .env.example .env }

# 5. Start development server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- **Backend Health Check**: http://127.0.0.1:8000/health
- **Interactive Swagger Documentation**: http://127.0.0.1:8000/docs
- **ReDoc Documentation**: http://127.0.0.1:8000/redoc

---

### Step 3: Setup & Start the React + Vite Frontend

In a **third PowerShell window**:

```powershell
cd D:\Projects\ACC_Group9_Log_Aggregator_and_Indexer\frontend

# 1. Install npm dependencies
npm install

# 2. Start Vite development server
npm run dev
```

Open your browser to: **http://127.0.0.1:5173**

---

### Step 4: Run Multi-Agent Log Simulation

In a **fourth PowerShell window**, launch simulated microservice log generators and shipping agents:

```powershell
cd D:\Projects\ACC_Group9_Log_Aggregator_and_Indexer

# Launch simulated microservices (server-1, server-2, server-3) in dedicated windows:
.\agent\start_agents.ps1 -Sources @("server-1", "server-2", "server-3") -Interval 2.0
```

This starts:
- 3 generator processes appending realistic `INFO`, `WARNING`, and `ERROR` events to `logs/*.log`.
- 3 shipping agents tailing the files, recording byte offsets in `logs/*.offset`, and sending logs to the aggregator.

---

## Testing & Verification

### 1. Run Automated Test Suite (31 Tests)

```powershell
cd D:\Projects\ACC_Group9_Log_Aggregator_and_Indexer
.\backend\.venv\Scripts\python.exe -m pytest -v
```

All 31 unit, integration, and E2E pipeline tests pass:
- `agent/test_agent.py`: Offset persistence, backoff retries, schema parsing.
- `backend/tests/test_models.py`: Schema normalization and deterministic ID computation.
- `backend/tests/test_health.py`: Health check and cluster connectivity.
- `backend/tests/test_ingest.py`: Log ingestion and duplicate rejection (`409 Conflict`).
- `backend/tests/test_router.py`: Deterministic routing and hash-ring failover.
- `backend/tests/test_search.py`: Elasticsearch query construction and time filtering.
- `backend/tests/test_e2e_full_pipeline.py`: Full end-to-end integration across all subsystems.

---

### 2. Verify Key Features via PowerShell

#### A. Health Check
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -Method Get | ConvertTo-Json -Depth 4
```

#### B. Check Partition Ring & Route Preview
```powershell
# View active logical partitions on the hash ring
Invoke-RestMethod -Uri "http://127.0.0.1:8000/routing/partitions" | ConvertTo-Json -Depth 4

# Check where server-1 routes deterministically
Invoke-RestMethod -Uri "http://127.0.0.1:8000/routing/resolve?source=server-1" | ConvertTo-Json
```

#### C. Test Dynamic Partition Failover
```powershell
# 1. Mark partition-2 unavailable
Invoke-RestMethod -Uri "http://127.0.0.1:8000/routing/partitions/partition-2/toggle" -Method Post | ConvertTo-Json

# 2. Check resolution: server-1 automatically fails over to next active node (partition-1)
Invoke-RestMethod -Uri "http://127.0.0.1:8000/routing/resolve?source=server-1" | ConvertTo-Json

# 3. Restore partition-2
Invoke-RestMethod -Uri "http://127.0.0.1:8000/routing/partitions/partition-2/toggle" -Method Post | ConvertTo-Json
```

#### D. Ingest a Log Entry (POST /logs)
```powershell
$log = @{
    level = "INFO"
    message = "Payment transaction verified"
    source = "payment-service"
    metadata = @{ amount = 129.50; currency = "USD" }
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://127.0.0.1:8000/logs" -Method Post -Body $log -ContentType "application/json" | ConvertTo-Json
```

#### E. Test Duplicate Prevention
Sending the identical log ID a second time returns `HTTP 409 Conflict`:
```powershell
$dupLog = @{
    id = "fixed-unique-sample-001"
    level = "ERROR"
    message = "Database lock acquisition failed"
    source = "order-service"
} | ConvertTo-Json

# First request succeeds (201 Created)
Invoke-RestMethod -Uri "http://127.0.0.1:8000/logs" -Method Post -Body $dupLog -ContentType "application/json"

# Second request triggers HTTP 409 Conflict
try {
    Invoke-RestMethod -Uri "http://127.0.0.1:8000/logs" -Method Post -Body $dupLog -ContentType "application/json"
} catch {
    $_.Exception.Response.StatusCode
}
```

#### F. Query Logs by Keyword, Source, and Partition
```powershell
# Search by keyword
Invoke-RestMethod -Uri "http://127.0.0.1:8000/logs/search?query=payment" | ConvertTo-Json -Depth 4

# Filter by partition
Invoke-RestMethod -Uri "http://127.0.0.1:8000/logs/search?partition=partition-0&limit=5" | ConvertTo-Json -Depth 4
```

---

## Troubleshooting Guide

| Issue | Cause | Solution |
| :--- | :--- | :--- |
| **Port 9200 already in use** | An existing process or container is bound to port 9200. | Run `Get-NetTCPConnection -LocalPort 9200` to find the process ID or stop other containers. |
| **Port 8000 or 5173 in use** | A previous instance of Uvicorn or Vite is running. | Use `Get-Process python` or `Get-Process node` and stop the conflicting process. |
| **Elasticsearch Out of Memory** | Docker Desktop has limited memory. | The JVM is configured with `-Xms512m -Xmx512m` in [docker-compose.yml](docker-compose.yml). Ensure Docker Desktop has at least 2GB of RAM allocated. |
| **Agent not shipping logs** | Fast API backend is offline or offset file is ahead of log. | Check that `http://127.0.0.1:8000/health` returns `healthy`. Delete `logs/*.offset` to re-read files from byte 0 if needed. |
| **409 Conflict in Agent Logs** | Duplicate log detected by aggregator. | This is expected behavior: the agent acknowledges the duplicate and advances the offset without data loss. |

---

## Graceful Shutdown Commands

To cleanly shut down all local components:

```powershell
# 1. Stop simulated generators and shipping agents
# Close the PowerShell windows spawned by start_agents.ps1, or stop them:
Get-Process python | Where-Object { $_.MainWindowTitle -like "*server-*" } | Stop-Process -Force

# 2. Stop Vite Frontend
# Press Ctrl+C in the frontend terminal, or:
Get-Process node | Stop-Process -Force

# 3. Stop FastAPI Backend
# Press Ctrl+C in the backend terminal

# 4. Stop Elasticsearch Container (Preserving Volume Data)
docker compose down
```

To remove all persistent data and start completely fresh:
```powershell
docker compose down -v
Remove-Item -Path logs\*.log*, logs\*.offset -ErrorAction SilentlyContinue
```

---

## AWS Cloud Deployment Readiness

For deploying Group9-Log-Aggregator to Amazon Web Services (AWS EC2, EBS, S3, and CloudWatch):

- **Deployment Guide**: See [DEPLOYMENT_AWS.md](DEPLOYMENT_AWS.md) for full step-by-step instructions on Ubuntu 22.04/24.04 (`t3.small` / `t3.medium`).
- **Production Compose File**: [docker-compose.prod.yml](docker-compose.prod.yml) orchestrates Nginx, FastAPI, and private Elasticsearch (port 9200 is never exposed publicly).
- **S3 Cold Storage Archival**: [scripts/s3_log_archiver.py](scripts/s3_log_archiver.py) compresses historical logs (`.gz`) and uploads them to Amazon S3 with AES256 encryption.
- **CloudWatch Agent Config**: [aws/cloudwatch/amazon-cloudwatch-agent.json](aws/cloudwatch/amazon-cloudwatch-agent.json) streams EC2 CPU, Memory, Disk metrics, and container logs.
- **IAM Least-Privilege Policy**: [aws/iam-policy.json](aws/iam-policy.json) provides granular EC2 Instance Profile permissions for S3 and CloudWatch.