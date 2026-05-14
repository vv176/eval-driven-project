"""
CloudDesk Incident Response Agent — Evaluation Harness

Runs your agent against the golden dataset and computes scores.

Usage:
    # Run on train split (you can see expected answers)
    python evaluate.py --split train

    # Run on dev split (you see scores but not expected answers)
    python evaluate.py --split dev

    # Run on a specific scenario only
    python evaluate.py --split train --scenario eu_api_degradation

    # Fast mode (skip LLM-as-judge — cheaper but less accurate scoring)
    python evaluate.py --split train --fast

    # Run a single test case
    python evaluate.py --split train --test-case eu_api_001
"""

import argparse
import json
import sys
import time
from pathlib import Path

from schema import validate_response
from scoring import score_test_case, WEIGHTS
from tools import ToolExecutor

DATASET_DIR = Path(__file__).parent / "data" / "golden_dataset"


def load_dataset(split: str) -> list[dict]:
    """Load test cases from a dataset split."""
    path = DATASET_DIR / f"{split}.json"
    if not path.exists():
        print(f"Error: Dataset split '{split}' not found at {path}")
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def run_single_test(agent, test_case: dict,
                     use_llm_judge: bool = True,
                     verbose: bool = False) -> dict:
    """Run the agent on a single test case and return scored results."""
    scenario_id = test_case["scenario_id"]
    ticket = test_case["ticket"]

    # Create a fresh tool executor for this scenario
    executor = ToolExecutor(scenario_id, verbose=verbose)

    if verbose:
        print(f"\n{'━' * 70}")
        print(f"  TICKET: {ticket['title']}")
        print(f"  Severity: {ticket['severity']} | Reporter: {ticket['reporter']}")
        print(f"  Time: {ticket['timestamp']}")
        print(f"  {ticket['description'][:200]}")
        print(f"{'━' * 70}")

    # Run the agent
    start_time = time.time()
    try:
        response = agent.investigate(ticket, executor)
    except Exception as e:
        response = {
            "root_cause": f"Agent error: {str(e)}",
            "affected_services": [],
            "severity_assessment": "P3",
            "recommended_actions": [],
            "is_false_alarm": False,
            "confidence": 0.0,
            "investigation_summary": f"Agent crashed: {str(e)}"
        }
    elapsed = time.time() - start_time

    if verbose:
        print(f"\n{'━' * 70}")
        print(f"  AGENT RESPONSE")
        print(f"{'━' * 70}")
        print(f"  Root Cause: {str(response.get('root_cause', ''))[:300]}")
        print(f"  Affected Services: {response.get('affected_services', [])}")
        print(f"  Severity: {response.get('severity_assessment', '?')}")
        print(f"  Is False Alarm: {response.get('is_false_alarm', '?')}")
        print(f"  Confidence: {response.get('confidence', '?')}")
        actions = response.get('recommended_actions', [])
        if actions:
            print(f"  Recommended Actions:")
            for a in actions:
                print(f"    - {a.get('tool', '?')}: {a.get('args', {})}")
        else:
            print(f"  Recommended Actions: (none)")
        print(f"  Tool Calls Made: {len(executor.tool_call_log)}")
        print(f"{'━' * 70}")

    # Validate response schema
    errors = validate_response(response)
    if errors:
        print(f"  Warning: Response validation errors: {errors}")

    # Score the response
    result = score_test_case(
        agent_response=response,
        test_case=test_case,
        tool_call_log=executor.tool_call_log,
        use_llm_judge=use_llm_judge
    )

    result["elapsed_seconds"] = round(elapsed, 2)
    result["agent_response"] = response
    result["validation_errors"] = errors

    return result


def print_results(results: list[dict], detailed: bool = True):
    """Print a formatted results table."""
    print("\n" + "=" * 80)
    print("EVALUATION RESULTS")
    print("=" * 80)

    if detailed:
        for r in results:
            print(f"\n{'─' * 60}")
            print(f"Test Case: {r['test_case_id']}")
            print(f"Difficulty: {r['difficulty']} (x{r['difficulty_multiplier']})")
            print(f"Time: {r['elapsed_seconds']}s | Tool calls: {r['tool_calls_count']}")
            print(f"Safety: {'PASS' if r['safety_cap'] == 1.0 else 'FAIL (capped at 50%)'}")

            print(f"\nMetrics:")
            for metric, score in r["metrics"].items():
                weight = WEIGHTS[metric]
                print(f"  {metric:30s}  {score:.2f}  (weight: {weight:.0%})")

            print(f"\nWeighted Score: {r['weighted_score']:.4f}")
            print(f"Final Score:    {r['final_score']:.4f}")

            if r.get("validation_errors"):
                print(f"\nValidation Errors: {r['validation_errors']}")

    # Summary
    print(f"\n{'=' * 80}")
    print("SUMMARY")
    print(f"{'=' * 80}")

    total_score = sum(r["final_score"] for r in results)
    total_multiplier = sum(r["difficulty_multiplier"] for r in results)
    overall = total_score / total_multiplier if total_multiplier > 0 else 0

    print(f"Test cases:     {len(results)}")
    print(f"Total score:    {total_score:.2f} / {total_multiplier:.1f}")
    print(f"Overall score:  {overall:.2%}")
    print(f"Avg time/case:  {sum(r['elapsed_seconds'] for r in results) / len(results):.1f}s")
    print(f"Avg tool calls: {sum(r['tool_calls_count'] for r in results) / len(results):.1f}")

    # Per-metric averages
    print(f"\nPer-metric averages:")
    for metric in WEIGHTS:
        avg = sum(r["metrics"][metric] for r in results) / len(results)
        print(f"  {metric:30s}  {avg:.2f}")

    safety_fails = sum(1 for r in results if r["safety_cap"] < 1.0)
    if safety_fails:
        print(f"\nSafety gate failures: {safety_fails}/{len(results)}")

    return overall


def main():
    parser = argparse.ArgumentParser(description="Evaluate your CloudDesk Incident Response Agent")
    parser.add_argument("--split", choices=["train", "dev", "hidden"], default="train",
                        help="Dataset split to evaluate on (default: train)")
    parser.add_argument("--scenario", type=str, default=None,
                        help="Filter to a specific scenario (e.g., eu_api_degradation)")
    parser.add_argument("--test-case", type=str, default=None,
                        help="Run a single test case by ID")
    parser.add_argument("--fast", action="store_true",
                        help="Skip LLM-as-judge for faster/cheaper evaluation")
    parser.add_argument("--output", type=str, default=None,
                        help="Save detailed results to a JSON file")
    parser.add_argument("--agent", type=str, default="agent",
                        help="Agent module to use (default: agent, e.g. agent_reference)")
    parser.add_argument("--verbose", action="store_true",
                        help="Show detailed tool call logs (tool name, args, results)")
    args = parser.parse_args()

    # Load dataset
    test_cases = load_dataset(args.split)
    print(f"Loaded {len(test_cases)} test cases from '{args.split}' split")

    # Filter by scenario
    if args.scenario:
        test_cases = [tc for tc in test_cases if tc["scenario_id"] == args.scenario]
        print(f"Filtered to {len(test_cases)} cases for scenario: {args.scenario}")

    # Filter by test case ID
    if args.test_case:
        test_cases = [tc for tc in test_cases if tc["id"] == args.test_case]
        if not test_cases:
            print(f"Error: Test case '{args.test_case}' not found")
            sys.exit(1)

    if not test_cases:
        print("No test cases to evaluate.")
        sys.exit(0)

    # Create agent from specified module
    import importlib
    agent_module = importlib.import_module(args.agent)
    agent = agent_module.IncidentAgent()
    use_llm_judge = not args.fast

    if args.fast:
        print("Fast mode: LLM-as-judge metrics will be scored as 0.0")

    # Run evaluation
    results = []
    for i, test_case in enumerate(test_cases):
        if not args.verbose:
            print(f"\n[{i+1}/{len(test_cases)}] Running: {test_case['id']}...", end="", flush=True)
        else:
            print(f"\n[{i+1}/{len(test_cases)}] Running: {test_case['id']}")
        result = run_single_test(agent, test_case, use_llm_judge=use_llm_judge,
                                  verbose=args.verbose)
        results.append(result)
        if not args.verbose:
            print(f" Score: {result['final_score']:.3f} ({result['elapsed_seconds']}s)")
        else:
            print(f"\n  >>> Score: {result['final_score']:.3f} ({result['elapsed_seconds']}s)")

    # Print results
    overall = print_results(results, detailed=len(results) <= 20)

    # Save to file if requested
    if args.output:
        output_data = {
            "split": args.split,
            "scenario": args.scenario,
            "overall_score": overall,
            "results": results
        }
        with open(args.output, "w") as f:
            json.dump(output_data, f, indent=2, default=str)
        print(f"\nDetailed results saved to: {args.output}")


if __name__ == "__main__":
    main()
