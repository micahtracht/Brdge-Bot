# Stop all WBridge5 instances (they run with hidden windows by default,
# so they cannot be closed from the taskbar).
#
# Usage: powershell -File harness\wb5_stop.ps1

$procs = @(Get-Process -Name Wbridge5 -ErrorAction SilentlyContinue)
if ($procs.Count -eq 0) {
    Write-Output "no WBridge5 instances running"
} else {
    $procs | Stop-Process -Force -Confirm:$false
    Write-Output "stopped $($procs.Count) WBridge5 instance(s)"
}
