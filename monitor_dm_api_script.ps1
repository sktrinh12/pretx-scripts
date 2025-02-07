$scriptPath = "C:\Users\Disco-lx\Dotmatics%20Scripts\compare_eln_writeup_dm_api.py"
$logFile = "C:\Users\Disco-lx\dm_api_script_log.txt"

$firstRun = $true

while ($true) {
    $cmdArgs = "-l 100000 -s 30"
    if ($firstRun) {
        $cmdArgs += " -c"
    }

    Write-Output "$(Get-Date) - Running: python $scriptPath $cmdArgs" | Out-File -Append $logFile
    $process = Start-Process -FilePath "python" -ArgumentList "$scriptPath $cmdArgs" -NoNewWindow -PassThru -Wait

    if ($process.ExitCode -ne 0) {
        Write-Output "$(Get-Date) - Script failed, restarting..." | Out-File -Append $logFile
        Start-Sleep -Seconds 45 
        $firstRun = $false
    } else {
        Write-Output "$(Get-Date) - Script completed successfully" | Out-File -Append $logFile
        break
    }
}
