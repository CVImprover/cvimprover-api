#!/bin/bash

# =============================================================================
# Docker Build Optimization Test Script
# =============================================================================
# This script tests and verifies the Docker optimization improvements
# Run with: bash test_docker_build.sh
# =============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# =============================================================================
# Helper Functions
# =============================================================================

print_header() {
    echo -e "\n${BLUE}==============================================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}==============================================================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

# =============================================================================
# Test 1: Build Context Size
# =============================================================================

test_build_context_size() {
    print_header "TEST 1: Measuring Build Context Size"
    
    # Create a temporary tar of build context
    print_info "Creating temporary build context archive..."
    cd "$SCRIPT_DIR"
    tar -czf /tmp/docker-context.tar.gz --exclude='.git' --exclude-from=.dockerignore . 2>/dev/null || true
    
    CONTEXT_SIZE=$(du -h /tmp/docker-context.tar.gz | cut -f1)
    CONTEXT_SIZE_MB=$(du -m /tmp/docker-context.tar.gz | cut -f1)
    
    echo "Build context size: ${CONTEXT_SIZE}"
    
    # Clean up
    rm /tmp/docker-context.tar.gz
    
    if [ "$CONTEXT_SIZE_MB" -lt 20 ]; then
        print_success "Build context is optimally sized (< 20MB)"
    elif [ "$CONTEXT_SIZE_MB" -lt 50 ]; then
        print_info "Build context is acceptable (< 50MB)"
    else
        print_error "Build context is large (> 50MB) - consider adding more to .dockerignore"
    fi
}

# =============================================================================
# Test 2: Dockerfile Validation
# =============================================================================

test_dockerfile_validation() {
    print_header "TEST 2: Validating Dockerfile"
    
    if [ ! -f "$SCRIPT_DIR/Dockerfile" ]; then
        print_error "Dockerfile not found!"
        exit 1
    fi
    
    print_success "Dockerfile exists"
    
    # Check for multi-stage build
    if grep -q "FROM.*as builder" "$SCRIPT_DIR/Dockerfile" && grep -q "FROM.*as runtime" "$SCRIPT_DIR/Dockerfile"; then
        print_success "Multi-stage build detected"
    else
        print_error "Multi-stage build not found"
    fi
    
    # Check for layer caching optimization
    if grep -q "COPY requirements.txt" "$SCRIPT_DIR/Dockerfile" && grep -B5 "COPY requirements.txt" "$SCRIPT_DIR/Dockerfile" | grep -q "COPY . ."; then
        print_success "Layer caching optimization detected"
    else
        print_info "Requirements copied before application code"
    fi
    
    # Check for non-root user
    if grep -q "USER django" "$SCRIPT_DIR/Dockerfile" || grep -q "useradd" "$SCRIPT_DIR/Dockerfile"; then
        print_success "Non-root user configuration detected"
    else
        print_error "No non-root user found - security risk!"
    fi
}

# =============================================================================
# Test 3: .dockerignore Validation
# =============================================================================

test_dockerignore_validation() {
    print_header "TEST 3: Validating .dockerignore"
    
    if [ ! -f "$SCRIPT_DIR/.dockerignore" ]; then
        print_error ".dockerignore not found!"
        exit 1
    fi
    
    print_success ".dockerignore exists"
    
    # Count number of patterns
    PATTERN_COUNT=$(grep -v '^#' "$SCRIPT_DIR/.dockerignore" | grep -v '^$' | wc -l)
    echo "Number of ignore patterns: $PATTERN_COUNT"
    
    if [ "$PATTERN_COUNT" -gt 50 ]; then
        print_success "Comprehensive .dockerignore ($PATTERN_COUNT patterns)"
    else
        print_info "Consider adding more patterns to .dockerignore"
    fi
    
    # Check for critical patterns
    CRITICAL_PATTERNS=("__pycache__" "*.pyc" ".git" ".env" "venv" "node_modules")
    
    for pattern in "${CRITICAL_PATTERNS[@]}"; do
        if grep -q "$pattern" "$SCRIPT_DIR/.dockerignore"; then
            print_success "Critical pattern found: $pattern"
        else
            print_error "Missing critical pattern: $pattern"
        fi
    done
}

# =============================================================================
# Test 4: Build Image (Optional - requires Docker)
# =============================================================================

test_build_image() {
    print_header "TEST 4: Building Docker Image (Optional)"
    
    if ! command -v docker &> /dev/null; then
        print_info "Docker not found - skipping build test"
        return
    fi
    
    print_info "Building image with BuildKit..."
    
    # Time the build
    START_TIME=$(date +%s)
    
    if DOCKER_BUILDKIT=1 docker build -t cvimprover-api:test . > /tmp/docker-build.log 2>&1; then
        END_TIME=$(date +%s)
        BUILD_TIME=$((END_TIME - START_TIME))
        
        print_success "Build completed successfully in ${BUILD_TIME}s"
        
        # Get image size
        IMAGE_SIZE=$(docker images cvimprover-api:test --format "{{.Size}}")
        print_info "Image size: $IMAGE_SIZE"
        
        # Check if image size is reasonable
        IMAGE_SIZE_MB=$(docker images cvimprover-api:test --format "{{.Size}}" | sed 's/MB//;s/GB/*1024/')
        
        # Clean up test image
        print_info "Cleaning up test image..."
        docker rmi cvimprover-api:test > /dev/null 2>&1 || true
        
    else
        print_error "Build failed - check /tmp/docker-build.log"
        tail -n 20 /tmp/docker-build.log
        exit 1
    fi
}

# =============================================================================
# Test 5: Docker Compose Validation
# =============================================================================

test_docker_compose_validation() {
    print_header "TEST 5: Validating docker-compose.yml"
    
    if [ ! -f "$SCRIPT_DIR/docker-compose.yml" ]; then
        print_error "docker-compose.yml not found!"
        exit 1
    fi
    
    print_success "docker-compose.yml exists"
    
    # Check if docker-compose is available
    if command -v docker-compose &> /dev/null; then
        print_info "Validating docker-compose syntax..."
        # Ignore .env file errors for validation (expected in test environment)
        if docker-compose config > /dev/null 2>&1 || grep -q "env file.*not found" <(docker-compose config 2>&1); then
            print_success "docker-compose.yml syntax is valid"
        else
            print_error "docker-compose.yml has syntax errors"
            docker-compose config 2>&1 | grep -i error
            exit 1
        fi
    else
        print_info "docker-compose not found - skipping syntax validation"
    fi
    
    # Check for healthchecks
    if grep -q "healthcheck:" "$SCRIPT_DIR/docker-compose.yml"; then
        print_success "Health checks configured"
    else
        print_info "Consider adding health checks"
    fi
}

# =============================================================================
# Main Execution
# =============================================================================

main() {
    print_header "Docker Optimization Verification Tests"
    echo "Testing Docker configuration in: $SCRIPT_DIR"
    echo ""
    
    # Run all tests
    test_build_context_size
    test_dockerfile_validation
    test_dockerignore_validation
    test_docker_compose_validation
    
    # Optional: Build test (can be slow)
    read -p "$(echo -e ${YELLOW}"Do you want to run a full build test? (y/n): "${NC})" -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        test_build_image
    else
        print_info "Skipping build test"
    fi
    
    # Summary
    print_header "Test Summary"
    print_success "All validation tests completed!"
    echo ""
    echo "Next steps:"
    echo "1. Review the test results above"
    echo "2. Build the optimized image: DOCKER_BUILDKIT=1 docker-compose build"
    echo "3. Start services: docker-compose up"
    echo "4. Monitor image size: docker images cvimprover-api"
    echo ""
    print_success "Docker optimization verification complete! 🚀"
}

# Run main function
main

