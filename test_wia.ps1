try {
    $dm = New-Object -ComObject WIA.DeviceManager
    Write-Output "WIA OK"
    Write-Output ("Devices: " + $dm.DeviceInfos.Count)
} catch {
    Write-Output ("WIA Failed: " + $_.Exception.Message)
}
