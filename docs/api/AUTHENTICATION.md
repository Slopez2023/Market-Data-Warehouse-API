# API Key Management & Authentication

Complete guide to managing API keys and authenticating requests in the Market Data API.

---

## Overview

The Market Data API uses API key authentication for protected endpoints. All admin endpoints (key management, symbol management) require a valid API key.

**Key Features**:
- ✅ Create and manage API keys
- ✅ Audit logging of all API key operations
- ✅ Key revocation and restoration
- ✅ Rate limiting and request tracking
- ✅ Secure key storage with hashing

---

## Creating API Keys

### Bootstrap API Key

When you first set up the database, a bootstrap admin API key is created:

```bash
python scripts/bootstrap_db.py
```

Output:
```
3️⃣  Generating initial admin API key...
✅ Initial API key generated
   Key preview: mdw_abc123def...
   Full key: mdw_abc123def456...
   ⚠️  Save this key securely! It will not be shown again.
```

**⚠️ Important**: Save this key in a secure location. It cannot be retrieved again.

### Creating Additional Keys via API

```bash
curl -X POST http://localhost:8000/api/v1/admin/api-keys \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "my-app-key"}'
```

Response:
```json
{
  "status": "success",
  "data": {
    "id": "key_uuid_here",
    "name": "my-app-key",
    "key_preview": "mdw_abc123...",
    "full_key": "mdw_abc123def456...",
    "created_at": "2025-11-10T14:00:00Z"
  }
}
```

---

## Using API Keys

### Adding to Request Headers

Include the API key in the `X-API-Key` header:

```bash
export API_KEY="mdw_your_key_here"

curl -H "X-API-Key: $API_KEY" \
  http://localhost:8000/api/v1/admin/api-keys
```

### Python Example

```python
import requests

headers = {
    "X-API-Key": "mdw_your_key_here",
    "Content-Type": "application/json"
}

response = requests.get(
    "http://localhost:8000/api/v1/admin/api-keys",
    headers=headers
)

print(response.json())
```

### JavaScript Example

```javascript
const apiKey = "mdw_your_key_here";

const response = await fetch(
  "http://localhost:8000/api/v1/admin/api-keys",
  {
    headers: {
      "X-API-Key": apiKey,
      "Content-Type": "application/json"
    }
  }
);

const data = await response.json();
console.log(data);
```

---

## API Key Operations

### List All Keys

```bash
curl -H "X-API-Key: $API_KEY" \
  http://localhost:8000/api/v1/admin/api-keys
```

Response:
```json
{
  "status": "success",
  "data": [
    {
      "id": "key_uuid",
      "name": "admin-key",
      "key_preview": "mdw_abc123...",
      "active": true,
      "created_at": "2025-11-10T12:00:00Z",
      "last_used": "2025-11-10T14:00:00Z",
      "usage_count": 42
    }
  ]
}
```

### View Audit Log

See all operations on a specific API key:

```bash
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/api/v1/admin/api-keys/{key_id}/audit?limit=20&offset=0"
```

Response:
```json
{
  "status": "success",
  "data": [
    {
      "id": "audit_uuid",
      "key_id": "key_uuid",
      "action": "create",
      "details": {
        "name": "admin-key"
      },
      "timestamp": "2025-11-10T12:00:00Z"
    },
    {
      "id": "audit_uuid_2",
      "key_id": "key_uuid",
      "action": "use",
      "details": {
        "endpoint": "/api/v1/admin/api-keys",
        "method": "GET"
      },
      "timestamp": "2025-11-10T14:00:00Z"
    }
  ],
  "pagination": {
    "total": 15,
    "limit": 20,
    "offset": 0
  }
}
```

### Revoke a Key

Temporarily disable a key without deleting it:

```bash
curl -X PUT http://localhost:8000/api/v1/admin/api-keys/{key_id} \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"active": false}'
```

Response:
```json
{
  "status": "success",
  "data": {
    "id": "key_uuid",
    "name": "my-app-key",
    "active": false,
    "revoked_at": "2025-11-10T14:00:00Z"
  }
}
```

**Note**: Revoked keys cannot be used for authentication but can be restored.

### Restore a Revoked Key

Re-enable a previously revoked key:

```bash
curl -X PUT http://localhost:8000/api/v1/admin/api-keys/{key_id} \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"active": true}'
```

### Delete a Key

Permanently delete a key:

```bash
curl -X DELETE http://localhost:8000/api/v1/admin/api-keys/{key_id} \
  -H "X-API-Key: $API_KEY"
```

Response:
```json
{
  "status": "success",
  "message": "API key deleted successfully"
}
```

**⚠️ Warning**: Deletion is permanent and cannot be undone.

---

## Protected Endpoints

The following endpoints require authentication:

### API Key Management
- `POST /api/v1/admin/api-keys` - Create key
- `GET /api/v1/admin/api-keys` - List keys
- `GET /api/v1/admin/api-keys/{id}/audit` - View audit log
- `PUT /api/v1/admin/api-keys/{id}` - Revoke/restore key
- `DELETE /api/v1/admin/api-keys/{id}` - Delete key

### Symbol Management
- `POST /api/v1/admin/symbols` - Add symbol
- `GET /api/v1/admin/symbols` - List symbols with stats
- `PUT /api/v1/admin/symbols/{id}` - Update symbol
- `DELETE /api/v1/admin/symbols/{id}` - Delete symbol

### Performance Monitoring
- `GET /api/v1/performance/cache-stats` - Cache statistics
- `GET /api/v1/performance/bottlenecks` - Bottleneck detection

### Observability
- `GET /api/v1/observability/metrics` - System metrics
- `GET /api/v1/observability/alerts` - Alert history

---

## Public Endpoints (No Auth Required)

These endpoints don't require authentication:

```bash
# Health check
curl http://localhost:8000/api/v1/status

# Get symbols
curl http://localhost:8000/api/v1/symbols

# Get tickers
curl http://localhost:8000/api/v1/tickers

# Get market data
curl "http://localhost:8000/api/v1/bars?symbol=AAPL&limit=10"
```

---

## Security Best Practices

### 1. Secure Key Storage
- ❌ Don't hardcode keys in source code
- ✅ Use environment variables
- ✅ Use secret management (AWS Secrets Manager, HashiCorp Vault, etc.)
- ✅ Store in `.env` file (never commit to git)

### 2. Key Rotation
- Rotate keys regularly (monthly recommended)
- Create new key, test it
- Update applications to use new key
- Revoke old key
- Monitor audit logs for old key usage

### 3. Least Privilege
- Create separate keys for different applications
- Each app gets only the permissions it needs
- Revoke keys that are no longer used

### 4. Audit Logging
- Monitor audit logs regularly
- Alert on unusual activity
- Check for keys with high usage
- Verify expected endpoints are being called

### 5. Secure Transport
- Always use HTTPS in production
- Never send keys in URLs
- Always use `X-API-Key` header
- Enable CORS only for trusted domains

---

## Common Scenarios

### Scenario 1: Rotate API Key

```bash
# 1. Create new key
NEW_KEY=$(curl -s -X POST http://localhost:8000/api/v1/admin/api-keys \
  -H "X-API-Key: $OLD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "rotated-key"}' | jq -r '.data.full_key')

echo "New key: $NEW_KEY"

# 2. Test new key
curl -H "X-API-Key: $NEW_KEY" \
  http://localhost:8000/api/v1/status

# 3. Update applications to use new key
# (Update in your app code/config)

# 4. Verify old key is no longer needed by checking audit logs
curl -H "X-API-Key: $NEW_KEY" \
  "http://localhost:8000/api/v1/admin/api-keys/{old_key_id}/audit"

# 5. Revoke old key
curl -X PUT http://localhost:8000/api/v1/admin/api-keys/{old_key_id} \
  -H "X-API-Key: $NEW_KEY" \
  -H "Content-Type: application/json" \
  -d '{"active": false}'
```

### Scenario 2: Monitor Key Usage

```bash
# View audit log for specific key
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/api/v1/admin/api-keys/{key_id}/audit?limit=50"

# Check which endpoints are being used
# (Look at "endpoint" field in audit log)

# Look for unexpected activity
```

### Scenario 3: Create Per-App Keys

```bash
# Create key for app 1
curl -X POST http://localhost:8000/api/v1/admin/api-keys \
  -H "X-API-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "app-1-trading"}' \
  | jq -r '.data.full_key'

# Create key for app 2
curl -X POST http://localhost:8000/api/v1/admin/api-keys \
  -H "X-API-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "app-2-analytics"}' \
  | jq -r '.data.full_key'

# Each app uses its own key
# Monitor each key separately via audit logs
```

---

## Error Codes

| Code | Status | Meaning | Solution |
|------|--------|---------|----------|
| `AUTH_001` | 401 | Invalid API key | Check key format and validity |
| `AUTH_002` | 401 | Key not found | Verify key exists and hasn't been deleted |
| `AUTH_003` | 401 | Key is revoked | Restore key or create new one |
| `AUTH_004` | 403 | Insufficient permissions | Use admin key for admin endpoints |
| `KEY_001` | 409 | Key name already exists | Use unique name |
| `KEY_002` | 400 | Invalid key format | Key should start with "mdw_" |

---

## Troubleshooting

### Key Not Working
1. Check key format (should start with `mdw_`)
2. Verify key hasn't been revoked: check audit log
3. Check key exists: list all keys
4. Try creating new key

### Can't List Keys
1. Check API key is correct
2. Verify API key is active (not revoked)
3. Check X-API-Key header is spelled correctly
4. Try using curl directly to test

### Audit Log Empty
- Newly created keys won't have audit history
- Only operations after creation are logged
- Check database for data

---

## API Reference

### Create API Key
```
POST /api/v1/admin/api-keys
X-API-Key: <admin_key>
Content-Type: application/json

{
  "name": "key-name"
}
```

### List API Keys
```
GET /api/v1/admin/api-keys
X-API-Key: <admin_key>
```

### Get Audit Log
```
GET /api/v1/admin/api-keys/{key_id}/audit?limit=20&offset=0
X-API-Key: <admin_key>
```

### Revoke/Restore Key
```
PUT /api/v1/admin/api-keys/{key_id}
X-API-Key: <admin_key>
Content-Type: application/json

{
  "active": false  // or true to restore
}
```

### Delete Key
```
DELETE /api/v1/admin/api-keys/{key_id}
X-API-Key: <admin_key>
```

---

## Next Steps

- [Symbols Management](/docs/api/SYMBOLS.md) - Managing market symbols
- [Cryptocurrency](/docs/api/CRYPTO.md) - Working with crypto assets
- [Endpoints Reference](/docs/api/ENDPOINTS.md) - All API endpoints
- [Deployment Guide](/docs/operations/DEPLOYMENT.md) - Production setup

---

**Status**: Production Ready ✅  
**Last Updated**: November 10, 2025  
**Tests Passing**: 70 (API Key Management)
