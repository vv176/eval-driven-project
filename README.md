# CloudDesk Incident Response Agent

Build an AI agent that investigates production incidents for CloudDesk, a fictional B2B SaaS platform (project management + docs).

Your agent receives support tickets, uses 17 diagnostic tools to investigate, and produces structured incident reports — all scored against a golden dataset.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Add your OpenAI API key to .env
```

## How It Works

1. **You modify `agent.py`** — implement your investigation logic
2. **Run the eval** — your agent gets scored against test cases with known answers
3. **Check your scores** — see where your agent succeeds and fails
4. **Iterate** — improve your agent and re-run

```bash
# Run eval on training data (you can see expected answers)
python3 evaluate.py --split train

# Run on a single test case
python3 evaluate.py --split train --test-case eu_api_001

# Fast mode (skips LLM-as-judge, cheaper)
python3 evaluate.py --split train --fast

# Save detailed results
python3 evaluate.py --split train --output results.json
```

## Available Tools (17)

Your agent can call these via `tools.execute(tool_name, **kwargs)`:

### Diagnostic (6)
| Tool | Purpose |
|------|---------|
| `get_service_status(service_name)` | Service health, version, uptime |
| `get_service_metrics(service_name, metric_type, time_range_minutes?)` | Time-series metrics (cpu, memory, disk, request_rate, error_rate, latency_p50, latency_p99) |
| `get_service_dependencies(service_name)` | Upstream and downstream dependencies |
| `search_logs(service_name, query?, log_level?, time_range_minutes?)` | Grep-style log search, max 25 results |
| `get_deployment_history(service_name, limit?)` | Recent deployments |
| `get_deployment_diff(deploy_id)` | Code changes in a deployment |

### Source Code & Knowledge (4)
| Tool | Purpose |
|------|---------|
| `get_source_code(service_name, file_path)` | Read a Java source file |
| `list_source_files(service_name)` | List available source files |
| `search_runbooks(query)` | Search operational runbooks (BM25) |
| `get_customer_info(customer_id)` | Customer details, region, feature flags |

### Actions (5)
| Tool | Purpose |
|------|---------|
| `restart_service(service_name)` | Restart a service |
| `scale_service(service_name, replicas)` | Scale replicas |
| `rollback_deployment(service_name, target_version)` | Roll back to previous version |
| `update_feature_flag(flag_name, enabled, scope?)` | Toggle feature flags |
| `create_incident_ticket(title, severity, description, affected_services)` | Create incident ticket |

### Communication (2)
| Tool | Purpose |
|------|---------|
| `page_oncall(team_name, message, severity)` | Page oncall engineer |
| `send_status_update(channel, message)` | Post status update |

## Response Format

Your agent must return a dict with these fields (see `schema.py`):

```python
{
    "root_cause": "Free text explanation...",
    "affected_services": ["project-service", "api-gateway"],
    "severity_assessment": "P2",  # P1, P2, P3, or P4
    "recommended_actions": [
        {"tool": "rollback_deployment", "args": {"service_name": "project-service", "target_version": "v2.3.0"}}
    ],
    "is_false_alarm": False,
    "confidence": 0.85,
    "investigation_summary": "Step by step reasoning..."
}
```

## Scoring (7 metrics)

| Metric | Weight | How |
|--------|--------|-----|
| Root cause accuracy | 25% | LLM-as-judge (component + mechanism + evidence) |
| Affected services | 15% | Jaccard similarity with expected set |
| Recommended actions | 15% | Tool + key args match |
| Investigation quality | 15% | LLM-as-judge (sequence + evidence + efficiency) |
| Severity assessment | 10% | Exact match (P1-P4) |
| False alarm detection | 10% | Boolean exact match |
| Tool argument quality | 10% | Did you pass sensible args to key tools? |

**Difficulty multiplier:** Easy 1.0x, Medium 1.5x, Hard 2.5x

**Safety gate:** Taking destructive actions (restart, rollback) on a false alarm caps your score at 50%.

## CloudDesk Architecture

```
api-gateway → auth-service
api-gateway → project-service → project-db, redis-cache, notification-service
api-gateway → task-service → task-db, project-service, notification-service
api-gateway → search-service → elasticsearch
notification-service → redis-queue, email-service
auth-service → auth-db, redis-session
```

## Tips

- Start with `search_logs` and `get_service_metrics` to identify which service is affected
- Use `get_service_dependencies` to understand cascade patterns
- Check `get_deployment_history` for recent changes
- Use `get_deployment_diff` to review actual code changes
- Read the source code when logs show stack traces
- Don't forget to check if it might be a false alarm
- Runbooks contain investigation procedures — search them
