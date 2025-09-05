# Dyson Alt Development Docker Helper Script (PowerShell)

param(
    [Parameter(Position=0)]
    [ValidateSet("start", "stop", "restart", "logs", "shell", "clean", "status", "url", "help")]
    [string]$Command = "help"
)

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

function Show-Help {
    Write-Host "Dyson Alt Development Environment" -ForegroundColor Green
    Write-Host ""
    Write-Host "Usage: .\docker-dev.ps1 [COMMAND]"
    Write-Host ""
    Write-Host "Commands:"
    Write-Host "  start     Start Home Assistant and MQTT broker"
    Write-Host "  stop      Stop all containers"
    Write-Host "  restart   Restart containers"
    Write-Host "  logs      Show Home Assistant logs"
    Write-Host "  shell     Open shell in Home Assistant container"
    Write-Host "  clean     Stop and remove containers and volumes"
    Write-Host "  status    Show container status"
    Write-Host "  url       Show Home Assistant URL"
    Write-Host ""
}

function Start-Services {
    Write-Host "🏠 Starting Home Assistant development environment..." -ForegroundColor Green
    
    # Ensure config directory exists
    New-Item -ItemType Directory -Force -Path "docker/config" | Out-Null
    
    # Start services
    docker-compose up -d
    
    Write-Host "✅ Services started!" -ForegroundColor Green
    Write-Host "🌐 Home Assistant will be available at: http://localhost:8123" -ForegroundColor Cyan
    Write-Host "📡 MQTT broker available at: localhost:1883" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Run '.\docker-dev.ps1 logs' to follow startup logs"
}

function Stop-Services {
    Write-Host "🛑 Stopping services..." -ForegroundColor Yellow
    docker-compose down
    Write-Host "✅ Services stopped" -ForegroundColor Green
}

function Restart-Services {
    Write-Host "🔄 Restarting services..." -ForegroundColor Yellow
    docker-compose restart
    Write-Host "✅ Services restarted" -ForegroundColor Green
}

function Show-Logs {
    Write-Host "📋 Following Home Assistant logs (Ctrl+C to exit)..." -ForegroundColor Cyan
    docker-compose logs -f homeassistant
}

function Open-Shell {
    Write-Host "🐚 Opening shell in Home Assistant container..." -ForegroundColor Cyan
    docker-compose exec homeassistant bash
}

function Clean-Environment {
    Write-Host "🧹 Cleaning up development environment..." -ForegroundColor Yellow
    docker-compose down -v --remove-orphans
    docker-compose rm -f
    Write-Host "✅ Environment cleaned" -ForegroundColor Green
}

function Show-Status {
    Write-Host "📊 Container Status:" -ForegroundColor Cyan
    docker-compose ps
    Write-Host ""
    
    $status = docker-compose ps --services --filter "status=running"
    if ($status -contains "homeassistant") {
        Write-Host "🌐 Home Assistant: http://localhost:8123" -ForegroundColor Green
        Write-Host "📡 MQTT Broker: localhost:1883" -ForegroundColor Green
    }
}

function Show-Url {
    $status = docker-compose ps --services --filter "status=running"
    if ($status -contains "homeassistant") {
        Write-Host "🌐 Home Assistant: http://localhost:8123" -ForegroundColor Green
        Start-Process "http://localhost:8123"
    } else {
        Write-Host "❌ Home Assistant is not running. Use '.\docker-dev.ps1 start' to start it." -ForegroundColor Red
    }
}

# Main command handling
switch ($Command) {
    "start" { Start-Services }
    "stop" { Stop-Services }
    "restart" { Restart-Services }
    "logs" { Show-Logs }
    "shell" { Open-Shell }
    "clean" { Clean-Environment }
    "status" { Show-Status }
    "url" { Show-Url }
    "help" { Show-Help }
    default {
        Write-Host "❌ Unknown command: $Command" -ForegroundColor Red
        Write-Host ""
        Show-Help
        exit 1
    }
}
