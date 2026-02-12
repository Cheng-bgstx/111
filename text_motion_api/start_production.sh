#!/bin/bash

# Text-to-Motion API Gateway - Production Startup Script

# Load environment variables from .env file if it exists
if [ -f .env ]; then
    echo "Loading configuration from .env file..."
    export $(grep -v '^#' .env | xargs)
fi

# Default configuration
export PORT=${PORT:-8080}
export HOST=${HOST:-0.0.0.0}
export REMOTE_WS_HOST=${REMOTE_WS_HOST:-127.0.0.1}
export REMOTE_WS_PORT=${REMOTE_WS_PORT:-8000}
export REMOTE_WS_PATH=${REMOTE_WS_PATH:-/ws}
export DATA_RETENTION_MINUTES=${DATA_RETENTION_MINUTES:-30}
export CLEANUP_INTERVAL_MINUTES=${CLEANUP_INTERVAL_MINUTES:-5}
export MAX_STORED_MOTIONS_PER_USER=${MAX_STORED_MOTIONS_PER_USER:-10}
export MAX_REQUESTS_PER_MINUTE=${MAX_REQUESTS_PER_MINUTE:-10}
export ALLOWED_ORIGINS=${ALLOWED_ORIGINS:-*}

echo "=========================================="
echo "Text-to-Motion API Gateway (Production)"
echo "=========================================="
echo ""
echo "Configuration:"
echo "  Local API:     http://${HOST}:${PORT}"
echo "  Remote WS:     ws://${REMOTE_WS_HOST}:${REMOTE_WS_PORT}${REMOTE_WS_PATH}"
echo "  Data retention: ${DATA_RETENTION_MINUTES} minutes"
echo "  Max motions:   ${MAX_STORED_MOTIONS_PER_USER} per user"
echo "  Rate limit:    ${MAX_REQUESTS_PER_MINUTE} req/min"
echo ""
echo "Starting server with production settings..."
echo ""

# Run with uvicorn in production mode
# - More workers for better concurrency
# - No reload for stability
# - Larger timeout for long generation requests
exec uvicorn main:app \
    --host ${HOST} \
    --port ${PORT} \
    --workers 4 \
    --timeout-keep-alive 120 \
    --access-log \
    --proxy-headers
