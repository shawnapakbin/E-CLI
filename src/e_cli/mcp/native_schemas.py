"""JSON Schema definitions for all 9 native e-cli tools with safetyClass annotations."""

from __future__ import annotations

from typing import Any

# Each entry: name -> {"description": ..., "inputSchema": {...}, "safetyClass": ...}
NATIVE_TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "shell": {
        "description": "Execute a shell command and return its output.",
        "safetyClass": "mutating",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute."},
            },
            "required": ["command"],
        },
    },
    "file.read": {
        "description": "Read the contents of a file at the given path.",
        "safetyClass": "read-only",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative or absolute file path to read."},
            },
            "required": ["path"],
        },
    },
    "file.write": {
        "description": "Write content to a file at the given path.",
        "safetyClass": "mutating",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative or absolute file path to write."},
                "content": {"type": "string", "description": "Content to write into the file."},
            },
            "required": ["path", "content"],
        },
    },
    "git.diff": {
        "description": "Show git diff for the workspace or a specific path.",
        "safetyClass": "read-only",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Optional path to limit the diff scope."},
            },
            "required": [],
        },
    },
    "http.get": {
        "description": "Perform an HTTP GET request and return the response body.",
        "safetyClass": "read-only",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to fetch."},
            },
            "required": ["url"],
        },
    },
    "browser": {
        "description": "Open a URL in a headless browser and return the page content.",
        "safetyClass": "mutating",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to open in the browser."},
            },
            "required": ["url"],
        },
    },
    "ssh": {
        "description": "Execute a command on a remote host via SSH.",
        "safetyClass": "elevated",
        "inputSchema": {
            "type": "object",
            "properties": {
                "host": {"type": "string", "description": "Remote hostname or IP address."},
                "command": {"type": "string", "description": "Command to execute on the remote host."},
                "user": {"type": "string", "description": "SSH username (optional)."},
                "port": {"type": "integer", "description": "SSH port (optional, default 22)."},
                "identityFile": {"type": "string", "description": "Path to SSH identity file (optional)."},
            },
            "required": ["host", "command"],
        },
    },
    "curl": {
        "description": "Perform an HTTP request using curl semantics.",
        "safetyClass": "mutating",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL for the request."},
                "method": {"type": "string", "description": "HTTP method (default GET)."},
                "headers": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                    "description": "Optional HTTP headers.",
                },
                "content": {"type": "string", "description": "Optional request body."},
            },
            "required": ["url"],
        },
    },
    "rag.search": {
        "description": "Search the RAG memory store for relevant chunks.",
        "safetyClass": "read-only",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query string."},
                "corpus": {
                    "type": "string",
                    "description": "Corpus to search: session, workspace, or combined.",
                },
                "topK": {"type": "integer", "description": "Number of results to return."},
            },
            "required": ["query"],
        },
    },
}


def get_native_schema(tool_name: str) -> dict[str, Any] | None:
    """Return the schema dict for a native tool, or None if not found."""
    return NATIVE_TOOL_SCHEMAS.get(tool_name)
