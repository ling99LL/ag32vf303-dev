$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
Set-Location -LiteralPath $PSScriptRoot
. "$PSScriptRoot/build_helpers.ps1"
try {
    $manifest = Get-Content -LiteralPath 'quartus_validated.json' -Raw | ConvertFrom-Json
    foreach ($entry in $manifest.hashes.PSObject.Properties) {
        if ((File-Hash $entry.Name) -ne $entry.Value) {
            throw "Quartus input changed: $($entry.Name); run build_steps.bat again"
        }
    }
    $backup = Join-Path $PSScriptRoot '../.pio/previous-logic'
    New-Item -ItemType Directory -Path $backup -Force | Out-Null
    foreach ($file in @('foc2205.bin','foc2205.inc','foc2205_batch.bin','logic_log.txt')) {
        if (Test-Path -LiteralPath $file) {
            Copy-Item -LiteralPath $file -Destination $backup -Force
            Remove-Item -LiteralPath $file
        }
    }
    foreach ($file in @('alta_db/setup_summary.rpt','alta_db/hold_summary.rpt')) {
        Remove-Item -LiteralPath $file -ErrorAction SilentlyContinue
    }
    $code = Run-Native $env:ComSpec '/d /s /c ""C:\Users\Administrator\.platformio\packages\tool-agrv_logic\bin\af_cmd.bat" -f af_run.tcl"' 'supra_build.log'
    if ($code -ne 0) { throw "Supra exit $code; see supra_build.log" }
    foreach ($file in @('foc2205.bin','foc2205.inc','foc2205_batch.bin')) {
        if (!(Test-Path -LiteralPath $file) -or (Get-Item -LiteralPath $file).Length -eq 0) {
            throw "Missing fresh Supra output: $file"
        }
    }
    if (!(Select-String -LiteralPath 'supra_build.log' -Pattern 'Total 0 fatals, 0 errors' -Quiet)) {
        throw 'Supra did not report zero errors'
    }
    foreach ($file in @('alta_db/setup_summary.rpt','alta_db/hold_summary.rpt')) {
        $timing = Get-Content -LiteralPath $file -Raw
        if ($timing -match 'Worst\s+(setup|hold):\s*-') { throw "Negative Supra slack: $file" }
    }
    Write-Host 'Supra PASS: fresh compressed bitstream, include and batch files'
    Write-Host ('SHA256: ' + (File-Hash 'foc2205.bin'))
    exit 0
} catch {
    Write-Error $_ -ErrorAction Continue
    exit 1
}
