# Use the official Python devcontainer image as base - image format is patch-major.minor-OS
FROM mcr.microsoft.com/devcontainers/python:3-3.14-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.9.8 /uv /uvx /usr/local/bin/
ENV UV_SYSTEM_PYTHON=1 \
    UV_PYTHON=/usr/local/bin/python \
    UV_PYTHON_PREFERENCE=only-system

# Remove Yarn repository to avoid GPG key errors
RUN rm -f /etc/apt/sources.list.d/yarn.list

# Install system dependencies needed for Home Assistant
RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    libssl-dev \
    libjpeg-dev \
    zlib1g-dev \
    autoconf \
    libopenjp2-7 \
    libtiff6 \
    libturbojpeg0-dev \
    tzdata \
    libxml2-dev \
    libxslt-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libwebp-dev \
    tcl8.6-dev \
    tk8.6-dev \
    python3-tk \
    libharfbuzz-dev \
    libfribidi-dev \
    libxcb1-dev \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /workspaces
WORKDIR /workspaces

# Install the locked dependencies into the image's system Python.
# The project source is mounted into the container at runtime.
COPY pyproject.toml uv.lock /tmp/hass-dyson/
RUN cd /tmp/hass-dyson && \
    UV_PROJECT_ENVIRONMENT="$(/usr/local/bin/python -c 'import sys; print(sys.prefix)')" \
      uv sync --locked --extra dev \
      --no-install-project --inexact

# Switch to vscode user (created by base image)
USER vscode
