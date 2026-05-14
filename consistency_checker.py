"""
CloudDesk Incident Response Agent — Consistency Checker

Validates cross-artifact consistency across the entire project.
Run this after any data modification to catch inconsistencies early.

Usage:
    python consistency_checker.py
    python consistency_checker.py --scenario eu_api_degradation
    python consistency_checker.py --verbose
"""

import argparse
import json
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent / "data"
SCENARIOS_DIR = BASE_DIR / "scenarios"
SERVICES_DIR = BASE_DIR / "services"
SOURCE_CODE_DIR = BASE_DIR / "source_code"
RUNBOOKS_DIR = BASE_DIR / "runbooks"
CUSTOMERS_DIR = BASE_DIR / "customers"
GOLDEN_DIR = BASE_DIR / "golden_dataset"


class ConsistencyChecker:
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.checks_passed = 0

        # Load shared data
        self.dep_graph = self._load_json(SERVICES_DIR / "dependency_graph.json")
        self.service_registry = self._load_json(SERVICES_DIR / "service_registry.json")
        self.customer_profiles = self._load_json(CUSTOMERS_DIR / "customer_profiles.json")

        self.all_services = set(self.dep_graph.get("services", {}).keys())
        self.app_services = set(self.service_registry.get("services", {}).keys())
        self.all_customers = set(self.customer_profiles.get("customers", {}).keys())

    def run(self, scenario_filter: str = None):
        """Run all consistency checks."""
        print("=" * 60)
        print("CloudDesk Consistency Checker")
        print("=" * 60)

        self._check_dependency_graph()
        self._check_source_code_files()
        self._check_runbooks()

        # Check each scenario
        scenarios = sorted(SCENARIOS_DIR.iterdir()) if SCENARIOS_DIR.exists() else []
        for scenario_dir in scenarios:
            if not scenario_dir.is_dir():
                continue
            if scenario_filter and scenario_dir.name != scenario_filter:
                continue
            self._check_scenario(scenario_dir)

        # Check golden dataset
        self._check_golden_dataset()

        # Print results
        self._print_results()

    def _check_dependency_graph(self):
        """Validate the dependency graph is internally consistent."""
        self._info("Checking dependency graph...")
        services = self.dep_graph.get("services", {})

        for svc, info in services.items():
            for dep in info.get("depends_on", []):
                if dep not in services:
                    self._error(f"Dependency graph: {svc} depends on '{dep}' which is not in the graph")
                else:
                    self._pass()

        # Check all app services exist in dep graph
        for svc in self.app_services:
            if svc not in services:
                self._error(f"Service '{svc}' in registry but not in dependency graph")
            else:
                self._pass()

    def _check_source_code_files(self):
        """Validate source code directory structure."""
        self._info("Checking source code files...")

        for svc in self.app_services:
            svc_dir = SOURCE_CODE_DIR / svc
            if not svc_dir.exists():
                self._error(f"Source code dir missing for service: {svc}")
                continue

            java_files = list(svc_dir.glob("*.java"))
            if not java_files:
                self._error(f"No Java files found for service: {svc}")
            else:
                self._pass()
                for jf in java_files:
                    content = jf.read_text()
                    if len(content.strip()) < 50:
                        self._error(f"Source file appears empty or too short: {svc}/{jf.name}")
                    else:
                        self._pass()

    def _check_runbooks(self):
        """Validate runbook files exist and have content."""
        self._info("Checking runbooks...")
        if not RUNBOOKS_DIR.exists():
            self._error("Runbooks directory missing")
            return

        runbooks = list(RUNBOOKS_DIR.glob("*.md"))
        if len(runbooks) < 5:
            self._warn(f"Only {len(runbooks)} runbooks found (expected ~10)")

        for rb in runbooks:
            content = rb.read_text()
            if not content.startswith("#"):
                self._warn(f"Runbook {rb.name} doesn't start with a heading")
            if len(content) < 200:
                self._warn(f"Runbook {rb.name} seems too short ({len(content)} chars)")
            self._pass()

    def _check_scenario(self, scenario_dir: Path):
        """Validate a single scenario's data."""
        name = scenario_dir.name
        self._info(f"Checking scenario: {name}...")

        # Check scenario.json exists and is valid
        scenario_file = scenario_dir / "scenario.json"
        if not scenario_file.exists():
            self._error(f"[{name}] scenario.json missing")
            return

        scenario = self._load_json(scenario_file)

        # Check required fields
        for field in ["id", "name", "difficulty", "timeline", "root_cause",
                       "affected_services", "correct_severity", "is_false_alarm"]:
            if field not in scenario:
                self._error(f"[{name}] scenario.json missing field: {field}")
            else:
                self._pass()

        # Check affected services exist
        for svc in scenario.get("affected_services", []):
            if svc not in self.all_services:
                self._error(f"[{name}] affected service '{svc}' not in dependency graph")
            else:
                self._pass()

        # Check affected customers exist
        for cust in scenario.get("affected_customers", []):
            if cust not in self.all_customers:
                self._error(f"[{name}] affected customer '{cust}' not in customer profiles")
            else:
                self._pass()

        # Check services_status references valid services
        for svc in scenario.get("services_status", {}):
            if svc not in self.app_services:
                self._error(f"[{name}] services_status references unknown service: {svc}")
            else:
                self._pass()

        # Check log files
        logs_dir = scenario_dir / "logs"
        if logs_dir.exists():
            for log_file in logs_dir.glob("*.log"):
                self._check_log_file(name, log_file, scenario)
        else:
            self._warn(f"[{name}] No logs directory")

        # Check metrics files
        metrics_dir = scenario_dir / "metrics"
        if metrics_dir.exists():
            for metric_file in metrics_dir.glob("*.json"):
                self._check_metric_file(name, metric_file, scenario)
        else:
            self._warn(f"[{name}] No metrics directory")

        # Check deployments
        deploy_dir = scenario_dir / "deployments"
        if deploy_dir.exists():
            self._check_deployments(name, deploy_dir, scenario)

    def _check_log_file(self, scenario_name: str, log_file: Path, scenario: dict):
        """Validate a log file's entries."""
        service = log_file.stem
        self._info(f"  Checking logs: {service}...")

        timeline = scenario.get("timeline", {})
        snapshot = timeline.get("scenario_snapshot_time", "")

        lines = []
        with open(log_file) as f:
            for i, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    lines.append(entry)
                except json.JSONDecodeError:
                    self._error(f"[{scenario_name}] {log_file.name}:{i} — invalid JSON")

        if not lines:
            self._error(f"[{scenario_name}] {log_file.name} is empty")
            return

        # Check log entries have required fields
        for entry in lines[:5]:
            for field in ["timestamp", "level", "message"]:
                if field not in entry:
                    self._error(f"[{scenario_name}] {log_file.name} — log entry missing '{field}'")
                    break
            else:
                self._pass()

        # Check timestamps are within reasonable range (not more than 24h before snapshot)
        if snapshot:
            for entry in lines:
                ts = entry.get("timestamp", "")
                if ts and ts > snapshot:
                    self._warn(f"[{scenario_name}] {log_file.name} has log entry after snapshot time: {ts}")
                    break

        # Check for stack traces referencing source code — validate line numbers
        for entry in lines:
            msg = entry.get("message", "")
            # Look for patterns like "at com.clouddesk.project.service.ProjectService.method(ProjectService.java:51)"
            stack_refs = re.findall(r'(\w+Service|\w+Controller|\w+Repository|\w+Filter)\.java:(\d+)', msg)
            for class_name, line_num in stack_refs:
                self._check_source_line_ref(scenario_name, service, class_name, int(line_num))

        self._pass()

    def _check_source_line_ref(self, scenario_name: str, service: str,
                                class_name: str, line_num: int):
        """Verify a stack trace line number reference exists in source code."""
        # Find the Java file
        found = False
        for svc_dir in SOURCE_CODE_DIR.iterdir():
            if not svc_dir.is_dir():
                continue
            java_file = svc_dir / f"{class_name}.java"
            if java_file.exists():
                content = java_file.read_text()
                total_lines = len(content.split("\n"))
                if line_num > total_lines:
                    self._error(
                        f"[{scenario_name}] Stack trace references {class_name}.java:{line_num} "
                        f"but file only has {total_lines} lines"
                    )
                else:
                    self._pass()
                found = True
                break

        if not found:
            self._warn(f"[{scenario_name}] Stack trace references {class_name}.java but file not found")

    def _check_metric_file(self, scenario_name: str, metric_file: Path, scenario: dict):
        """Validate a metrics file."""
        service = metric_file.stem
        self._info(f"  Checking metrics: {service}...")

        data = self._load_json(metric_file)
        if not isinstance(data, list):
            self._error(f"[{scenario_name}] {metric_file.name} — expected JSON array")
            return

        valid_types = {"cpu", "memory", "disk", "request_rate", "error_rate",
                       "latency_p50", "latency_p99"}

        for metric in data:
            mt = metric.get("metric_type", "")
            if mt not in valid_types:
                self._error(f"[{scenario_name}] {metric_file.name} — unknown metric type: {mt}")
            else:
                self._pass()

            points = metric.get("data", [])
            if not points:
                self._error(f"[{scenario_name}] {metric_file.name} — metric '{mt}' has no data points")
            else:
                self._pass()

                # Check data points are sorted by timestamp
                timestamps = [p["timestamp"] for p in points]
                if timestamps != sorted(timestamps):
                    self._error(f"[{scenario_name}] {metric_file.name} — metric '{mt}' timestamps not sorted")

    def _check_deployments(self, scenario_name: str, deploy_dir: Path, scenario: dict):
        """Validate deployment records and diffs."""
        self._info(f"  Checking deployments...")

        deploy_file = deploy_dir / "deployments.json"
        if deploy_file.exists():
            deploys = self._load_json(deploy_file)
            deploy_ids = set()
            for d in deploys:
                for field in ["deploy_id", "service", "timestamp", "version_to"]:
                    if field not in d:
                        self._error(f"[{scenario_name}] deployment missing field: {field}")
                deploy_ids.add(d.get("deploy_id"))
                # Check service exists
                svc = d.get("service", "")
                if svc not in self.all_services and svc not in self.app_services:
                    self._warn(f"[{scenario_name}] deployment for unknown service: {svc}")
                self._pass()

        diffs_file = deploy_dir / "diffs.json"
        if diffs_file.exists():
            diffs = self._load_json(diffs_file)
            if isinstance(diffs, dict):
                for did, diff in diffs.items():
                    if did not in deploy_ids:
                        self._warn(f"[{scenario_name}] diff for unknown deploy_id: {did}")
                    # Check file references
                    for fc in diff.get("files_changed", []):
                        file_path = fc.get("path", "")
                        # Extract service name and filename from path
                        parts = file_path.split("/")
                        if len(parts) >= 2:
                            svc_name = parts[0]
                            fname = parts[-1]
                            src_file = SOURCE_CODE_DIR / svc_name / fname
                            if not src_file.exists() and not file_path.startswith("infrastructure/"):
                                self._warn(f"[{scenario_name}] diff references file not in source_code: {file_path}")
                    self._pass()

    def _check_golden_dataset(self):
        """Validate golden dataset test cases."""
        self._info("Checking golden dataset...")

        if not GOLDEN_DIR.exists():
            self._warn("Golden dataset directory missing")
            return

        from schema import VALID_SERVICES, VALID_TOOLS

        for split_file in GOLDEN_DIR.glob("*.json"):
            split = split_file.stem
            self._info(f"  Checking split: {split}...")

            test_cases = self._load_json(split_file)
            if not isinstance(test_cases, list):
                self._error(f"[{split}] expected JSON array")
                continue

            ids_seen = set()
            for tc in test_cases:
                tc_id = tc.get("id", "UNKNOWN")

                # Check for duplicate IDs
                if tc_id in ids_seen:
                    self._error(f"[{split}] duplicate test case ID: {tc_id}")
                ids_seen.add(tc_id)

                # Check scenario exists
                scenario_id = tc.get("scenario_id", "")
                if not (SCENARIOS_DIR / scenario_id).exists():
                    self._error(f"[{split}:{tc_id}] scenario '{scenario_id}' doesn't exist")

                # Check expected services
                expected = tc.get("expected", {})
                for svc in expected.get("affected_services", []):
                    if svc not in VALID_SERVICES:
                        self._error(f"[{split}:{tc_id}] unknown affected service: {svc}")
                    else:
                        self._pass()

                # Check expected actions reference valid tools
                for action in expected.get("recommended_actions", []):
                    tool = action.get("tool", "")
                    if tool not in VALID_TOOLS:
                        self._error(f"[{split}:{tc_id}] unknown tool in actions: {tool}")
                    else:
                        self._pass()

                # Check severity
                severity = expected.get("severity_assessment", "")
                if severity not in ["P1", "P2", "P3", "P4"]:
                    self._error(f"[{split}:{tc_id}] invalid severity: {severity}")
                else:
                    self._pass()

                # Check difficulty
                difficulty = tc.get("difficulty", "")
                if difficulty not in ["easy", "medium", "hard"]:
                    self._error(f"[{split}:{tc_id}] invalid difficulty: {difficulty}")
                else:
                    self._pass()

                # Check ticket has required fields
                ticket = tc.get("ticket", {})
                for field in ["title", "description", "reporter", "severity", "timestamp"]:
                    if field not in ticket:
                        self._error(f"[{split}:{tc_id}] ticket missing field: {field}")
                    else:
                        self._pass()

    # ── Helpers ────────────────────────────────────────────────────

    @staticmethod
    def _load_json(path: Path) -> dict | list:
        with open(path) as f:
            return json.load(f)

    def _error(self, msg: str):
        self.errors.append(msg)
        if self.verbose:
            print(f"  ERROR: {msg}")

    def _warn(self, msg: str):
        self.warnings.append(msg)
        if self.verbose:
            print(f"  WARN:  {msg}")

    def _pass(self):
        self.checks_passed += 1

    def _info(self, msg: str):
        if self.verbose:
            print(msg)

    def _print_results(self):
        print(f"\n{'=' * 60}")
        print("RESULTS")
        print(f"{'=' * 60}")
        print(f"Checks passed:  {self.checks_passed}")
        print(f"Warnings:       {len(self.warnings)}")
        print(f"Errors:         {len(self.errors)}")

        if self.warnings:
            print(f"\nWarnings:")
            for w in self.warnings:
                print(f"  - {w}")

        if self.errors:
            print(f"\nErrors:")
            for e in self.errors:
                print(f"  - {e}")
            print(f"\n FAILED — {len(self.errors)} error(s) found")
            sys.exit(1)
        else:
            print(f"\n PASSED — all checks OK")


def main():
    parser = argparse.ArgumentParser(description="CloudDesk Consistency Checker")
    parser.add_argument("--scenario", type=str, default=None,
                        help="Check a specific scenario only")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show detailed check progress")
    args = parser.parse_args()

    checker = ConsistencyChecker(verbose=args.verbose)
    checker.run(scenario_filter=args.scenario)


if __name__ == "__main__":
    main()
