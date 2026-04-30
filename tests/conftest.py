"""Pytest configuration and fixtures."""

import pytest


@pytest.fixture
def temp_wiki_dir(tmp_path):
    """Create temporary wiki directory."""
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    return wiki_dir


@pytest.fixture
def temp_skills_dir(tmp_path):
    """Create temporary skills directory."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    return skills_dir


@pytest.fixture
def temp_workflows_dir(tmp_path):
    """Create temporary workflows directory."""
    workflows_dir = tmp_path / "workflows"
    workflows_dir.mkdir()
    return workflows_dir


@pytest.fixture
def sample_workflow_yaml(tmp_path):
    """Create a sample workflow YAML file."""
    content = """name: test-workflow
version: 1.0.0
description: Test workflow for testing
author: test
tags:
  - test
parameters:
  - name: project_name
    type: string
    required: true
steps:
  - name: Create directory
    tool: shell
    parameters:
      command: mkdir ${project_name}
  - name: Initialize git
    tool: shell
    parameters:
      command: cd ${project_name} && git init
"""
    workflow_file = tmp_path / "test-workflow.yaml"
    workflow_file.write_text(content)
    return workflow_file
