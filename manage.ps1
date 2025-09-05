# WhisperLiveKit Production Server Management Script for Windows PowerShell
# Скрипт управления production сервером WhisperLiveKit для Windows PowerShell

param(
    [Parameter(Position=0)]
    [ValidateSet(\"start\", \"stop\", \"restart\", \"reload\", \"status\", \"logs\", \"clean\", \"help\")]
    [string]$Command = \"help\"
)

# Colors for output
$colors = @{
    Red = \"Red\"
    Green = \"Green\"
    Yellow = \"Yellow\"
    Blue = \"Blue\"
    White = \"White\"
}

function Write-Status {
    param([string]$Message)
    Write-Host \"[INFO] $Message\" -ForegroundColor $colors.Blue
}

function Write-Success {
    param([string]$Message)
    Write-Host \"[SUCCESS] $Message\" -ForegroundColor $colors.Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host \"[WARNING] $Message\" -ForegroundColor $colors.Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host \"[ERROR] $Message\" -ForegroundColor $colors.Red
}

# Configuration
$PidFile = $env:WLK_GUNICORN_PIDFILE ?? \"./gunicorn.pid\"
$LogDir = \"./logs\"
$AccessLog = \"$LogDir/gunicorn_access.log\"
$ErrorLog = \"$LogDir/gunicorn_error.log\"

function Show-Help {
    Write-Host \"WhisperLiveKit Production Server Management\" -ForegroundColor $colors.Blue
    Write-Host \"\"
    Write-Host \"Usage: .\\manage.ps1 [COMMAND]\"
    Write-Host \"\"
    Write-Host \"Commands:\"
    Write-Host \"  start    - Start the production server\"
    Write-Host \"  stop     - Stop the production server gracefully\"
    Write-Host \"  restart  - Restart the production server\"
    Write-Host \"  reload   - Reload configuration without downtime\"
    Write-Host \"  status   - Show server status\"
    Write-Host \"  logs     - Show server logs\"
    Write-Host \"  clean    - Clean up log files and PID files\"
    Write-Host \"\"
    Write-Host \"Examples:\"
    Write-Host \"  .\\manage.ps1 start                    # Start server\"
    Write-Host \"  .\\manage.ps1 status                   # Check if server is running\"
    Write-Host \"  .\\manage.ps1 reload                   # Reload config without downtime\"
    Write-Host \"  .\\manage.ps1 logs                     # Show server logs\"
    Write-Host \"\"
}

# Check if server is running
function Test-ServerRunning {
    if (Test-Path $PidFile) {
        $pid = Get-Content $PidFile -ErrorAction SilentlyContinue
        if ($pid -and (Get-Process -Id $pid -ErrorAction SilentlyContinue)) {
            return $true
        }
        else {
            # PID file exists but process is not running
            Remove-Item $PidFile -ErrorAction SilentlyContinue
            return $false
        }
    }
    return $false
}

# Get PID if running
function Get-ServerPid {
    if (Test-Path $PidFile) {
        return Get-Content $PidFile -ErrorAction SilentlyContinue
    }
    return $null
}

# Start server
function Start-Server {
    if (Test-ServerRunning) {
        $pid = Get-ServerPid
        Write-Warning \"Server is already running (PID: $pid)\"
        return
    }
    
    Write-Status \"Starting WhisperLiveKit production server...\"
    
    # Create logs directory
    if (-not (Test-Path $LogDir)) {
        New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
    }
    
    # Start server using start.ps1
    try {
        Start-Process -FilePath \"powershell\" -ArgumentList @(\"-File\", \".\\start.ps1\", \"--production\") -NoNewWindow
        
        # Wait a moment for startup
        Start-Sleep -Seconds 3
        
        if (Test-ServerRunning) {
            $pid = Get-ServerPid
            Write-Success \"Server started successfully (PID: $pid)\"
            Show-Status
        }
        else {
            Write-Error \"Failed to start server\"
        }
    }
    catch {
        Write-Error \"Failed to start server: $_\"
    }
}

# Stop server
function Stop-Server {
    if (-not (Test-ServerRunning)) {
        Write-Warning \"Server is not running\"
        return
    }
    
    $pid = Get-ServerPid
    Write-Status \"Stopping server (PID: $pid)...\"
    
    try {
        # Try graceful shutdown first
        Stop-Process -Id $pid -ErrorAction Stop
        
        # Wait for graceful shutdown
        $timeout = 30
        $count = 0
        
        while ($count -lt $timeout -and (Test-ServerRunning)) {
            Start-Sleep -Seconds 1
            $count++
            Write-Host \".\" -NoNewline
        }
        Write-Host \"\"
        
        if (Test-ServerRunning) {
            Write-Warning \"Graceful shutdown timed out, forcing shutdown...\"
            Stop-Process -Id $pid -Force
            Start-Sleep -Seconds 2
        }
        
        if (-not (Test-ServerRunning)) {
            Write-Success \"Server stopped successfully\"
            Remove-Item $PidFile -ErrorAction SilentlyContinue
        }
        else {
            Write-Error \"Failed to stop server\"
        }
    }
    catch {
        Write-Error \"Failed to stop server: $_\"
    }
}

# Restart server
function Restart-Server {
    Write-Status \"Restarting server...\"
    Stop-Server
    Start-Sleep -Seconds 2
    Start-Server
}

# Reload configuration
function Reload-Config {
    if (-not (Test-ServerRunning)) {
        Write-Error \"Server is not running\"
        return
    }
    
    # Note: Windows doesn't have SIGHUP equivalent
    # For now, we'll do a restart
    Write-Status \"Reloading configuration (restart required on Windows)...\"
    Restart-Server
}

# Show server status
function Show-Status {
    Write-Host \"\"
    Write-Host \"================================================================\" -ForegroundColor $colors.Blue
    Write-Host \"           WhisperLiveKit Server Status\" -ForegroundColor $colors.Blue
    Write-Host \"================================================================\" -ForegroundColor $colors.Blue
    
    if (Test-ServerRunning) {
        $pid = Get-ServerPid
        Write-Success \"Server is running (PID: $pid)\"
        
        # Show process information
        Write-Host \"\"
        Write-Status \"Process information:\"
        try {
            $process = Get-Process -Id $pid -ErrorAction Stop
            Write-Host \"  PID: $($process.Id)\"
            Write-Host \"  Name: $($process.ProcessName)\"
            Write-Host \"  CPU: $($process.CPU)%\"
            Write-Host \"  Memory: $([math]::Round($process.WorkingSet64/1MB, 2)) MB\"
            Write-Host \"  Start Time: $($process.StartTime)\"
        }
        catch {
            Write-Host \"  Could not retrieve process information\"
        }
        
        # Show server configuration
        Write-Host \"\"
        Write-Status \"Configuration:\"
        Write-Host \"  Host: $($env:WLK_HOST ?? 'localhost')\"
        Write-Host \"  Port: $($env:WLK_PORT ?? '8000')\"
        Write-Host \"  Model: $($env:WLK_MODEL ?? 'small')\"
        Write-Host \"  Workers: $($env:WLK_GUNICORN_WORKERS ?? '4')\"
        
    }
    else {
        Write-Warning \"Server is not running\"
    }
    
    # Show log file sizes
    Write-Host \"\"
    Write-Status \"Log files:\"
    if (Test-Path $AccessLog) {
        $size = [math]::Round((Get-Item $AccessLog).Length/1KB, 2)
        Write-Host \"  Access log: $AccessLog ($size KB)\"
    }
    else {
        Write-Host \"  Access log: Not found\"
    }
    
    if (Test-Path $ErrorLog) {
        $size = [math]::Round((Get-Item $ErrorLog).Length/1KB, 2)
        Write-Host \"  Error log: $ErrorLog ($size KB)\"
    }
    else {
        Write-Host \"  Error log: Not found\"
    }
    
    Write-Host \"\"
}

# Show logs
function Show-Logs {
    if (-not (Test-Path $LogDir)) {
        Write-Error \"Log directory not found: $LogDir\"
        return
    }
    
    Write-Host \"Showing server logs (Press Ctrl+C to exit)...\"
    Write-Host \"\"
    
    # Show both access and error logs
    $logFiles = @()
    if (Test-Path $AccessLog) { $logFiles += $AccessLog }
    if (Test-Path $ErrorLog) { $logFiles += $ErrorLog }
    
    if ($logFiles.Count -gt 0) {
        try {
            Get-Content $logFiles -Wait -Tail 50
        }
        catch {
            Write-Warning \"Error reading log files: $_\"
        }
    }
    else {
        Write-Warning \"No log files found\"
    }
}

# Clean up files
function Clean-Files {
    Write-Status \"Cleaning up log files and PID files...\"
    
    if (Test-ServerRunning) {
        Write-Error \"Cannot clean while server is running. Stop the server first.\"
        return
    }
    
    # Remove PID file
    if (Test-Path $PidFile) {
        Remove-Item $PidFile -Force
        Write-Status \"Removed PID file: $PidFile\"
    }
    
    # Archive and remove old logs
    if (Test-Path $LogDir) {
        $timestamp = Get-Date -Format \"yyyyMMdd_HHmmss\"
        $archiveDir = \"$LogDir\\archive\"
        
        if (-not (Test-Path $archiveDir)) {
            New-Item -ItemType Directory -Path $archiveDir -Force | Out-Null
        }
        
        if (Test-Path $AccessLog) {
            Move-Item $AccessLog \"$archiveDir\\access_$timestamp.log\"
            Write-Status \"Archived access log\"
        }
        
        if (Test-Path $ErrorLog) {
            Move-Item $ErrorLog \"$archiveDir\\error_$timestamp.log\"
            Write-Status \"Archived error log\"
        }
        
        # Remove old archives (keep last 10)
        Get-ChildItem \"$archiveDir\\*.log\" | Sort-Object LastWriteTime -Descending | Select-Object -Skip 10 | Remove-Item -Force
    }
    
    Write-Success \"Cleanup completed\"
}

# Main function
switch ($Command) {
    \"start\" {
        Start-Server
    }
    \"stop\" {
        Stop-Server
    }
    \"restart\" {
        Restart-Server
    }
    \"reload\" {
        Reload-Config
    }
    \"status\" {
        Show-Status
    }
    \"logs\" {
        Show-Logs
    }
    \"clean\" {
        Clean-Files
    }
    \"help\" {
        Show-Help
    }
    default {
        Write-Error \"Unknown command: $Command\"
        Show-Help
    }
}