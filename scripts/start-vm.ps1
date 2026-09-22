$ErrorActionPreference = 'Stop'
$configPath = Join-Path $PSScriptRoot '../local_runtime/connection.json'
$config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
foreach ($name in @('VMAuthdService', 'VMnetDHCP', 'VMware NAT Service')) {
    $service = Get-Service -Name $name
    if ($service.Status -ne 'Running') {
        try { Start-Service -Name $name } catch {
            throw "Cannot start $name. Run this script in an Administrator PowerShell. $($_.Exception.Message)"
        }
    }
}
$running = & $config.vmrun list
if ($LASTEXITCODE -ne 0) { throw 'VMware could not list running VMs.' }
$target = [IO.Path]::GetFullPath($config.vmx)
$found = @($running | Where-Object { $_ -like '*.vmx' } | Where-Object {
    [IO.Path]::GetFullPath($_) -eq $target
}).Count -gt 0
if (-not $found) {
    & $config.vmrun start $config.vmx gui
    if ($LASTEXITCODE -ne 0) { throw 'VMware could not start the project VM.' }
}
& $config.vmrun getGuestIPAddress $config.vmx -wait
if ($LASTEXITCODE -ne 0) { throw 'VMware Tools could not discover the guest address.' }
& python (Join-Path $PSScriptRoot 'tcad.py') doctor
if ($LASTEXITCODE -ne 0) { throw 'VM started, but SSH/tool verification failed.' }
