"""
CloudDesk Incident Response Agent — Response Schema

Defines the expected output format for the student's agent.
The eval harness validates agent responses against this schema.
"""

RESPONSE_SCHEMA = {
    "type": "object",
    "required": [
        "root_cause",
        "affected_services",
        "severity_assessment",
        "recommended_actions",
        "is_false_alarm",
        "confidence",
        "investigation_summary"
    ],
    "properties": {
        "root_cause": {
            "type": "string",
            "description": "Free text explanation of the root cause. Should identify the specific component, mechanism, and evidence."
        },
        "affected_services": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of service names affected by this incident (e.g., ['project-service', 'api-gateway'])"
        },
        "severity_assessment": {
            "type": "string",
            "enum": ["P1", "P2", "P3", "P4"],
            "description": "Incident severity: P1 (critical), P2 (high), P3 (medium), P4 (low)"
        },
        "recommended_actions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["tool", "args"],
                "properties": {
                    "tool": {"type": "string"},
                    "args": {"type": "object"}
                }
            },
            "description": "List of recommended actions, each with a tool name and arguments"
        },
        "is_false_alarm": {
            "type": "boolean",
            "description": "True if the incident is a false alarm (e.g., monitoring misconfiguration)"
        },
        "confidence": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "description": "Agent's confidence in its diagnosis (0.0 to 1.0)"
        },
        "investigation_summary": {
            "type": "string",
            "description": "Step-by-step summary of the investigation process and reasoning"
        }
    }
}

# Valid service names in CloudDesk
VALID_SERVICES = [
    "api-gateway",
    "project-service",
    "task-service",
    "notification-service",
    "auth-service",
    "search-service",
    "project-db",
    "task-db",
    "auth-db",
    "redis-cache",
    "redis-session",
    "redis-queue",
    "elasticsearch",
    "email-service"
]

# Valid tool names for recommended_actions
VALID_TOOLS = [
    "restart_service",
    "scale_service",
    "rollback_deployment",
    "update_feature_flag",
    "create_incident_ticket",
    "page_oncall",
    "send_status_update"
]


def validate_response(response: dict) -> list[str]:
    """Validate an agent response against the schema. Returns list of errors."""
    errors = []

    for field in RESPONSE_SCHEMA["required"]:
        if field not in response:
            errors.append(f"Missing required field: {field}")

    if "affected_services" in response:
        for svc in response["affected_services"]:
            if svc not in VALID_SERVICES:
                errors.append(f"Unknown service: {svc}")

    if "severity_assessment" in response:
        if response["severity_assessment"] not in ["P1", "P2", "P3", "P4"]:
            errors.append(f"Invalid severity: {response['severity_assessment']}")

    if "recommended_actions" in response:
        for action in response["recommended_actions"]:
            if "tool" not in action or "args" not in action:
                errors.append(f"Action missing 'tool' or 'args': {action}")
            elif action["tool"] not in VALID_TOOLS:
                errors.append(f"Unknown tool in action: {action['tool']}")

    if "confidence" in response:
        if not (0.0 <= response["confidence"] <= 1.0):
            errors.append(f"Confidence out of range: {response['confidence']}")

    if "is_false_alarm" in response:
        if not isinstance(response["is_false_alarm"], bool):
            errors.append(f"is_false_alarm must be boolean, got: {type(response['is_false_alarm'])}")

    return errors
