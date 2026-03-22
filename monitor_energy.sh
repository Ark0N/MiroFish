#!/bin/bash
# MiroFish Energy Prediction Monitor
# Checks API availability, runs pipeline when ready, monitors continuously
#
# Usage: ./monitor_energy.sh [hours] [check_interval_minutes]
#   hours: how long to monitor (default: 10)
#   check_interval: minutes between API checks when waiting (default: 5)

set -euo pipefail

HOURS=${1:-10}
CHECK_INTERVAL=${2:-5}
BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$BASE_DIR/backend"
LOG_FILE="$BASE_DIR/energy_monitor.log"
MAX_ROUNDS=15
BASE_URL="http://localhost:5001"
END_TIME=$(($(date +%s) + HOURS * 3600))

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "$msg" | tee -a "$LOG_FILE"
}

check_api() {
    cd "$BACKEND_DIR"
    uv run python -c "
from dotenv import load_dotenv
import os, sys, anthropic
load_dotenv('../.env')
client = anthropic.Anthropic(api_key=os.environ['LLM_API_KEY'])
try:
    resp = client.messages.create(
        model=os.environ.get('LLM_MODEL_NAME','claude-haiku-4-5-20251001'),
        max_tokens=5, messages=[{'role':'user','content':'hi'}])
    print('OK')
except Exception as e:
    err = str(e).lower()
    if 'credit balance' in err:
        print('NO_CREDITS')
    elif 'authentication' in err:
        print('AUTH_FAIL')
    else:
        print('ERROR:' + str(e)[:150])
    sys.exit(1)
" 2>/dev/null || true
}

check_server() {
    curl -sf "$BASE_URL/health" > /dev/null 2>&1
}

start_server() {
    log "Starting backend server..."
    cd "$BACKEND_DIR"
    nohup uv run python run.py >> /tmp/mirofish-backend.log 2>&1 &
    local pid=$!
    log "Server started (PID: $pid)"
    sleep 5
    if check_server; then
        log "Server is healthy"
        return 0
    else
        log "ERROR: Server failed to start"
        return 1
    fi
}

run_pipeline() {
    log "=== STARTING ENERGY PREDICTION PIPELINE ==="
    cd "$BASE_DIR"

    # Run with output captured
    uv run python run_energy_prediction.py \
        --base-url "$BASE_URL" \
        --max-rounds "$MAX_ROUNDS" \
        --skip-server-check 2>&1 | tee -a "$LOG_FILE"

    local exit_code=${PIPESTATUS[0]}

    if [ $exit_code -eq 0 ]; then
        log "=== PIPELINE COMPLETED SUCCESSFULLY ==="
        return 0
    else
        log "=== PIPELINE FAILED (exit code: $exit_code) ==="
        return 1
    fi
}

# ── Main Loop ──

log "========================================"
log "MiroFish Energy Prediction Monitor"
log "========================================"
log "Duration: ${HOURS} hours (until $(date -d "@$END_TIME" '+%Y-%m-%d %H:%M:%S'))"
log "Check interval: ${CHECK_INTERVAL} minutes"
log "Max rounds: ${MAX_ROUNDS}"
log "Log file: ${LOG_FILE}"
log ""

PIPELINE_RUN_COUNT=0
PIPELINE_SUCCESS=false

while [ "$(date +%s)" -lt "$END_TIME" ]; do
    remaining=$(( (END_TIME - $(date +%s)) / 60 ))
    log "--- Check cycle (${remaining} minutes remaining) ---"

    # 1. Ensure server is running
    if ! check_server; then
        log "Server not running, starting it..."
        start_server || { log "Cannot start server, waiting..."; sleep $((CHECK_INTERVAL * 60)); continue; }
    fi

    # 2. Check API availability
    log "Checking LLM API credits..."
    api_result=$(check_api 2>&1 || true)

    if [ "$api_result" = "OK" ]; then
        log "API credits available!"

        # 3. Run pipeline
        PIPELINE_RUN_COUNT=$((PIPELINE_RUN_COUNT + 1))
        log "Pipeline run #${PIPELINE_RUN_COUNT}"

        if run_pipeline; then
            PIPELINE_SUCCESS=true
            log "Pipeline succeeded! Report should be available at $BASE_URL"

            # Check if report file was saved
            if [ -f "$BASE_DIR/energy_prediction_report.md" ]; then
                local_size=$(wc -c < "$BASE_DIR/energy_prediction_report.md")
                log "Report saved locally: energy_prediction_report.md (${local_size} bytes)"
            fi

            # After successful run, wait longer before next check
            log "Waiting 30 minutes before next monitoring cycle..."
            sleep 1800
        else
            log "Pipeline failed. Will retry in ${CHECK_INTERVAL} minutes..."
            sleep $((CHECK_INTERVAL * 60))
        fi
    elif [ "$api_result" = "NO_CREDITS" ]; then
        log "API: No credits available. Add credits at https://console.anthropic.com/settings/billing"
        log "API: Retrying in ${CHECK_INTERVAL} minutes..."
        sleep $((CHECK_INTERVAL * 60))
    elif [ "$api_result" = "AUTH_FAIL" ]; then
        log "API: Authentication failed. Check LLM_API_KEY in .env"
        sleep $((CHECK_INTERVAL * 60))
    else
        log "API: Unavailable - ${api_result:0:150}"
        sleep $((CHECK_INTERVAL * 60))
    fi
done

log ""
log "========================================"
log "Monitor session complete"
log "========================================"
log "Total pipeline runs: ${PIPELINE_RUN_COUNT}"
log "Last successful: ${PIPELINE_SUCCESS}"
log "Log saved to: ${LOG_FILE}"
