"""Property-based tests for Task_Envelope and Result_Envelope.

**Validates: Requirements 4.1, 4.2, 11.4**
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from e_cli.sub_agent.models import Result_Envelope, Task_Envelope

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

valid_status = st.sampled_from(["completed", "failed", "timeout"])


def result_envelope_strategy():
    return st.builds(
        Result_Envelope,
        task_id=st.text(min_size=1),
        status=valid_status,
        output=st.text(),
        confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        tool_calls_made=st.integers(min_value=0),
    )


# ---------------------------------------------------------------------------
# Task_Envelope property tests
# ---------------------------------------------------------------------------


@given(task=st.text(min_size=1))
@settings(max_examples=100)
def test_task_envelope_construction_with_arbitrary_task(task: str) -> None:
    """Task_Envelope can be constructed with any non-empty task string."""
    envelope = Task_Envelope(task=task)
    assert envelope.task == task


@given(task=st.text(min_size=1))
@settings(max_examples=100)
def test_task_envelope_default_tool_allowlist(task: str) -> None:
    """Default tool_allowlist always contains the four read-only tools."""
    envelope = Task_Envelope(task=task)
    assert envelope.tool_allowlist == ["file.read", "http.get", "rag.search", "git.diff"]


@given(task=st.text(min_size=1))
@settings(max_examples=100)
def test_task_envelope_default_timeout(task: str) -> None:
    """Default timeout_seconds is always 120."""
    envelope = Task_Envelope(task=task)
    assert envelope.timeout_seconds == 120


@given(task=st.text(min_size=1))
@settings(max_examples=100)
def test_task_envelope_default_model_params(task: str) -> None:
    """Default model_params always has temperature=0.1 and top_p=0.95."""
    envelope = Task_Envelope(task=task)
    assert envelope.model_params == {"temperature": 0.1, "top_p": 0.95}


@given(task=st.text(min_size=1))
@settings(max_examples=100)
def test_task_envelope_task_field_preserved(task: str) -> None:
    """task field is always the non-empty string that was provided."""
    envelope = Task_Envelope(task=task)
    assert len(envelope.task) >= 1
    assert envelope.task == task


# ---------------------------------------------------------------------------
# Property 8: Result_Envelope completeness
# **Validates: Requirements 4.1, 4.2, 11.4**
# ---------------------------------------------------------------------------


@given(result=result_envelope_strategy())
@settings(max_examples=100)
def test_result_envelope_all_required_fields_present(result: Result_Envelope) -> None:
    """Property 8: Result_Envelope always has all five required fields present.

    **Validates: Requirements 4.1, 4.2, 11.4**
    """
    assert hasattr(result, "task_id")
    assert hasattr(result, "status")
    assert hasattr(result, "output")
    assert hasattr(result, "confidence")
    assert hasattr(result, "tool_calls_made")


@given(result=result_envelope_strategy())
@settings(max_examples=100)
def test_result_envelope_confidence_in_range(result: Result_Envelope) -> None:
    """Property 8: confidence is always in [0.0, 1.0].

    **Validates: Requirements 4.2, 11.4**
    """
    assert 0.0 <= result.confidence <= 1.0


@given(result=result_envelope_strategy())
@settings(max_examples=100)
def test_result_envelope_task_id_is_string(result: Result_Envelope) -> None:
    """task_id is always a non-empty string.

    **Validates: Requirements 4.2**
    """
    assert isinstance(result.task_id, str)
    assert len(result.task_id) >= 1


@given(result=result_envelope_strategy())
@settings(max_examples=100)
def test_result_envelope_status_is_valid(result: Result_Envelope) -> None:
    """status is always one of the three valid literals.

    **Validates: Requirements 4.2**
    """
    assert result.status in {"completed", "failed", "timeout"}


@given(result=result_envelope_strategy())
@settings(max_examples=100)
def test_result_envelope_tool_calls_made_non_negative(result: Result_Envelope) -> None:
    """tool_calls_made is always a non-negative integer.

    **Validates: Requirements 4.2**
    """
    assert isinstance(result.tool_calls_made, int)
    assert result.tool_calls_made >= 0


@given(result=result_envelope_strategy())
@settings(max_examples=100)
def test_result_envelope_output_is_string(result: Result_Envelope) -> None:
    """output is always a string.

    **Validates: Requirements 4.2**
    """
    assert isinstance(result.output, str)
