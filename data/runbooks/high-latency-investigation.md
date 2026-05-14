# High Latency Investigation Runbook

## Overview
This runbook covers investigation steps when latency alerts fire for any CloudDesk service. Latency issues can stem from code changes, infrastructure problems, or downstream dependencies.

## Triage Checklist

1. **Check which services are affected**
   - Look at the API gateway metrics first — it sees all traffic
   - Identify if latency is global or region-specific (EU vs US vs AP)
   - Check if latency correlates with specific endpoints or is service-wide

2. **Check recent deployments**
   - Review deployment history for all affected services in the last 6 hours
   - Pay special attention to deployments that happened just before latency started
   - If a suspicious deployment exists, review the diff for query changes, new loops, or added I/O

3. **Check downstream dependencies**
   - Use the dependency graph to identify all services the affected service calls
   - Check latency and error rates for each dependency
   - A slow downstream service will cause the upstream to appear slow too

4. **Check database metrics**
   - Query count per second — sudden increases suggest N+1 query problems
   - Connection pool utilization — above 80% is concerning
   - Lock wait times — contention causes latency spikes
   - Slow query log — look for queries taking >100ms

5. **Check resource utilization**
   - CPU: above 80% sustained → scaling issue
   - Memory: check for GC pauses (Java services — look for GC logs)
   - Disk I/O: high iowait → disk bottleneck

## Common Root Causes

### N+1 Query Pattern
- **Symptom:** Latency scales with number of items (e.g., projects, tasks)
- **Signal:** Database query count proportional to result set size
- **Fix:** Batch queries, use JOINs, or add caching
- **Example:** A loop that calls `SELECT * FROM compliance_audit WHERE project_id = ?` per project instead of using `WHERE project_id IN (...)`

### Connection Pool Exhaustion
- **Symptom:** Intermittent timeouts, some requests succeed while others fail
- **Signal:** Active connections at max, queue depth growing
- **Fix:** Increase pool size, fix connection leaks, reduce query time

### Cache Miss Storm
- **Symptom:** Latency spike after deployment or restart
- **Signal:** Redis hit rate drops, database query rate spikes
- **Fix:** Warm cache before switching traffic, use stale-while-revalidate

### Downstream Cascade
- **Symptom:** Multiple services degrade simultaneously
- **Signal:** Latency/error spikes with time offset matching dependency order
- **Fix:** Identify the root service, add circuit breakers

## Escalation
- P1 (>1s p99 for tier-1 service): Page oncall immediately
- P2 (>500ms p99 or region-specific): Investigate within 30 minutes
- P3 (>200ms p99, not customer-impacting): Investigate within 4 hours
