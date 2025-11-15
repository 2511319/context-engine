param(
  [string]$InstallPath = "D:\\VS\\BuildTools"
)

$ErrorActionPreference = "Stop"

# Create target directory
New-Item -ItemType Directory -Force -Path $InstallPath | Out-Null
$dl = Join-Path $InstallPath "vs_BuildTools.exe"

# Download official installer
$Url = "https://aka.ms/vs/17/release/vs_BuildTools.exe"
Invoke-WebRequest -UseBasicParsing -Uri $Url -OutFile $dl

# Build arguments
$log = Join-Path $InstallPath "install.log"
$args = @(
  "--quiet","--norestart","--nocache",
  "--installPath","$InstallPath",
  "--add","Microsoft.VisualStudio.Workload.VCTools",
  "--add","Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
  "--add","Microsoft.VisualStudio.Component.VC.CoreBuildTools",
  "--add","Microsoft.VisualStudio.Component.Windows10SDK.19041",
  "--includeRecommended",
  "--wait",
  "--log","$log"
)

# Start and wait
$proc = Start-Process -FilePath $dl -ArgumentList $args -PassThru -Wait

# Verify vcvars script exists
$vcvars = Join-Path $InstallPath "VC\Auxiliary\Build\vcvars64.bat"
if (-not (Test-Path $vcvars)) {
  Write-Warning "vcvars64.bat not found at $vcvars. See log: $log"
  Get-Content $log -Tail 100 | Write-Output
  throw "VS Build Tools installation failed"
}

Write-Host "VS Build Tools installed at $InstallPath" -ForegroundColor Green
