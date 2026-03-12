"""Tests for tool-calling protocol parsing."""

from e_cli.agent.protocol import parse_tool_call


def test_parse_tool_call_valid_json() -> None:
    """Verifies valid tool JSON is parsed into a tool call object."""

    parsed = parse_tool_call('{"tool":"shell","command":"echo test"}')
    assert parsed.toolCall is not None
    assert parsed.toolCall.tool == "shell"
    assert parsed.toolCall.command == "echo test"


def test_parse_tool_call_plain_text_fallback() -> None:
    """Verifies non-JSON output is preserved as plain assistant text."""

    parsed = parse_tool_call("I think nginx service is misconfigured")
    assert parsed.toolCall is None
    assert "nginx" in parsed.assistantMessage


def test_parse_tool_call_json_in_fenced_block() -> None:
    """Verifies parser extracts and validates JSON tool calls from fenced markdown."""

    parsed = parse_tool_call(
        """
I will inspect service status first.
```json
{"tool":"shell","command":"systemctl status nginx","reason":"check service health"}
```
"""
    )
    assert parsed.toolCall is not None
    assert parsed.toolCall.tool == "shell"
    assert parsed.toolCall.command == "systemctl status nginx"


def test_parse_tool_call_json_embedded_in_text() -> None:
    """Verifies parser can find JSON tool calls when surrounded by plain text."""

    parsed = parse_tool_call(
        "Run this next: {\"tool\":\"file.read\",\"path\":\"README.md\",\"reason\":\"gather context\"} then summarize"
    )
    assert parsed.toolCall is not None
    assert parsed.toolCall.tool == "file.read"
    assert parsed.toolCall.path == "README.md"


def test_parse_tool_call_ignores_invalid_json_objects() -> None:
    """Verifies invalid JSON snippets do not suppress later valid tool JSON."""

    parsed = parse_tool_call(
        "Bad: {not valid} and then {\"tool\":\"done\",\"reason\":\"complete\"}"
    )
    assert parsed.toolCall is not None
    assert parsed.toolCall.tool == "done"
    assert parsed.toolCall.reason == "complete"


def test_parse_tool_call_unwraps_json_response_payload() -> None:
    """Verifies non-tool JSON response wrappers are converted to plain assistant text."""

    parsed = parse_tool_call('{"response":"Hello! How can I help?"}')
    assert parsed.toolCall is None
    assert parsed.assistantMessage == "Hello! How can I help?"


def test_parse_tool_call_unwraps_nested_json_message_payload() -> None:
    """Verifies nested response/message/content wrappers are flattened to plain text."""

    parsed = parse_tool_call('{"message":{"content":"I am E-CLI."}}')
    assert parsed.toolCall is None
    assert parsed.assistantMessage == "I am E-CLI."


def test_parse_tool_call_browser_json() -> None:
    """Verifies parser accepts browser tool payloads."""

    parsed = parse_tool_call('{"tool":"browser","url":"https://example.com"}')
    assert parsed.toolCall is not None
    assert parsed.toolCall.tool == "browser"
    assert parsed.toolCall.url == "https://example.com"


def test_parse_tool_call_ssh_json() -> None:
    """Verifies parser accepts SSH tool payloads with host and command."""

    parsed = parse_tool_call('{"tool":"ssh","host":"server.local","command":"uname -a"}')
    assert parsed.toolCall is not None
    assert parsed.toolCall.tool == "ssh"
    assert parsed.toolCall.host == "server.local"


def test_parse_tool_call_curl_json() -> None:
    """Verifies parser accepts curl tool payloads with method and URL."""

    parsed = parse_tool_call('{"tool":"curl","url":"https://example.com","method":"POST"}')
    assert parsed.toolCall is not None
    assert parsed.toolCall.tool == "curl"
    assert parsed.toolCall.method == "POST"


def test_parse_tool_call_rag_search_json() -> None:
    """Verifies parser accepts rag.search payloads with query/corpus fields."""

    parsed = parse_tool_call('{"tool":"rag.search","query":"router execute","corpus":"combined","topK":5}')
    assert parsed.toolCall is not None
    assert parsed.toolCall.tool == "rag.search"
    assert parsed.toolCall.query == "router execute"
    assert parsed.toolCall.corpus == "combined"
