# Database Disk Space Runbook

## Overview
Disk space alerts fire when any PostgreSQL instance exceeds 80% disk usage. If a database runs out of disk, it goes read-only — this is a P1 incident.

## Immediate Triage

1. **Check current disk usage and growth rate**
   - Get disk metrics with 60-minute time range to see the trend
   - Calculate growth rate: if growing >1GB/hour, this is urgent
   - Estimate time until disk full

2. **Identify what's consuming space**

### WAL (Write-Ahead Log) Accumulation
- **Most common cause of sudden disk growth**
- Check for stale replication slots: `SELECT * FROM pg_replication_slots WHERE NOT active;`
- A stale replication slot prevents WAL cleanup even when WAL is no longer needed
- Fix: Drop the stale slot: `SELECT pg_drop_replication_slot('slot_name');`
- WAL segments are typically 16MB each — hundreds of retained segments = GBs of wasted space

### Table Bloat
- Tables that receive heavy UPDATE/DELETE operations accumulate dead tuples
- Check: `SELECT relname, n_dead_tup FROM pg_stat_user_tables ORDER BY n_dead_tup DESC;`
- Fix: Run `VACUUM FULL` on bloated tables (requires maintenance window — locks table)
- Prevention: Tune autovacuum parameters

### Large Temp Files
- Failed or long-running queries can leave temp files
- Check `/tmp` directory within PostgreSQL data directory
- Fix: Identify and kill the responsible queries, then clean up

### Backup Accumulation
- Check if old backup files are not being rotated
- Verify backup retention policy

## Recovery Steps

1. If disk >95%: **Emergency** — immediately identify and drop stale replication slots
2. If WAL is the cause: dropping the stale slot immediately frees space (WAL cleanup runs automatically)
3. If table bloat: schedule VACUUM FULL during maintenance window
4. If temp files: kill long-running queries and clean up

## Prevention
- Monitor replication slot status daily
- Set up alerts for inactive replication slots
- Autovacuum tuning for high-write tables
- Disk growth rate alerting (not just threshold)

## Escalation
- Disk >90%: P1 — page DBA oncall
- Disk >80% with growth trend: P2 — investigate within 1 hour
- Disk >80% stable: P3 — investigate within 24 hours
