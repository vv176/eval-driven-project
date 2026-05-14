# Customer Impact Assessment

## Overview
When an incident occurs, quickly determining which customers are affected and how severely is critical for communication and prioritization.

## Assessment Steps

### 1. Identify Affected Region/Segment
- Check if the issue is region-specific (EU, US, AP)
- Check if it's plan-specific (enterprise, business, starter)
- Check if it's feature-flag-specific (only customers with a certain flag enabled)

### 2. Quantify Impact
- **Number of affected customers:** Check customer profiles filtered by region/plan/flags
- **Revenue impact:** Platinum > Gold > Silver > Bronze. A platinum enterprise customer outage is more critical than a bronze starter customer.
- **Affected functionality:** Core functionality (project management, tasks) vs. secondary (search, notifications)

### 3. Impact Matrix

| Customer Tier | Core Functionality | Secondary Functionality |
|--------------|-------------------|------------------------|
| Platinum | P1 | P2 |
| Gold | P2 | P3 |
| Silver | P2 | P3 |
| Bronze | P3 | P4 |

### 4. Communication Templates

**For P1/P2 customer-impacting incidents:**
> We are aware of an issue affecting [description]. Our engineering team is actively investigating. We will provide an update within [30/60] minutes.

**For resolution:**
> The issue affecting [description] has been resolved. Root cause: [brief]. We are implementing [prevention measures]. Full post-mortem will be shared within 48 hours.

## Feature Flag Considerations
- Some features are only enabled for specific customers via feature flags
- If an incident is in a feature-flagged path, only customers with that flag are affected
- Check customer profiles to identify which customers have the relevant flag enabled
- Disabling the feature flag can be an immediate mitigation

## CloudDesk Customer Segments
- **EU Enterprise (GDPR):** Meridian Analytics, Fjord Design, Quantum Financial, Nordic Health — all have `gdpr_strict_mode: true`. Issues in GDPR data paths affect only these customers.
- **US Enterprise:** TechNova, Pinnacle Media — no GDPR overhead
- **Beta users:** Customers with `beta_search_v2: true` — TechNova, BrightPath, Atlas, Pinnacle
- **Small accounts:** GreenLeaf Startups — starter plan, minimal impact if affected
