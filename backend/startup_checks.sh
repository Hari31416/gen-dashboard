#!/bin/bash

# Startup script for Gen-BI backend
# Runs all necessary checks before starting the application

set -e  # Exit on error

echo "========================================"
echo "Gen-BI Backend Startup Checks"
echo "========================================"
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ️  $1${NC}"
}

# Change to backend directory if script is run from there
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Step 1: Check dependencies (MongoDB, Milvus, etc.)
print_info "Step 1: Checking service dependencies..."
if python check_dependencies.py; then
    print_success "All required services are running"
else
    print_error "Dependency check failed"
    exit 1
fi

echo ""

# Step 2: Setup admin user
print_info "Step 2: Setting up admin user..."
if python setup_admin_user.py; then
    print_success "Admin user setup completed"
else
    print_error "Admin user setup failed"
    exit 1
fi

echo ""

# Step 3: Setup MongoDB indexes for artifact storage
print_info "Step 3: Setting up MongoDB indexes for artifact storage..."
if [ "${ARTIFACT_STORAGE_ENABLED:-false}" = "true" ]; then
    if python setup_artifact_indexes.py; then
        print_success "Artifact storage indexes created"
    else
        print_error "Artifact index setup failed (non-critical)"
        # Don't exit - this is not critical for app startup
    fi
else
    print_info "Artifact storage disabled, skipping index setup"
fi

echo ""
echo "========================================"
print_success "All startup checks passed!"
echo "========================================"
echo ""

exit 0
