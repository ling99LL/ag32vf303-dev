$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false
Set-Location -LiteralPath $PSScriptRoot
. "$PSScriptRoot/build_helpers.ps1"
$qbin = 'C:/altera/13.0sp1/quartus/bin64'
$stamp = 'quartus_validated.json'
Remove-Item -LiteralPath $stamp -ErrorAction SilentlyContinue

function Run-Step($tool, $toolArgs, $log, $report, $success) {
    if ($report) { Remove-Item -LiteralPath $report -ErrorAction SilentlyContinue }
    Write-Host "$tool $toolArgs"
    $code = Run-Native "$qbin/$tool.exe" ($toolArgs -join ' ') $log
    # Quartus 13 on this host can fast-fail AFTER writing a successful report.
    # Tolerate only this known exit code, with fresh evidence from each step.
    if ($code -ne 0 -and $code -ne -1073740791) { throw "$tool exit $code; see $log" }
    if ($report) {
        if (!(Test-Path -LiteralPath $report)) { throw "Missing fresh report: $report" }
        if (!(Select-String -LiteralPath $report -Pattern $success -Quiet)) {
            throw "Unsuccessful report: $report"
        }
    }
    Write-Host "  exit=$code; evidence=$report"
}

try {
    # prelogic overwrites QSF. Reapply the required host workaround explicitly.
    $qsf = Get-Content -LiteralPath 'foc2205.qsf'
    $qsf = @($qsf | Where-Object { $_ -notmatch 'PARALLEL_SYNTHESIS|OPTIMIZE_HOLD_TIMING|\-tag alta_auto' })
    $qsf += 'set_global_assignment -name PARALLEL_SYNTHESIS OFF'
    $qsf += 'set_global_assignment -name OPTIMIZE_HOLD_TIMING "ALL PATHS"'
    [IO.File]::WriteAllLines((Join-Path $PSScriptRoot 'foc2205.qsf'), $qsf)
    Run-Step 'quartus_sh' @('-t','af_ip.tcl') 'step1_af_ip.log' '' ''
    $parts = @(Select-String -LiteralPath 'foc2205.qsf' -Pattern 'PARTITION_HIERARCHY.*alta_adc:.*alta_auto')
    if ($parts.Count -ne 3) { throw 'Expected 3 protected alta_adc instances after macro scan' }

    Run-Step 'quartus_map' @('foc2205') 'step2_map.log' 'quartus_logs/foc2205.map.summary' 'Status\s*:\s*Successful'
    Run-Step 'quartus_cdb' @('foc2205','--merge') 'step3_merge.log' 'quartus_logs/foc2205.merge.summary' 'Status\s*:\s*Successful'
    Run-Step 'quartus_fit' @('foc2205') 'step4_fit.log' 'quartus_logs/foc2205.fit.summary' 'Status\s*:\s*Successful'
    Run-Step 'quartus_sta' @('foc2205') 'step5_sta.log' 'quartus_logs/foc2205.sta.summary' 'TimeQuest Timing Analyzer Summary'
    $timing = Get-Content -LiteralPath 'quartus_logs/foc2205.sta.summary' -Raw
    if ($timing -match 'Slack\s*:\s*-') { throw 'Negative Quartus timing slack' }
    Remove-Item -LiteralPath 'simulation/modelsim/foc2205.vo' -ErrorAction SilentlyContinue
    Run-Step 'quartus_eda' @('foc2205','--simulation','--tool=modelsim','--format=verilog') 'step6_eda.log' '' ''
    if (!(Select-String -LiteralPath 'step6_eda.log' -Pattern 'EDA Netlist Writer was successful' -Quiet)) {
        throw 'EDA did not report success'
    }
    $vo = Get-Content -LiteralPath 'simulation/modelsim/foc2205.vo' -Raw
    if ([regex]::Matches($vo, '(?m)^\s*alta_adc(?:_\d+)?\s+\\').Count -ne 3) {
        throw 'Post-fit netlist lost ADC hard macros; refusing Supra'
    }
    $inputs = @('analog_ip.v','spi_mode_wrap.v','ahb2apb.v','reg_ctrl.v','foc2205.v',
                'foc2205.vex','foc2205.qsf','foc2205.sdc','simulation/modelsim/foc2205.vo')
    $hashes = @{}
    foreach ($file in $inputs) { $hashes[$file] = File-Hash $file }
    @{ validatedUtc=[DateTime]::UtcNow.ToString('o'); hashes=$hashes } |
        ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $stamp -Encoding UTF8
    Write-Host 'Quartus PASS: fresh reports, timing summary, ADC x3, netlist manifest'
    exit 0
} catch {
    Write-Error $_ -ErrorAction Continue
    exit 1
}
