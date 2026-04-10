from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Task_Envelope(BaseModel):
    task: str
    context: str = ""
    tool_allowlist: list[str] = Field(
        default_factory=lambda: ["file.read", "http.get", "rag.search", "git.diff"]
    )
    result_schema: dict[str, Any] | None = None
    timeout_seconds: int = 120
    model_params: dict[str, float] = Field(
        default_factory=lambda: {"temperature": 0.1, "top_p": 0.95}
    )


class Result_Envelope(BaseModel):
    task_id: str
    status: Literal["completed", "failed", "timeout"]
    output: str
    confidence: float = 0.5
    tool_calls_made: int = 0
    schema_valid: bool | None = None
    schema_errors: list[str] = Field(default_factory=list)
    duration_seconds: float = 0.0
