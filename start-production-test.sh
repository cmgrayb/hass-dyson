#!/bin/bash

# Production Home Assistant Test Environment Setup Script
# This script sets up a clean Home Assistant instance for testing the Dyson integration

set -e

echo "🏠 Setting up Production Home Assistant Test Environment"
echo "=================================================="

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p docker/ha-config
mkdir -p docker/logs
mkdir -p docker/mosquitto-data
mkdir -p docker/mosquitto-logs

# Set proper permissions for Docker volumes
echo "🔐 Setting permissions..."
chmod -R 755 docker/
chmod -R 755 custom_components/

# Pull the latest Home Assistant image
echo "🐳 Pulling latest Home Assistant image..."
docker-compose pull homeassistant

# Stop any existing containers
echo "🛑 Stopping existing containers..."
docker-compose down --remove-orphans

# Start the production test environment
echo "🚀 Starting Home Assistant production test environment..."
docker-compose up -d homeassistant mosquitto

# Wait for Home Assistant to start
echo "⏳ Waiting for Home Assistant to start..."
echo "This may take a few minutes for the first startup..."

# Check if Home Assistant is running
for i in {1..30}; do
    if curl -s http://localhost:8124 > /dev/null; then
        echo "✅ Home Assistant is running!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ Timeout waiting for Home Assistant to start"
        echo "Check logs with: docker-compose logs homeassistant"
        exit 1
    fi
    sleep 10
done

echo ""
echo "🎉 Production Home Assistant Test Environment Ready!"
echo "=================================================="
echo "🌐 Home Assistant URL: http://localhost:8124"
echo "📊 MQTT Broker: localhost:1883"
echo "🕷️ MQTT WebSocket: ws://localhost:9001"
echo ""
echo "📋 Next Steps:"
echo "1. Open http://localhost:8124 in your browser"
echo "2. Complete the initial Home Assistant setup"
echo "3. Go to Configuration → Integrations → Add Integration"
echo "4. Search for 'Dyson' to test the integration"
echo ""
echo "🔧 Useful Commands:"
echo "  View logs:           docker-compose logs homeassistant"
echo "  Follow logs:         docker-compose logs -f homeassistant"
echo "  Restart:             docker-compose restart homeassistant"
echo "  Stop:                docker-compose down"
echo "  Integration logs:    docker-compose exec homeassistant tail -f /config/home-assistant.log"
echo ""
echo "🐛 Debugging:"
echo "  Shell into container: docker-compose exec homeassistant bash"
echo "  Check integration:    docker-compose exec homeassistant ls -la /config/custom_components/hass_dyson/"
