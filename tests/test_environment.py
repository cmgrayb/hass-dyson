"""Test project structure and development environment."""

import shutil
import subprocess
import sys
from pathlib import Path


def _run_dev_tool(module_name: str, *args: str) -> subprocess.CompletedProcess:
    """Run a dev tool via Python module, falling back to PATH binary.

    When tests run under the VS Code pydevd test runner, subprocess calls
    to ``sys.executable -m <tool>`` can produce empty stdout even when the
    tool is installed (debugger intercepts the output).  This helper falls
    back to the standalone binary found on PATH in that case.
    """
    result = subprocess.run(
        [sys.executable, "-m", module_name, *args],
        capture_output=True,
        text=True,
        check=False,
    )
    # Fall back to binary on PATH if module invocation produced no usable output
    if not result.stdout.strip():
        binary = shutil.which(module_name)
        if binary:
            result = subprocess.run(
                [binary, *args],
                capture_output=True,
                text=True,
                check=False,
            )
    return result


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
    result = _run_dev_tool("ruff", "--version")
    assert result.returncode == 0
    assert "ruff" in result.stdout.lower()


def test_ruff_format_works():
    """Test that ruff format command is working."""
    result = _run_dev_tool("ruff", "format", "--check", "--help")
    assert result.returncode == 0
    assert "format" in result.stdout.lower()


def test_ruff_check_works():
    """Test that ruff check command is working."""
    result = _run_dev_tool("ruff", "check", "--help")
    assert result.returncode == 0
    assert "check" in result.stdout.lower()


def test_mypy_works():
    """Test that mypy is installed and working."""
    result = _run_dev_tool("mypy", "--version")
    assert result.returncode == 0
    assert "mypy" in result.stdout.lower()


def test_pytest_works():
    """Test that pytest is installed and working."""
    result = _run_dev_tool("pytest", "--version")
    assert result.returncode == 0
    assert "pytest" in result.stdout.lower()
