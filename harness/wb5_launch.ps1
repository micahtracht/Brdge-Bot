# Launch WBridge5 instances and auto-connect them to a Blue Chip table manager.
# No GUI interaction required: drives the native menu (WM_COMMAND) and the
# Setup dialog's controls (BM_CLICK / WM_SETTEXT) directly.
#
# Usage:
#   powershell -File harness\wb5_launch.ps1                     # all four seats
#   powershell -File harness\wb5_launch.ps1 -Seats East,West    # one pair
#   powershell -File harness\wb5_launch.ps1 -TmHost 127.0.0.1 -Port 2000
#
# Note: avoid helper functions around the Win32 enum callbacks — PS 5.1
# delegate scriptblocks resolve variables unreliably inside function scopes,
# so all state lives in $script: scope and the logic is inline per seat.

param(
    [string[]]$Seats = @("North", "East", "South", "West"),
    [string]$TmHost = "LocalHost",
    [int]$Port = 2000,
    [string]$Wb5Dir = "C:\Wbridge5",
    [int]$ConnectDelayMs = 1500,
    [string]$IniSnapshot = "",
    # By default instances run invisibly (no windows, no focus stealing);
    # pass -Visible for debugging. Use wb5_stop.ps1 to kill hidden instances.
    [switch]$Visible
)

$ErrorActionPreference = "Stop"

# When invoked via `powershell -File`, "-Seats East,West" arrives as the single
# string "East,West" — split it ourselves.
$Seats = @($Seats | ForEach-Object { $_ -split ',' } | Where-Object { $_ } | ForEach-Object { $_.Trim() })

Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class Wb5 {
    public delegate bool EnumProc(IntPtr hWnd, IntPtr lParam);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr lParam);
    [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr parent, EnumProc cb, IntPtr lParam);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint pid);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr hWnd, StringBuilder sb, int max);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr hWnd, StringBuilder sb, int max);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern IntPtr SendMessage(IntPtr hWnd, uint Msg, IntPtr wParam, string lParam);
    [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr hWnd, uint Msg, IntPtr wParam, IntPtr lParam);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr hWnd, IntPtr after, int x, int y, int cx, int cy, uint flags);
    public const uint WM_COMMAND = 0x0111;
    public const uint WM_SETTEXT = 0x000C;
    public const uint BM_CLICK = 0x00F5;
    public const uint BM_GETCHECK = 0x00F0;
    public const int SW_HIDE = 0;
    public const uint SWP_NOSIZE_NOACTIVATE = 0x0001 | 0x0010; // NOSIZE | NOACTIVATE
}
'@

# Hides every window belonging to the given process ids (invisible operation:
# our automation is message-based, so hidden windows keep working).
function Hide-ProcessWindows([uint32[]]$Pids) {
    $script:toHide = New-Object System.Collections.ArrayList
    $script:hidePids = $Pids
    $cb = [Wb5+EnumProc]{
        param($h, $l)
        [uint32]$p = 0
        $null = [Wb5]::GetWindowThreadProcessId($h, [ref]$p)
        if ($script:hidePids -contains $p -and [Wb5]::IsWindowVisible($h)) { $null = $script:toHide.Add($h) }
        return $true
    }
    $null = [Wb5]::EnumWindows($cb, [IntPtr]::Zero)
    foreach ($h in $script:toHide) { $null = [Wb5]::ShowWindow([IntPtr]$h, [Wb5]::SW_HIDE) }
}

# Menu command id of Actions -> Connection... (from menu enumeration of 5.12)
$MENU_CONNECTION = 37

# Optionally restore a known configuration snapshot first (e.g. the committed
# harness\wbridge5-sayc.ini: bidding system SAYC for both sides, level 4,
# 500 ms delay). WBridge5 only persists settings via Preferences->Save, so a
# snapshot is the reliable way to pin the engine's configuration for a match.
$ini = Join-Path $Wb5Dir "WBRIDGE5.INI"
if ($IniSnapshot) {
    Copy-Item -Path $IniSnapshot -Destination $ini -Force
}

# Point the shared INI at the table manager before launching anything.
$iniHost = if ($TmHost -eq "LocalHost") { "127.0.0.1" } else { $TmHost }
(Get-Content $ini) `
    -replace '^Table=.*', 'Table=1' `
    -replace '^Port=.*', "Port=$Port" `
    -replace '^Adresse=.*', "Adresse=$iniHost" |
    Set-Content -Encoding ascii $ini

foreach ($seat in $Seats) {
    $style = if ($Visible) { "Normal" } else { "Minimized" }
    $proc = Start-Process -FilePath (Join-Path $Wb5Dir "Wbridge5.exe") -WorkingDirectory $Wb5Dir -WindowStyle $style -PassThru
    $script:targetPid = [uint32]$proc.Id

    # --- wait for the main form (TSDIAppForm) ---
    $script:hit = [IntPtr]::Zero
    $findForm = [Wb5+EnumProc]{
        param($h, $l)
        [uint32]$p = 0
        $null = [Wb5]::GetWindowThreadProcessId($h, [ref]$p)
        if ($p -eq $script:targetPid) {
            $cls = New-Object System.Text.StringBuilder 256
            $null = [Wb5]::GetClassName($h, $cls, 256)
            if ($cls.ToString() -eq 'TSDIAppForm' -and [Wb5]::IsWindowVisible($h)) {
                $script:hit = $h
                return $false
            }
        }
        return $true
    }
    foreach ($try in 1..40) {
        Start-Sleep -Milliseconds 250
        $null = [Wb5]::EnumWindows($findForm, [IntPtr]::Zero)
        if ($script:hit -ne [IntPtr]::Zero) { break }
    }
    if ($script:hit -eq [IntPtr]::Zero) { throw "no TSDIAppForm for pid $($proc.Id)" }
    $form = $script:hit
    if (-not $Visible) { $null = [Wb5]::ShowWindow($form, [Wb5]::SW_HIDE) }
    Start-Sleep -Milliseconds $ConnectDelayMs

    # --- open Actions -> Connection ---
    $null = [Wb5]::PostMessage($form, [Wb5]::WM_COMMAND, [IntPtr]$MENU_CONNECTION, [IntPtr]::Zero)
    $script:hit = [IntPtr]::Zero
    $findSetup = [Wb5+EnumProc]{
        param($h, $l)
        [uint32]$p = 0
        $null = [Wb5]::GetWindowThreadProcessId($h, [ref]$p)
        if ($p -eq $script:targetPid) {
            $cls = New-Object System.Text.StringBuilder 256
            $null = [Wb5]::GetClassName($h, $cls, 256)
            if ($cls.ToString() -eq 'TSetupform' -and [Wb5]::IsWindowVisible($h)) {
                $script:hit = $h
                return $false
            }
        }
        return $true
    }
    foreach ($try in 1..40) {
        Start-Sleep -Milliseconds 250
        $null = [Wb5]::EnumWindows($findSetup, [IntPtr]::Zero)
        if ($script:hit -ne [IntPtr]::Zero) { break }
    }
    if ($script:hit -eq [IntPtr]::Zero) { throw "Setup dialog did not appear for pid $($proc.Id)" }
    $setup = $script:hit
    if (-not $Visible) {
        # shove the dialog off-screen so it never flashes over the user's work
        $null = [Wb5]::SetWindowPos($setup, [IntPtr]::Zero, -4000, -4000, 0, 0, [Wb5]::SWP_NOSIZE_NOACTIVATE)
    }

    # --- enumerate dialog controls ---
    $script:items = New-Object System.Collections.ArrayList
    $collect = [Wb5+EnumProc]{
        param($h, $l)
        $cls = New-Object System.Text.StringBuilder 256
        $null = [Wb5]::GetClassName($h, $cls, 256)
        $txt = New-Object System.Text.StringBuilder 256
        $null = [Wb5]::GetWindowText($h, $txt, 256)
        $null = $script:items.Add([pscustomobject]@{ Hwnd = $h; Class = $cls.ToString(); Text = $txt.ToString().Trim() })
        return $true
    }
    $null = [Wb5]::EnumChildWindows($setup, $collect, [IntPtr]::Zero)
    $controls = @($script:items)

    $seatBtn = $controls | Where-Object { $_.Class -eq "TGroupButton" -and $_.Text -eq $seat }
    $autoBox = $controls | Where-Object { $_.Class -eq "TCheckBox" -and $_.Text -match "Auto" }
    $connBtn = $controls | Where-Object { $_.Class -eq "TBitBtn" -and $_.Text -match "connection" }
    # Edits (in enumeration order): opaque numeric field, host, team name.
    $hostEdit = $controls | Where-Object { $_.Class -eq "TEdit" -and $_.Text -notmatch '^\d+$' } | Select-Object -First 1
    if (-not $seatBtn -or -not $autoBox -or -not $connBtn) {
        $diag = "seat='$seat' seatBtn=$($null -ne $seatBtn) autoBox=$($null -ne $autoBox) connBtn=$($null -ne $connBtn)`n"
        foreach ($c in $controls) {
            $codes = ($c.Text.ToCharArray() | ForEach-Object { [int]$_ }) -join ','
            $diag += "  [$($c.Class)] '$($c.Text)' codes=[$codes]`n"
        }
        throw "Setup dialog controls not found for pid $($proc.Id):`n$diag"
    }

    # --- fill and connect ---
    if ($hostEdit) {
        $null = [Wb5]::SendMessage([IntPtr]$hostEdit.Hwnd, [Wb5]::WM_SETTEXT, [IntPtr]::Zero, $TmHost)
    }
    $null = [Wb5]::SendMessage([IntPtr]$seatBtn.Hwnd, [Wb5]::BM_CLICK, [IntPtr]::Zero, [IntPtr]::Zero)
    Start-Sleep -Milliseconds 200
    $checked = [Wb5]::SendMessage([IntPtr]$autoBox.Hwnd, [Wb5]::BM_GETCHECK, [IntPtr]::Zero, [IntPtr]::Zero)
    if ($checked -eq [IntPtr]::Zero) {
        $null = [Wb5]::SendMessage([IntPtr]$autoBox.Hwnd, [Wb5]::BM_CLICK, [IntPtr]::Zero, [IntPtr]::Zero)
    }
    Start-Sleep -Milliseconds 200
    $null = [Wb5]::SendMessage([IntPtr]$connBtn.Hwnd, [Wb5]::BM_CLICK, [IntPtr]::Zero, [IntPtr]::Zero)
    Start-Sleep -Milliseconds 500
    if (-not $Visible) { Hide-ProcessWindows @([uint32]$proc.Id) }
    Write-Output "launched pid $($proc.Id) -> $seat @ ${TmHost}:$Port (Auto$(if (-not $Visible) { ', hidden' }))"
}
