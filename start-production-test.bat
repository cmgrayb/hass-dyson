@echo off
REM Production Home Assistant Test Environment Setup Script (Windows)
REM This script sets up a clean Home Assistant instance for testing the Dyson integration

echo 🏠 Setting up Production Home Assistant Test Environment
echo ==================================================

REM Create necessary directories
echo 📁 Creating directories...
if not exist "docker\ha-config\custom_components" mkdir "docker\ha-config\custom_components"
if not exist "docker\logs" mkdir "docker\logs"
if not exist "docker\mosquitto-data" mkdir "docker\mosquitto-data"
if not exist "docker\mosquitto-logs" mkdir "docker\mosquitto-logs"

REM Pull the latest Home Assistant image
echo 🐳 Pulling latest Home Assistant image...
docker-compose pull homeassistant

REM Stop any existing containers
echo 🛑 Stopping existing containers...
docker-compose down --remove-orphans

REM Start the production test environment
echo 🚀 Starting Home Assistant production test environment...
docker-compose up -d homeassistant mosquitto

REM Wait for Home Assistant to start
echo ⏳ Waiting for Home Assistant to start...
echo This may take a few minutes for the first startup...

REM Simple wait loop (Windows doesn't have curl by default in older versions)
timeout /t 60 /nobreak >nul

echo.
echo 🎉 Production Home Assistant Test Environment Ready!
echo ==================================================
echo 🌐 Home Assistant URL: http://localhost:8123
echo 📊 MQTT Broker: localhost:1883
echo 🕷️ MQTT WebSocket: ws://localhost:9001
echo.
echo 📋 Next Steps:
echo 1. Open http://localhost:8123 in your browser
echo 2. Complete the initial Home Assistant setup
echo 3. Go to Configuration → Integrations → Add Integration
echo 4. Search for 'Dyson Alternative' to test the integration
echo.
echo 🔧 Useful Commands:
echo   View logs:           docker-compose logs homeassistant
echo   Follow logs:         docker-compose logs -f homeassistant
echo   Restart:             docker-compose restart homeassistant
echo   Stop:                docker-compose down
echo.
echo 🐛 Debugging:
echo   Shell into container: docker-compose exec homeassistant bash
echo   Check integration:    docker-compose exec homeassistant ls -la /config/custom_components/hass_dyson/

pause
