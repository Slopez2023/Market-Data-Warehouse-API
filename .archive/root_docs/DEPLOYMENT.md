# Deployment Guide

## Port Configuration

This application uses standardized ports that work across all deployment scenarios.

### Default Ports
- **API**: `8000` (HTTP)
- **Database**: `5432` (PostgreSQL)
- **Dashboard**: Served at `http://localhost:8000/dashboard/`

## Quick Start (Docker)

```bash
# 1. Copy environment template
cp .env.example .env

# 2. Set required values
export POLYGON_API_KEY=pk_your_key_here
export DB_PASSWORD=secure_password_here

# 3. Start services
docker-compose up -d

# 4. Access
- Dashboard: http://localhost:8000/dashboard/
- API Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health
```

## Local Development

### Prerequisites
- Python 3.11+
- PostgreSQL 12+

### Setup

```bash
# 1. Copy environment
cp .env.example .env

# 2. Edit .env with local values
export DATABASE_URL=postgresql://user:pass@localhost:5432/market_data
export POLYGON_API_KEY=pk_your_key_here

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run migrations (automatic on startup)

# 5. Start API
python main.py

# 6. Access
- Dashboard: http://localhost:8000/dashboard/
- API Docs: http://localhost:8000/docs
```

## Reverse Proxy Setup (Nginx)

If running behind Nginx on a different port:

```nginx
server {
    listen 80;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Access dashboard at: `http://api.yourdomain.com/dashboard/`

## Reverse Proxy with Custom API Port

If API is on different host/port than dashboard:

```
http://yourdomain.com/dashboard/?api_base=http://api.yourdomain.com:9000
```

The `?api_base=` parameter overrides the default origin detection.

## Production Environment

Key variables for production:

```bash
# .env
API_HOST=0.0.0.0          # Listen on all interfaces
API_PORT=8000              # Standard port
API_WORKERS=8              # Increase for more throughput
LOG_LEVEL=WARNING          # Reduce verbose logging
DATABASE_URL=postgresql://... # Use managed database
POLYGON_API_KEY=pk_...     # Your Polygon API key
ALERT_EMAIL_ENABLED=true   # Enable monitoring
ALERT_EMAIL_TO=admin@...   # Alert recipient
```

## Port Debugging

If dashboard can't connect to API:

1. **Check API is running**:
   ```bash
   curl http://localhost:8000/health
   ```

2. **Check CORS headers**:
   ```bash
   curl -i http://localhost:8000/health
   ```
   Look for `Access-Control-Allow-Origin: *`

3. **Check dashboard config**:
   - Open browser console (F12)
   - Check `CONFIG.API_BASE` value
   - Verify it matches actual API URL

4. **Override API base if needed**:
   ```
   http://localhost:8000/dashboard/?api_base=http://actual-api-host:8000
   ```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Dashboard shows "Offline" | Check API health at `/health` |
| API_PORT env ignored | Ensure it's in `.env` before app starts |
| Database connection fails | Verify `DATABASE_URL` format |
| CORS errors in console | API must allow requests from dashboard origin |
| Port already in use | Change `API_PORT` or kill process on port |

## Health Endpoints

- `GET /health` - Quick health check
- `GET /api/v1/status` - Full system status with metrics
- `GET /api/v1/metrics` - Detailed monitoring data
