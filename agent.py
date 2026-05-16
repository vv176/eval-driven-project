"""
CloudDesk Incident Response Agent — Student Starter Kit

This is YOUR agent. Modify this file to build an AI agent that investigates
production incidents for CloudDesk.

Your agent receives:
  1. A support ticket describing an incident
  2. A ToolExecutor with 17 tools for investigating the incident

Your agent must return a structured response (see schema.py) with:
  - Root cause analysis
  - Affected services
  - Severity assessment (P1-P4)
  - Recommended actions
  - Whether it's a false alarm

Run the eval to measure your agent's accuracy:
  python evaluate.py --scenario eu_api_degradation --split train

Iterate: improve your agent → run eval → check scores → repeat.
"""

import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from schema import RESPONSE_SCHEMA, VALID_SERVICES, VALID_TOOLS
from tool_schemas import TOOL_SCHEMAS
from tools import ToolExecutor

load_dotenv()
client = OpenAI()

MODEL = "gpt-4o"

SYSTEM_PROMPT = """You are an incident response agent for CloudDesk, a B2B SaaS platform.
You investigate production incidents by using diagnostic tools, analyzing logs and metrics,
and determining root causes.

When given a support ticket, you should:
1. Gather information using the available tools
2. Analyze the evidence
3. Determine the root cause, affected services, and severity
4. Recommend appropriate actions

Always think step by step and gather sufficient evidence before making conclusions."""


class IncidentAgent:
    def __init__(self, model: str = MODEL):
        self.model = model
        self.messages = []

    def investigate(self, ticket: dict, tools: ToolExecutor) -> dict:
        """
        Investigate an incident ticket and return a structured response.

        Args:
            ticket: The support ticket (title, description, reporter, severity, timestamp)
            tools: ToolExecutor instance — call tools.execute(tool_name, **kwargs)

        Returns:
            A dict matching RESPONSE_SCHEMA (see schema.py)
        """
        # Build the initial message with the ticket
        ticket_text = (
            f"INCIDENT TICKET\n"
            f"Title: {ticket['title']}\n"
            f"Description: {ticket['description']}\n"
            f"Reporter: {ticket['reporter']}\n"
            f"Reported Severity: {ticket['severity']}\n"
            f"Time: {ticket['timestamp']}\n"
        )

        self.messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": ticket_text}
        ]

        # ── Agent loop: call LLM → execute tools → repeat ──
        max_iterations = 15
        for _ in range(max_iterations):
            response = client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                tools=TOOL_SCHEMAS,
                tool_choice="auto"
            )

            message = response.choices[0].message
            self.messages.append(message)

            # If no tool calls, the agent is done — extract the response
            if not message.tool_calls:
                return self._parse_response(message.content)

            # Execute each tool call
            for tool_call in message.tool_calls:
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments)

                result = tools.execute(fn_name, **fn_args)

                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result)
                })

        # If we hit max iterations, try to get a final answer
        self.messages.append({
            "role": "user",
            "content": "Please provide your final analysis now based on everything you've gathered."
        })

        response = client.chat.completions.create(
            model=self.model,
            messages=self.messages
        )

        return self._parse_response(response.choices[0].message.content)

    def _parse_response(self, content: str) -> dict:
        """Parse the LLM's final response into the expected schema."""
        # Try to extract JSON from the response
        try:
            # Look for JSON block in the response
            json_match = content
            if "```json" in content:
                json_match = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                json_match = content.split("```")[1].split("```")[0]

            return json.loads(json_match)
        except (json.JSONDecodeError, IndexError):
            # Fallback: return a basic structure with the raw content
            return {
                "root_cause": content,
                "affected_services": [],
                "severity_assessment": "P3",
                "recommended_actions": [],
                "is_false_alarm": False,
                "confidence": 0.3,
                "investigation_summary": content
            }


# ── Quick test ────────────────────────────────────────────────────

if __name__ == "__main__":
    # Run a quick test with the eu_api_degradation scenario
    executor = ToolExecutor("eu_api_degradation")

    test_ticket = {
        "title": "EU customers reporting slow project loading",
        "description": "Multiple EU enterprise customers (Meridian Analytics, Quantum Financial) "
                       "are reporting that project listing pages take 5-10 seconds to load. "
                       "US customers are not affected. Started approximately 1 hour ago.",
        "reporter": "support-team",
        "severity": "P2",
        "timestamp": "2024-01-15T14:30:00Z"
    }

    agent = IncidentAgent()
    result = agent.investigate(test_ticket, executor)

    print("\n" + "=" * 60)
    print("AGENT RESPONSE")
    print("=" * 60)
    print(json.dumps(result, indent=2))
