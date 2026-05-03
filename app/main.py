import os, time, random, threading
from flask import Flask, request, jsonify, g

app = Flask(__name__)
START_TIME = time.time()
MODE = os.environ.get("MODE", "stable")
VERSION = os.environ.get("APP_VERSION", "1.0.0")

# Chaos state — shared across requests
chaos_state = {"mode": None, "duration": None, "rate": None}
chaos_lock = threading.Lock()

def add_mode_header(response):
    """Add X-Mode: canary header on every response when in canary mode."""
    if MODE == "canary":
        response.headers["X-Mode"] = "canary"
    response.headers["X-Deployed-By"] = "swiftdeploy"
    return response

app.after_request(add_mode_header)

@app.route("/")
def index():
    # Apply chaos if active
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
    # Only active in canary mode
    if MODE != "canary":
        return jsonify({"error": "chaos only available in canary mode"}), 403

    body = request.get_json(force=True)
    mode = body.get("mode")

    with chaos_lock:
        if mode == "recover":
            chaos_state.update({"mode": None, "duration": None, "rate": None})
        elif mode == "slow":
            chaos_state.update({"mode": "slow", "duration": body.get("duration", 2), "rate": None})
        elif mode == "error":
            chaos_state.update({"mode": "error", "rate": body.get("rate", 0.5), "duration": None})
        else:
            return jsonify({"error": "unknown chaos mode"}), 400

    return jsonify({"chaos": chaos_state})

if __name__ == "__main__":
    port = int(os.environ.get("APP_PORT", 3000))
    app.run(host="0.0.0.0", port=port)
