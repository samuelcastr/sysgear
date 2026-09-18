# gearctl — Script de instalación y creación de acceso directo en Windows.
# Uso (PowerShell, como Administrador):
#     Set-ExecutionPolicy Bypass -Scope Process -Force
#     .\install.ps1
#
<#
.SYNOPSIS
    Instala gearctl: dependencias, compila con PyInstaller y crea
    acceso directo en el Escritorio y en el Menú Inicio.
#>

[CmdletBinding()]
param(
    [string]$Python = "python",
    [switch]$NoShortcut,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$dist = Join-Path $root "dist"
$exe  = Join-Path $dist "gearctl.exe"

Write-Host "== gearctl installer ==" -ForegroundColor Cyan

function Test-Command([string]$cmd) {
    try { Get-Command $cmd -ErrorAction Stop | Out-Null; return $true }
    catch { return $false }
}

# 1) Verificar Python
if (-not (Test-Command $Python)) {
    Write-Error "Python no encontrado en el PATH. Use `-Python <ruta a python.exe>`."
}
Write-Host "[1/4] Python detectado: $((Get-Command $Python).Source)" -ForegroundColor Green

# 2) Instalar dependencias
if (-not (Test-Path (Join-Path $root "requirements.txt"))) {
    Write-Error "requirements.txt no encontrado en $root"
}
Write-Host "[2/4] Instalando dependencias (pip install -r requirements.txt)..."
& $Python -m pip install --upgrade pip
& $Python -m pip install -r (Join-Path $root "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    Write-Error "Fallo al instalar dependencias."
}

# 3) Compilar con PyInstaller
if (-not (Test-Command "pyinstaller")) {
    Write-Host "Instalando PyInstaller..."
    & $Python -m pip install pyinstaller
}
Write-Host "[3/4] Compilando con PyInstaller (pyinstaller --onefile main.py)..."
Push-Location $root
try {
    & pyinstaller --onefile --name gearctl main.py
}
finally {
    Pop-Location
}
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $exe)) {
    Write-Error "La compilación falló: no se generó $exe"
}
Write-Host "[4/4] binario: $exe" -ForegroundColor Green

# 4) Crear accesos directos
if ($NoShortcut) {
    Write-Host "Omitido: creación de accesos directos (-NoShortcut)."
    exit 0
}

$wsh = New-Object -ComObject WScript.Shell
$target = $exe

$startMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$desktopPath  = [Environment]::GetFolderPath("Desktop")

foreach ($folder in @($startMenuDir, $desktopPath)) {
    if (-not (Test-Path $folder)) { continue }
    $shortcutPath = Join-Path $folder "gearctl.lnk"
    if ((Test-Path $shortcutPath) -and -not $Force) {
        Write-Host "Ya existe: $shortcutPath (use -Force para sobrescribir)"
        continue
    }
    $sc = $wsh.CreateShortcut($shortcutPath)
    $sc.TargetPath = $target
    $sc.WorkingDirectory = Split-Path $target
    $sc.Description = "gearctl - Control de mouse y teclado (RGB y macros)"
    $sc.Save()
    Write-Host "Acceso directo creado: $shortcutPath" -ForegroundColor Green
}

Write-Host ""
Write-Host "Instalación completada. Ejecute gearctl desde el acceso directo." -ForegroundColor Green
exit 0