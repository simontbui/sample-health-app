#requires -Version 5.1
<#
.SYNOPSIS
Creates and loads the local PostgreSQL 17 benchmark database.
.EXAMPLE
.\scripts\setup.ps1
.EXAMPLE
.\scripts\setup.ps1 -Database docbench_smoke -Documents 800 -BatchSize 200
.EXAMPLE
.\scripts\setup.ps1 -Plan
#>
[CmdletBinding()]
param(
    [ValidatePattern('^[a-z_][a-z0-9_]{0,62}$')]
    [string]$Database = 'docbench',
    [ValidateSet('127.0.0.1', 'localhost', '::1')]
    [string]$Server = '127.0.0.1',
    [ValidateRange(1, 65535)]
    [int]$Port = 5432,
    [ValidateNotNullOrEmpty()]
    [string]$UserName = 'postgres',
    [ValidateScript({ $_ -ge 2 -and $_ % 2 -eq 0 })]
    [long]$Documents = 5000000,
    [ValidateScript({ $_ -ge 2 -and $_ % 2 -eq 0 })]
    [int]$BatchSize = 20000,
    [string]$PostgresBin = 'C:\Program Files\PostgreSQL\17\bin',
    [string]$PythonPath,
    [switch]$UseExistingAuthentication,
    [switch]$Plan
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (-not $PythonPath) {
    $bundledPython = Join-Path (Split-Path $PostgresBin -Parent) 'pgAdmin 4\python\python.exe'
    if (Test-Path -LiteralPath $bundledPython -PathType Leaf) {
        $PythonPath = $bundledPython
    } else {
        $pythonCommand = Get-Command python.exe -CommandType Application -ErrorAction SilentlyContinue
        if ($pythonCommand) { $PythonPath = $pythonCommand.Source }
    }
}
if (-not $PythonPath) {
    throw 'Python was not found. Supply -PythonPath with a Python 3.10+ executable.'
}
& $PythonPath -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)'
if ($LASTEXITCODE -ne 0) { throw 'A working Python 3.10+ executable is required.' }

$loader = Join-Path $PSScriptRoot 'setup.py'
if ($Plan) {
    Write-Host "Plan for ${Server}:$Port / $Database (no database connection or changes)"
    & $PythonPath $loader --documents $Documents --batch-size $BatchSize --plan
    if ($LASTEXITCODE -ne 0) { throw 'Could not generate the load plan.' }
    return
}

$psqlPath = Join-Path $PostgresBin 'psql.exe'
if (-not (Test-Path -LiteralPath $psqlPath -PathType Leaf)) {
    throw "psql.exe was not found in $PostgresBin. Supply -PostgresBin with the PostgreSQL 17 bin directory."
}

# Restore the caller's connection settings and password even when setup fails.
$savedEnvironment = @{}
foreach ($name in @('PSQL','PGHOST','PGPORT','PGUSER','PGDATABASE','PGPASSWORD','PGCONNECT_TIMEOUT','PGCLIENTENCODING')) {
    $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
try {
    $env:PSQL = $psqlPath
    $env:PGHOST = $Server
    $env:PGPORT = [string]$Port
    $env:PGUSER = $UserName
    $env:PGDATABASE = $Database
    $env:PGCONNECT_TIMEOUT = '10'
    $env:PGCLIENTENCODING = 'UTF8'
    if (-not $UseExistingAuthentication) {
        $securePassword = Read-Host "PostgreSQL password for $UserName on ${Server}:$Port" -AsSecureString
        $credential = New-Object System.Net.NetworkCredential($UserName, $securePassword)
        $env:PGPASSWORD = $credential.Password
    }
    $clientArgs = @('-X','-w','-q','-At','-v','ON_ERROR_STOP=1','-h',$Server,'-p',"$Port",'-U',$UserName,'-d','postgres')
    $version = & $psqlPath @clientArgs -c 'SHOW server_version_num;'
    if ($LASTEXITCODE -ne 0) {
        throw 'Cannot connect. Check the PostgreSQL Windows service, port, and database account password.'
    }
    if ([int]$version -lt 170000 -or [int]$version -ge 180000) {
        throw 'This benchmark requires PostgreSQL 17.'
    }
    # Database is limited to lowercase SQL identifiers above, making both uses safe.
    $exists = & $psqlPath @clientArgs -c "SELECT count(*) FROM pg_database WHERE datname='$Database';"
    if ($LASTEXITCODE -ne 0) { throw 'Could not check whether the database exists.' }
    if ([int]$exists -eq 0) {
        Write-Host "Creating database $Database..."
        & $psqlPath @clientArgs -c "CREATE DATABASE $Database;"
        if ($LASTEXITCODE -ne 0) { throw 'Database creation failed. The account needs CREATEDB permission.' }
    } else {
        Write-Host "Database $Database exists; the loader will initialize or resume its benchmark tables."
    }
    & $psqlPath @clientArgs -c "ALTER DATABASE $Database SET search_path TO public;"
    if ($LASTEXITCODE -ne 0) { throw 'Could not configure the database search path. Use the database owner account.' }
    Write-Host ("Loading {0:N0} documents and related rows. Committed batches can be resumed by rerunning this command." -f $Documents)
    & $PythonPath $loader --documents $Documents --batch-size $BatchSize
    if ($LASTEXITCODE -ne 0) {
        throw 'Loading failed. Review the error above. Resume using the same database, document count, and batch size.'
    }
    Write-Host "Ready: ${Server}:$Port / $Database / $UserName"
} finally {
    foreach ($name in $savedEnvironment.Keys) {
        if ($null -eq $savedEnvironment[$name]) {
            Remove-Item -LiteralPath "Env:$name" -ErrorAction SilentlyContinue
        } else {
            [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], 'Process')
        }
    }
    if (Test-Path variable:credential) { Remove-Variable credential }
    if (Test-Path variable:securePassword) { $securePassword.Dispose() }
}
