# Cascading Failure Playbook

## Overview
Cascading failures occur when one service's failure causes dependent services to fail in sequence. These are the most dangerous incidents because they can take down the entire platform quickly.

## Identifying a Cascade

### Key Signals
1. **Multiple services degrading with a time offset** — Service A fails, then 30-60 seconds later Service B fails, then Service C
2. **Error rates spreading along the dependency graph** — the pattern follows the edges in the dependency graph
3. **Connection pool exhaustion propagating** — Service A's pool exhausts, causing B to timeout waiting for A, causing B's pool to exhaust
4. **Retry amplification** — failed requests trigger retries, multiplying load on the already-struggling service

### How to Find the Root Service
1. Get the dependency graph for all affected services
2. Find the service that failed FIRST (earliest error timestamp)
3. Verify it's upstream of all other failing services in the dependency graph
4. Check: did this service's failure precede the others, or did they all fail simultaneously?
   - Time-offset pattern → cascade from one root
   - Simultaneous failure → shared dependency (database, network, etc.)

## Investigation Steps

1. **Map the blast radius**
   - List all affected services
   - Get the dependency graph — trace upstream from each affected service
   - Identify the common ancestor

2. **Investigate the root service**
   - Check deployment history — was there a recent deploy?
   - Check metrics: CPU, memory, connection pool, error rate
   - Search logs for the earliest errors
   - Check if the service's own dependencies are healthy

3. **Check for multi-cause scenarios**
   - Sometimes a cascade requires TWO conditions: a latent bug + a trigger
   - Example: A connection leak (latent bug) + traffic spike (trigger) = pool exhaustion
   - The bug may have existed for weeks — the trigger is what tipped it over

4. **Check for retry storms**
   - When Service B retries failed calls to Service A, it can 3x-10x the load on A
   - Look for exponentially increasing request rates on the root service
   - Circuit breakers should prevent this — check if they're configured

## Mitigation

### Immediate
1. **Break the cascade** — if a circuit breaker isn't firing, manually disable traffic to the failing path
2. **Reduce load on root service** — scale up replicas, shed non-critical traffic
3. **Don't restart everything at once** — start from the root service and work downstream

### After Recovery
1. Add or tune circuit breakers
2. Add connection pool monitoring with alerting
3. Review retry policies — ensure exponential backoff with jitter
4. Add dependency health checks to readiness probes

## Escalation
- Any cascade affecting 3+ services: P1 — page all affected teams
- Cascade in tier-1 services: P1 — page platform-oncall AND service oncalls
