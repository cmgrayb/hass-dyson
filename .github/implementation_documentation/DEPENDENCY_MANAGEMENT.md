# Automated Dependency Management

This project uses [Renovate Bot](https://github.com/renovatebot/renovate) for automated dependency management across multiple file types:

## **Managed Dependencies**

- **`requirements.txt`** - Production dependencies (conservative 7-day minimum age)
- **`requirements-dev.txt`** - Development tools (3-day minimum age)
- **`.devcontainer/Dockerfile`** - Docker base images and system packages
- **`custom_components/hass_dyson/manifest.json`** - Home Assistant integration requirements

## **Update Categories**

- **Home Assistant Dependencies** - 14-day stabilization period for core HA packages
- **Security Updates** - 1-day minimum age for security-related packages (cryptography, requests, etc.)
- **Code Quality Tools** - 3-day minimum age for development tools (ruff, pytest, mypy)
- **Dyson Libraries** - 14-day stabilization with code owner review for `libdyson-rest`
- **Docker Images** - 7-day minimum age for base images and system dependencies

## **Automation Features**

- **Weekly Schedule** - Runs every Monday at 6 AM UTC
- **Dependency Dashboard** - GitHub issue tracking all available updates
- **Smart Grouping** - Related dependencies updated together
- **Security Priority** - Vulnerability fixes get immediate attention
- **Self-hosted** - No external reporting, all processing within GitHub

Renovate automatically creates pull requests for dependency updates, which are reviewed and tested by the CI pipeline before merging.
