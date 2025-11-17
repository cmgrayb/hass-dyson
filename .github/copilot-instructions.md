# Copilot Instructions

## Personality
Copilot will be the primary developer, taking cues for architecture and design from the user.  It will also provide suggestions and recommendations based on best practices and design patterns.  If unexpected code changes are found, NEVER assume that code changes were made by the user.  Usually these unexpected code changes are created by disconnections and malfunctions between Copilot and VSCode.  Ask questions to clarify requirements and gather more context if needed.  If output is not received from a command, notify the user so that the user can resolve the issue.

### Communication
Copilot will communicate its thought process and reasoning behind code suggestions. It will also provide explanations for any code changes it makes. If the user disagrees with a suggestion, Copilot will be open to feedback and willing to explore alternative solutions, if they follow best practices and good design principles.

Avoid saying "I found THE solution..." or "I found THE problem..." or similar phrases that imply a single correct cause or answer.  Instead say "I found A solution..." or "I found A problem..." indicating that there may be multiple valid approaches or perspectives to consider.

## Project Design
The integration is architected to be modular, allowing for easy addition of new Dyson products and features. It leverages asynchronous programming to ensure non-blocking operations within Home Assistant. The design prioritizes security, maintainability, and adherence to Home Assistant's integration guidelines. The integration should handle ONLY the Home Assistant orchestration, event handling, logging, and state management. All direct communication with Dyson devices and APIs should be abstracted away into separate libraries or services.

Design documentation may be found in the `.github/design/` directory of the project repository.

## Development Standards

### Code Quality Tools

- **Ruff**: Python code formatting and linting (line length: 88 characters, Home Assistant compliance)
- **mdformat**: Markdown file formatting
- **markdownlint**: Markdown file linting
- **Pytest**: Python unit and integration testing
- **MyPy**: Python static type checking
- **Bandit**: Python security static analysis
- **Peach Fuzzer**: Fuzz testing for security vulnerabilities

### Product Quality

- The integration must provide a seamless and intuitive user experience within Home Assistant.
- All features should be fully functional and free of critical bugs.
- Performance should be optimized to minimize resource usage and latency.
- The integration must handle errors gracefully and provide meaningful feedback to users.
- Compatibility with the latest Home Assistant release and supported Dyson products must be ensured.
- Documentation must be comprehensive, up-to-date, and accessible.
- Target quality rating by Home Assistant should aim to meet Platinum designation <https://www.home-assistant.io/docs/quality_scale/>.

### Testing and Validation
- As the devices being integrated are costly to acquire, comprehensive mocking and simulation of device behavior is essential to ensure comprehensive test coverage without requiring physical hardware for every test scenario.
- All defined tests must pass before merging code changes
- Unit tests must cover all new features and bug fixes
- Integration tests must validate interactions with external APIs and services
- End-to-end tests should simulate real user scenarios
- Tests must be automated and runnable via a single command
- Test results must be included in the CI/CD pipeline reports

### Code Quality Requirements
- All code must pass Ruff formatting and linting (PEP 8 compliance)
- All tests must pass before commits
- All code must pass mypy static type checks
- Minimum test coverage should be maintained
- All public methods must have type hints
- All public classes must have docstrings
- All public functions must have docstrings
- All public modules must have docstrings
- All new code must include corresponding tests
- No usage of print statements for debugging; use logging instead
- All logging must be done using the standard Python logging library with appropriate log levels
- All configuration and sensitive information must be managed through environment variables or secure storage, not hardcoded
- Secrets must never be logged or exposed in error messages
- Use HTTPS for all API communications
- Validate SSL certificates for all external connections
- Implement rate limiting and retry logic for API calls
- Ensure all third-party dependencies are regularly updated and security patches are applied promptly
- Conduct regular security audits and code reviews to identify and mitigate vulnerabilities
- Implement secure coding practices
- Use static analysis tools (e.g., Bandit) to detect security issues in code
- Follow the principle of least privilege for any access controls
- Encrypt sensitive data at rest and in transit
- Implement authentication and authorization for all API endpoints
- Log all security-relevant events with sufficient detail for auditing
- Include security headers in all HTTP responses (e.g., Content-Security-Policy, X-Content-Type-Options)
- All user-facing messages (logs, errors, UI text) must be clear, non-technical, and avoid exposing sensitive information
- All user-facing messages must be localized and support internationalization
- Follow best practices for API design, including RESTful principles, proper use of HTTP methods and status codes, and clear endpoint structures
- Code must be modular, maintainable, and adhere to SOLID principles
- Write comprehensive unit and integration tests to ensure code reliability and facilitate future changes
- Code must be well-documented, with clear and concise docstrings for all public classes, methods, and functions
- Use type hints for all public methods and functions to improve code readability and facilitate static analysis
- Code must implement DRY (Don't Repeat Yourself) principles to avoid redundancy and improve maintainability
- Code should be able to pass all configured linters, formatters, and static analysis tools without errors or warnings
- Code should be able to pass Peach Fuzzer tests without triggering security vulnerabilities

## Configuration Files

### pyproject.toml
- Ruff configuration
- Project metadata
- Build system configuration

### requirements.txt
- Production dependencies only
- Pinned versions for reproducibility

### requirements-dev.txt
- Development dependencies (ruff, pytest, mypy, etc.)
- Pre-commit hooks

## VSCode Tasks
The following tasks should be available:
- **Format Code**: Run Ruff formatting on the entire codebase
- **Ruff Check**: Run Ruff linting on the entire codebase
- **Run Tests**: Execute pytest with coverage
- **Check All**: Run all quality checks in sequence
- **Setup Dev Environment**: Create venv and install dependencies

### Testing Strategy

### Test Categories and Scope
- **Unit tests**: Individual functions and classes in isolation
- **Integration tests**: API interactions with external services
- **Component tests**: Home Assistant platform setup and entity functionality
- **Mock external dependencies**: API calls, MQTT connections, device communication
- **Use real endpoints sparingly**: Only for integration tests with proper credentials
- **Target coverage**: Maintain test coverage above 75%

### Home Assistant Integration Testing Patterns

#### Required Testing Infrastructure
The project includes comprehensive Home Assistant testing setup:

- **`pytest-homeassistant-custom-component==0.13.277`**: HA-specific pytest fixtures
- **Comprehensive `conftest.py`**: Event loop cleanup and warning suppression
- **Mock patterns**: Proper mocking for HA components and async operations

#### Essential Mock Patterns for HA Integration Tests

```python
# 1. Mock Home Assistant Instance
@pytest.fixture
def mock_hass():
    """Create a properly mocked Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = {DOMAIN: {}}
    hass.loop = MagicMock()
    hass.loop.call_soon_threadsafe = MagicMock()
    hass.async_create_task = MagicMock()
    hass.add_job = MagicMock()
    hass.bus = MagicMock()
    hass.bus.async_fire = MagicMock()
    hass.config_entries = MagicMock()
    hass.config_entries.async_entries_for_config_entry_id = MagicMock(return_value=[])
    return hass

# 2. Mock Config Entry
@pytest.fixture  
def mock_config_entry():
    """Create a mock config entry."""
    config_entry = MagicMock()
    config_entry.data = {
        CONF_SERIAL_NUMBER: "VS6-EU-HJA1234A",
        # Add other required config data
    }
    return config_entry

# 3. Mock Coordinator (Method 1: Direct Mock)
@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock(spec=DysonDataUpdateCoordinator)
    coordinator.serial_number = "TEST-SERIAL-123"
    coordinator.device = MagicMock()
    coordinator.device.set_sleep_timer = AsyncMock()
    return coordinator

# 4. Mock Coordinator (Method 2: Patched Initialization)
@pytest.mark.asyncio
async def test_coordinator_method(mock_hass, mock_config_entry):
    """Test coordinator method with patched initialization."""
    with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
        coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)
        
        # Manually set required attributes normally set by parent __init__
        coordinator.hass = mock_hass
        coordinator.config_entry = mock_config_entry
        coordinator._listeners = {}  # Set by HA DataUpdateCoordinator parent
        coordinator.async_update_listeners = MagicMock()
        
        # Test the specific method logic
        result = coordinator.some_method()
        assert result == expected_value
```

#### Testing Complex HA Components

**For DataUpdateCoordinators:**
- **Never call real `__init__`**: Always patch `DataUpdateCoordinator.__init__`
- **Set required attributes manually**: `hass`, `_listeners`, `async_update_listeners`
- **Mock HA framework calls**: `hass.loop.call_soon_threadsafe`, `hass.async_create_task`
- **Test method logic**: Focus on business logic, not HA framework integration

**For Platform Setup (setup_entry functions):**
- **Mock add_entities**: Use `MagicMock()` for the add_entities callback
- **Mock coordinator**: Create coordinator mocks with required attributes
- **Test entity creation**: Verify correct entities are created and configured
- **Mock async operations**: Use `AsyncMock` for async setup methods

**For Entity Classes:**
- **Mock coordinator dependencies**: Provide mock coordinator with required data
- **Test state properties**: Verify entity reports correct state from device data
- **Test service calls**: Mock device methods and verify they're called correctly
- **Mock async operations**: Use `AsyncMock` for async entity methods

#### Common Testing Pitfalls to Avoid

1. **DON'T initialize real HA components in unit tests**:
   ```python
   # ❌ This will fail - requires full HA context
   coordinator = DysonDataUpdateCoordinator(hass, config_entry)
   
   # ✅ This works - patches parent initialization
   with patch("...DataUpdateCoordinator.__init__"):
       coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)
   ```

2. **DON'T forget to set required attributes after patching**:
   ```python
   # ❌ Missing required attributes
   with patch("...DataUpdateCoordinator.__init__"):
       coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)
       result = coordinator.some_method()  # May fail
   
   # ✅ Set required attributes manually
   with patch("...DataUpdateCoordinator.__init__"):
       coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)
       coordinator.hass = mock_hass
       coordinator._listeners = {}
       result = coordinator.some_method()  # Works
   ```

3. **DO use proper async mocking**:
   ```python
   # ✅ Use AsyncMock for async methods
   mock_device.connect = AsyncMock(return_value=True)
   mock_device.get_state = AsyncMock(return_value={"fan": {"speed": 5}})
   ```

4. **DO follow existing patterns in the codebase**:
   - Check `tests/test_services.py` for service testing patterns
   - Check `tests/test_switch.py` for entity platform testing patterns
   - Use the same fixture names and mock setups for consistency

#### Test File Organization
- **One test file per module**: `test_coordinator.py` for `coordinator.py`
- **Group related tests in classes**: `TestCoordinatorDeviceSetup`, `TestCoordinatorMQTT`
- **Descriptive test names**: `test_async_update_data_device_reconnection_success`
- **Comprehensive docstrings**: Explain what scenario each test covers

#### Coverage Improvement Strategy
- **Focus on complex logic first**: Error handling, reconnection scenarios, validation
- **Test edge cases**: Missing data, network failures, invalid responses
- **Mock external dependencies**: APIs, MQTT, device connections
- **Verify error paths**: Exception handling and recovery logic
- **Test async operations**: Connection setup, data updates, background tasks

### Testing Environment Setup

#### Available Testing Tools
The development environment includes all necessary Home Assistant testing infrastructure:

- **Home Assistant Core**: Pre-installed in devcontainer
- **pytest-homeassistant-custom-component**: HA-specific testing utilities and fixtures
- **Comprehensive conftest.py**: Handles async teardown, warning suppression, event loop cleanup
- **Mock libraries**: pytest-mock, unittest.mock, aioresponses, responses
- **MQTT testing**: paho-mqtt for MQTT protocol testing

#### Troubleshooting Common Test Issues

**Issue: "RuntimeError: Frame helper not set up"**
```python
# ❌ Don't try to initialize real HA coordinators in unit tests
coordinator = DysonDataUpdateCoordinator(hass, config_entry)

# ✅ Use proper mocking instead
with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
    coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)
    coordinator.hass = mock_hass  # Set manually
```

**Issue: "Event loop is closed" warnings**
- Handled automatically by `conftest.py` 
- Comprehensive warning suppression already configured
- Event loop cleanup patches applied

**Issue: "AttributeError: '_mock_methods'"**
```python
# ❌ Avoid complex mock nesting
mock_obj.attr = another_mock_obj  # Can cause issues

# ✅ Use simpler mock setup
mock_obj = MagicMock()
mock_obj.attr.configure_mock(**{"method.return_value": "value"})
```

**Issue: Missing coordinator attributes**
```python
# ✅ Always set these after patching parent __init__
coordinator.hass = mock_hass
coordinator.config_entry = mock_config_entry
coordinator._listeners = {}
coordinator.async_update_listeners = MagicMock()
```

#### Test Execution Commands
```bash
# Run specific test file with coverage
python -m pytest tests/test_coordinator.py --cov=custom_components/hass_dyson/coordinator

# Run specific test method
python -m pytest tests/test_coordinator.py::TestClass::test_method -v

# Run with coverage report
python -m pytest --cov=custom_components/hass_dyson --cov-report=term-missing

# Run only unit tests (excluding integration tests)
python -m pytest tests/ -m 'not integration'
```

## Security Considerations
- No hardcoded credentials or sensitive data
- API hostnames and decryption keys are the only allowed static values
- Use environment variables for configuration
- Validate all user inputs
- Sanitize API responses

## API Design Principles
- Clean, intuitive public interface
- Proper exception handling with custom exception classes
- Type hints for all public methods
- Comprehensive docstrings following Google or NumPy style
- Support for both synchronous and asynchronous operations (if needed)

## Development Workflow
1. Create/activate virtual environment
2. Install development dependencies
3. Make changes following coding standards
4. Run format/lint/test tasks
5. Ensure all checks pass before committing
6. Use pre-commit hooks for automated checks

## Dependencies Management
- Use virtual environments for isolation
- Pin exact versions in requirements.txt
- Use requirements-dev.txt for development tools
- Regular dependency updates with testing

## Version Synchronization Process
When updating development tool versions, ensure consistency across all configuration files:

### Current Tool Versions (as of Aug 16, 2025)
- Black: 25.1.0
- Flake8: 7.3.0
- isort: 6.0.1
- pytest: 8.4.1
- pytest-cov: 6.2.1
- pytest-asyncio: 1.1.0
- pytest-homeassistant-custom-component: 0.13.277
- pytest-mock: 3.15.0
- mypy: 1.17.1
- pre-commit: 4.3.0
- types-requests: 2.32.4.20250809
- types-cryptography: 3.3.23.2
- aioresponses: 0.7.7
- responses: 0.25.8
- paho-mqtt: 2.1.0

### Step-by-Step Version Update Process

1. **Check Local Environment Versions**
   ```bash
   # Activate virtual environment
   .venv\Scripts\activate

   # Check currently installed versions
   pip list | findstr "black flake8 isort pytest mypy"
   ```

2. **Synchronize requirements-dev.txt**
   - Update to exact version pins matching pre-commit hooks
   - Use `==` instead of `>=` for consistency
   - Include all development dependencies with exact versions

3. **Update pyproject.toml Optional Dependencies**
   - Match the exact versions from requirements-dev.txt
   - Update `[project.optional-dependencies].dev` section
   - Use exact version pins (`==`) for consistency

4. **Verification Steps**
   ```bash
   # Install updated dependencies
   pip install -r requirements-dev.txt

   # Verify all tools work locally
   python -m ruff format --check .
   python -m ruff check .
   python -m mypy custom_components/hass_dyson
   python -m pytest
   python -m peach_fuzzer
   ```

5. **Files to Update**
   - `requirements-dev.txt` (manual exact version pins)
   - `pyproject.toml` (`[project.optional-dependencies].dev` section)

### Version Selection Strategy
- Use newest available versions when possible
- Always verify all quality checks pass after version updates
- Document version changes for future reference

## Continuous Integration
- All PRs must pass quality checks
- Automated testing on multiple Python versions
- Code coverage reporting
- Security scanning of dependencies
- Security scanning of application code with Peach Fuzzer
- **Important**: CI workflows must install package in development mode (`pip install -e .`) for tests to import modules

## Documentation
- README with clear usage examples
- API documentation generated from docstrings
- Contributing guidelines
- Changelog maintenance

## Common Commands
```bash
# Setup development environment
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements-dev.txt
pip install -e .  # Install package in development mode for testing

# Code quality checks
python -m ruff format --check .
python -m ruff check .
python -m mypy custom_components/hass_dyson
python -m pytest
python -m peach_fuzzer

# Then manually update requirements-dev.txt and pyproject.toml to match
pip install -r requirements-dev.txt     # Install updated versions
```

## VSCode Tasks
The project includes comprehensive VSCode tasks accessible via Ctrl+Shift+P → "Tasks: Run Task":

### Development Tasks
- **Setup Dev Environment**: Create virtual environment
- **Install Dev Dependencies**: Install development packages
- **Format Code**: Run Ruff code formatting
- **Ruff Check**: Run Ruff linting with problem matchers
- **Type Check**: Run mypy type checking with problem matchers
- **Check All**: Run complete quality check sequence

### Testing Tasks
- **Run Tests**: Execute full test suite with coverage
- **Run Unit Tests**: Execute unit tests only
- **Run Integration Tests**: Execute integration tests only

### Security Scanning Tasks (Docker-based)
- **Security Scan (Bandit)**: Run Bandit security scanner using Docker container (cross-platform)
- **Security Scan (Safety)**: Check for known security vulnerabilities in dependencies using Docker
- **Security Scan (All)**: Run all security scans using Docker containers
- **Security Scan (Peach Fuzzer)**: Run Peach Fuzzer for application security testing

## GitHub Actions CI/CD

The project must include comprehensive GitHub Actions workflows for continuous integration, quality assurance, and security testing:

### Quality Assurance Workflows
- **Code Quality Checks**: Ruff formatting and linting, mypy types, pytest tests across Python 3.9-3.13
- **Build Testing**: Cross-platform package building and installation testing (Ubuntu/Windows/macOS)

### Security Testing Workflows
- **Security Scan (Bandit)**: Run Bandit security scanner
- **Security Scan (Safety)**: Check for known vulnerabilities in dependencies
- **Security Scan (All)**: Run all security scans sequentially
- **Peach Fuzzer Scan**: Run Peach Fuzzer for application security testing

### Security and Maintenance
- **Security Scanning**: Weekly vulnerability scanning with Safety and Bandit tools
- **Dependency Updates**: Automated monitoring with GitHub issue creation for available updates
- **Version Synchronization**: Validates tool version alignment across configuration files

### CI Pipeline Features
- **Smart Execution**: Skips CI for draft PRs (unless `ci-force` label present)
- **Parallel Processing**: Runs quality checks simultaneously for faster feedback
- **Automated PR Comments**: Provides actionable feedback directly in pull requests
- **Artifact Management**: Stores build artifacts and security reports for review

### Branch Protection Requirements
Required status checks for merge approval:
- Quality checks pass (Python 3.10)
- Build test passes (Ubuntu/Python 3.10)
- Version sync check (when configuration files modified)

## Automated Dependency Management

The project uses Renovate Bot for self-hosted automated dependency management:

### Self-hosted Renovate Features
- **No external reporting**: All dependency scanning happens locally within GitHub
- **Automated PRs**: Creates pull requests for dependency updates weekly (Mondays 6 AM UTC)
- **Intelligent grouping**: Groups related dependencies (dev tools, production, security)
- **Security alerts**: Immediate PRs for vulnerability fixes

### Dependency Update Categories
- **Production dependencies** (requirements.txt): 7-day minimum age, conservative updates
- **Development dependencies** (requirements-dev.txt): 3-day minimum age
- **Code quality tools** (black, flake8, isort, mypy, pytest): 3-day minimum age
- **GitHub Actions**: 3-day minimum age, updates workflow dependencies
- **Security tools**: 1-day minimum age for faster security patches

### Renovate Configuration
- **Configuration**: `renovate.json` - Main Renovate settings
- **Workflow**: `.github/workflows/renovate.yml` - Self-hosted execution
- **Dashboard**: Automatic dependency dashboard issue for overview
- **Manual trigger**: Available via GitHub Actions for immediate checks
