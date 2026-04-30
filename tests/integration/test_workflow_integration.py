"""Integration tests for workflow execution with tools."""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock

from e_cli.workflows.manager import Workflow, WorkflowStep, WorkflowExecutor
from e_cli.agent.protocol import ToolCall, ToolResult


class TestWorkflowToolIntegration:
    """Test workflow execution with tool integration."""

    def test_workflow_with_mock_tool_router(self):
        """Test workflow execution with mocked tool router."""
        # Create mock tool router
        mock_router = Mock()
        mock_router.execute = Mock(return_value=ToolResult(
            ok=True,
            output="Command executed successfully"
        ))

        # Create executor with mock router
        executor = WorkflowExecutor(tool_router=mock_router)

        # Create workflow
        workflow = Workflow(
            name="test-workflow",
            description="Test workflow with tools",
            steps=[
                WorkflowStep(
                    name="Run shell command",
                    tool="shell",
                    parameters={"command": "echo hello"},
                ),
            ],
        )

        # Execute workflow
        result = executor.execute(workflow)

        # Verify execution
        assert result["success"] is True
        assert len(result["steps"]) == 1
        assert result["steps"][0]["status"] == "completed"
        mock_router.execute.assert_called_once()

    def test_workflow_with_failing_tool(self):
        """Test workflow handling tool failure."""
        # Create mock router that fails
        mock_router = Mock()
        mock_router.execute = Mock(return_value=ToolResult(
            ok=False,
            output="Tool execution failed"
        ))

        executor = WorkflowExecutor(tool_router=mock_router)

        workflow = Workflow(
            name="failing-workflow",
            description="Workflow with failing tool",
            steps=[
                WorkflowStep("Fail", "shell", {"command": "fail"}),
                WorkflowStep("Skip", "shell", {"command": "skip"}),
            ],
        )

        result = executor.execute(workflow)

        # Workflow should stop on first failure
        assert result["success"] is False
        assert len(result["steps"]) == 1
        assert result["steps"][0]["status"] == "failed"

    def test_workflow_with_parameter_substitution_in_tools(self):
        """Test parameter substitution in tool parameters."""
        mock_router = Mock()
        mock_router.execute = Mock(return_value=ToolResult(
            ok=True,
            output="Success"
        ))

        executor = WorkflowExecutor(tool_router=mock_router)

        workflow = Workflow(
            name="params-workflow",
            description="Workflow with parameters",
            steps=[
                WorkflowStep(
                    "Echo name",
                    "shell",
                    {"command": "echo ${username}"},
                ),
            ],
        )

        result = executor.execute(workflow, {"username": "alice"})

        # Verify parameter was substituted
        assert result["success"] is True
        call_args = mock_router.execute.call_args
        tool_call = call_args[0][0]
        assert "alice" in str(tool_call)


class TestWorkflowSkillIntegration:
    """Test workflow execution with skill integration."""

    def test_workflow_with_mock_skill_manager(self):
        """Test workflow execution with mocked skill manager."""
        from e_cli.skills.base import SkillResult

        # Create mock skill manager
        mock_manager = Mock()
        mock_manager.execute_skill = Mock(return_value=SkillResult(
            ok=True,
            output="Skill executed successfully"
        ))

        executor = WorkflowExecutor(skill_manager=mock_manager)

        workflow = Workflow(
            name="skill-workflow",
            description="Workflow with skills",
            steps=[
                WorkflowStep(
                    "Run git-helper",
                    "skill:git-helper",
                    {"operation": "status"},
                ),
            ],
        )

        result = executor.execute(workflow)

        assert result["success"] is True
        assert result["steps"][0]["status"] == "completed"
        mock_manager.execute_skill.assert_called_once_with(
            "git-helper",
            operation="status"
        )

    def test_workflow_with_mixed_tools_and_skills(self):
        """Test workflow with both tools and skills."""
        from e_cli.skills.base import SkillResult

        mock_router = Mock()
        mock_router.execute = Mock(return_value=ToolResult(
            ok=True,
            output="Tool success"
        ))

        mock_manager = Mock()
        mock_manager.execute_skill = Mock(return_value=SkillResult(
            ok=True,
            output="Skill success"
        ))

        executor = WorkflowExecutor(
            tool_router=mock_router,
            skill_manager=mock_manager
        )

        workflow = Workflow(
            name="mixed-workflow",
            description="Mix of tools and skills",
            steps=[
                WorkflowStep("Tool step", "shell", {"command": "test"}),
                WorkflowStep("Skill step", "skill:test", {"param": "value"}),
            ],
        )

        result = executor.execute(workflow)

        assert result["success"] is True
        assert len(result["steps"]) == 2
        mock_router.execute.assert_called_once()
        mock_manager.execute_skill.assert_called_once()
