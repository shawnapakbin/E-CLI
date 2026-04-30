"""Workflow and macro system for E-CLI."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from e_cli.config import get_app_dir


@dataclass
class WorkflowStep:
    """A single step in a workflow."""

    name: str
    tool: str
    parameters: dict[str, Any] = field(default_factory=dict)
    condition: str | None = None  # Optional condition for execution


@dataclass
class Workflow:
    """A workflow definition."""

    name: str
    description: str
    version: str = "1.0.0"
    author: str = "user"
    parameters: list[dict[str, Any]] = field(default_factory=list)
    steps: list[WorkflowStep] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    @staticmethod
    def from_yaml(yaml_path: Path) -> Workflow:
        """Load workflow from YAML file."""
        import yaml

        with open(yaml_path) as f:
            data = yaml.safe_load(f)

        steps = []
        for step_data in data.get("steps", []):
            steps.append(
                WorkflowStep(
                    name=step_data["name"],
                    tool=step_data["tool"],
                    parameters=step_data.get("parameters", {}),
                    condition=step_data.get("condition"),
                )
            )

        return Workflow(
            name=data["name"],
            description=data.get("description", ""),
            version=data.get("version", "1.0.0"),
            author=data.get("author", "user"),
            parameters=data.get("parameters", []),
            steps=steps,
            tags=data.get("tags", []),
        )

    def save(self, workflow_dir: Path) -> None:
        """Save workflow to YAML file."""
        import yaml

        workflow_file = workflow_dir / f"{self.name}.yaml"
        workflow_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "tags": self.tags,
            "parameters": self.parameters,
            "steps": [
                {
                    "name": step.name,
                    "tool": step.tool,
                    "parameters": step.parameters,
                    **({"condition": step.condition} if step.condition else {}),
                }
                for step in self.steps
            ],
        }

        with open(workflow_file, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)


class WorkflowManager:
    """Manages workflows and macros."""

    def __init__(self, workflows_dir: Path | None = None) -> None:
        """Initialize workflow manager."""
        if workflows_dir is None:
            workflows_dir = get_app_dir() / "workflows"

        self.workflows_dir = workflows_dir
        self.workflows_dir.mkdir(parents=True, exist_ok=True)

    def list_workflows(self) -> list[Workflow]:
        """List all available workflows."""
        workflows = []

        for yaml_file in self.workflows_dir.glob("*.yaml"):
            try:
                workflow = Workflow.from_yaml(yaml_file)
                workflows.append(workflow)
            except Exception:
                continue

        return workflows

    def get_workflow(self, name: str) -> Workflow | None:
        """Get a workflow by name."""
        workflow_file = self.workflows_dir / f"{name}.yaml"

        if not workflow_file.exists():
            return None

        try:
            return Workflow.from_yaml(workflow_file)
        except Exception:
            return None

    def save_workflow(self, workflow: Workflow) -> None:
        """Save a workflow."""
        workflow.save(self.workflows_dir)

    def delete_workflow(self, name: str) -> bool:
        """Delete a workflow."""
        workflow_file = self.workflows_dir / f"{name}.yaml"

        if workflow_file.exists():
            workflow_file.unlink()
            return True

        return False


class WorkflowExecutor:
    """Executes workflows."""

    def __init__(
        self,
        tool_router: Any | None = None,
        skill_manager: Any | None = None,
        timeout_seconds: int = 120,
    ) -> None:
        """Initialize workflow executor.

        Args:
            tool_router: Optional ToolRouter instance for tool execution
            skill_manager: Optional SkillManager instance for skill execution
            timeout_seconds: Default timeout for tool/skill execution
        """
        self.tool_router = tool_router
        self.skill_manager = skill_manager
        self.timeout_seconds = timeout_seconds

    def _substitute_parameters(self, text: str, params: dict[str, Any]) -> str:
        """Substitute parameter placeholders in text.

        Supports both ${param} and {param} syntax.

        Args:
            text: Text with parameter placeholders
            params: Parameter values

        Returns:
            Text with substituted values
        """

        result = text

        # Substitute ${param} style
        for key, value in params.items():
            result = result.replace(f"${{{key}}}", str(value))
            result = result.replace(f"{{{key}}}", str(value))

        return result

    def execute(
        self,
        workflow: Workflow,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a workflow.

        Args:
            workflow: Workflow to execute
            parameters: Runtime parameters

        Returns:
            Execution results
        """
        params = parameters or {}
        results = {
            "workflow": workflow.name,
            "steps": [],
            "success": True,
            "error": None,
        }

        for step in workflow.steps:
            # Evaluate condition if present
            if step.condition:
                # Substitute parameters in condition
                condition = self._substitute_parameters(step.condition, params)

                # Simple condition evaluation (can be enhanced)
                try:
                    if not eval(condition, {}, params):
                        results["steps"].append({
                            "name": step.name,
                            "skipped": True,
                            "reason": "Condition not met",
                        })
                        continue
                except Exception as e:
                    results["steps"].append({
                        "name": step.name,
                        "error": f"Condition evaluation failed: {e}",
                    })
                    results["success"] = False
                    break

            # Execute step
            step_result = {
                "name": step.name,
                "tool": step.tool,
                "status": "pending",
            }

            try:
                # Substitute parameters in step parameters
                step_params = {}
                for key, value in step.parameters.items():
                    if isinstance(value, str):
                        step_params[key] = self._substitute_parameters(value, params)
                    else:
                        step_params[key] = value

                # Execute based on tool type
                if self.tool_router and step.tool in [
                    "shell", "git.diff", "http.get", "browser", "ssh", "curl",
                    "rag.search", "file.read", "file.write", "file.list"
                ]:
                    # Execute via ToolRouter
                    from e_cli.agent.protocol import ToolCall

                    # Build ToolCall from step parameters
                    tool_call = ToolCall(tool=step.tool, **step_params)
                    tool_result = self.tool_router.execute(tool_call, self.timeout_seconds)

                    if tool_result.ok:
                        step_result["status"] = "completed"
                        step_result["output"] = tool_result.output[:500]  # Truncate for display
                    else:
                        step_result["status"] = "failed"
                        step_result["error"] = tool_result.output
                        results["success"] = False

                elif self.skill_manager and step.tool.startswith("skill:"):
                    # Execute via SkillManager
                    skill_name = step.tool.replace("skill:", "")
                    skill_result = self.skill_manager.execute_skill(skill_name, **step_params)

                    if skill_result.ok:
                        step_result["status"] = "completed"
                        step_result["output"] = skill_result.output[:500]  # Truncate
                    else:
                        step_result["status"] = "failed"
                        step_result["error"] = skill_result.error
                        results["success"] = False

                else:
                    # Unknown tool or no router available - simulate execution
                    step_result["status"] = "simulated"
                    step_result["note"] = "Tool router not available, execution simulated"

            except Exception as e:
                step_result["status"] = "error"
                step_result["error"] = str(e)
                results["success"] = False

            results["steps"].append(step_result)

            # Stop on first failure unless configured otherwise
            if not results["success"]:
                break

        return results
