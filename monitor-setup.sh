#!/bin/bash

# Market Data API - Monitoring Setup Script
# This script creates monitoring infrastructure for the deployed API
# Run as: bash monitor-setup.sh

set -e

PROJECT_DIR="/opt/market-data-api"
USER=$(whoami)
HOME_DIR=$(eval echo ~$USER)
SCRIPT_DIR="$PROJECT_DIR/scripts"
MONITOR_SCRIPT="$HOME_DIR/monitor-api.sh"
LOG_FILE="$HOME_DIR/api-monitor.log"

echo "================================"
echo "Market Data API - Monitoring Setup"
echo "================================"
echo ""

# Check if project directory exists
if [ ! -d "$PROJECT_DIR" ]; then
    echo "❌ Error: Project directory not found at $PROJECT_DIR"
    exit 1
fi

echo "✓ Project directory found at $PROJECT_DIR"
echo ""

# Create scripts directory if needed
mkdir -p "$SCRIPT_DIR"

# Create main monitoring script
echo "Creating monitoring script at $MONITOR_SCRIPT..."
cat > "$MONITOR_SCRIPT" << 'EOF'
#!/bin/bash

# Market Data API Monitoring Script
# This script performs health checks and logs metrics

set -e

API_URL="http://localhost:8000"
LOG_FILE="$(dirname "$0")/api-monitor.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
PROJECT_DIR="/opt/market-data-api"

# Color codes for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo "[${TIMESTAMP}] $1" >> "$LOG_FILE"
    echo "$1"
}

# Error logging
error_log() {
    echo "[${TIMESTAMP}] ❌ ERROR: $1" >> "$LOG_FILE"
    echo -e "${RED}❌ ERROR: $1${NC}"
}

# Success logging
success_log() {
    echo "[${TIMESTAMP}] ✓ $1" >> "$LOG_FILE"
    echo -e "${GREEN}✓ $1${NC}"
}

# Check API health
check_health() {
    log ""
    log "=== API Health Check ==="
    
    if response=$(curl -s -w "\n%{http_code}" "$API_URL/health" 2>/dev/null); then
        http_code=$(echo "$response" | tail -n1)
        body=$(echo "$response" | head -n-1)
        
        if [ "$http_code" = "200" ]; then
            success_log "Health endpoint responding (HTTP 200)"
            echo "$body" | jq '.' >> "$LOG_FILE" 2>/dev/null || echo "$body" >> "$LOG_FILE"
        else
            error_log "Health endpoint returned HTTP $http_code"
        fi
    else
        error_log "Failed to connect to API"
    fi
}

# Check API status and metrics
check_status() {
    log ""
    log "=== API Status & Metrics ==="
    
    if response=$(curl -s "$API_URL/api/v1/status" 2>/dev/null); then
        if echo "$response" | jq . >/dev/null 2>&1; then
            success_log "Status endpoint responding"
            symbols=$(echo "$response" | jq -r '.symbols_available // "N/A"')
            validation=$(echo "$response" | jq -r '.validation_rate // "N/A"')
            total=$(echo "$response" | jq -r '.total_records // "N/A"')
            
            log "  - Symbols: $symbols"
            log "  - Validation Rate: $validation%"
            log "  - Total Records: $total"
        else
            error_log "Status endpoint returned invalid JSON"
            log "Response: $response"
        fi
    else
        error_log "Failed to reach status endpoint"
    fi
}

# Check database
check_database() {
    log ""
    log "=== Database Check ==="
    
    if ! command -v docker &> /dev/null; then
        log "Docker not found, skipping database check"
        return
    fi
    
    if docker-compose -f "$PROJECT_DIR/docker-compose.yml" ps timescaledb &>/dev/null; then
        if total=$(docker-compose -f "$PROJECT_DIR/docker-compose.yml" exec -T timescaledb \
            psql -U postgres -d market_data -t -c "SELECT COUNT(*) FROM market_data;" 2>/dev/null); then
            success_log "Database responding - $total total candles"
        else
            error_log "Database query failed"
        fi
    else
        error_log "TimescaleDB container not running"
    fi
}

# Check disk usage
check_disk() {
    log ""
    log "=== Disk Usage ==="
    
    usage=$(df -h "$PROJECT_DIR" | awk 'NR==2 {print $5}')
    available=$(df -h "$PROJECT_DIR" | awk 'NR==2 {print $4}')
    
    log "  - Disk Used: $usage"
    log "  - Available: $available"
    
    # Warn if >80% full
    usage_num="${usage%\%}"
    if [ "$usage_num" -gt 80 ]; then
        error_log "Disk usage high ($usage_num%)"
    fi
}

# Check system resources
check_resources() {
    log ""
    log "=== System Resources ==="
    
    # Memory
    mem_info=$(free -h | grep Mem)
    log "Memory: $(echo $mem_info | awk '{print $3 " / " $2}')"
    
    # CPU load
    load=$(uptime | awk -F'load average:' '{print $2}')
    log "Load Average:$load"
}

# Check recent logs for errors
check_logs() {
    log ""
    log "=== Recent Errors (last 24h) ==="
    
    api_log="$PROJECT_DIR/logs/api.log"
    if [ -f "$api_log" ]; then
        errors=$(grep -i "error\|exception" "$api_log" 2>/dev/null | tail -5 || echo "None")
        if [ "$errors" = "None" ]; then
            success_log "No recent errors in API logs"
        else
            log "Recent errors found:"
            echo "$errors" | sed 's/^/  - /' >> "$LOG_FILE"
        fi
    else
        log "API log not found at $api_log"
    fi
}

# Check service status
check_service() {
    log ""
    log "=== Service Status ==="
    
    if systemctl is-active --quiet market-data-api; then
        success_log "Systemd service running"
    else
        error_log "Systemd service not running"
        if command -v systemctl &> /dev/null; then
            systemctl status market-data-api >> "$LOG_FILE" 2>&1 || true
        fi
    fi
}

# Main execution
main() {
    echo "================================================"
    echo "Market Data API Monitoring - $(date)"
    echo "================================================"
    
    check_health
    check_status
    check_database
    check_disk
    check_resources
    check_logs
    check_service
    
    echo ""
    echo "Log saved to: $LOG_FILE"
    echo "================================================"
}

# Run main function
main
EOF

chmod +x "$MONITOR_SCRIPT"
success_log "Monitoring script created at $MONITOR_SCRIPT"
echo ""

# Create cron scheduling helper
echo "Setting up cron job scheduling..."
cat > "$SCRIPT_DIR/setup-cron.sh" << 'EOF'
#!/bin/bash
# Setup cron jobs for monitoring and backups

USER=$(whoami)
MONITOR_SCRIPT="$(eval echo ~$USER)/monitor-api.sh"
BACKUP_SCRIPT="/opt/market-data-api/backup.sh"

echo "Current cron jobs:"
crontab -l 2>/dev/null | grep -E "monitor|backup" || echo "None"
echo ""

read -p "Add monitoring job? (every hour at :00) [y/n] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    (crontab -l 2>/dev/null; echo "0 * * * * $MONITOR_SCRIPT") | crontab -
    echo "✓ Added hourly monitoring job"
fi

echo ""
read -p "Add backup job? (weekly Sunday 3 AM UTC) [y/n] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    (crontab -l 2>/dev/null; echo "0 3 * * 0 $BACKUP_SCRIPT") | crontab -
    echo "✓ Added weekly backup job"
fi

echo ""
echo "Final cron jobs:"
crontab -l 2>/dev/null | tail -5
EOF

chmod +x "$SCRIPT_DIR/setup-cron.sh"
echo "✓ Cron setup script created"
echo ""

# Create dashboard helper
echo "Creating monitoring dashboard helper..."
cat > "$SCRIPT_DIR/dashboard.sh" << 'EOF'
#!/bin/bash
# Simple real-time dashboard for API monitoring

clear

while true; do
    clear
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║          Market Data API - Live Monitoring                 ║"
    echo "║                    $(date '+%Y-%m-%d %H:%M:%S UTC')                ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""
    
    # Health status
    echo "📊 API Health:"
    curl -s http://localhost:8000/health 2>/dev/null | jq -r '"\(.status) - \(.timestamp)"' || echo "❌ Unreachable"
    echo ""
    
    # Metrics
    echo "📈 Metrics:"
    if response=$(curl -s http://localhost:8000/api/v1/status 2>/dev/null); then
        echo "$response" | jq -r '"  Symbols: \(.symbols_available // "N/A")
  Records: \(.total_records // "N/A")
  Validation: \(.validation_rate // "N/A")%
  Gaps Detected: \(.gap_detection_results // "N/A")"'
    else
        echo "  ❌ Status endpoint unreachable"
    fi
    echo ""
    
    # System stats
    echo "🖥️  System:"
    free -h | grep Mem | awk '{print "  Memory: " $3 " / " $2}'
    df -h / | tail -1 | awk '{print "  Disk: " $3 " / " $2 " (" $5 ")"}'
    echo ""
    
    # Service status
    echo "⚙️  Service:"
    if systemctl is-active --quiet market-data-api; then
        echo "  Status: ✓ Running"
        uptime_info=$(systemctl status market-data-api 2>/dev/null | grep "Active:" | sed 's/.*Active: /  /')
        echo "$uptime_info"
    else
        echo "  Status: ❌ Not running"
    fi
    echo ""
    
    echo "─────────────────────────────────────────────────────────────"
    echo "Press Ctrl+C to exit. Refreshing every 30 seconds..."
    sleep 30
done
EOF

chmod +x "$SCRIPT_DIR/dashboard.sh"
echo "✓ Dashboard script created"
echo ""

# Create weekly summary script
cat > "$SCRIPT_DIR/weekly-summary.sh" << 'EOF'
#!/bin/bash
# Generate weekly monitoring summary

PROJECT_DIR="/opt/market-data-api"
MONITOR_LOG="$(eval echo ~$(whoami))/api-monitor.log"
SUMMARY_FILE="$(eval echo ~$(whoami))/api-summary-$(date +%Y-W%V).txt"

echo "Generating weekly summary..."
echo "Market Data API - Weekly Summary" > "$SUMMARY_FILE"
echo "Week of $(date '+%Y-%m-%d')" >> "$SUMMARY_FILE"
echo "" >> "$SUMMARY_FILE"

if [ -f "$MONITOR_LOG" ]; then
    echo "Recent Checks:" >> "$SUMMARY_FILE"
    tail -50 "$MONITOR_LOG" >> "$SUMMARY_FILE"
fi

echo "Database Status:" >> "$SUMMARY_FILE"
docker-compose -f "$PROJECT_DIR/docker-compose.yml" exec -T timescaledb \
    psql -U postgres -d market_data -c "SELECT symbol, COUNT(*) as candles FROM market_data GROUP BY symbol ORDER BY candles DESC;" >> "$SUMMARY_FILE" 2>/dev/null || echo "Database unavailable" >> "$SUMMARY_FILE"

echo ""
echo "✓ Summary saved to $SUMMARY_FILE"
cat "$SUMMARY_FILE"
EOF

chmod +x "$SCRIPT_DIR/weekly-summary.sh"
echo "✓ Weekly summary script created"
echo ""

# Summary
echo "✅ Monitoring setup complete!"
echo ""
echo "Scripts created:"
echo "  • $MONITOR_SCRIPT - Run health checks"
echo "  • $SCRIPT_DIR/setup-cron.sh - Configure cron jobs"
echo "  • $SCRIPT_DIR/dashboard.sh - Live monitoring dashboard"
echo "  • $SCRIPT_DIR/weekly-summary.sh - Generate weekly report"
echo ""
echo "Next steps:"
echo "  1. Run monitoring test: $MONITOR_SCRIPT"
echo "  2. Setup cron jobs: bash $SCRIPT_DIR/setup-cron.sh"
echo "  3. View live dashboard: bash $SCRIPT_DIR/dashboard.sh"
echo ""
echo "Logs stored at: $LOG_FILE"
