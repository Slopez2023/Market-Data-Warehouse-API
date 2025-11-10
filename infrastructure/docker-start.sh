#!/bin/bash

##############################################################################
# Market Data API - Docker Startup & Management Script
#
# Usage: ./docker-start.sh [command]
#
# Commands:
#   up       - Start services (default)
#   down     - Stop services
#   logs     - Show logs
#   status   - Show status
#   test     - Run health checks
#   clean    - Remove stopped containers and images
#   reset    - Complete reset (WARNING: deletes data)
#
##############################################################################

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Helper functions
log() {
    echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}[$(date +'%H:%M:%S')] ✓ $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%H:%M:%S')] ✗ $1${NC}"
}

warning() {
    echo -e "${YELLOW}[$(date +'%H:%M:%S')] ⚠ $1${NC}"
}

##############################################################################
# Commands
##############################################################################

cmd_up() {
    log "Starting Market Data API services..."
    
    # Check .env file
    if [ ! -f .env ]; then
        error ".env file not found"
        log "Create it from .env.example:"
        log "  cp .env.example .env"
        log "  nano .env  # Edit with your API keys"
        exit 1
    fi
    
    # Check Docker daemon
    if ! docker info > /dev/null 2>&1; then
        error "Docker daemon is not running"
        exit 1
    fi
    
    success "Docker daemon is running"
    
    # Start services
    docker-compose up -d
    
    # Wait for database to be ready
    log "Waiting for database to be ready..."
    max_attempts=30
    attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if docker-compose exec -T timescaledb pg_isready -U postgres > /dev/null 2>&1; then
            success "Database is ready"
            break
        fi
        attempt=$((attempt + 1))
        echo -n "."
        sleep 1
    done
    
    if [ $attempt -eq $max_attempts ]; then
        error "Database failed to start after ${max_attempts}s"
        docker-compose logs timescaledb
        exit 1
    fi
    
    # Wait for API to be ready
    log "Waiting for API to be ready..."
    attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            success "API is ready"
            break
        fi
        attempt=$((attempt + 1))
        echo -n "."
        sleep 1
    done
    
    if [ $attempt -eq $max_attempts ]; then
        warning "API did not respond after ${max_attempts}s (check logs)"
    fi
    
    echo ""
    cmd_status
}

cmd_down() {
    log "Stopping Market Data API services..."
    docker-compose down
    success "Services stopped"
}

cmd_logs() {
    log "Showing logs (Ctrl+C to exit)..."
    docker-compose logs -f
}

cmd_status() {
    echo ""
    log "Service Status:"
    docker-compose ps
    
    echo ""
    log "API Endpoints:"
    echo "  Health:           http://localhost:8000/health"
    echo "  Status:           http://localhost:8000/api/v1/status"
    echo "  Documentation:    http://localhost:8000/docs"
    echo "  ReDoc:            http://localhost:8000/redoc"
    
    echo ""
    log "Testing API..."
    if curl -s http://localhost:8000/health > /dev/null; then
        success "API is responding"
        
        # Show health status
        echo ""
        log "Health Check:"
        curl -s http://localhost:8000/health | jq '.' 2>/dev/null || echo "  Could not parse response"
    else
        warning "API is not responding (check logs with: docker-compose logs api)"
    fi
    
    echo ""
}

cmd_test() {
    echo ""
    log "Running Health Checks..."
    
    # Check containers
    log "1. Container Status:"
    if docker-compose ps | grep -q "Up"; then
        success "Containers are running"
    else
        error "Not all containers are running"
        docker-compose ps
        exit 1
    fi
    
    # Check API
    log "2. API Health:"
    if curl -s http://localhost:8000/health | jq -e '.status == "healthy"' > /dev/null 2>&1; then
        success "API is healthy"
    else
        error "API health check failed"
        exit 1
    fi
    
    # Check database
    log "3. Database Connection:"
    if curl -s http://localhost:8000/api/v1/status | jq -e '.status == "healthy"' > /dev/null 2>&1; then
        success "Database is connected"
    else
        error "Database connection failed"
        exit 1
    fi
    
    # Check scheduler
    log "4. Scheduler Status:"
    if curl -s http://localhost:8000/health | jq -e '.scheduler_running == true' > /dev/null 2>&1; then
        success "Scheduler is running"
    else
        warning "Scheduler is not running"
    fi
    
    echo ""
    success "All health checks passed!"
    echo ""
}

cmd_clean() {
    log "Cleaning up stopped containers and unused images..."
    docker system prune -a -f
    success "Cleanup complete"
}

cmd_reset() {
    warning "DESTRUCTIVE OPERATION: This will delete all data!"
    read -p "Are you sure? Type 'yes' to confirm: " confirm
    
    if [ "$confirm" != "yes" ]; then
        log "Cancelled"
        exit 0
    fi
    
    log "Stopping services..."
    docker-compose down -v
    
    log "Removing all containers, images, and volumes..."
    docker system prune -a -f -v
    
    success "Complete reset finished"
}

cmd_help() {
    echo ""
    echo "Market Data API - Docker Management"
    echo ""
    echo "Usage: ./docker-start.sh [command]"
    echo ""
    echo "Commands:"
    echo "  up       - Start services (default)"
    echo "  down     - Stop services"
    echo "  logs     - Show logs (tail -f)"
    echo "  status   - Show status and test endpoints"
    echo "  test     - Run health checks"
    echo "  clean    - Remove stopped containers and images"
    echo "  reset    - Complete reset (WARNING: deletes all data)"
    echo ""
    echo "Examples:"
    echo "  ./docker-start.sh              # Start services"
    echo "  ./docker-start.sh status       # Check status"
    echo "  ./docker-start.sh logs         # Watch logs"
    echo ""
}

##############################################################################
# Main
##############################################################################

COMMAND=${1:-up}

case "$COMMAND" in
    up)
        cmd_up
        ;;
    down)
        cmd_down
        ;;
    logs)
        cmd_logs
        ;;
    status)
        cmd_status
        ;;
    test)
        cmd_test
        ;;
    clean)
        cmd_clean
        ;;
    reset)
        cmd_reset
        ;;
    help|--help|-h)
        cmd_help
        ;;
    *)
        error "Unknown command: $COMMAND"
        cmd_help
        exit 1
        ;;
esac
