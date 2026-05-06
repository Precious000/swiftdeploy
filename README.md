# SwiftDeploy

A declarative deployment CLI that generates all infrastructure config files from a single `manifest.yaml`, enforces deployment policies through OPA, and monitors itself with Prometheus metrics.

## Architecture
manifest.yaml          ← the only file you ever edit
↓
swiftdeploy CLI        ← reads manifest, fills templates, manages lifecycle
↓
nginx.conf             ← generated (never hand-edited)
docker-compose.yml     ← generated (never hand-edited)
↓
┌─────────────────────────────────────────┐
│           swiftdeploy-net               │
│        (Docker bridge network)          │
│                                         │
│  Nginx :8080  →  Python API :3000       │
│                                         │
│  OPA :8181  (internal only, no public)  │
└─────────────────────────────────────────┘

## Requirements

- Ubuntu 22.04+ EC2 instance
- Docker + Docker Compose plugin
- Python 3 + PyYAML (`sudo apt install python3-yaml`)
- Ports 22 and 8080 open in security group

## Setup

```bash
# Clone the repo
git clone https://github.com/Precious000/swiftdeploy.git
cd swiftdeploy

# Install system dependency
sudo apt install -y python3-yaml

# Build the app image
docker build -t swift-deploy-1-node:latest .

# Deploy the full stack
./swiftdeploy deploy
```

## Subcommands

### init
Parses `manifest.yaml` and generates `nginx.conf` and `docker-compose.yml` from templates. These files are never hand-edited — always regenerated.
```bash
./swiftdeploy init
```

### validate
Runs 5 pre-flight checks and exits non-zero on any failure:
- manifest.yaml exists and is valid YAML
- All required fields are present and non-empty
- Docker image exists locally
- Nginx port is not already bound
- nginx.conf is syntactically valid

```bash
./swiftdeploy validate
```

### deploy
Starts OPA first, runs infrastructure policy checks, then brings up the full stack and blocks until health checks pass or 60s timeout.
```bash
./swiftdeploy deploy
```

If disk or CPU limits are violated, deployment is blocked:
✗ Infrastructure policy: BLOCKED
✗ Disk too full: 3.6GB free, need 10.0GB
✗ Deployment blocked by policy. Fix the violations above and retry.

### promote
Switches deployment mode with a rolling service restart. Checks live Prometheus metrics against OPA canary policy before promoting.
```bash
./swiftdeploy promote canary
./swiftdeploy promote stable
```

If error rate or P99 latency exceeds thresholds, promotion is blocked:
✗ Canary safety policy: BLOCKED
✗ Error rate too high: 84.62%, limit is 1.00%
✗ Promotion blocked by policy. Fix the violations above and retry.

### status
Live-refreshing terminal dashboard that scrapes `/metrics` every 5 seconds, displays real-time stats and policy compliance, and appends every scrape to `history.jsonl`.
```bash
./swiftdeploy status
```

### audit
Parses `history.jsonl` and generates `audit_report.md` — a GitHub Flavored Markdown report with a full timeline, policy violations, and summary.
```bash
./swiftdeploy audit
```

### teardown
Stops and removes all containers, networks, and volumes.
```bash
./swiftdeploy teardown
./swiftdeploy teardown --clean   # also deletes generated configs
```

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Welcome message with mode, version, timestamp |
| `/healthz` | GET | Health check with uptime in seconds |
| `/metrics` | GET | Prometheus metrics in text format |
| `/chaos` | POST | Inject chaos (canary mode only) |

### Chaos modes
```bash
# Slow responses
curl -X POST http://localhost:8080/chaos \
  -H "Content-Type: application/json" \
  -d '{"mode":"slow","duration":5}'

# Random errors (~50% failure rate)
curl -X POST http://localhost:8080/chaos \
  -H "Content-Type: application/json" \
  -d '{"mode":"error","rate":0.5}'

# Recover
curl -X POST http://localhost:8080/chaos \
  -H "Content-Type: application/json" \
  -d '{"mode":"recover"}'
```

## OPA Policies

All deployment decisions are made by OPA — the CLI never makes allow/deny decisions itself.

### Infrastructure Policy (`policies/infra.rego`)
Checked before every deployment:
- Disk free must be above `min_disk_free_gb`
- CPU load must be below `max_cpu_load`

### Canary Safety Policy (`policies/canary.rego`)
Checked before every promotion:
- Error rate must be below `max_error_rate`
- P99 latency must be below `max_p99_latency_ms`

### Thresholds (`policies/data.json`)
All threshold values live here — never hardcoded in Rego files:
```json
{
  "thresholds": {
    "min_disk_free_gb": 10.0,
    "max_cpu_load": 2.0,
    "max_error_rate": 0.01,
    "max_p99_latency_ms": 500.0
  }
}
```

## Prometheus Metrics

The app exposes standard Prometheus metrics at `/metrics`:

| Metric | Type | Description |
|---|---|---|
| `http_requests_total` | Counter | Total requests by method, path, status |
| `http_request_duration_seconds` | Histogram | Latency distribution by path |
| `app_uptime_seconds` | Gauge | Seconds since app started |
| `app_mode` | Gauge | 0=stable, 1=canary |
| `chaos_active` | Gauge | 0=none, 1=slow, 2=error |

## Project Structure
swiftdeploy/
├── manifest.yaml                    ← single source of truth
├── swiftdeploy                      ← bash CLI
├── Dockerfile                       ← builds swift-deploy-1-node image
├── app/
│   ├── main.py                      ← Flask API with Prometheus metrics
│   └── requirements.txt
├── templates/
│   ├── nginx.conf.tmpl              ← nginx template
│   └── docker-compose.yml.tmpl     ← compose template
├── policies/
│   ├── infra.rego                   ← infrastructure policy
│   ├── canary.rego                  ← canary safety policy
│   └── data.json                    ← threshold values
└── README.md

## How It Works

1. Edit `manifest.yaml` — the only file you ever touch
2. Run `./swiftdeploy deploy` — OPA checks host stats, generates configs, starts stack
3. Traffic enters via Nginx on port 8080, proxied to Python API on port 3000
4. OPA runs as a sidecar on the internal network — never reachable via Nginx
5. `./swiftdeploy status` watches metrics live and logs everything to `history.jsonl`
6. `./swiftdeploy audit` turns that history into a markdown report
