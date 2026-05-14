# Redis Troubleshooting

## Overview
CloudDesk uses three Redis instances: `redis-cache` (project-service cache), `redis-session` (auth-service sessions), and `redis-queue` (notification-service queue). Each has different failure modes.

## Common Issues

### High Memory Usage
- **Symptom:** Redis memory approaching `maxmemory` limit
- **Investigation:**
  1. Check which keys are consuming the most memory
  2. Check if eviction policy is set correctly (`allkeys-lru` for cache, `noeviction` for queue)
  3. Check for key expiry — are TTLs set on all cache keys?
- **Fix:**
  - Cache: Increase maxmemory or reduce TTL
  - Queue: Check if consumers are keeping up — a growing queue means consumers are slow
  - Session: Check for session leak — are sessions being invalidated on logout?

### Connection Refused
- **Symptom:** Services get "Connection refused" or "Connection reset" errors to Redis
- **Possible causes:**
  1. Redis process crashed (check if running)
  2. Max connections reached (default 10000)
  3. Network issue between service and Redis
- **Fix:** Restart Redis if crashed, increase maxclients if connection limit hit

### Slow Operations
- **Symptom:** Redis operations taking >10ms (should be <1ms)
- **Possible causes:**
  1. Running expensive commands (KEYS *, SMEMBERS on large sets)
  2. Memory swapping (Redis process exceeding physical memory)
  3. Background save (BGSAVE) running
- **Fix:** Replace KEYS with SCAN, increase memory, schedule BGSAVE during low traffic

### Queue Backlog (redis-queue)
- **Symptom:** Notification queue length growing, notifications delayed
- **Possible causes:**
  1. Notification-service is down or slow
  2. Upstream services flooding the queue (incident causing retry storms)
  3. Email-service (SendGrid) rate limiting
- **Investigation:**
  1. Check notification-service health
  2. Check queue length trend
  3. Check dead letter queue size — high DLQ = systematic failure
- **Fix:** Scale notification-service, temporarily pause non-critical notifications

## Impact on CloudDesk Services

| Redis Instance | If Down/Slow | Impact |
|---------------|-------------|--------|
| redis-cache | Cache misses → DB load increase | Latency increase for project-service (30-50%) |
| redis-session | Sessions unavailable | Users can't authenticate — P1 |
| redis-queue | Queue stops processing | Notifications delayed — P2 (not user-blocking) |

## Escalation
- redis-session down: P1 — page platform-oncall
- redis-cache down: P2 — page core-product-oncall
- redis-queue backlog >10000: P2 — page engagement-oncall
