# Switch maintenance mode ON/OFF for a site served through BunkerWeb. The application keeps running.
#   .\maintenance.ps1 python on      .\maintenance.ps1 python off
#   .\maintenance.ps1 notes  on      .\maintenance.ps1 all    off
param(
  [Parameter(Mandatory)][ValidateSet('python','notes','all')][string]$Site,
  [Parameter(Mandatory)][ValidateSet('on','off')][string]$State
)
$files = @{ python = 'maintenance-python.yaml'; notes = 'maintenance-notes.yaml' }
$targets = if ($Site -eq 'all') { $files.Keys } else { @($Site) }
foreach ($t in $targets) {
  $f = Join-Path $PSScriptRoot $files[$t]
  if ($State -eq 'on') { kubectl apply -f $f } else { kubectl delete -f $f --ignore-not-found }
}
Write-Host "Maintenance $State for: $($targets -join ', '). Takes effect in about 30-45 seconds."
