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

    def __init__(self) -> None:
        """Initialize workflow executor."""
        pass

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
                # Simple condition evaluation (can be enhanced)
                try:
                    if not eval(step.condition, {}, params):
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

            # Execute step (placeholder - would integrate with tools/skills)
            step_result = {
                "name": step.name,
                "tool": step.tool,
                "status": "pending",
            }

            # Here would be actual tool execution
            # For now, mark as executed
            step_result["status"] = "executed"

            results["steps"].append(step_result)

        return results
