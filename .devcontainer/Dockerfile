# Use the official Python devcontainer image as base
FROM mcr.microsoft.com/devcontainers/python:3.13-bookworm

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

# Copy requirements to temporary location for installation
COPY requirements-dev.txt /tmp/
COPY requirements.txt /tmp/

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir homeassistant && \
    pip install --no-cache-dir -r /tmp/requirements-dev.txt

# Install additional development tools
RUN pip install --no-cache-dir \
    pytest-asyncio \
    pytest-mock \
    bandit \
    safety

# Create workspace directory but don't set it as WORKDIR during build
RUN mkdir -p /workspaces

# Note: Project files will be available via volume mount
# Package installation in development mode happens in postCreate script

# Switch to vscode user (created by base image)
USER vscode
