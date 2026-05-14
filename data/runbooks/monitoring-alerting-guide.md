# Monitoring & Alerting Guide

## Overview
CloudDesk uses Prometheus for metrics collection and Grafana for dashboards. Alerts are configured in Prometheus Alertmanager and route to PagerDuty for oncall notification.

## Alert Categories

### Infrastructure Alerts
| Alert | Threshold | Severity | Notes |
|-------|-----------|----------|-------|
| HighCPU | >80% for 5min | P2 | Check if correlated with traffic spike or code issue |
| HighMemory | >85% for 5min | P2 | Check for memory leaks, GC pressure |
| DiskSpaceWarning | >80% used | P3 | Monitor trend — may need cleanup |
| DiskSpaceCritical | >90% used | P1 | Immediate action required |
| ServiceDown | Health check fails 3x | P1 | Service unresponsive |

### Application Alerts
| Alert | Threshold | Severity | Notes |
|-------|-----------|----------|-------|
| HighErrorRate | >5% 5xx for 5min | P2 | Check recent deployments first |
| HighLatency | p99 >1s for 5min | P2 | Check downstream dependencies |
| ConnectionPoolExhausted | Active == Max for 2min | P1 | Connection leak or undersized pool |

### Database Alerts
| Alert | Threshold | Severity | Notes |
|-------|-----------|----------|-------|
| PostgresHighConnections | >80% max_connections | P2 | Check for connection leaks |
| PostgresReplicationLag | >30s | P2 | Check replica health |
| PostgresDeadTuples | >1M dead tuples | P3 | Schedule VACUUM |

## Known False Positives

### HighLatency on api-gateway during deployments
- **What happens:** During rolling deployment, a few requests get routed to pods that are starting up → cold JVM → high latency for 30-60 seconds
- **How to identify:** Latency spike is brief (<2 minutes) and correlates exactly with a deployment timestamp
- **Action:** No action needed. This is expected behavior.

### DiskSpaceWarning after schema migration
- **What happens:** Schema migration creates temporary files that spike disk usage temporarily
- **How to identify:** Disk spike correlates with a deployment that includes migration files, and the spike resolves within 30 minutes
- **Action:** Monitor but no action needed if trend is returning to baseline

### HighErrorRate during config rollout
- **What happens:** Config changes that affect request routing can cause brief 4xx spike as caches update
- **How to identify:** Error spike is 4xx (not 5xx), lasts <5 minutes, resolves automatically
- **Action:** No action needed for 4xx spikes <5 minutes

### Alert Threshold Misconfiguration
- **What happens:** Alert fires but all metrics are actually normal when checked manually
- **How to identify:** Check the alert rule — the threshold may be set too aggressively or the query may be wrong
- **Common causes:**
  - Threshold set in wrong units (bytes vs megabytes)
  - Alert query doesn't filter by environment (picks up staging data)
  - Percentile calculation over too-short window (1 minute p99 is noisy)
- **Action:** Fix the alert configuration. Create a P4 ticket to update the threshold.

## Dashboard Reference
- **API Gateway Overview:** Latency, error rate, request rate by region and endpoint
- **Service Health:** Per-service CPU, memory, error rate, active connections
- **Database Dashboard:** Query rate, connection pool, disk, replication lag
- **Redis Dashboard:** Memory usage, hit rate, connected clients, queue depth

## Oncall Rotation
- `platform-oncall`: Covers api-gateway, auth-service, infrastructure
- `core-product-oncall`: Covers project-service, task-service, search-service
- `engagement-oncall`: Covers notification-service
