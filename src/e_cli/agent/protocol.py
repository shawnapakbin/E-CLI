"""Tool-calling protocol contracts and parser helpers."""

from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

ToolName = Literal["shell", "file.read", "file.write", "git.diff", "http.get", "done"]


class ToolCall(BaseModel):
    """Represents one requested tool invocation emitted by the model."""

    tool: ToolName = Field(...)
    command: str | None = Field(default=None)
    path: str | None = Field(default=None)
    url: str | None = Field(default=None)
    content: str | None = Field(default=None)
    reason: str | None = Field(default=None)


class ToolResult(BaseModel):
    """Represents one normalized tool execution result returned to the model."""

    ok: bool
    output: str


class ParsedAgentOutput(BaseModel):
    """Represents parser result with optional tool call and fallback assistant message."""

    toolCall: ToolCall | None = None
    assistantMessage: str = ""


def _extractJsonObjects(text: str) -> list[str]:
    """Return candidate JSON object strings from mixed assistant output."""

    try:
        candidates: list[str] = []
        stripped = text.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            candidates.append(stripped)

        fencedMatches = re.findall(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text, flags=re.IGNORECASE)
        for match in fencedMatches:
            candidate = match.strip()
            if candidate:
                candidates.append(candidate)

        depth = 0
        startIndex = -1
        inString = False
        escaped = False
        for index, char in enumerate(text):
            if inString:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    inString = False
                continue

            if char == '"':
                inString = True
                continue

            if char == "{":
                if depth == 0:
                    startIndex = index
                depth += 1
            elif char == "}":
                if depth > 0:
                    depth -= 1
                    if depth == 0 and startIndex >= 0:
                        candidate = text[startIndex : index + 1].strip()
                        if candidate:
                            candidates.append(candidate)
                        startIndex = -1

        deduped: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            if candidate not in seen:
                deduped.append(candidate)
                seen.add(candidate)
        return deduped
    except Exception:
        return []


def _tryParseToolCall(candidate: str) -> ToolCall | None:
    """Parse one JSON candidate to a validated ToolCall, if possible."""

    try:
        parsedJson = json.loads(candidate)
        if not isinstance(parsedJson, dict):
            return None
        return ToolCall(**parsedJson)
    except (json.JSONDecodeError, ValidationError, TypeError):
        return None


def _extractAssistantText(value: object) -> str | None:
    """Extract a plain-text assistant response from generic JSON payloads."""

    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None

    if isinstance(value, dict):
        preferredKeys = ("response", "message", "content", "answer", "text")
        for key in preferredKeys:
            if key in value:
                extracted = _extractAssistantText(value[key])
                if extracted:
                    return extracted

    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            extracted = _extractAssistantText(item)
            if extracted:
                parts.append(extracted)
        if parts:
            return "\n".join(parts)

    return None


def _tryParseAssistantJson(candidate: str) -> str | None:
    """Parse non-tool JSON replies and extract plain assistant text when possible."""

    try:
        parsedJson = json.loads(candidate)
        if not isinstance(parsedJson, dict):
            return None
        return _extractAssistantText(parsedJson)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def parse_tool_call(model_output: str) -> ParsedAgentOutput:
    """Parse model output as JSON tool call and fallback to plain assistant text."""

    try:
        strippedOutput = model_output.strip()
        candidates = _extractJsonObjects(model_output)
        for candidate in candidates:
            toolCall = _tryParseToolCall(candidate)
            if toolCall is not None:
                return ParsedAgentOutput(toolCall=toolCall, assistantMessage="")

        # Some models wrap normal replies like {"response": "..."}; unwrap these to plain text.
        assistantJsonText = _tryParseAssistantJson(strippedOutput)
        if assistantJsonText:
            return ParsedAgentOutput(toolCall=None, assistantMessage=assistantJsonText)

        for candidate in candidates:
            candidateAssistantText = _tryParseAssistantJson(candidate)
            if candidateAssistantText:
                return ParsedAgentOutput(toolCall=None, assistantMessage=candidateAssistantText)

        return ParsedAgentOutput(toolCall=None, assistantMessage=strippedOutput)
    except Exception:
        return ParsedAgentOutput(toolCall=None, assistantMessage=model_output.strip())
