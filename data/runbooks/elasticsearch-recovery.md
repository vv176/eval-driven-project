# Elasticsearch Recovery

## Overview
CloudDesk's search-service uses a 3-node Elasticsearch cluster. Elasticsearch failures typically affect search functionality but don't impact core CRUD operations.

## Cluster Health States

- **Green:** All primary and replica shards assigned. Fully operational.
- **Yellow:** All primary shards assigned, some replicas unassigned. Search works but no redundancy.
- **Red:** Some primary shards unassigned. Search partially or fully broken.

## Common Issues

### Cluster Status Yellow
- **Usual cause:** A node restarted and replicas haven't been reassigned yet
- **Action:** Wait 10-15 minutes for automatic recovery. If persists, check the node that was restarted.
- **Not urgent:** Yellow means search still works, just without full redundancy.

### Cluster Status Red
- **Possible causes:**
  1. Node permanently failed (disk failure, OOM kill)
  2. Index corruption
  3. Disk full on data nodes
- **Immediate:** Check which indices are red, check node status
- **Fix:** If node is down — restart it. If disk full — free space or add nodes. If index corrupted — restore from snapshot.

### High Search Latency
- **Possible causes:**
  1. Large result sets without pagination
  2. Complex aggregation queries
  3. Too many concurrent searches
  4. GC pauses on data nodes
- **Investigation:** Check search thread pool stats, look for rejected searches
- **Fix:** Add pagination, optimize queries, scale cluster

### Index Corruption
- **Symptom:** Specific searches fail with shard failures
- **Fix:** 
  1. Close the corrupted index
  2. Restore from the latest snapshot
  3. Re-index from source database if snapshot unavailable

## Impact on CloudDesk
- Search is tier-2 — outage is P2, not P1
- Users can still create/edit projects and tasks without search
- Admin search (finding users, audit logs) is affected

## Escalation
- Cluster red: P2 — page core-product-oncall
- Cluster yellow >1 hour: P3 — investigate during business hours
- Search latency >5s: P2 — page core-product-oncall
