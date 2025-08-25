#!/bin/bash

# Dyson Alt Development Docker Helper Script

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

show_help() {
    echo "Dyson Alt Development Environment"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  start     Start Home Assistant and MQTT broker"
    echo "  stop      Stop all containers"
    echo "  restart   Restart containers"
    echo "  logs      Show Home Assistant logs"
    echo "  shell     Open shell in Home Assistant container"
    echo "  clean     Stop and remove containers and volumes"
    echo "  status    Show container status"
    echo "  url       Show Home Assistant URL"
    echo ""
}

start_services() {
    echo "🏠 Starting Home Assistant development environment..."
    
    # Ensure config directory exists
    mkdir -p docker/config
    
    # Start services
    docker-compose up -d
    
    echo "✅ Services started!"
    echo "🌐 Home Assistant will be available at: http://localhost:8123"
    echo "📡 MQTT broker available at: localhost:1883"
    echo ""
    echo "Run '$0 logs' to follow startup logs"
}

stop_services() {
    echo "🛑 Stopping services..."
    docker-compose down
    echo "✅ Services stopped"
}

restart_services() {
    echo "🔄 Restarting services..."
    docker-compose restart
    echo "✅ Services restarted"
}

show_logs() {
    echo "📋 Following Home Assistant logs (Ctrl+C to exit)..."
    docker-compose logs -f homeassistant
}

open_shell() {
    echo "🐚 Opening shell in Home Assistant container..."
    docker-compose exec homeassistant bash
}

clean_environment() {
    echo "🧹 Cleaning up development environment..."
    docker-compose down -v --remove-orphans
    docker-compose rm -f
    echo "✅ Environment cleaned"
}

show_status() {
    echo "📊 Container Status:"
    docker-compose ps
    echo ""
    
    if docker-compose ps | grep -q "Up"; then
        echo "🌐 Home Assistant: http://localhost:8123"
        echo "📡 MQTT Broker: localhost:1883"
    fi
}

show_url() {
    if docker-compose ps | grep -q "homeassistant.*Up"; then
        echo "🌐 Home Assistant: http://localhost:8123"
    else
        echo "❌ Home Assistant is not running. Use '$0 start' to start it."
    fi
}

# Main command handling
case "${1:-help}" in
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        restart_services
        ;;
    logs)
        show_logs
        ;;
    shell)
        open_shell
        ;;
    clean)
        clean_environment
        ;;
    status)
        show_status
        ;;
    url)
        show_url
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo "❌ Unknown command: $1"
        echo ""
        show_help
        exit 1
        ;;
esac
