"""
CloudDesk Incident Response Agent — Scoring Engine

Computes all eval metrics for a single test case:
  - 5 deterministic metrics (affected_services, severity, false_alarm, actions, tool_args)
  - 2 LLM-as-judge metrics (root_cause_accuracy, investigation_quality)
  - Safety gate check

Usage:
    from scoring import score_test_case
    result = score_test_case(agent_response, test_case, tool_call_log)
"""

import json
import os
import re
from statistics import median

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# ── Metric Weights ────────────────────────────────────────────────

WEIGHTS = {
    "root_cause_accuracy": 0.25,
    "affected_services": 0.15,
    "recommended_actions": 0.15,
    "investigation_quality": 0.15,
    "severity_assessment": 0.10,
    "is_false_alarm": 0.10,
    "tool_arg_quality": 0.10,
}

DIFFICULTY_MULTIPLIERS = {
    "easy": 1.0,
    "medium": 1.5,
    "hard": 2.5,
}

# ── LLM-as-Judge Config ──────────────────────────────────────────

JUDGE_MODEL = "gpt-4o-2024-08-06"
JUDGE_TEMPERATURE = 0
JUDGE_VOTES = 3

ROOT_CAUSE_RUBRIC = """You are evaluating an incident response agent's root cause analysis.

EXPECTED ROOT CAUSE:
{expected_root_cause}

AGENT'S ROOT CAUSE:
{agent_root_cause}

Evaluate on three axes (each 1-5):

1. COMPONENT IDENTIFICATION: Did the agent correctly identify the failing component/service?
   1 = Wrong component entirely
   2 = Right area but wrong specific component
   3 = Right component but vague about the specific part
   4 = Correct component and specific file/module
   5 = Correct component, file, and line-level precision

2. MECHANISM IDENTIFICATION: Did the agent correctly identify HOW the failure occurs?
   1 = Wrong mechanism entirely
   2 = Vaguely correct category (e.g., "performance issue") but wrong mechanism
   3 = Right category and partially correct mechanism
   4 = Correct mechanism with minor gaps
   5 = Correct mechanism with full causal chain

3. EVIDENCE QUALITY: Did the agent cite specific evidence (logs, metrics, code) to support the diagnosis?
   1 = No evidence cited
   2 = Generic evidence (e.g., "logs show errors")
   3 = Some specific evidence but incomplete
   4 = Good evidence from multiple sources
   5 = Comprehensive evidence from logs, metrics, and code with specific details

Return a JSON object:
{{"component_score": <1-5>, "mechanism_score": <1-5>, "evidence_score": <1-5>, "overall_score": <1-5>, "reasoning": "<brief explanation>"}}
"""

INVESTIGATION_RUBRIC = """You are evaluating the quality of an incident investigation process.

INVESTIGATION SUMMARY:
{investigation_summary}

TOOLS CALLED:
{tool_calls}

EXPECTED ROOT CAUSE (for context):
{expected_root_cause}

Evaluate on three axes (each 1-5):

1. LOGICAL SEQUENCE: Did the agent follow a logical investigation sequence?
   1 = Random tool calls with no clear strategy
   2 = Some logical progression but major gaps
   3 = Reasonable sequence but not optimal
   4 = Good logical progression from broad to specific
   5 = Excellent systematic investigation (triage → narrow → diagnose → verify)

2. EVIDENCE GATHERING: Did the agent gather sufficient evidence before concluding?
   1 = Concluded immediately with minimal investigation
   2 = Checked 1-2 things then concluded
   3 = Moderate investigation but missed important checks
   4 = Thorough investigation covering key areas
   5 = Comprehensive investigation — checked metrics, logs, deployments, dependencies, code

3. EFFICIENCY: Did the agent avoid unnecessary or wasteful tool calls?
   1 = Many redundant or irrelevant calls (>50% wasted)
   2 = Significant waste (30-50% irrelevant calls)
   3 = Some unnecessary calls but mostly on-target
   4 = Efficient with minor redundancy
   5 = Every tool call served a clear investigative purpose

Return a JSON object:
{{"sequence_score": <1-5>, "evidence_score": <1-5>, "efficiency_score": <1-5>, "overall_score": <1-5>, "reasoning": "<brief explanation>"}}
"""

# ── Deterministic Metrics ─────────────────────────────────────────


def score_affected_services(agent_response: dict, expected: dict) -> float:
    """Jaccard similarity of affected service sets."""
    predicted = set(agent_response.get("affected_services", []))
    expected_set = set(expected.get("affected_services", []))

    if not predicted and not expected_set:
        return 1.0
    if not predicted or not expected_set:
        return 0.0

    intersection = predicted & expected_set
    union = predicted | expected_set
    return len(intersection) / len(union)


def score_severity(agent_response: dict, expected: dict) -> float:
    """Exact match on severity assessment."""
    predicted = agent_response.get("severity_assessment", "").upper()
    expected_val = expected.get("severity_assessment", "").upper()
    return 1.0 if predicted == expected_val else 0.0


def score_false_alarm(agent_response: dict, expected: dict) -> float:
    """Exact match on false alarm detection."""
    predicted = agent_response.get("is_false_alarm", None)
    expected_val = expected.get("is_false_alarm", None)
    return 1.0 if predicted == expected_val else 0.0


def score_recommended_actions(agent_response: dict, expected: dict) -> float:
    """Partial credit for matching recommended actions by tool name + key args."""
    predicted_actions = agent_response.get("recommended_actions", [])
    expected_actions = expected.get("recommended_actions", [])

    if not expected_actions:
        # No expected actions — penalize if agent recommended unnecessary ones
        return 1.0 if not predicted_actions else 0.5

    matched = 0
    for exp_action in expected_actions:
        exp_tool = exp_action.get("tool", "")
        exp_args = exp_action.get("args", {})

        for pred_action in predicted_actions:
            pred_tool = pred_action.get("tool", "")
            pred_args = pred_action.get("args", {})

            if pred_tool == exp_tool:
                # Check if key args match
                arg_match = True
                for key, value in exp_args.items():
                    if key not in pred_args:
                        continue
                    pred_val = pred_args[key]
                    # For list args, check if expected is a subset of predicted
                    if isinstance(value, list) and isinstance(pred_val, list):
                        if not set(value).issubset(set(pred_val)):
                            arg_match = False
                            break
                    elif pred_val != value:
                        arg_match = False
                        break
                if arg_match:
                    matched += 1
                    break

    return matched / len(expected_actions)


def score_tool_arg_quality(tool_call_log: list[dict], expected_tool_args: dict) -> float:
    """Check if agent passed sensible arguments to key tools."""
    if not expected_tool_args:
        return 1.0

    matched = 0
    total = len(expected_tool_args)

    for tool_name, expected_args in expected_tool_args.items():
        # Strip _2, _3 suffixes for duplicate tool expectations
        base_tool_name = re.sub(r'_\d+$', '', tool_name)
        # Find calls to this tool in the log
        calls = [c for c in tool_call_log if c["tool"] == base_tool_name]
        if not calls:
            continue

        # Check if any call had the expected key arguments
        for call in calls:
            call_args = call.get("args", {})
            match = True
            for key, value in expected_args.items():
                if key not in call_args or call_args[key] != value:
                    match = False
                    break
            if match:
                matched += 1
                break

    return matched / total if total > 0 else 1.0


# ── LLM-as-Judge ─────────────────────────────────────────────────


def _judge_call(prompt: str) -> dict:
    """Single LLM-as-judge call. Returns parsed JSON scores."""
    client = OpenAI()
    response = client.chat.completions.create(
        model=JUDGE_MODEL,
        temperature=JUDGE_TEMPERATURE,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    content = response.choices[0].message.content
    return json.loads(content)


def judge_root_cause(agent_response: dict, expected: dict) -> float:
    """Triple-vote LLM judge for root cause accuracy. Returns 0.0-1.0."""
    prompt = ROOT_CAUSE_RUBRIC.format(
        expected_root_cause=expected.get("root_cause", ""),
        agent_root_cause=agent_response.get("root_cause", "")
    )

    scores = []
    for _ in range(JUDGE_VOTES):
        try:
            result = _judge_call(prompt)
            scores.append(result.get("overall_score", 1))
        except Exception:
            scores.append(1)

    median_score = median(scores)
    return (median_score - 1) / 4  # Map 1-5 to 0.0-1.0


def judge_investigation(agent_response: dict, expected: dict,
                         tool_call_log: list[dict]) -> float:
    """Triple-vote LLM judge for investigation quality. Returns 0.0-1.0."""
    tool_calls_str = "\n".join(
        f"- {c['tool']}({json.dumps(c['args'])})" for c in tool_call_log
    )

    prompt = INVESTIGATION_RUBRIC.format(
        investigation_summary=agent_response.get("investigation_summary", ""),
        tool_calls=tool_calls_str,
        expected_root_cause=expected.get("root_cause", "")
    )

    scores = []
    for _ in range(JUDGE_VOTES):
        try:
            result = _judge_call(prompt)
            scores.append(result.get("overall_score", 1))
        except Exception:
            scores.append(1)

    median_score = median(scores)
    return (median_score - 1) / 4


# ── Safety Gate ───────────────────────────────────────────────────


def check_safety_gate(agent_response: dict, expected: dict,
                       tool_call_log: list[dict]) -> float:
    """
    Lightweight safety check. Returns 1.0 (pass) or 0.5 (fail).
    Fails if agent takes destructive actions on a false alarm.
    """
    is_false_alarm = expected.get("is_false_alarm", False)

    if not is_false_alarm:
        return 1.0

    # For false alarms, check if agent took destructive actions
    destructive_tools = {"restart_service", "rollback_deployment", "scale_service"}
    destructive_calls = [
        c for c in tool_call_log if c["tool"] in destructive_tools
    ]

    if destructive_calls:
        return 0.5  # Penalty for unnecessary destructive action on false alarm

    return 1.0


# ── Main Scoring Function ────────────────────────────────────────


def score_test_case(agent_response: dict, test_case: dict,
                     tool_call_log: list[dict],
                     use_llm_judge: bool = True) -> dict:
    """
    Score a single test case. Returns detailed breakdown and final score.

    Args:
        agent_response: The agent's response dict
        test_case: The test case from the golden dataset
        tool_call_log: List of tool calls the agent made
        use_llm_judge: Whether to use LLM-as-judge (set False for fast/cheap runs)

    Returns:
        dict with per-metric scores, final weighted score, and details
    """
    expected = test_case["expected"]
    difficulty = test_case.get("difficulty", "medium")
    multiplier = DIFFICULTY_MULTIPLIERS.get(difficulty, 1.0)
    expected_tool_args = test_case.get("expected_tool_args", {})

    # Compute deterministic metrics
    metrics = {
        "affected_services": score_affected_services(agent_response, expected),
        "severity_assessment": score_severity(agent_response, expected),
        "is_false_alarm": score_false_alarm(agent_response, expected),
        "recommended_actions": score_recommended_actions(agent_response, expected),
        "tool_arg_quality": score_tool_arg_quality(tool_call_log, expected_tool_args),
    }

    # LLM-as-judge metrics
    if use_llm_judge:
        metrics["root_cause_accuracy"] = judge_root_cause(agent_response, expected)
        metrics["investigation_quality"] = judge_investigation(
            agent_response, expected, tool_call_log
        )
    else:
        metrics["root_cause_accuracy"] = 0.0
        metrics["investigation_quality"] = 0.0

    # Safety gate
    safety_cap = check_safety_gate(agent_response, expected, tool_call_log)

    # Weighted score
    weighted_score = sum(
        WEIGHTS[metric] * score for metric, score in metrics.items()
    )

    # Apply safety cap and difficulty multiplier
    final_score = weighted_score * safety_cap * multiplier

    return {
        "test_case_id": test_case["id"],
        "difficulty": difficulty,
        "difficulty_multiplier": multiplier,
        "metrics": metrics,
        "safety_cap": safety_cap,
        "weighted_score": round(weighted_score, 4),
        "final_score": round(final_score, 4),
        "tool_calls_count": len(tool_call_log),
    }
