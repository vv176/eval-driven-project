# Deployment Rollback Procedure

## Overview
Rollback is the fastest way to mitigate an incident caused by a bad deployment. This runbook covers when and how to roll back safely.

## When to Roll Back

### Roll back immediately if:
- A deployment correlates with the start of an incident (deployed within 30 minutes of first alert)
- The deployment diff contains changes to critical paths (query logic, auth, payment)
- Error rates spiked right after deployment
- Latency increased by >50% after deployment

### Do NOT roll back if:
- The incident started before the deployment
- The deployment only contains config changes that are already active
- Rolling back would cause a different failure (e.g., schema migration already ran)
- The deployment was a hotfix for a previous incident

## Pre-Rollback Checklist

1. **Check for database migrations**
   - If the deployment included a schema migration, rolling back the code may break against the new schema
   - Check the deployment diff for any Flyway/Liquibase migration files
   - If migration is backwards-compatible (adding columns/tables): safe to roll back code
   - If migration is destructive (dropping columns/tables): DO NOT roll back without DBA consult

2. **Check for API contract changes**
   - If the deployment changed API response format, downstream services may depend on the new format
   - Check if any dependent service was also deployed after this one

3. **Identify the target version**
   - Roll back to the last known good version (the version running before this deployment)
   - Verify that version was stable (check its deployment record)

## Rollback Steps

1. Use the rollback tool: `rollback_deployment(service_name, target_version)`
2. Monitor the service for 5 minutes after rollback
3. Check error rates and latency — they should return to pre-deployment levels
4. If metrics don't improve, the deployment was not the cause — investigate further

## After Rollback

1. Create an incident ticket documenting what happened
2. Notify the team that deployed the change
3. The fix should be deployed as a NEW deployment after the bug is identified and fixed
4. Never re-deploy the same version that was rolled back without fixing the issue

## Escalation
- If unsure whether rollback is safe: consult the deploying team before rolling back
- If rollback fails: P1 — page platform-oncall
