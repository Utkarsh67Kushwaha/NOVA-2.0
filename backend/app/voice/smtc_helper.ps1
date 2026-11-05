param(
    [string]$Action = "pause"
)

try {
    [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager, Windows.Media, ContentType = WindowsRuntime] | Out-Null
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    $asTaskGeneric = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { 
        $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' 
    }[0]

    $op = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]::RequestAsync()
    $task = $asTaskGeneric.MakeGenericMethod([Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]).Invoke($null, @($op))
    $mgr = $task.GetAwaiter().GetResult()
    $sessions = $mgr.GetSessions()

    $acted = $false
    foreach ($s in $sessions) {
        $status = $s.GetPlaybackInfo().PlaybackStatus
        # Status: 4 = Playing, 5 = Paused
        if ($Action -eq "pause" -and $status -eq 4) {
            $pOp = $s.TryPauseAsync()
            $pTask = $asTaskGeneric.MakeGenericMethod([bool]).Invoke($null, @($pOp))
            $res = $pTask.GetAwaiter().GetResult()
            if ($res) { $acted = $true }
        } elseif ($Action -eq "resume" -and $status -eq 5) {
            $pOp = $s.TryPlayAsync()
            $pTask = $asTaskGeneric.MakeGenericMethod([bool]).Invoke($null, @($pOp))
            $res = $pTask.GetAwaiter().GetResult()
            if ($res) { $acted = $true }
        }
    }
    Write-Output $acted
} catch {
    Write-Output $false
}
