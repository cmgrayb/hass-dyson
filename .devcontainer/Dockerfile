# Use the official Python devcontainer image as base - image format is patch-major.minor-OS
FROM mcr.microsoft.com/devcontainers/python:3-3.14-bookworm

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

# Create workspace directory but don't set it as WORKDIR during build
RUN mkdir -p /workspaces

# Note: Project files will be available via volume mount
# Package installation in development mode happens in postCreate script

# Switch to vscode user (created by base image)
USER vscode
