# E-CLI Test Suite

This directory contains comprehensive tests for E-CLI 2.0 enhancements.

## Test Structure

```
tests/
├── __init__.py              # Test configuration
├── conftest.py             # Pytest fixtures
├── unit/                   # Unit tests
│   ├── test_skills_base.py
│   ├── test_skills_registry.py
│   ├── test_workflow_manager.py
│   └── test_wiki_page.py
└── integration/            # Integration tests
    ├── test_rag_wiki_integration.py
    └── test_workflow_integration.py
```

## Running Tests

### All Tests
```bash
pytest tests/
```

### Unit Tests Only
```bash
pytest tests/unit/
```

### Integration Tests Only
```bash
pytest tests/integration/
```

### Specific Test File
```bash
pytest tests/unit/test_skills_base.py
```

### With Coverage
```bash
pytest --cov=src/e_cli --cov-report=html tests/
```

### Verbose Output
```bash
pytest -v tests/
```

## Test Coverage

### Unit Tests

**Skills System:**
- `test_skills_base.py` - SkillMetadata, SkillResult, BaseSkill
- `test_skills_registry.py` - SkillRegistry operations

**Workflows:**
- `test_workflow_manager.py` - Workflow, WorkflowStep, WorkflowManager, WorkflowExecutor

**Wiki:**
- `test_wiki_page.py` - WikiPage, WikiLink, wikilink parsing

### Integration Tests

**RAG Integration:**
- `test_rag_wiki_integration.py` - RAG search with wiki corpus

**Workflow Integration:**
- `test_workflow_integration.py` - Workflow execution with tools and skills

## Writing New Tests

### Unit Test Template

```python
"""Unit tests for module_name."""

import pytest
from e_cli.module import ClassName


class TestClassName:
    """Test ClassName."""

    def test_method_name(self):
        """Test specific behavior."""
        # Arrange
        obj = ClassName()

        # Act
        result = obj.method()

        # Assert
        assert result == expected
```

### Integration Test Template

```python
"""Integration tests for feature."""

import pytest
from unittest.mock import Mock


class TestFeatureIntegration:
    """Test feature integration."""

    @pytest.fixture
    def setup(self, tmp_path):
        """Set up test environment."""
        # Setup code
        return test_data

    def test_integration_scenario(self, setup):
        """Test integration scenario."""
        # Test code
        assert condition
```

## Test Dependencies

Tests use:
- `pytest` - Test framework
- `pytest-cov` - Coverage reporting
- `unittest.mock` - Mocking for integration tests

Install test dependencies:
```bash
pip install pytest pytest-cov
```

## Continuous Integration

Tests run automatically on:
- Pull requests
- Commits to main branch
- Release tags

See `.github/workflows/test.yml` for CI configuration.

## Coverage Goals

- **Unit Tests**: 80%+ coverage of new modules
- **Integration Tests**: Key integration points tested
- **E2E Tests**: Major user workflows validated

## Known Limitations

- Some tests require external dependencies (git, docker)
- Cloud provider tests require API keys
- Network-dependent tests may be flaky

## Future Test Additions

- [ ] Multi-provider switching tests
- [ ] Shell completion generation tests
- [ ] Menu rendering tests
- [ ] Personality adaptation tests
- [ ] Wiki indexer performance tests
