# GitHub Actions Workflows

This directory contains automated workflows for continuous integration and testing.

## Workflows Overview

### 🧪 PR Tests (`pr-test.yml`)

**Triggers:** Pull requests opened, updated, or reopened
**Purpose:** Fast feedback for PR contributors

**Jobs:**

- **Quick Test Suite:** Runs all tests in `/tests` folder with Python 3.13
- **Test Coverage Analysis:** Generates detailed coverage reports

**Key Features:**

- ⚡ Optimized for speed with caching
- 🎯 Focused on PR-specific validation
- 📊 Coverage artifacts for detailed analysis
- 💬 Automatic PR summary comments

### 🔬 Tests (`test.yml`)

**Triggers:** Push to main/develop, pull requests, manual dispatch
**Purpose:** Comprehensive testing across multiple environments

**Jobs:**

- **Tests:** Core test suite on Python 3.13
- **Code Coverage Analysis:** Comprehensive coverage reporting with artifacts
- **Quality:** Code formatting, linting, type checking, security
- **Integration:** Full test suite validation (all tests)
- **Build:** Package building and validation

**Key Features:**

- 🎯 Focused Python 3.13 testing
- 📊 Dedicated code coverage analysis
- 🛡️ Security scanning with Bandit
- 📦 Package build verification
- 🔧 Comprehensive quality checks
- 📈 Codecov integration

### 🔧 DevContainer Test (`devcontainer-test.yml`)

**Triggers:** Changes to devcontainer configuration
**Purpose:** Validate development environment setup

## Test Execution Details

### What Gets Tested

All workflows execute: `python -m pytest tests/`

This runs **all tests defined in the `/tests` folder**, including:

- Unit tests for individual components
- Integration tests for external dependencies
- Configuration flow tests
- Device capability tests
- Entity behavior tests
- Coordinator functionality tests

### Current Test Suite (86 tests total)

Based on the latest successful run:

- ✅ **86 passed, 0 failed**
- 🎯 **100% success rate**
- 📊 **Coverage tracking enabled**

### Test Categories

- **Unit Tests:** Fast, isolated component testing
- **Integration Tests:** External API and service integration
- **Mock Tests:** Simulated Home Assistant environment
- **Device Tests:** Dyson device capability validation

## Workflow Triggers

### Pull Request Events

```yaml
on:
  pull_request:
    branches: [main, develop]
    types: [opened, synchronize, reopened]
```

- **opened:** New PR created
- **synchronize:** PR updated with new commits
- **reopened:** Previously closed PR reopened

### Push Events

```yaml
on:
  push:
    branches: [main, develop]
```

- Validates main/develop branch integrity
- Runs comprehensive test suite
- Updates coverage reports

### Manual Dispatch

```yaml
on:
  workflow_dispatch:
```

- Allows manual workflow triggering
- Useful for testing workflow changes
- Available in GitHub Actions tab

## Caching Strategy

All workflows use intelligent caching:

```yaml
- name: Cache pip dependencies
  uses: actions/cache@v4
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ matrix.python-version }}-${{ hashFiles('pyproject.toml') }}
```

**Benefits:**

- ⚡ Faster workflow execution
- 💰 Reduced GitHub Actions minutes usage
- 🔄 Automatic cache invalidation on dependency changes

## Artifact Management

### Coverage Reports

- **Format:** HTML and XML
- **Storage:** 7 days retention
- **Access:** Download from workflow run page

### Build Packages

- **Format:** Wheel and source distributions
- **Storage:** 7 days retention
- **Validation:** Automated with `twine check`

## Quality Gates

### Required Checks for PR Merge

1. **Quick Test Suite** - All tests in `/tests` pass
2. **Tests** - Core test suite passes
3. **Code Coverage Analysis** - Coverage requirements met
4. **Code Quality Checks** - Formatting, linting, types
5. **Build Package** - Successful package creation

### Code Quality Standards

- **Black:** Code formatting (120 char line length)
- **isort:** Import sorting
- **Flake8:** PEP 8 linting
- **MyPy:** Static type checking
- **Bandit:** Security vulnerability scanning

## Branch Protection Integration

These workflows are designed to work with GitHub branch protection rules:

**Recommended Settings:**

- ✅ Require pull request reviews
- ✅ Require status checks to pass
- ✅ Require branches to be up to date
- ✅ Include administrators

See `.github/BRANCH_PROTECTION.md` for detailed configuration.

## Troubleshooting

### Common Issues

**Tests failing locally but passing in CI:**

- Check Python version compatibility
- Verify dependency versions match the `dev` extra in `pyproject.toml`
- Run `pip install -e '.[dev]'` to install in development mode

**Coverage reports missing:**

- Ensure `pytest-cov` is installed
- Check coverage configuration in `pyproject.toml`
- Verify file paths in coverage commands

**Quality checks failing:**

- Run local quality tools: `ruff format .`, `ruff check . --fix`
- Check `pyproject.toml` configuration
- Ensure code follows project style guidelines

### Local Development Commands

```bash
# Install development dependencies
pip install -e '.[dev]'

# Run the same tests as CI
python -m pytest tests/ -v

# Run quality checks
python -m black --check .
python -m isort --check-only .
python -m flake8 .
python -m mypy custom_components/hass_dyson
```

## Workflow Monitoring

### Success Indicators

- ✅ Green checkmarks on all jobs
- 📊 Coverage reports generated
- 🎯 All 86 tests passing
- 📦 Successful package build

### Failure Indicators

- ❌ Red X marks on failed jobs
- 📝 Detailed error logs in job output
- 🚨 Failed quality checks with specific violations
- 💥 Build failures with dependency issues

## Contributing

When contributing to this project:

1. **Create a PR** - Triggers `pr-test.yml` automatically
2. **Review results** - Check workflow status in PR
3. **Fix issues** - Address any failing tests or quality checks
4. **Update PR** - Push fixes to trigger re-testing
5. **Merge** - All required checks must pass

The workflows ensure that all tests defined in the `/tests` folder are executed for every PR, maintaining code quality and preventing regressions.
