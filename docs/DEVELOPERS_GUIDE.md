# Developers Guide

## **Quick Start with DevContainer**

The easiest way to get started with development is using the provided devcontainer:

1. **Prerequisites**: Install VS Code with the "Dev Containers" extension
2. **Open Project**: Open the repository in VS Code
3. **Reopen in Container**: Press `Ctrl+Shift+P` → "Dev Containers: Reopen in Container"
4. **Start Developing**: All dependencies, tools, and Home Assistant are pre-installed!

The devcontainer includes:

- **Home Assistant Core** with all dependencies
- **Development Tools**: Ruff, mypy, pytest
- **MQTT Broker**: Local Mosquitto for testing
- **VS Code Extensions**: Python tools and GitHub Copilot
- **Pre-configured Settings**: Optimized for HA development

See [`.devcontainer/README.md`](.devcontainer/README.md) for detailed documentation.

### **Manual Development Setup**

If you prefer local development:

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# Install development dependencies
pip install -r requirements-dev.txt
pip install -e .

# Install Home Assistant for testing
pip install homeassistant
```

### **Architecture**

```
Config Flow → Coordinator → Device Wrapper → MQTT Client
     ↓            ↓              ↓
Platform Setup → Data Updates → Real Device
```

### **Project Structure**

```
custom_components/hass_dyson/
├── __init__.py          # Integration setup
├── config_flow.py       # Setup wizard
├── coordinator.py       # Data coordination
├── device.py           # MQTT device wrapper
├── const.py            # Constants
├── manifest.json       # Metadata
├── fan.py              # Fan platform
├── sensor.py           # Sensor platform
├── binary_sensor.py    # Binary sensor platform
├── button.py           # Button platform
├── number.py           # Number platform
├── select.py           # Select platform
├── switch.py           # Switch platform
└── climate.py          # Climate platform
```

### **Contributing**

1. Fork the repository
2. **Recommended**: Use the devcontainer for consistent development environment
   - Open in VS Code with Dev Containers extension
   - All tools and dependencies are pre-configured
3. Create feature branch (`git checkout -b feature/amazing-feature`)
4. Make your changes following the code quality standards:

   ```bash
   # Format and lint code (unified with Ruff)
   python -m ruff format .
   python -m ruff check . --fix

   # Run tests
   python -m pytest
   ```

5. **For developers**: See [Testing Patterns Documentation](.github/design/testing-patterns.md) for unit testing guidance and mock setups
6. Commit changes (`git commit -am 'Add amazing feature'`)
7. Push branch (`git push origin feature/amazing-feature`)
8. Open Pull Request
