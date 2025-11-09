#!/bin/bash

##############################################################################
# Market Data API - Database Backup Script
#
# Purpose: Automated weekly backup of TimescaleDB to external storage
# Schedule: Sunday 3 AM (add to crontab: 0 3 * * 0 /opt/market-data-api/backup.sh)
# Retention: Keep last 12 backups (~12 weeks)
#
# Configuration:
#   - Backup directory: /mnt/external-backup/market-data-backups
#   - Database: market_data (PostgreSQL in Docker)
#   - Format: Compressed SQL dump (gzip)
#   - Log file: /var/log/market-data-api-backup.log
#
##############################################################################

set -e

# Configuration
BACKUP_DIR="/mnt/external-backup/market-data-backups"
DB_NAME="market_data"
DB_CONTAINER="timescaledb"  # Docker container name from docker-compose.yml
DB_USER="postgres"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="/var/log/market-data-api-backup.log"
PROJECT_DIR="/opt/market-data-api"

# Color output (for terminal viewing)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    local level=$1
    shift
    local message="$@"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "[${timestamp}] [${level}] ${message}" | tee -a "$LOG_FILE"
}

# Error handling
error_exit() {
    log "ERROR" "${RED}$1${NC}"
    exit 1
}

success() {
    log "INFO" "${GREEN}$1${NC}"
}

warning() {
    log "WARN" "${YELLOW}$1${NC}"
}

##############################################################################
# Main Backup Process
##############################################################################

log "INFO" "==============================================="
log "INFO" "Market Data API - Backup Started"
log "INFO" "==============================================="

# Check if backup directory exists and is writable
if [ ! -d "$BACKUP_DIR" ]; then
    warning "Backup directory does not exist: $BACKUP_DIR"
    log "INFO" "Creating backup directory..."
    mkdir -p "$BACKUP_DIR" || error_exit "Failed to create backup directory"
fi

if [ ! -w "$BACKUP_DIR" ]; then
    error_exit "Backup directory is not writable: $BACKUP_DIR"
fi

# Verify Docker container is running
if ! docker ps | grep -q "$DB_CONTAINER"; then
    error_exit "Database container '$DB_CONTAINER' is not running. Start with: docker-compose up -d"
fi

success "Database container is running"

# Load .env variables if available
if [ -f "$PROJECT_DIR/.env" ]; then
    export $(grep -v '^#' "$PROJECT_DIR/.env" | xargs)
    log "INFO" "Loaded configuration from $PROJECT_DIR/.env"
else
    warning "Configuration file not found: $PROJECT_DIR/.env"
fi

# Perform backup
BACKUP_FILE="$BACKUP_DIR/market_data_$TIMESTAMP.sql.gz"

log "INFO" "Starting database dump..."
log "INFO" "Output file: $BACKUP_FILE"

if docker exec \
    -e PGPASSWORD="${DB_PASSWORD}" \
    "$DB_CONTAINER" \
    pg_dump -h localhost -U "$DB_USER" "$DB_NAME" | \
    gzip > "$BACKUP_FILE" 2>/dev/null; then
    
    # Get file size
    FILE_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    success "Backup completed: $FILE_SIZE"
    
    # Verify backup integrity
    if gzip -t "$BACKUP_FILE" 2>/dev/null; then
        success "Backup integrity verified"
    else
        error_exit "Backup file is corrupted"
    fi
    
else
    error_exit "Failed to create database dump"
fi

##############################################################################
# Backup Retention Policy
##############################################################################

log "INFO" "Applying retention policy (keep last 12 backups)..."

cd "$BACKUP_DIR" || error_exit "Cannot change to backup directory"

# Count existing backups
TOTAL_BACKUPS=$(ls -1 market_data_*.sql.gz 2>/dev/null | wc -l)
log "INFO" "Total backups: $TOTAL_BACKUPS"

# Delete older backups if we have more than 12
if [ "$TOTAL_BACKUPS" -gt 12 ]; then
    log "INFO" "Removing old backups (keeping last 12)..."
    ls -1t market_data_*.sql.gz | tail -n +13 | while read file; do
        log "INFO" "Deleting old backup: $file"
        rm -f "$file"
    done
    success "Old backups removed"
fi

##############################################################################
# Cleanup & Reporting
##############################################################################

# List all current backups
log "INFO" "Current backups:"
ls -lh market_data_*.sql.gz | awk '{print "  " $9 " (" $5 ")"}'

# Calculate total backup size
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
log "INFO" "Total backup storage: $TOTAL_SIZE"

##############################################################################
# Optional: Upload to Remote Storage (Future Enhancement)
##############################################################################

# Example: Uncomment to enable S3 upload
# if [ -n "$AWS_S3_BUCKET" ]; then
#     log "INFO" "Uploading backup to S3: $AWS_S3_BUCKET"
#     aws s3 cp "$BACKUP_FILE" "s3://$AWS_S3_BUCKET/market-data-backups/"
#     success "Backup uploaded to S3"
# fi

##############################################################################
# Summary
##############################################################################

log "INFO" "==============================================="
success "Backup job completed successfully"
log "INFO" "  Timestamp: $TIMESTAMP"
log "INFO" "  File: $BACKUP_FILE"
log "INFO" "  Size: $FILE_SIZE"
log "INFO" "  Total backups: $(ls -1 market_data_*.sql.gz 2>/dev/null | wc -l)"
log "INFO" "  Storage: $TOTAL_SIZE"
log "INFO" "==============================================="

exit 0
