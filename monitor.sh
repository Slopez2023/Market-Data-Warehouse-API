#!/bin/bash

##############################################################################
# Market Data API - Monitoring & Status Script
#
# Purpose: Real-time monitoring of API and database health
# Usage: ./monitor.sh
#
# Displays:
#   - Container status (health, uptime)
#   - API status (endpoints responding)
#   - Database metrics (records, validation rate, data freshness)
#   - Scheduler status (next backfill time)
#   - Storage usage (disk space, backup count)
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
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Configuration
API_URL="http://localhost:8000"
REFRESH_INTERVAL=5
BACKUP_DIR="/mnt/external-backup/market-data-backups"

##############################################################################
# Helper Functions
##############################################################################

clear_screen() {
    clear
}

print_header() {
    echo -e "${BOLD}${CYAN}╔════════════════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${CYAN}║${NC} ${BOLD}Market Data API - System Monitor${NC} ${CYAN}$(date '+%Y-%m-%d %H:%M:%S')${NC} ${BOLD}${CYAN}║${NC}"
    echo -e "${BOLD}${CYAN}╚════════════════════════════════════════════════════════════════════════════════════╝${NC}"
}

print_section() {
    echo ""
    echo -e "${BOLD}${BLUE}▶ $1${NC}"
}

status_ok() {
    echo -e "${GREEN}✓${NC} $1"
}

status_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

status_error() {
    echo -e "${RED}✗${NC} $1"
}

##############################################################################
# Container Status
##############################################################################

check_containers() {
    print_section "Container Status"
    
    # Check if docker-compose file exists
    if [ ! -f "docker-compose.yml" ]; then
        status_error "docker-compose.yml not found"
        return 1
    fi
    
    # Check each container
    local api_status=$(docker-compose ps -q api 2>/dev/null)
    local db_status=$(docker-compose ps -q timescaledb 2>/dev/null)
    
    if [ -z "$api_status" ] && [ -z "$db_status" ]; then
        status_error "No containers running"
        return 1
    fi
    
    # API Container
    if docker-compose ps api 2>/dev/null | grep -q "Up"; then
        local uptime=$(docker-compose ps api 2>/dev/null | grep api | awk '{print $(NF-1)" "$NF}')
        status_ok "API: Running ($uptime)"
    else
        status_error "API: Not running"
    fi
    
    # Database Container
    if docker-compose ps timescaledb 2>/dev/null | grep -q "Up"; then
        local uptime=$(docker-compose ps timescaledb 2>/dev/null | grep timescaledb | awk '{print $(NF-1)" "$NF}')
        status_ok "Database: Running ($uptime)"
    else
        status_error "Database: Not running"
    fi
}

##############################################################################
# API Health
##############################################################################

check_api_health() {
    print_section "API Health"
    
    # Try to connect
    if ! curl -s "$API_URL/health" > /dev/null 2>&1; then
        status_error "API not responding on $API_URL"
        return 1
    fi
    
    status_ok "API is responding"
    
    # Get health details
    local health=$(curl -s "$API_URL/health" 2>/dev/null)
    local scheduler=$(echo "$health" | jq -r '.scheduler_running' 2>/dev/null)
    local timestamp=$(echo "$health" | jq -r '.timestamp' 2>/dev/null)
    
    if [ "$scheduler" = "true" ]; then
        status_ok "Scheduler: Running"
    else
        status_warn "Scheduler: Not running"
    fi
    
    echo "  Last check: $timestamp"
}

##############################################################################
# Database Metrics
##############################################################################

check_database_metrics() {
    print_section "Database Metrics"
    
    # Get status from API
    local status=$(curl -s "$API_URL/api/v1/status" 2>/dev/null)
    
    if [ -z "$status" ]; then
        status_error "Could not fetch database metrics"
        return 1
    fi
    
    # Extract metrics
    local symbols=$(echo "$status" | jq -r '.database.symbols_available // 0')
    local records=$(echo "$status" | jq -r '.database.total_records // 0')
    local validated=$(echo "$status" | jq -r '.database.validation_rate_pct // 0')
    local latest=$(echo "$status" | jq -r '.database.latest_data // "N/A"')
    local gaps=$(echo "$status" | jq -r '.data_quality.records_with_gaps_flagged // 0')
    
    # Display metrics
    echo "  Symbols in database: $symbols"
    echo "  Total records: $(printf "%'d\n" "$records")"
    
    # Validation rate with color coding
    if (( $(echo "$validated >= 95" | bc -l) )); then
        status_ok "Validation rate: ${validated}%"
    elif (( $(echo "$validated >= 85" | bc -l) )); then
        status_warn "Validation rate: ${validated}%"
    else
        status_error "Validation rate: ${validated}%"
    fi
    
    echo "  Latest data: $latest"
    
    if [ "$gaps" -gt 0 ]; then
        status_warn "Records with gaps: $gaps"
    else
        status_ok "Records with gaps: 0"
    fi
}

##############################################################################
# Storage Usage
##############################################################################

check_storage() {
    print_section "Storage Usage"
    
    # Root filesystem
    local root_usage=$(df -h / | tail -1 | awk '{print $5}')
    local root_available=$(df -h / | tail -1 | awk '{print $4}')
    
    echo "  Root filesystem: $root_usage used ($root_available available)"
    
    # Docker volumes
    if command -v docker &> /dev/null; then
        local docker_usage=$(docker system df | grep "Local Volumes" | awk '{print $4}')
        if [ -n "$docker_usage" ]; then
            echo "  Docker volumes: $docker_usage"
        fi
    fi
    
    # Backup storage
    if [ -d "$BACKUP_DIR" ]; then
        local backup_count=$(ls -1 "$BACKUP_DIR"/market_data_*.sql.gz 2>/dev/null | wc -l)
        local backup_size=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)
        
        if [ "$backup_count" -gt 0 ]; then
            status_ok "Backups: $backup_count (${backup_size} total)"
            
            # Show latest backup
            local latest_backup=$(ls -t "$BACKUP_DIR"/market_data_*.sql.gz 2>/dev/null | head -1)
            if [ -n "$latest_backup" ]; then
                local backup_time=$(stat -f %Sm -t "%Y-%m-%d %H:%M:%S" "$latest_backup" 2>/dev/null)
                echo "  Latest: $backup_time"
            fi
        else
            status_warn "Backups: None found"
        fi
    else
        status_warn "Backup directory not found: $BACKUP_DIR"
    fi
}

##############################################################################
# Scheduler Status
##############################################################################

check_scheduler() {
    print_section "Scheduler Status"
    
    # Get API logs for scheduler info
    if [ -f ".env" ]; then
        local hour=$(grep BACKFILL_SCHEDULE_HOUR .env | cut -d= -f2 | tr -d ' ')
        local minute=$(grep BACKFILL_SCHEDULE_MINUTE .env | cut -d= -f2 | tr -d ' ')
        
        hour=${hour:-2}
        minute=${minute:-0}
        
        status_ok "Scheduled backfill: ${hour}:${minute} UTC daily"
    else
        status_warn "Could not read schedule from .env"
    fi
    
    # Check recent backfill attempts
    local recent_logs=$(docker-compose logs api 2>/dev/null | grep -i "backfill\|scheduler" | tail -5)
    
    if [ -n "$recent_logs" ]; then
        echo ""
        echo "  Recent activity:"
        echo "$recent_logs" | sed 's/^/    /'
    fi
}

##############################################################################
# System Performance
##############################################################################

check_performance() {
    print_section "System Performance"
    
    # CPU usage (containers only)
    local cpu=$(docker stats --no-stream 2>/dev/null | tail -2 | awk '{print $3}' | tr -d '%' | paste -sd+ | bc 2>/dev/null)
    if [ -n "$cpu" ]; then
        echo "  Container CPU: ${cpu}%"
    fi
    
    # Memory usage (containers only)
    local mem=$(docker stats --no-stream 2>/dev/null | tail -2 | awk '{print $7}' | tr -d '%' | paste -sd+ | bc 2>/dev/null)
    if [ -n "$mem" ]; then
        echo "  Container Memory: ${mem}%"
    fi
    
    # API response time
    local start_time=$(date +%s%N)
    curl -s "$API_URL/health" > /dev/null 2>&1
    local end_time=$(date +%s%N)
    local response_time=$(( (end_time - start_time) / 1000000 ))
    
    if [ "$response_time" -lt 100 ]; then
        status_ok "API response time: ${response_time}ms"
    elif [ "$response_time" -lt 500 ]; then
        status_warn "API response time: ${response_time}ms"
    else
        status_error "API response time: ${response_time}ms"
    fi
}

##############################################################################
# Error Log Summary
##############################################################################

check_errors() {
    print_section "Error Log Summary"
    
    # Get error count from API logs
    local error_count=$(docker-compose logs api 2>/dev/null | grep -i "error\|exception" | wc -l)
    
    if [ "$error_count" -eq 0 ]; then
        status_ok "No recent errors"
    else
        status_warn "Found $error_count recent errors"
        echo ""
        echo "  Recent errors:"
        docker-compose logs api 2>/dev/null | grep -i "error\|exception" | tail -3 | sed 's/^/    /'
    fi
}

##############################################################################
# Main Loop
##############################################################################

main() {
    while true; do
        clear_screen
        print_header
        
        check_containers
        check_api_health
        check_database_metrics
        check_storage
        check_scheduler
        check_performance
        check_errors
        
        echo ""
        echo -e "${BOLD}${CYAN}═════════════════════════════════════════════════════════════════════════════════════${NC}"
        echo "Press Ctrl+C to exit. Refreshing in ${REFRESH_INTERVAL}s..."
        
        sleep "$REFRESH_INTERVAL"
    done
}

# Run main loop
main
