# Getting Started with SentinelOps

Welcome to SentinelOps, the autonomous multi-agent incident response and reliability orchestration platform.

## 15-Minute Onboarding

### 1. Prerequisites
Ensure you have the following installed:
- Docker and Docker Compose
- Python 3.11+
- Node.js 20+

### 2. Quickstart
Clone the repository and spin up the development environment:

```bash
# Clone the repository
git clone https://github.com/purvanshh/SentinelOps.git
cd SentinelOps

# Copy environment variables
cp .env.example .env

# Build and start all services
make up

# Verify API is healthy
curl http://localhost:8000/health
```

### 3. Verification
Verify that the following endpoints are reachable:
- FastAPI API Docs: `http://localhost:8000/docs`
- Web Dashboard: `http://localhost:3001`
- Prometheus UI: `http://localhost:9090`
- Grafana: `http://localhost:3000`
