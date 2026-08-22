# Launch (or resume) the BEN vs WBridge5 baseline probe: 256 boards, 2 table-pairs.
#
# Usage:  powershell -ExecutionPolicy Bypass -File harness\run_baseline.ps1
#         powershell -File harness\run_baseline.ps1 -Boards 2048 -Tables 4 -Name ben-vs-wb5-2048
#
# Re-running with the same -Name resumes every room from its last completed
# board. Output: matches\<Name>\ (report.md, results.json, per-room JSONL,
# wire logs, BEN per-seat logs, run.log). WBridge5 runs hidden; BEN runs with
# dds_max_threads=4 per process (harness\ben-baseline.conf) so 4 BEN processes
# share the 16 logical cores without thrashing.

param(
    [string]$Name = "ben-vs-wb5-256",
    [int]$Boards = 256,
    [int]$Tables = 2,
    [int]$Seed = 20260822,
    [int]$Port = 2000
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $repo

$matchDir = Join-Path $repo "matches\$Name"
New-Item -ItemType Directory -Force $matchDir | Out-Null
$runLog = Join-Path $matchDir "run.log"
$benConf = Join-Path $repo "harness\ben-baseline.conf"
$iniSnapshot = Join-Path $repo "harness\wbridge5-sayc.ini"

# Pin WBridge5's configuration (SAYC both sides) before the launcher rewrites
# the table-manager port into the shared INI.
Copy-Item -Path $iniSnapshot -Destination "C:\Wbridge5\WBRIDGE5.INI" -Force

# Make sure no stale WBridge5 instances from an earlier session are around.
& powershell -ExecutionPolicy Bypass -File (Join-Path $repo "harness\wb5_stop.ps1") | Out-Null

"$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') starting $Name : $Boards boards, $Tables table-pair(s), seed $Seed" | Tee-Object -FilePath $runLog -Append

& "$repo\.venv\Scripts\python.exe" -m harness.match `
    --name $Name --boards $Boards --seed $Seed --tables $Tables --port $Port `
    --team-a BEN --team-b WBridge5 --ben-a --wb5-b `
    --ben-config $benConf --ben-opponent config/opponent/WBridge5-Sayc.conf `
    2>&1 | Tee-Object -FilePath $runLog -Append

"$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') finished (exit $LASTEXITCODE)" | Tee-Object -FilePath $runLog -Append
