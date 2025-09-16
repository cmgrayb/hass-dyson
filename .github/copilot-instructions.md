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

- **Black**: Python code formatting (line length: 120 characters)
- **mdformat**: Markdown file formatting
- **Flake8**: Python linting and style checking
- **markdownlint**: Markdown file linting
- **isort**: Python import sorting and organization
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
- Unit tests must cover all new features and bug fixes
- Integration tests must validate interactions with external APIs and services
- End-to-end tests should simulate real user scenarios
- Tests must be automated and runnable via a single command
- Test results must be included in the CI/CD pipeline reports

### Code Quality Requirements
- All code must pass black formatting
- All code must pass flake8 linting (PEP 8 compliance)
- All imports must be sorted with isort
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
- Black configuration
- isort configuration
- Project metadata
- Build system configuration

### .flake8
- Flake8 configuration
- Ignore rules if necessary
- Max line length: 120 (to match Black)

### requirements.txt
- Production dependencies only
- Pinned versions for reproducibility

### requirements-dev.txt
- Development dependencies (black, flake8, isort, pytest, etc.)
- Pre-commit hooks

## VSCode Tasks
The following tasks should be available:
- **Format Code**: Run black on the entire codebase
- **Lint Code**: Run flake8 on the entire codebase
- **Sort Imports**: Run isort on the entire codebase
- **Run Tests**: Execute pytest with coverage
- **Check All**: Run all quality checks in sequence
- **Setup Dev Environment**: Create venv and install dependencies

## Testing Strategy
- Unit tests for individual functions and classes
- Integration tests for API interactions
- Mock external API calls in unit tests
- Use real API endpoints in integration tests (with proper credentials)
- Maintain test coverage above 80%

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
- mypy: 1.17.1
- pre-commit: 4.3.0
- types-requests: 2.32.4.20250809
- types-cryptography: 3.3.23.2
- peach-fuzzer: unknown (please update)

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
   python -m black --check .
   python -m flake8 .
   python -m isort --check-only .
   python -m mypy src/
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
python -m black --check .
python -m flake8 .
python -m isort --check-only .
python -m mypy src/
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
- **Format Code**: Run Black code formatting
- **Lint Code**: Run Flake8 linting with problem matchers
- **Sort Imports**: Run isort import sorting
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
- **Code Quality Checks**: Black formatting, Flake8 linting, isort imports, mypy types, pytest tests across Python 3.9-3.13
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
