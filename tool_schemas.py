"""
CloudDesk Incident Response Agent — Tool Schemas

OpenAI function-calling schemas for all 17 mock tools.
These schemas are passed to the LLM so it knows how to call each tool.
"""

TOOL_SCHEMAS = [
    # ── Diagnostic Tools ──────────────────────────────────────────

    {
        "type": "function",
        "function": {
            "name": "get_service_status",
            "description": "Get the current status of a CloudDesk service including health checks, version, and uptime.",
            "parameters": {
                "type": "object",
                "required": ["service_name"],
                "properties": {
                    "service_name": {
                        "type": "string",
                        "description": "Name of the service (e.g., 'project-service', 'api-gateway')"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_service_metrics",
            "description": "Get time-series metrics for a service over a specified time range. Returns data points at 5-minute intervals.",
            "parameters": {
                "type": "object",
                "required": ["service_name", "metric_type"],
                "properties": {
                    "service_name": {
                        "type": "string",
                        "description": "Name of the service or infrastructure component"
                    },
                    "metric_type": {
                        "type": "string",
                        "enum": ["cpu", "memory", "disk", "request_rate", "error_rate", "latency_p50", "latency_p99"],
                        "description": "Type of metric to retrieve"
                    },
                    "time_range_minutes": {
                        "type": "integer",
                        "description": "How many minutes of history to retrieve (default: 60, max: 240)",
                        "default": 60
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_service_dependencies",
            "description": "Get the upstream and downstream dependencies of a service from the dependency graph.",
            "parameters": {
                "type": "object",
                "required": ["service_name"],
                "properties": {
                    "service_name": {
                        "type": "string",
                        "description": "Name of the service"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_logs",
            "description": "Search service logs with optional filters. Returns up to 25 matching log lines sorted by timestamp (newest first), plus total count.",
            "parameters": {
                "type": "object",
                "required": ["service_name"],
                "properties": {
                    "service_name": {
                        "type": "string",
                        "description": "Name of the service to search logs for"
                    },
                    "query": {
                        "type": "string",
                        "description": "Substring to search for in log messages (e.g., 'ERROR', 'timeout', 'connection pool')"
                    },
                    "log_level": {
                        "type": "string",
                        "enum": ["DEBUG", "INFO", "WARN", "ERROR", "FATAL"],
                        "description": "Filter logs by level"
                    },
                    "time_range_minutes": {
                        "type": "integer",
                        "description": "How many minutes of log history to search (default: 60, max: 240)",
                        "default": 60
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_deployment_history",
            "description": "Get recent deployment history for a service.",
            "parameters": {
                "type": "object",
                "required": ["service_name"],
                "properties": {
                    "service_name": {
                        "type": "string",
                        "description": "Name of the service"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of recent deployments to return (default: 5)",
                        "default": 5
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_deployment_diff",
            "description": "Get the code changes (diff) for a specific deployment.",
            "parameters": {
                "type": "object",
                "required": ["deploy_id"],
                "properties": {
                    "deploy_id": {
                        "type": "string",
                        "description": "Deployment ID (e.g., 'DEPLOY-PS-042')"
                    }
                }
            }
        }
    },

    # ── Source Code & Knowledge Tools ─────────────────────────────

    {
        "type": "function",
        "function": {
            "name": "get_source_code",
            "description": "Read a source code file from a service's codebase. Returns the file contents with line numbers.",
            "parameters": {
                "type": "object",
                "required": ["service_name", "file_path"],
                "properties": {
                    "service_name": {
                        "type": "string",
                        "description": "Name of the service"
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Path to the source file (e.g., 'ProjectService.java')"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_source_files",
            "description": "List all available source code files for a service.",
            "parameters": {
                "type": "object",
                "required": ["service_name"],
                "properties": {
                    "service_name": {
                        "type": "string",
                        "description": "Name of the service"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_runbooks",
            "description": "Search CloudDesk operational runbooks for relevant procedures and troubleshooting guides.",
            "parameters": {
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g., 'high latency investigation', 'database disk space')"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_customer_info",
            "description": "Get information about a CloudDesk customer including region, plan, and feature flags.",
            "parameters": {
                "type": "object",
                "required": ["customer_id"],
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "Customer ID (e.g., 'CUST-001')"
                    }
                }
            }
        }
    },

    # ── Action Tools ──────────────────────────────────────────────

    {
        "type": "function",
        "function": {
            "name": "restart_service",
            "description": "Restart a CloudDesk service. Use with caution — causes brief downtime for the service.",
            "parameters": {
                "type": "object",
                "required": ["service_name"],
                "properties": {
                    "service_name": {
                        "type": "string",
                        "description": "Name of the service to restart"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "scale_service",
            "description": "Scale a service to a specified number of replicas.",
            "parameters": {
                "type": "object",
                "required": ["service_name", "replicas"],
                "properties": {
                    "service_name": {
                        "type": "string",
                        "description": "Name of the service to scale"
                    },
                    "replicas": {
                        "type": "integer",
                        "description": "Target number of replicas",
                        "minimum": 1,
                        "maximum": 20
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rollback_deployment",
            "description": "Roll back a service to a previous version. This triggers a new deployment with the target version.",
            "parameters": {
                "type": "object",
                "required": ["service_name", "target_version"],
                "properties": {
                    "service_name": {
                        "type": "string",
                        "description": "Name of the service to roll back"
                    },
                    "target_version": {
                        "type": "string",
                        "description": "Version to roll back to (e.g., 'v2.3.0')"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_feature_flag",
            "description": "Enable or disable a feature flag, optionally scoped to specific customers or regions.",
            "parameters": {
                "type": "object",
                "required": ["flag_name", "enabled"],
                "properties": {
                    "flag_name": {
                        "type": "string",
                        "description": "Name of the feature flag (e.g., 'gdpr_strict_mode', 'beta_search_v2')"
                    },
                    "enabled": {
                        "type": "boolean",
                        "description": "Whether to enable or disable the flag"
                    },
                    "scope": {
                        "type": "string",
                        "description": "Optional scope — 'global', a customer ID, or a region (e.g., 'eu-west-1')"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_incident_ticket",
            "description": "Create an incident ticket in the CloudDesk incident management system.",
            "parameters": {
                "type": "object",
                "required": ["title", "severity", "description", "affected_services"],
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Brief title for the incident"
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["P1", "P2", "P3", "P4"],
                        "description": "Incident severity"
                    },
                    "description": {
                        "type": "string",
                        "description": "Detailed description of the incident"
                    },
                    "affected_services": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of affected service names"
                    }
                }
            }
        }
    },

    # ── Communication Tools ───────────────────────────────────────

    {
        "type": "function",
        "function": {
            "name": "page_oncall",
            "description": "Page the oncall engineer for a team. Use only for P1/P2 incidents.",
            "parameters": {
                "type": "object",
                "required": ["team_name", "message", "severity"],
                "properties": {
                    "team_name": {
                        "type": "string",
                        "description": "Oncall team name (e.g., 'platform-oncall', 'core-product-oncall')"
                    },
                    "message": {
                        "type": "string",
                        "description": "Message to include in the page"
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["P1", "P2", "P3", "P4"],
                        "description": "Incident severity"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_status_update",
            "description": "Send a status update to a communication channel (Slack, status page, etc.).",
            "parameters": {
                "type": "object",
                "required": ["channel", "message"],
                "properties": {
                    "channel": {
                        "type": "string",
                        "description": "Channel to post to (e.g., '#incidents', '#engineering', 'status-page')"
                    },
                    "message": {
                        "type": "string",
                        "description": "Status update message"
                    }
                }
            }
        }
    }
]
