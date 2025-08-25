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
    custom_components = project_root / "custom_components" / "dyson_alt"
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


def test_black_works():
    """Test that black is installed and working."""
    result = subprocess.run([sys.executable, "-m", "black", "--version"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "black" in result.stdout.lower()


def test_flake8_works():
    """Test that flake8 is installed and working."""
    result = subprocess.run([sys.executable, "-m", "flake8", "--version"], capture_output=True, text=True)
    assert result.returncode == 0
    # flake8 version output just shows version numbers, not the name
    assert "mccabe" in result.stdout.lower()  # mccabe is part of flake8


def test_mypy_works():
    """Test that mypy is installed and working."""
    result = subprocess.run([sys.executable, "-m", "mypy", "--version"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "mypy" in result.stdout.lower()


def test_pytest_works():
    """Test that pytest is installed and working."""
    result = subprocess.run([sys.executable, "-m", "pytest", "--version"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "pytest" in result.stdout.lower()
