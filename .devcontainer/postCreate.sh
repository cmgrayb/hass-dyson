#!/bin/bash

echo "🚀 Setting up Dyson Home Assistant Integration development environment..."

# Get the current workspace directory
WORKSPACE_DIR=$(pwd)
echo "📁 Working in workspace: $WORKSPACE_DIR"

# Install development dependencies
echo "📦 Installing development dependencies..."
pip install -r requirements-dev.txt

# Install the package in development mode
echo "🔧 Installing package in development mode..."
pip install -e .

# Set up git hooks (if pre-commit is available)
if command -v pre-commit &> /dev/null; then
    echo "🪝 Setting up pre-commit hooks..."
    pre-commit install
fi

echo "✅ Development environment setup complete!"
echo ""
echo "🎯 Quick commands:"
echo "   Format code:     python -m ruff format ."
echo "   Lint code:       python -m ruff check ."
echo "   Fix linting:     python -m ruff check . --fix"
echo "   Type check:      python -m mypy custom_components/hass_dyson"
echo "   Run tests:       python -m pytest"
echo "   Run unit tests:  python -m pytest tests/ -m 'not integration'"
echo ""
echo "🏠 Home Assistant test instance available at: http://homeassistant:8123"
echo "🦟 MQTT broker available at: mosquitto:1883"
echo "📁 Workspace: $WORKSPACE_DIR"
echo ""
