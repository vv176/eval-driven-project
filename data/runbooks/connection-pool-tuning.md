# Connection Pool Tuning & Troubleshooting

## Overview
CloudDesk Java services use HikariCP for database connection pooling. Connection pool issues are a common source of latency and errors.

## Key Metrics to Monitor

- **Active connections**: Currently in use. Should be well below max pool size.
- **Idle connections**: Available but not in use. Should be >0.
- **Pending threads**: Waiting for a connection. Should be 0. Any non-zero value means the pool is saturated.
- **Connection wait time**: Time spent waiting for a connection. Should be <100ms.
- **Total connections**: Active + idle. Should equal max pool size when under load.

## Common Issues

### Connection Pool Exhaustion
- **Symptom:** Requests timeout with "Connection is not available, request timed out after 30000ms"
- **Possible causes:**
  1. **Connection leak** — code gets a connection but doesn't return it. Look for JDBC code that doesn't use try-with-resources.
  2. **Long-running queries** — connections held for too long. Check slow query log.
  3. **Pool too small** — max connections < concurrent request count. Increase pool size.
  4. **Transaction held open** — code opens a transaction but doesn't commit/rollback (often in error paths).
- **Investigation:**
  1. Check HikariCP metrics: active connections == max pool size?
  2. Enable leak detection: `leak-detection-threshold: 60000` (logs warning if connection not returned within 60s)
  3. Search logs for "Connection leak detection" warnings
  4. Review recent deployment diffs for new JDBC/raw SQL code

### Connection Leak Detection
- HikariCP logs a warning when a connection is held longer than the leak detection threshold
- The log includes the stack trace of where the connection was acquired
- Search logs for: "Connection leak detection triggered"
- The stack trace shows you exactly which code path is leaking

### Identifying Leaks in Code
- Look for patterns like:
  ```java
  Connection conn = dataSource.getConnection();
  // ... code that might throw ...
  conn.close();  // WRONG: not in finally block
  ```
- Correct pattern:
  ```java
  try (Connection conn = dataSource.getConnection()) {
      // ... code ...
  }  // auto-closed even on exception
  ```

## Tuning Guide

| Parameter | Default | Recommendation |
|-----------|---------|----------------|
| maximumPoolSize | 10 | 20-30 for high-traffic services |
| minimumIdle | 10 | Same as max for stable workloads |
| connectionTimeout | 30000ms | 30s is fine for most cases |
| idleTimeout | 600000ms | 10 minutes |
| maxLifetime | 1800000ms | 30 minutes (must be less than DB's wait_timeout) |
| leakDetectionThreshold | 0 (disabled) | 60000ms (60s) — always enable in production |

## PostgreSQL Side
- Check `max_connections` setting on PostgreSQL (default 100, CloudDesk uses 200)
- Total connections from all services must be < max_connections
- Each service pool: 20 connections x 3 replicas = 60 connections per service
- With 3 services per database: 180 connections — close to the 200 limit

## Escalation
- Pool exhaustion on tier-1 service: P1 — page oncall
- Leak detected but service still functional: P2 — fix within 24 hours
