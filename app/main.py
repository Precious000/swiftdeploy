import os, time, random, threading
from flask import Flask, request, jsonify, Response
from prometheus_client import (
    Counter, Histogram, Gauge,
    generate_latest, CONTENT_TYPE_LATEST,
    REGISTRY
)

app = Flask(__name__)
START_TIME = time.time()
MODE = os.environ.get("MODE", "stable")
VERSION = os.environ.get("APP_VERSION", "1.0.0")

chaos_state = {"mode": None, "duration": None, "rate": None}
chaos_lock = threading.Lock()

# ── Prometheus metrics definitions ───────────────────────────────────────────

# Counter: only goes up, tracks total requests by method/path/status
REQUEST_COUNTER = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status_code"]
)

# Histogram: tracks latency distribution, auto-calculates buckets
REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "Request latency in seconds",
    ["path"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

# Gauges: can go up or down, represent current state
UPTIME_GAUGE = Gauge(
    "app_uptime_seconds",
    "Seconds since app started"
)

MODE_GAUGE = Gauge(
    "app_mode",
    "Current deployment mode (0=stable, 1=canary)"
)

CHAOS_GAUGE = Gauge(
    "chaos_active",
    "Current chaos state (0=none, 1=slow, 2=error)"
)

# Set initial mode value immediately
MODE_GAUGE.set(1 if MODE == "canary" else 0)
CHAOS_GAUGE.set(0)

# ── request tracking middleware ───────────────────────────────────────────────

@app.before_request
def start_timer():
    # Store request start time in Flask's per-request context
    request._start_time = time.time()

@app.after_request
def track_metrics(response):
    # Calculate how long this request took
    duration = time.time() - request._start_time

    # Only track app routes, not /metrics itself
    if request.path != "/metrics":
        REQUEST_COUNTER.labels(
            method=request.method,
            path=request.path,
            status_code=str(response.status_code)
        ).inc()

        REQUEST_DURATION.labels(
            path=request.path
        ).observe(duration)

    # Update uptime gauge on every request
    UPTIME_GAUGE.set(time.time() - START_TIME)

    # Add headers
    if MODE == "canary":
        response.headers["X-Mode"] = "canary"
    response.headers["X-Deployed-By"] = "swiftdeploy"
    return response

# ── routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    with chaos_lock:
        state = chaos_state.copy()

    if state["mode"] == "slow" and MODE == "canary":
        time.sleep(state["duration"] or 0)
    if state["mode"] == "error" and MODE == "canary":
        if random.random() < (state["rate"] or 0):
            return jsonify({"error": "chaos-induced failure"}), 500

    return jsonify({
        "message": f"Welcome! Running in {MODE} mode.",
        "mode": MODE,
        "version": VERSION,
        "timestamp": time.time()
    })

@app.route("/healthz")
def healthz():
    return jsonify({
        "status": "ok",
        "uptime_seconds": round(time.time() - START_TIME, 2)
    })

@app.route("/chaos", methods=["POST"])
def chaos():
    if MODE != "canary":
        return jsonify({"error": "chaos only available in canary mode"}), 403

    body = request.get_json(force=True)
    mode = body.get("mode")

    with chaos_lock:
        if mode == "recover":
            chaos_state.update({"mode": None, "duration": None, "rate": None})
            CHAOS_GAUGE.set(0)
        elif mode == "slow":
            chaos_state.update({
                "mode": "slow",
                "duration": body.get("duration", 2),
                "rate": None
            })
            CHAOS_GAUGE.set(1)
        elif mode == "error":
            chaos_state.update({
                "mode": "error",
                "rate": body.get("rate", 0.5),
                "duration": None
            })
            CHAOS_GAUGE.set(2)
        else:
            return jsonify({"error": "unknown chaos mode"}), 400

    return jsonify({"chaos": chaos_state})

@app.route("/metrics")
def metrics():
    # Update uptime before serving metrics
    UPTIME_GAUGE.set(time.time() - START_TIME)
    # Return Prometheus text format
    return Response(generate_latest(REGISTRY), mimetype=CONTENT_TYPE_LATEST)

if __name__ == "__main__":
    port = int(os.environ.get("APP_PORT", 3000))
    app.run(host="0.0.0.0", port=port)
