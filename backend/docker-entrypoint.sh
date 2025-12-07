#!/bin/bash

# Docker entrypoint script for Gen-BI backend
# Runs startup checks and then starts the application

set -e  # Exit on error

echo "========================================"
echo "Gen-BI Backend Starting..."
echo "========================================"
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored messages
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Change to app directory
cd /app

# Check if we should skip startup checks
SKIP_STARTUP_CHECKS=${SKIP_STARTUP_CHECKS:-false}

if [ "$SKIP_STARTUP_CHECKS" = "true" ]; then
    print_warning "SKIP_STARTUP_CHECKS is set to true, skipping startup checks"
else
    # Run startup checks
    print_info "Running startup checks..."
    echo ""
    
    if bash startup_checks.sh; then
        print_success "Startup checks completed successfully"
    else
        print_error "Startup checks failed"
        exit 1
    fi
fi

echo ""
echo "========================================"
echo "Installing chrome using kaleido_get_chrome"
echo "========================================"
echo ""

# Install Chrome for Kaleido
if kaleido_get_chrome; then
    print_success "Chrome installed successfully"
else
    print_error "Failed to install Chrome"
    exit 1
fi


echo ""
echo "========================================"
print_info "Starting FastAPI application..."
echo "========================================"
echo ""

# Get configuration from environment variables
HOST=${HOST:-0.0.0.0}
PORT=${PORT:-8016}
WORKERS=${WORKERS:-1}
RELOAD=${RELOAD:-false}

# Build uvicorn command
CMD="uvicorn app:app --host $HOST --port $PORT --loop asyncio"

# Add workers if specified and reload is false
if [ "$RELOAD" = "false" ] && [ "$WORKERS" -gt 1 ]; then
    CMD="$CMD --workers $WORKERS"
fi

# Add reload flag if specified
if [ "$RELOAD" = "true" ]; then
    CMD="$CMD --reload"
    print_warning "Running in RELOAD mode (development only)"
fi

print_info "Starting with command: $CMD"
echo ""

# Execute the command
exec $CMD
