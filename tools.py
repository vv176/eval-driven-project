"""
CloudDesk Incident Response Agent — Mock Tool Implementations

The ToolExecutor class loads scenario data and provides deterministic tool
functions. No LLM calls — all responses come from pre-generated data files.

Usage:
    executor = ToolExecutor("eu_api_degradation")
    result = executor.execute("get_service_status", service_name="project-service")
"""

import json
import math
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path(__file__).parent / "data"
SCENARIOS_DIR = BASE_DIR / "scenarios"
SERVICES_DIR = BASE_DIR / "services"
SOURCE_CODE_DIR = BASE_DIR / "source_code"
RUNBOOKS_DIR = BASE_DIR / "runbooks"
CUSTOMERS_DIR = BASE_DIR / "customers"

MAX_LOG_RESULTS = 25
MAX_METRIC_HISTORY_MINUTES = 240
MAX_DEPLOYMENT_HISTORY = 10


class ToolExecutor:
    """Loads a scenario and provides deterministic tool functions."""

    def __init__(self, scenario_id: str, verbose: bool = False):
        self.scenario_id = scenario_id
        self.scenario_dir = SCENARIOS_DIR / scenario_id
        self.tool_call_log: list[dict] = []
        self.verbose = verbose

        # Load all data
        self.scenario = self._load_json(self.scenario_dir / "scenario.json")
        self.dependency_graph = self._load_json(SERVICES_DIR / "dependency_graph.json")
        self.service_registry = self._load_json(SERVICES_DIR / "service_registry.json")
        self.customer_profiles = self._load_json(CUSTOMERS_DIR / "customer_profiles.json")

        # Load logs (one file per service)
        self.logs = {}
        logs_dir = self.scenario_dir / "logs"
        if logs_dir.exists():
            for log_file in logs_dir.glob("*.log"):
                service_name = log_file.stem
                self.logs[service_name] = self._load_log_file(log_file)

        # Load metrics (one file per service)
        self.metrics = {}
        metrics_dir = self.scenario_dir / "metrics"
        if metrics_dir.exists():
            for metric_file in metrics_dir.glob("*.json"):
                service_name = metric_file.stem
                self.metrics[service_name] = self._load_json(metric_file)

        # Load deployments
        deploy_dir = self.scenario_dir / "deployments"
        self.deployments = self._load_json(deploy_dir / "deployments.json") if (deploy_dir / "deployments.json").exists() else []
        self.diffs = self._load_json(deploy_dir / "diffs.json") if (deploy_dir / "diffs.json").exists() else {}

        # Load runbooks for BM25 search
        self.runbooks = self._load_runbooks()

        # Snapshot time from scenario
        self.snapshot_time = datetime.fromisoformat(
            self.scenario["timeline"]["scenario_snapshot_time"]
        )

    def execute(self, tool_name: str, **kwargs) -> dict:
        """Execute a tool by name. Logs the call and returns the result."""
        call_index = len(self.tool_call_log) + 1
        self.tool_call_log.append({"tool": tool_name, "args": kwargs})

        if self.verbose:
            print(f"\n    ┌─ Tool Call #{call_index}: {tool_name}")
            for k, v in kwargs.items():
                print(f"    │  {k}: {v}")

        tool_fn = getattr(self, f"_tool_{tool_name}", None)
        if tool_fn is None:
            err = {"error": f"Unknown tool: {tool_name}"}
            if self.verbose:
                print(f"    └─ ERROR: {err['error']}")
            return err

        try:
            result = tool_fn(**kwargs)
            if self.verbose:
                self._print_result(result)
            return result
        except Exception as e:
            err = {"error": f"Tool execution failed: {str(e)}"}
            if self.verbose:
                print(f"    └─ ERROR: {err['error']}")
            return err

    def _print_result(self, result: dict):
        """Print a tool result in a compact, readable format."""
        result_str = json.dumps(result, indent=2, default=str)
        lines = result_str.split('\n')
        if len(lines) <= 20:
            for i, line in enumerate(lines):
                prefix = "    └─ " if i == 0 else "       "
                print(f"{prefix}{line}")
        else:
            # Show first 12 lines + last 3 lines with truncation indicator
            for i, line in enumerate(lines[:12]):
                prefix = "    └─ " if i == 0 else "       "
                print(f"{prefix}{line}")
            print(f"       ... ({len(lines) - 15} lines omitted)")
            for line in lines[-3:]:
                print(f"       {line}")

    # ── Diagnostic Tools ──────────────────────────────────────────

    def _tool_get_service_status(self, service_name: str) -> dict:
        # Check services
        services = self.service_registry.get("services", {})
        infra = self.service_registry.get("infrastructure", {})

        if service_name in services:
            svc = services[service_name]
            scenario_status = self.scenario.get("services_status", {}).get(service_name, {})
            return {
                "service_name": service_name,
                "status": scenario_status.get("status", "healthy"),
                "version": scenario_status.get("version", svc.get("current_version")),
                "uptime": "14d 6h 32m",
                "team": svc["team"],
                "tier": svc["tier"],
                "replicas": svc["replicas"],
                "health_checks": {
                    "liveness": "passing",
                    "readiness": "passing" if scenario_status.get("status") != "down" else "failing"
                }
            }
        elif service_name in infra:
            inf = infra[service_name]
            return {
                "service_name": service_name,
                "type": inf["type"],
                "status": "healthy",
                "version": inf.get("version", "unknown"),
                "host": inf.get("host", "unknown")
            }
        else:
            return {"error": f"Unknown service: {service_name}"}

    def _tool_get_service_metrics(self, service_name: str, metric_type: str,
                                   time_range_minutes: int = 60) -> dict:
        time_range_minutes = min(time_range_minutes, MAX_METRIC_HISTORY_MINUTES)

        if service_name not in self.metrics:
            return {"error": f"No metrics available for service: {service_name}"}

        service_metrics = self.metrics[service_name]

        # Find the matching metric type
        for metric in service_metrics:
            if metric["metric_type"] == metric_type:
                # Filter data points by time range
                cutoff = self.snapshot_time - timedelta(minutes=time_range_minutes)
                filtered_data = [
                    point for point in metric["data"]
                    if datetime.fromisoformat(point["timestamp"]) >= cutoff
                ]
                return {
                    "service_name": service_name,
                    "metric_type": metric_type,
                    "unit": metric["unit"],
                    "time_range_minutes": time_range_minutes,
                    "data_points": len(filtered_data),
                    "data": filtered_data
                }

        return {"error": f"Metric type '{metric_type}' not available for {service_name}"}

    def _tool_get_service_dependencies(self, service_name: str) -> dict:
        services = self.dependency_graph.get("services", {})

        if service_name not in services:
            return {"error": f"Unknown service: {service_name}"}

        downstream = services[service_name].get("depends_on", [])

        # Find upstream (who depends on this service)
        upstream = [
            svc for svc, info in services.items()
            if service_name in info.get("depends_on", [])
        ]

        return {
            "service_name": service_name,
            "upstream": upstream,
            "downstream": downstream
        }

    def _tool_search_logs(self, service_name: str, query: str = None,
                          log_level: str = None, time_range_minutes: int = 60) -> dict:
        time_range_minutes = min(time_range_minutes, MAX_METRIC_HISTORY_MINUTES)

        if service_name not in self.logs:
            return {"error": f"No logs available for service: {service_name}"}

        cutoff = self.snapshot_time - timedelta(minutes=time_range_minutes)
        lines = self.logs[service_name]

        # Filter by time range
        filtered = [
            line for line in lines
            if datetime.fromisoformat(line["timestamp"]) >= cutoff
        ]

        # Filter by log level
        if log_level:
            filtered = [line for line in filtered if line["level"] == log_level.upper()]

        # Filter by query substring
        if query:
            query_lower = query.lower()
            filtered = [
                line for line in filtered
                if query_lower in line["message"].lower()
            ]

        total_count = len(filtered)

        # Sort newest first, limit to MAX_LOG_RESULTS
        filtered.sort(key=lambda x: x["timestamp"], reverse=True)
        results = filtered[:MAX_LOG_RESULTS]

        return {
            "service_name": service_name,
            "total_count": total_count,
            "returned_count": len(results),
            "filters": {
                "query": query,
                "log_level": log_level,
                "time_range_minutes": time_range_minutes
            },
            "logs": results
        }

    def _tool_get_deployment_history(self, service_name: str, limit: int = 5) -> dict:
        limit = min(limit, MAX_DEPLOYMENT_HISTORY)

        # Filter deployments for this service
        service_deploys = [
            d for d in self.deployments
            if d["service"] == service_name
        ]

        # Sort newest first
        service_deploys.sort(key=lambda x: x["timestamp"], reverse=True)

        return {
            "service_name": service_name,
            "total_deployments": len(service_deploys),
            "deployments": service_deploys[:limit]
        }

    def _tool_get_deployment_diff(self, deploy_id: str) -> dict:
        if isinstance(self.diffs, list):
            for diff in self.diffs:
                if diff["deploy_id"] == deploy_id:
                    return diff
        elif isinstance(self.diffs, dict):
            if deploy_id in self.diffs:
                return self.diffs[deploy_id]

        return {"error": f"Deployment diff not found for: {deploy_id}"}

    # ── Source Code & Knowledge Tools ─────────────────────────────

    def _tool_get_source_code(self, service_name: str, file_path: str) -> dict:
        code_dir = SOURCE_CODE_DIR / service_name
        if not code_dir.exists():
            return {"error": f"No source code available for service: {service_name}"}

        file = code_dir / file_path
        if not file.exists():
            return {"error": f"File not found: {service_name}/{file_path}"}

        content = file.read_text()
        lines = content.split("\n")
        numbered = "\n".join(f"{i+1:4d} | {line}" for i, line in enumerate(lines))

        return {
            "service_name": service_name,
            "file_path": file_path,
            "total_lines": len(lines),
            "content": numbered
        }

    def _tool_list_source_files(self, service_name: str) -> dict:
        code_dir = SOURCE_CODE_DIR / service_name
        if not code_dir.exists():
            return {"error": f"No source code available for service: {service_name}"}

        files = [f.name for f in code_dir.glob("*.java")]
        return {
            "service_name": service_name,
            "files": sorted(files)
        }

    def _tool_search_runbooks(self, query: str) -> dict:
        """BM25-style search over runbook documents."""
        query_terms = self._tokenize(query)
        if not query_terms:
            return {"error": "Empty search query"}

        scored = []
        for runbook in self.runbooks:
            score = self._bm25_score(query_terms, runbook["tokens"], len(self.runbooks),
                                      sum(len(r["tokens"]) for r in self.runbooks) / len(self.runbooks))
            if score > 0:
                # Find the most relevant section
                relevant_section = self._find_relevant_section(query_terms, runbook["content"])
                scored.append({
                    "title": runbook["title"],
                    "file": runbook["file"],
                    "relevant_section": relevant_section,
                    "score": round(score, 3)
                })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return {
            "query": query,
            "results": scored[:3]
        }

    def _tool_get_customer_info(self, customer_id: str) -> dict:
        customers = self.customer_profiles.get("customers", {})
        if customer_id not in customers:
            return {"error": f"Unknown customer: {customer_id}"}
        customer = customers[customer_id].copy()
        customer["customer_id"] = customer_id
        return customer

    # ── Action Tools ──────────────────────────────────────────────

    def _tool_restart_service(self, service_name: str) -> dict:
        services = self.service_registry.get("services", {})
        if service_name not in services:
            return {"error": f"Unknown service: {service_name}"}
        return {
            "success": True,
            "service_name": service_name,
            "message": f"Service {service_name} restart initiated. Expected downtime: 30-60 seconds."
        }

    def _tool_scale_service(self, service_name: str, replicas: int) -> dict:
        services = self.service_registry.get("services", {})
        if service_name not in services:
            return {"error": f"Unknown service: {service_name}"}
        current = services[service_name]["replicas"]
        return {
            "success": True,
            "service_name": service_name,
            "previous_replicas": current,
            "new_replicas": replicas,
            "message": f"Scaling {service_name} from {current} to {replicas} replicas."
        }

    def _tool_rollback_deployment(self, service_name: str, target_version: str) -> dict:
        services = self.service_registry.get("services", {})
        if service_name not in services:
            return {"error": f"Unknown service: {service_name}"}

        scenario_status = self.scenario.get("services_status", {}).get(service_name, {})
        current_version = scenario_status.get("version", services[service_name].get("current_version"))

        return {
            "success": True,
            "service_name": service_name,
            "rolled_back_from": current_version,
            "rolled_back_to": target_version,
            "message": f"Rollback initiated: {service_name} {current_version} → {target_version}"
        }

    def _tool_update_feature_flag(self, flag_name: str, enabled: bool,
                                   scope: str = "global") -> dict:
        return {
            "success": True,
            "flag_name": flag_name,
            "previous_value": not enabled,
            "new_value": enabled,
            "scope": scope,
            "message": f"Feature flag '{flag_name}' {'enabled' if enabled else 'disabled'} (scope: {scope})"
        }

    def _tool_create_incident_ticket(self, title: str, severity: str,
                                      description: str, affected_services: list) -> dict:
        import random
        ticket_num = random.randint(10000, 99999)
        return {
            "success": True,
            "ticket_id": f"INC-{ticket_num}",
            "title": title,
            "severity": severity,
            "url": f"https://clouddesk.atlassian.net/browse/INC-{ticket_num}"
        }

    # ── Communication Tools ───────────────────────────────────────

    def _tool_page_oncall(self, team_name: str, message: str, severity: str) -> dict:
        oncall_engineers = {
            "platform-oncall": "Arjun Patel",
            "core-product-oncall": "Lisa Wang",
            "engagement-oncall": "Carlos Rivera"
        }
        engineer = oncall_engineers.get(team_name, "Unknown")
        return {
            "success": True,
            "team": team_name,
            "paged_engineer": engineer,
            "severity": severity,
            "eta_minutes": 15 if severity in ("P1", "P2") else 60,
            "message": f"Paged {engineer} ({team_name}) for {severity} incident."
        }

    def _tool_send_status_update(self, channel: str, message: str) -> dict:
        import random
        return {
            "success": True,
            "channel": channel,
            "message_id": f"msg-{random.randint(100000, 999999)}",
            "message": f"Status update posted to {channel}"
        }

    # ── Internal Helpers ──────────────────────────────────────────

    @staticmethod
    def _load_json(path: Path) -> dict | list:
        with open(path, "r") as f:
            return json.load(f)

    @staticmethod
    def _load_log_file(path: Path) -> list[dict]:
        lines = []
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        lines.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return lines

    def _load_runbooks(self) -> list[dict]:
        runbooks = []
        if RUNBOOKS_DIR.exists():
            for rb_file in sorted(RUNBOOKS_DIR.glob("*.md")):
                content = rb_file.read_text()
                title = content.split("\n")[0].lstrip("# ").strip()
                runbooks.append({
                    "file": rb_file.name,
                    "title": title,
                    "content": content,
                    "tokens": self._tokenize(content)
                })
        return runbooks

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Simple tokenizer for BM25."""
        text = text.lower()
        text = re.sub(r"[^a-z0-9\s\-_]", " ", text)
        tokens = text.split()
        # Remove very short tokens and common stop words
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                      "has", "have", "had", "do", "does", "did", "will", "would",
                      "can", "could", "may", "might", "shall", "should", "must",
                      "and", "or", "but", "if", "then", "else", "when", "where",
                      "how", "what", "which", "who", "whom", "this", "that",
                      "these", "those", "it", "its", "to", "of", "in", "for",
                      "on", "with", "at", "by", "from", "as", "into", "not", "no"}
        return [t for t in tokens if len(t) > 1 and t not in stop_words]

    @staticmethod
    def _bm25_score(query_terms: list[str], doc_tokens: list[str],
                     num_docs: int, avg_doc_len: float,
                     k1: float = 1.5, b: float = 0.75) -> float:
        """Simplified BM25 scoring."""
        doc_len = len(doc_tokens)
        if doc_len == 0:
            return 0.0

        # Term frequency in document
        tf_map = {}
        for token in doc_tokens:
            tf_map[token] = tf_map.get(token, 0) + 1

        score = 0.0
        for term in query_terms:
            tf = tf_map.get(term, 0)
            if tf == 0:
                continue

            # IDF (simplified — assume each doc containing the term is 1)
            df = 1  # simplified: just check presence
            idf = math.log((num_docs - df + 0.5) / (df + 0.5) + 1)

            # BM25 TF component
            tf_norm = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * doc_len / avg_doc_len))
            score += idf * tf_norm

        return score

    @staticmethod
    def _find_relevant_section(query_terms: list[str], content: str,
                                max_lines: int = 15) -> str:
        """Find the most relevant section of a runbook for the query."""
        lines = content.split("\n")
        best_score = 0
        best_start = 0

        query_set = set(query_terms)

        for i in range(len(lines)):
            window = " ".join(lines[i:i + max_lines]).lower()
            score = sum(1 for term in query_set if term in window)
            if score > best_score:
                best_score = score
                best_start = i

        section = "\n".join(lines[best_start:best_start + max_lines])
        return section.strip()
