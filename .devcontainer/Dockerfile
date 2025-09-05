# Use the official Python devcontainer image as base
FROM mcr.microsoft.com/devcontainers/python:3.11-bullseye

# Install system dependencies needed for Home Assistant
RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    libssl-dev \
    libjpeg-dev \
    zlib1g-dev \
    autoconf \
    libopenjp2-7 \
    libtiff5 \
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

# Install additional development tools
RUN pip install --no-cache-dir \
    homeassistant \
    pytest-asyncio \
    pytest-mock \
    bandit \
    safety

# Set up workspace
WORKDIR /workspaces
ENV PYTHONPATH=/workspaces

# Copy requirements and install dependencies
COPY requirements-dev.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements-dev.txt

USER vscode
