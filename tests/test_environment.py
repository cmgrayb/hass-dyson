"""Test project structure and development environment."""

import subprocess
import sys
from pathlib import Path


def test_project_structure():
    """Test that all required files exist."""
    project_root = Path(__file__).parent.parent

    # Check main project files
    assert (project_root / "pyproject.toml").exists()
    assert (project_root / "README.md").exists()
    assert (project_root / "LICENSE").exists()

    # Check custom component structure
    custom_components = project_root / "custom_components" / "hass_dyson"
    assert custom_components.exists()
    assert (custom_components / "__init__.py").exists()
    assert (custom_components / "manifest.json").exists()
    assert (custom_components / "const.py").exists()
    assert (custom_components / "coordinator.py").exists()
    assert (custom_components / "config_flow.py").exists()
    assert (custom_components / "device.py").exists()
    assert (custom_components / "fan.py").exists()
    assert (custom_components / "sensor.py").exists()

    # Check VSCode configuration
    vscode_dir = project_root / ".vscode"
    assert vscode_dir.exists()
    assert (vscode_dir / "tasks.json").exists()


def test_ruff_works():
    """Test that ruff is installed and working."""
    result = subprocess.run(
        [sys.executable, "-m", "ruff", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "ruff" in result.stdout.lower()


def test_ruff_format_works():
    """Test that ruff format command is working."""
    result = subprocess.run(
        [sys.executable, "-m", "ruff", "format", "--check", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "format" in result.stdout.lower()


def test_ruff_check_works():
    """Test that ruff check command is working."""
    result = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "check" in result.stdout.lower()


def test_mypy_works():
    """Test that mypy is installed and working."""
    result = subprocess.run(
        [sys.executable, "-m", "mypy", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "mypy" in result.stdout.lower()


def test_pytest_works():
    """Test that pytest is installed and working."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "pytest" in result.stdout.lower()
