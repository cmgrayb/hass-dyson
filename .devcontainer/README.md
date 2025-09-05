# Development Container Setup

This devcontainer provides a complete development environment for the Dyson Home Assistant integration with all necessary dependencies pre-installed.

## Features

- **Home Assistant Core**: Full Home Assistant installation for testing
- **Python 3.11**: Latest stable Python version supported by Home Assistant
- **Development Tools**: Black, Flake8, isort, mypy, pytest, and more
- **VS Code Extensions**: Python, linting, formatting, and GitHub Copilot extensions
- **MQTT Broker**: Local Mosquitto broker for testing device communication
- **System Dependencies**: All required libraries for Home Assistant development

## Quick Start

1. **Open in VS Code**: Make sure you have the "Dev Containers" extension installed
2. **Reopen in Container**: Press `Ctrl+Shift+P` → "Dev Containers: Reopen in Container"
3. **Wait for Setup**: The container will build and install all dependencies automatically
4. **Start Developing**: All tools are ready to use!

## Available Commands

### Code Quality
```bash
# Format code with Black
python -m black .

# Lint code with Flake8
python -m flake8 .

# Sort imports with isort
python -m isort .

# Type checking with mypy
python -m mypy custom_components/hass_dyson

# Run all quality checks
python -m black . && python -m flake8 . && python -m isort . && python -m mypy custom_components/hass_dyson
```

### Testing
```bash
# Run all tests
python -m pytest

# Run unit tests only
python -m pytest tests/ -m 'not integration'

# Run integration tests only
python -m pytest tests/ -m integration

# Run tests with coverage
python -m pytest --cov=custom_components.hass_dyson
```

### Security Scanning
```bash
# Security scan with Bandit
python -m bandit -r custom_components/

# Dependency vulnerability check
safety check
```

### Home Assistant Development
```bash
# Start Home Assistant with development config
hass --config /config

# Access Home Assistant at: http://localhost:8123
```

## VS Code Tasks

The following tasks are available via `Ctrl+Shift+P` → "Tasks: Run Task":

- **Setup Dev Environment**: Initialize virtual environment
- **Install Dev Dependencies**: Install all development packages
- **Format Code**: Run Black formatting
- **Lint Code**: Run Flake8 linting
- **Sort Imports**: Run isort import organization
- **Type Check**: Run mypy type checking
- **Run Tests**: Execute full test suite
- **Run Unit Tests**: Execute unit tests only
- **Run Integration Tests**: Execute integration tests only

## MQTT Testing

A local Mosquitto MQTT broker is available for testing:
- **Host**: `mosquitto` (from within the container)
- **Port**: `1883` (MQTT) and `9001` (WebSocket)
- **Authentication**: None (anonymous access enabled for development)

## Directory Structure

```
.devcontainer/
├── devcontainer.json          # Main devcontainer configuration
├── docker-compose.yml         # Multi-service setup with MQTT
├── Dockerfile                 # Custom container build (alternative)
├── postCreate.sh             # Setup script run after container creation
├── mosquitto.conf            # MQTT broker configuration
├── config/                   # Home Assistant configuration
│   ├── configuration.yaml    # Main HA config
│   ├── automations.yaml      # Automation configs
│   ├── scripts.yaml          # Script configs
│   └── scenes.yaml           # Scene configs
└── README.md                 # This file
```

## Troubleshooting

### Container Won't Start
- Ensure Docker is running
- Check that the "Dev Containers" VS Code extension is installed
- Try rebuilding the container: `Ctrl+Shift+P` → "Dev Containers: Rebuild Container"

### Dependencies Missing
- The setup script should install everything automatically
- Manually run: `bash .devcontainer/postCreate.sh`
- Check that `requirements-dev.txt` exists in the project root

### Tests Failing
- Ensure all dependencies are installed: `pip install -e .`
- Check that Home Assistant is properly installed: `pip install homeassistant`
- Verify the package is installed in development mode

### MQTT Not Working
- Check if the Mosquitto service is running: `docker-compose ps`
- Restart the MQTT service: `docker-compose restart mosquitto`
- Check logs: `docker-compose logs mosquitto`

## Performance Tips

- The devcontainer uses volume mounts for faster file I/O
- Pre-commit hooks are automatically installed for code quality
- VS Code settings are optimized for Home Assistant development
- Docker volumes persist data between container rebuilds
