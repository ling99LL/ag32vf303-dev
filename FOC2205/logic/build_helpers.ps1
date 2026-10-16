function File-Hash([string]$file) {
    $stream = [IO.File]::OpenRead((Join-Path $PSScriptRoot $file))
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-', '') }
    finally { $stream.Dispose(); $sha.Dispose() }
}

# Capture native stderr as log data, not a PowerShell terminating error.
# Some AGM tools print informational diagnostics to stderr on Windows.
function Run-Native([string]$exe, [string]$arguments, [string]$log) {
    $info = New-Object Diagnostics.ProcessStartInfo
    $info.FileName = $exe
    $info.Arguments = $arguments
    $info.WorkingDirectory = $PSScriptRoot
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $process = New-Object Diagnostics.Process
    $process.StartInfo = $info
    [void]$process.Start()
    $stdout = $process.StandardOutput.ReadToEndAsync()
    $stderr = $process.StandardError.ReadToEndAsync()
    $process.WaitForExit()
    [IO.File]::WriteAllText((Join-Path $PSScriptRoot $log), $stdout.Result + $stderr.Result)
    $code = $process.ExitCode
    $process.Dispose()
    return $code
}
