# Testing Patterns and Development Guidelines

This document provides comprehensive testing patterns, mock setups, and development guidelines for the Dyson Home Assistant integration. It's intended for developers working on the integration codebase.

## Unit Testing Infrastructure

### Testing Framework Setup

The project uses a pure pytest infrastructure for Home Assistant integration development:

- **Comprehensive `conftest.py`**: Event loop cleanup and warning suppression
- **Mock patterns**: Proper mocking for HA components and async operations

### Essential Mock Patterns for HA Integration Tests

#### Home Assistant Instance Mocking
```python
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
```

#### Config Entry Mocking
```python
@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    config_entry = MagicMock()
    config_entry.data = {
        CONF_SERIAL_NUMBER: "VS6-EU-HJA1234A",
        # Add other required config data
    }
    return config_entry
```

#### Coordinator Testing with Patched Initialization
```python
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

#### Direct Coordinator Mocking (Alternative Approach)
```python
@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock(spec=DysonDataUpdateCoordinator)
    coordinator.serial_number = "TEST-SERIAL-123"
    coordinator.device = MagicMock()
    coordinator.device.set_sleep_timer = AsyncMock()
    return coordinator
```

## Testing Complex HA Components

### DataUpdateCoordinators
- **Never call real `__init__`**: Always patch `DataUpdateCoordinator.__init__`
- **Set required attributes manually**: `hass`, `_listeners`, `async_update_listeners`
- **Mock HA framework calls**: `hass.loop.call_soon_threadsafe`, `hass.async_create_task`
- **Test method logic**: Focus on business logic, not HA framework integration

### Platform Setup (setup_entry functions)
- **Mock add_entities**: Use `MagicMock()` for the add_entities callback
- **Mock coordinator**: Create coordinator mocks with required attributes
- **Test entity creation**: Verify correct entities are created and configured
- **Mock async operations**: Use `AsyncMock` for async setup methods

### Entity Classes
- **Mock coordinator dependencies**: Provide mock coordinator with required data
- **Test state properties**: Verify entity reports correct state from device data
- **Test service calls**: Mock device methods and verify they're called correctly
- **Mock async operations**: Use `AsyncMock` for async entity methods

## Common Testing Pitfalls and Solutions

### 1. DON'T initialize real HA components in unit tests
```python
# ❌ This will fail - requires full HA context
coordinator = DysonDataUpdateCoordinator(hass, config_entry)

# ✅ This works - patches parent initialization
with patch("...DataUpdateCoordinator.__init__"):
    coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)
```

### 2. DON'T forget to set required attributes after patching
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

### 3. DO use proper async mocking
```python
# ✅ Use AsyncMock for async methods
mock_device.connect = AsyncMock(return_value=True)
mock_device.get_state = AsyncMock(return_value={"fan": {"speed": 5}})
```

### 4. DO follow existing patterns in the codebase
- Check `tests/test_services.py` for service testing patterns
- Check `tests/test_switch.py` for entity platform testing patterns
- Use the same fixture names and mock setups for consistency

## Test File Organization

### File Structure
- **One test file per module**: `test_coordinator.py` for `coordinator.py`
- **Group related tests in classes**: `TestCoordinatorDeviceSetup`, `TestCoordinatorMQTT`
- **Descriptive test names**: `test_async_update_data_device_reconnection_success`
- **Comprehensive docstrings**: Explain what scenario each test covers

### Coverage Improvement Strategy
- **Focus on complex logic first**: Error handling, reconnection scenarios, validation
- **Test edge cases**: Missing data, network failures, invalid responses
- **Mock external dependencies**: APIs, MQTT, device connections
- **Verify error paths**: Exception handling and recovery logic
- **Test async operations**: Connection setup, data updates, background tasks

## Troubleshooting Common Test Issues

### Issue: "RuntimeError: Frame helper not set up"
**Cause**: Trying to initialize real HA components without proper framework context.
**Solution**: Use mocking patterns instead of real initialization.

```python
# ❌ Don't do this
coordinator = DysonDataUpdateCoordinator(hass, config_entry)

# ✅ Do this instead
with patch("custom_components.hass_dyson.coordinator.DataUpdateCoordinator.__init__"):
    coordinator = DysonDataUpdateCoordinator(mock_hass, mock_config_entry)
    coordinator.hass = mock_hass
```

### Issue: "AttributeError: object has no attribute '_listeners'"
**Cause**: Missing required attributes normally set by parent class.
**Solution**: Manually set required attributes after patching.

```python
# ✅ Always set these after patching parent __init__
coordinator.hass = mock_hass
coordinator.config_entry = mock_config_entry
coordinator._listeners = {}
coordinator.async_update_listeners = MagicMock()
```

### Issue: "Event loop is closed" warnings
**Cause**: Async cleanup issues during test teardown.
**Solution**: Already handled by `conftest.py` - no action needed.

### Issue: "AttributeError: '_mock_methods'"
**Cause**: Complex mock nesting can cause attribute resolution issues.
**Solution**: Use simpler mock setup patterns.

```python
# ❌ Avoid complex mock nesting
mock_obj.attr = another_mock_obj  # Can cause issues

# ✅ Use simpler mock setup
mock_obj = MagicMock()
mock_obj.attr.configure_mock(**{"method.return_value": "value"})
```

## Test Execution Commands

### Basic Test Execution
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

### Advanced Test Options
```bash
# Run with verbose output and show local variables on failures
python -m pytest tests/test_coordinator.py -v -l

# Run tests in parallel (if pytest-xdist installed)
python -m pytest tests/ -n auto

# Run tests with coverage and generate HTML report
python -m pytest --cov=custom_components/hass_dyson --cov-report=html

# Run specific test pattern
python -m pytest -k "test_coordinator and not integration"
```

## Testing Environment Setup

### Available Testing Tools
The development environment includes all necessary Home Assistant testing infrastructure:

- **Home Assistant Core**: Pre-installed in devcontainer
- **Comprehensive conftest.py**: Handles async teardown, warning suppression, event loop cleanup
- **Mock libraries**: pytest-mock, unittest.mock, aioresponses, responses
- **MQTT testing**: paho-mqtt for MQTT protocol testing

### Development Testing Workflow
1. **Create/activate virtual environment**
2. **Install development dependencies**: `pip install -r requirements-dev.txt`
3. **Install package in development mode**: `pip install -e .`
4. **Make changes following coding standards**
5. **Run tests**: `python -m pytest`
6. **Check coverage**: `python -m pytest --cov-report=term-missing`
7. **Ensure all checks pass before committing**

## Coverage Analysis and Improvement

### Current Coverage Status
- **Overall project coverage**: ~10% (improved from 7%)
- **coordinator.py coverage**: 31% (improved from 12%)
- **Target coverage**: >75% for critical modules

### Priority Areas for Coverage Improvement
1. **coordinator.py**: Focus on async update methods, error handling
2. **device.py**: Test device connection and state management
3. **config_flow.py**: Test configuration flow logic and validation

### Coverage Improvement Strategies
- **Test complex logic first**: Error handling, reconnection scenarios
- **Mock external dependencies**: APIs, MQTT connections, device communication
- **Test edge cases**: Network failures, invalid responses, missing data
- **Verify error paths**: Exception handling and recovery logic
- **Test async operations**: Background tasks, connection setup, data updates

## Integration with CI/CD

### GitHub Actions Integration
- **Quality checks**: All tests must pass for PR approval
- **Coverage reporting**: Coverage results included in CI pipeline
- **Automated testing**: Tests run on multiple Python versions
- **Security scanning**: Static analysis and dependency vulnerability checks

### Pre-commit Hooks
- **Code formatting**: Black, isort automatically applied
- **Linting**: Flake8 checks for code quality issues
- **Type checking**: MyPy validates type hints
- **Test execution**: Unit tests run before commit

## Best Practices Summary

### Test Design Principles
1. **Test behavior, not implementation**: Focus on what the code does, not how
2. **One assertion per test**: Keep tests focused and specific
3. **Arrange-Act-Assert pattern**: Structure tests clearly
4. **Descriptive test names**: Test names should explain the scenario
5. **Independent tests**: Tests should not depend on each other

### Mock Strategy
1. **Mock external dependencies**: APIs, MQTT, device connections
2. **Use specific mocks**: MagicMock with spec when possible
3. **Set up required attributes**: Manually assign after patching
4. **Async operations**: Use AsyncMock for async methods
5. **Follow existing patterns**: Consistency with existing test code

### Coverage Goals
1. **Focus on critical paths**: Error handling, main functionality
2. **Test edge cases**: Boundary conditions, error scenarios
3. **Maintain quality**: High coverage with meaningful tests
4. **Regular monitoring**: Track coverage trends over time
5. **Continuous improvement**: Add tests with each new feature
