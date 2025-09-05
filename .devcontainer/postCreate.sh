#!/bin/bash

echo "🚀 Setting up Dyson Home Assistant Integration development environment..."

# Update system packages
echo "📦 Updating system packages..."
sudo apt-get update && sudo apt-get install -y \
    git \
    build-essential \
    libffi-dev \
    libssl-dev \
    libjpeg-dev \
    zlib1g-dev \
    autoconf \
    build-essential \
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
    libxcb1-dev

# Update pip to latest version
echo "📦 Updating pip..."
python -m pip install --upgrade pip

# Install development dependencies
echo "📚 Installing development dependencies..."
pip install -r requirements-dev.txt

# Install the package in development mode
echo "🔧 Installing package in development mode..."
pip install -e .

# Install Home Assistant core for testing
echo "🏠 Installing Home Assistant core..."
pip install homeassistant

# Install additional testing dependencies that might be missing
echo "🧪 Installing additional testing dependencies..."
pip install pytest-homeassistant-custom-component || echo "pytest-homeassistant-custom-component not available, continuing..."
pip install pytest-asyncio
pip install pytest-mock

# Create test configuration directory
echo "📁 Creating test configuration directory..."
mkdir -p /config

# Set up git hooks (if pre-commit is available)
if command -v pre-commit &> /dev/null; then
    echo "🪝 Setting up pre-commit hooks..."
    pre-commit install
fi

# Create basic Home Assistant configuration for testing
echo "⚙️ Creating basic Home Assistant configuration..."
cat > /config/configuration.yaml << EOF
# Basic Home Assistant configuration for testing
homeassistant:
  name: Dyson Dev
  latitude: 37.7749
  longitude: -122.4194
  elevation: 0
  unit_system: metric
  time_zone: UTC

logger:
  default: info
  logs:
    custom_components.hass_dyson: debug

# Enable the frontend
frontend:

# Enable configuration UI
config:

# Enable history
history:

# Enable logbook
logbook:

# Track the sun
sun:
EOF

echo "✅ Development environment setup complete!"
echo ""
echo "🎯 Quick commands:"
echo "   Format code:     python -m black ."
echo "   Lint code:       python -m flake8 ."
echo "   Sort imports:    python -m isort ."
echo "   Type check:      python -m mypy custom_components/hass_dyson"
echo "   Run tests:       python -m pytest"
echo "   Run unit tests:  python -m pytest tests/ -m 'not integration'"
echo ""
echo "🏠 Start Home Assistant with: hass --config /config"
echo ""
