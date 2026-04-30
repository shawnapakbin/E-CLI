"""Unit tests for workflow manager."""


from e_cli.workflows.manager import Workflow, WorkflowStep, WorkflowManager, WorkflowExecutor


class TestWorkflowStep:
    """Test WorkflowStep dataclass."""

    def test_step_creation(self):
        """Test creating a workflow step."""
        step = WorkflowStep(
            name="Test Step",
            tool="shell",
            parameters={"command": "echo test"},
            condition="True",
        )

        assert step.name == "Test Step"
        assert step.tool == "shell"
        assert step.parameters == {"command": "echo test"}
        assert step.condition == "True"

    def test_step_without_condition(self):
        """Test step without condition."""
        step = WorkflowStep(
            name="Simple Step",
            tool="shell",
            parameters={},
        )

        assert step.condition is None


class TestWorkflow:
    """Test Workflow dataclass."""

    def test_workflow_creation(self):
        """Test creating a workflow."""
        workflow = Workflow(
            name="test-workflow",
            description="Test workflow",
            version="1.0.0",
            author="tester",
            parameters=[{"name": "param1", "type": "string"}],
            steps=[
                WorkflowStep("Step 1", "shell", {"command": "echo 1"}),
                WorkflowStep("Step 2", "shell", {"command": "echo 2"}),
            ],
            tags=["test"],
        )

        assert workflow.name == "test-workflow"
        assert workflow.description == "Test workflow"
        assert len(workflow.steps) == 2
        assert len(workflow.parameters) == 1
        assert workflow.tags == ["test"]

    def test_workflow_save_and_load(self, tmp_path):
        """Test saving and loading workflow."""
        workflow = Workflow(
            name="save-test",
            description="Save test workflow",
            steps=[
                WorkflowStep("Test", "shell", {"command": "test"}),
            ],
        )

        # Save workflow
        workflow.save(tmp_path)
        saved_file = tmp_path / "save-test.yaml"
        assert saved_file.exists()

        # Load workflow
        loaded = Workflow.from_yaml(saved_file)
        assert loaded.name == "save-test"
        assert loaded.description == "Save test workflow"
        assert len(loaded.steps) == 1
        assert loaded.steps[0].name == "Test"


class TestWorkflowManager:
    """Test WorkflowManager class."""

    def test_manager_initialization(self, tmp_path):
        """Test manager initialization."""
        manager = WorkflowManager(tmp_path)
        assert manager.workflows_dir == tmp_path
        assert manager.workflows_dir.exists()

    def test_list_workflows_empty(self, tmp_path):
        """Test listing workflows when empty."""
        manager = WorkflowManager(tmp_path)
        workflows = manager.list_workflows()
        assert len(workflows) == 0

    def test_save_and_get_workflow(self, tmp_path):
        """Test saving and retrieving workflow."""
        manager = WorkflowManager(tmp_path)
        workflow = Workflow(
            name="test-workflow",
            description="Test",
            steps=[],
        )

        # Save workflow
        manager.save_workflow(workflow)

        # Get workflow
        retrieved = manager.get_workflow("test-workflow")
        assert retrieved is not None
        assert retrieved.name == "test-workflow"

    def test_delete_workflow(self, tmp_path):
        """Test deleting a workflow."""
        manager = WorkflowManager(tmp_path)
        workflow = Workflow(name="delete-me", description="", steps=[])

        manager.save_workflow(workflow)
        assert manager.get_workflow("delete-me") is not None

        result = manager.delete_workflow("delete-me")
        assert result is True
        assert manager.get_workflow("delete-me") is None

    def test_list_workflows(self, tmp_path):
        """Test listing multiple workflows."""
        manager = WorkflowManager(tmp_path)

        workflow1 = Workflow("workflow1", "First", steps=[])
        workflow2 = Workflow("workflow2", "Second", steps=[])

        manager.save_workflow(workflow1)
        manager.save_workflow(workflow2)

        workflows = manager.list_workflows()
        assert len(workflows) == 2
        assert any(w.name == "workflow1" for w in workflows)
        assert any(w.name == "workflow2" for w in workflows)


class TestWorkflowExecutor:
    """Test WorkflowExecutor class."""

    def test_executor_initialization(self):
        """Test executor initialization."""
        executor = WorkflowExecutor()
        assert executor.tool_router is None
        assert executor.skill_manager is None
        assert executor.timeout_seconds == 120

    def test_parameter_substitution(self):
        """Test parameter substitution."""
        executor = WorkflowExecutor()

        text = "Hello ${name}, version {version}"
        params = {"name": "World", "version": "1.0"}

        result = executor._substitute_parameters(text, params)
        assert result == "Hello World, version 1.0"

    def test_execute_simple_workflow(self):
        """Test executing a simple workflow."""
        executor = WorkflowExecutor()
        workflow = Workflow(
            name="simple",
            description="Simple workflow",
            steps=[
                WorkflowStep("Step 1", "unknown-tool", {}),
            ],
        )

        result = executor.execute(workflow)
        assert result["workflow"] == "simple"
        assert len(result["steps"]) == 1
        assert result["steps"][0]["status"] == "simulated"

    def test_execute_with_condition(self):
        """Test executing workflow with conditions."""
        executor = WorkflowExecutor()
        workflow = Workflow(
            name="conditional",
            description="Conditional workflow",
            steps=[
                WorkflowStep("Skip Me", "shell", {}, condition="False"),
                WorkflowStep("Run Me", "unknown", {}),
            ],
        )

        result = executor.execute(workflow, {"value": True})
        assert len(result["steps"]) == 2
        assert result["steps"][0]["skipped"] is True
        assert result["steps"][1]["status"] == "simulated"

    def test_execute_with_parameter_substitution(self):
        """Test workflow execution with parameter substitution."""
        executor = WorkflowExecutor()
        workflow = Workflow(
            name="params",
            description="Parameterized workflow",
            steps=[
                WorkflowStep(
                    "Echo",
                    "unknown",
                    {"message": "Hello ${user}"}
                ),
            ],
        )

        result = executor.execute(workflow, {"user": "Alice"})
        # Even though tool is unknown, parameters should be substituted
        assert result["workflow"] == "params"
