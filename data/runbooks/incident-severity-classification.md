# Incident Severity Classification

## Overview
Correct severity classification determines response urgency, who gets paged, and SLA expectations. Misclassification in either direction is costly — over-escalation causes alert fatigue, under-escalation delays response.

## Severity Levels

### P1 — Critical
- **Definition:** Complete service outage or severe degradation affecting >50% of users
- **Examples:**
  - API gateway returning 5xx for all requests
  - Database completely down or read-only (out of disk)
  - Authentication service down (no one can log in)
  - Cascading failure across 3+ tier-1 services
- **Response:** Page all affected oncalls immediately. War room within 15 minutes.
- **SLA:** Acknowledge within 5 minutes, mitigate within 1 hour
- **Communication:** Status page update within 15 minutes, customer notification within 30 minutes

### P2 — High
- **Definition:** Significant degradation affecting a subset of users or a specific region
- **Examples:**
  - EU customers experiencing >1s latency (but US/AP unaffected)
  - One non-critical service down (e.g., search)
  - Error rate >5% on a single endpoint
  - Disk space >90% and growing (not yet critical but will be)
- **Response:** Page oncall for affected service. Investigate within 30 minutes.
- **SLA:** Acknowledge within 15 minutes, mitigate within 4 hours
- **Communication:** Status page update if customer-visible

### P3 — Medium
- **Definition:** Minor degradation, workaround available, limited customer impact
- **Examples:**
  - Elevated latency (<500ms increase) on non-critical paths
  - Intermittent errors (<1% error rate)
  - Non-customer-facing service degradation
  - Disk space >80% but stable
- **Response:** Create ticket, investigate during business hours
- **SLA:** Investigate within 24 hours, resolve within 1 week

### P4 — Low
- **Definition:** No current customer impact, but requires attention
- **Examples:**
  - Monitoring alert misconfiguration (false positive)
  - Deprecated dependency warning
  - Non-critical performance regression in staging
- **Response:** Create ticket, schedule for next sprint
- **SLA:** Resolve within 1 month

## Classification Decision Tree

1. Is the service completely down? → **P1**
2. Is >50% of traffic affected? → **P1**
3. Is a specific customer segment affected? → **P2** (or P1 if platinum customers)
4. Is there a workaround? → **P3** at most
5. Is there current customer impact? → If no → **P4**

## Common Mistakes

- **Alert fires but metrics are normal:** Check if the alert threshold is misconfigured. A false positive is P4, not P2.
- **Single customer complaining:** Investigate before escalating. Could be client-side issue.
- **Slow but functional:** Latency increase from 100ms to 150ms is P3/P4, not P2 — unless it's a tier-1 service in a platinum customer's critical path.

## Escalation
- If unsure between P1 and P2: default to P1. Better to over-escalate than miss a real incident.
- If an incident is initially P3 but worsening: re-classify immediately.
